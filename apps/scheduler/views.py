"""Views for the scheduler app."""

import logging
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import F, QuerySet
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseStatus
from apps.cases.services import (
    CASE_COMMUNICATION_MAX_LENGTH,
    CaseCommunicationError,
    assert_case_lock,
    claim_case_lock,
    compute_lock_display,
    expire_stale_locks_for_statuses,
    get_post_schedule_issue_reason_label,
    post_case_communication_message,
)
from apps.cases.services import (
    release_case_lock as release_lock_service,
)
from apps.cases.services import (
    renew_case_lock as renew_lock_service,
)

from .forms import PostScheduleIssueForm, SchedulerDecisionForm

# ── Helper mappers ───────────────────────────────────────────────────────

DOCTOR_DECISION_MAP: dict[str, str] = {
    "accept": "ACEITAR",
    "deny": "NEGAR",
}

SUPPORT_FLAG_MAP: dict[str, str] = {
    "none": "Nenhum",
    "anesthesist": "Anestesista",
    "anesthesist_icu": "Anestesista + UTI",
}

ADMISSION_FLOW_MAP: dict[str, str] = {
    "scheduled": "Agendamento",
    "immediate": "Vinda Imediata",
}


def _get_patient_name(case: Case) -> str:
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            return str(patient.get("name", "Paciente"))
    return "Paciente"


def _get_patient_age(case: Case) -> str:
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            age = patient.get("age", "")
            return str(age) if age else ""
    return ""


def _get_patient_gender(case: Case) -> str:
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            return str(patient.get("gender", ""))
    return ""


def _get_diagnosis(case: Case) -> str:
    """Extract diagnosis display text.

    Prefers summary_text (populated by pipeline LLM1) over structured_data.
    """
    if case.summary_text:
        return case.summary_text
    if case.structured_data and isinstance(case.structured_data, dict):
        eda = case.structured_data.get("eda", {})
        if isinstance(eda, dict):
            indication = eda.get("indication_category", "")
            if indication:
                return str(indication)
    return ""


def _get_doctor_decision_display(case: Case) -> str:
    """Map doctor_decision to display label."""
    if case.doctor_decision:
        return DOCTOR_DECISION_MAP.get(case.doctor_decision, case.doctor_decision.upper())
    return ""


def _get_support_flag_display(case: Case) -> str:
    """Map doctor_support_flag to Portuguese label."""
    return SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag)


def _get_admission_flow_display(case: Case) -> str:
    """Map doctor_admission_flow to Portuguese label."""
    return ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow)


# ── Card builder ─────────────────────────────────────────────────────────


def _build_case_card(case: Case, wait_minutes: int, user: Any = None) -> dict[str, Any]:
    """Build a dict with all display data for a scheduler case card.

    If user is provided, lock status is computed relative to the current user.
    """
    has_psi = case.post_schedule_issue_status == "opened"
    return {
        "case_id": str(case.case_id),
        "patient_name": _get_patient_name(case),
        "patient_age": _get_patient_age(case),
        "patient_gender": _get_patient_gender(case),
        "agency_record_number": case.agency_record_number or "",
        "origin_unit": case.get_origin_unit_display(compact=True),
        "diagnosis": _get_diagnosis(case),
        "doctor_decision_display": _get_doctor_decision_display(case),
        "doctor_display": case.doctor_display,
        "support_flag_display": _get_support_flag_display(case),
        "admission_flow_display": _get_admission_flow_display(case),
        "has_doctor_observation": case.has_doctor_observation,
        "doctor_observation": case.doctor_observation,
        "wait_minutes": wait_minutes,
        # Lock fields
        **compute_lock_display(case, user=user),
        # Post-schedule intercurrence fields
        "regulation_days_on_screen": case.regulation_days_on_screen,
        "has_post_schedule_issue": has_psi,
        "post_schedule_issue_reason": case.post_schedule_issue_reason if has_psi else "",
        "post_schedule_issue_reason_label": get_post_schedule_issue_reason_label(case.post_schedule_issue_reason)
        if has_psi
        else "",
        "post_schedule_issue_message": case.post_schedule_issue_message if has_psi else "",
    }


# ── View ──────────────────────────────────────────────────────────────────


def _local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    """Retorna início e fim do dia local (timezone-aware) para filtros ORM.

    Usa o fuso horário configurado no Django (TIME_ZONE), não a data UTC
    de timezone.now().date().
    """
    local_day = day or timezone.localdate()
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(local_day, time.min), current_tz)
    end = start + timedelta(days=1)
    return start, end


def _scheduler_queue_context(user: Any = None, tab: str = "pending") -> dict[str, Any]:
    """Build context for full and HTMX scheduler queue renders.

    Accepts an optional user to compute lock status relative to the
    current user for each case card. The `tab` parameter controls which
    content is rendered (pending or processed).
    """
    # Lazily expire stale locks before querying
    expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_APPT])

    now = timezone.now()

    # ── Pending cases (always computed for badges) ──────────────────────
    pending_cases: QuerySet[Case] = (
        Case.objects.filter(status=CaseStatus.WAIT_APPT)
        .select_related("doctor", "locked_by")
        .order_by(F("regulation_days_on_screen").desc(nulls_last=True), "created_at")
    )

    pending_cards: list[dict[str, Any]] = []
    for case in pending_cases:
        delta = now - case.created_at
        wait_minutes = int(delta.total_seconds() // 60)
        pending_cards.append(_build_case_card(case, wait_minutes, user=user))

    pending_count = len(pending_cards)

    # ── Immediate notices (always computed for badges) ──────────────────
    today: date = timezone.localdate()

    immediate_notice_qs: QuerySet[Case] = (
        Case.objects.filter(
            doctor_admission_flow="immediate",
            events__event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            events__timestamp__date=today,
        )
        .exclude(status=CaseStatus.WAIT_APPT)
        .exclude(events__event_type="SCHEDULER_IMMEDIATE_ACK")
        .select_related("doctor")
        .distinct()
        .order_by("-doctor_decided_at", "-created_at")
    )

    immediate_notice_cards: list[dict[str, Any]] = []
    for case in immediate_notice_qs:
        delta = now - (case.doctor_decided_at or case.created_at)
        wait_minutes = int(delta.total_seconds() // 60)
        immediate_notice_cards.append(_build_case_card(case, wait_minutes))

    immediate_notice_count = len(immediate_notice_cards)

    # ── Processados hoje ────────────────────────────────────────────────
    start, end = _local_day_bounds()
    processed_qs: QuerySet[Case] = (
        Case.objects.filter(
            scheduler=user,
            appointment_status__in=["confirmed", "denied"],
            appointment_decided_at__gte=start,
            appointment_decided_at__lt=end,
        )
        .select_related("doctor")
        .order_by("-appointment_decided_at")
    )

    processed_today: list[dict[str, Any]] = []
    for case in processed_qs:
        processed_today.append(_build_processed_card(case))

    processed_today_count = len(processed_today)

    context: dict[str, Any] = {
        "active_tab": tab,
        "pending_cases": pending_cards,
        "immediate_notice_cases": immediate_notice_cards,
        "processed_today": processed_today,
        "pending_count": pending_count,
        "immediate_notice_count": immediate_notice_count,
        "processed_today_count": processed_today_count,
        "total_notice_count": pending_count + immediate_notice_count,
    }

    return context


def _build_processed_card(case: Case) -> dict[str, Any]:
    """Build a dict with display data for a processed case card."""
    return {
        "case_id": str(case.case_id),
        "patient_name": _get_patient_name(case),
        "patient_age": _get_patient_age(case),
        "patient_gender": _get_patient_gender(case),
        "agency_record_number": case.agency_record_number or "",
        "origin_unit": case.get_origin_unit_display(compact=True),
        "diagnosis": _get_diagnosis(case),
        "doctor_display": case.doctor_display,
        "support_flag_display": _get_support_flag_display(case),
        "admission_flow_display": _get_admission_flow_display(case),
        "appointment_status": case.appointment_status,
        "appointment_status_label": "Confirmado" if case.appointment_status == "confirmed" else "Recusado",
        "appointment_decided_at": case.appointment_decided_at,
        "appointment_at": case.appointment_at,
        "appointment_reason": case.appointment_reason or "",
    }


@login_required
@role_required("scheduler")
def scheduler_queue(request: HttpRequest) -> HttpResponse:
    """View da fila de agendamento: pendentes e processados hoje."""
    tab = request.GET.get("tab", "pending")
    return render(request, "scheduler/queue.html", _scheduler_queue_context(user=request.user, tab=tab))


@login_required
@role_required("scheduler")
def scheduler_queue_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial for polling the scheduler queue without full refresh."""
    tab = request.GET.get("tab", "pending")
    return render(request, "scheduler/_queue_content.html", _scheduler_queue_context(user=request.user, tab=tab))


@login_required
@role_required("scheduler")
def scheduler_processed_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Read-only detail of a case processed by the logged-in scheduler.

    Uses the scheduler detail template (context_detail.html), matching the
    same read-only experience as historical/contextual case detail.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
        scheduler=request.user,
        appointment_status__in=["confirmed", "denied"],
    )

    back_url = reverse("scheduler:queue") + "?tab=processed"
    back_label = "← Voltar aos processados hoje"

    context = _build_scheduler_detail_context(
        request=request,
        case=case,
        back_url=back_url,
        back_label=back_label,
        pdf_url=reverse("scheduler:processed_pdf", args=[case.case_id]),
    )

    return render(request, "scheduler/context_detail.html", context)


@login_required
@role_required("scheduler")
@xframe_options_sameorigin
def scheduler_processed_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve PDF for a case processed by the logged-in scheduler."""
    case = get_object_or_404(
        Case,
        case_id=case_id,
        scheduler=request.user,
        appointment_status__in=["confirmed", "denied"],
    )
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")
    return FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )


# ── Context detail (read-only, by mention) ─────────────────────────────────

NOTIFICATION_TITLE_FOR_CONTEXT = "Você foi mencionado em um caso"


def _scheduler_has_context_notification(user: Any, case: Case) -> bool:
    """Verifica se o scheduler possui UserNotification vinculada ao caso.

    Não faz render/redirect; apenas responde True/False para autorização.
    """
    from apps.accounts.models import UserNotification

    return UserNotification.objects.filter(
        recipient=user,
        case=case,
    ).exists()


def _is_scheduler_historical_case(case: Case) -> bool:
    """Verifica se o caso está no escopo histórico do scheduler.

    Critério:
    - doctor_decision == 'accept'
    - doctor_admission_flow == 'scheduled'
    - appointment_status in ('confirmed', 'denied', 'cancelled')

    Inclui CLEANED e casos finais pós-agendamento.
    """
    if case.doctor_decision != "accept":
        return False
    if case.doctor_admission_flow != "scheduled":
        return False
    if case.appointment_status not in ("confirmed", "denied", "cancelled"):
        return False
    return True


def _scheduler_historical_queryset() -> QuerySet[Case]:
    """Retorna QuerySet de casos no escopo histórico do scheduler.

    Usado por busca histórica e validação de acesso.
    """
    return Case.objects.filter(
        doctor_decision="accept",
        doctor_admission_flow="scheduled",
        appointment_status__in=["confirmed", "denied", "cancelled"],
    )


# ── Shared helper for scheduler detail context ─────────────────────────


def _build_scheduler_detail_context(
    *,
    request: HttpRequest,
    case: Case,
    back_url: str,
    back_label: str,
    pdf_url: str | None = None,
) -> dict[str, Any]:
    """Build context for scheduler case detail template (context_detail.html).

    Centraliza a montagem de contexto compartilhado entre:
    - scheduler_context_detail (detalhe por notificação/busca histórica)
    - scheduler_processed_detail (detalhe de processados hoje)

    Não adquire lock, não altera FSM, não mostra ações de workflow.
    """
    from apps.intake.views import (
        EVENT_DOT_CSS,
        EVENT_LABELS,
        STATUS_CSS_CLASS,
        STATUS_LABELS,
        STEP_STATUS_INDEX,
        STEPS,
    )

    events = case.events.all()

    current_step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    steps = STEPS

    enriched_events: list[dict[str, Any]] = []
    for e in events:
        enriched_events.append(
            {
                "event": e,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
            }
        )

    # Extract patient info
    patient_name = ""
    patient_age = ""
    patient_gender = ""
    diagnosis = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = str(patient.get("name", ""))
            patient_age = str(patient.get("age", ""))
            patient_gender = str(patient.get("gender", ""))
        eda = case.structured_data.get("eda", {})
        if isinstance(eda, dict):
            indication = eda.get("indication_category", "")
            if indication:
                diagnosis = str(indication)
    if not diagnosis and case.summary_text:
        diagnosis = case.summary_text

    doctor_decision_display = DOCTOR_DECISION_MAP.get(case.doctor_decision, "")
    support_flag_display = SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag)
    admission_flow_display = ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow)

    # Communication context
    # Para casos históricos/processados, comunicação ao NIR usa endpoint específico.
    is_historical = _is_scheduler_historical_case(case)
    can_message_nir = is_historical
    # Formulário genérico fica oculto quando o CTA Comunicar NIR está visível
    can_post_communication = case.status != CaseStatus.CLEANED and not can_message_nir

    communication_post_url = reverse("intake:post_case_communication", args=[case.case_id])
    communication_next_url = request.get_full_path() + "#case-communication"

    context: dict[str, Any] = {
        "case": case,
        "patient_name": patient_name,
        "patient_age": patient_age,
        "patient_gender": patient_gender,
        "diagnosis": diagnosis,
        "agency_record_number": case.agency_record_number or "",
        "origin_unit": case.get_origin_unit_display(compact=False),
        "doctor_decision_display": doctor_decision_display,
        "doctor_display": case.doctor_display,
        "support_flag_display": support_flag_display,
        "admission_flow_display": admission_flow_display,
        "has_doctor_observation": case.has_doctor_observation,
        "doctor_observation": case.doctor_observation,
        "created_by_display": case.created_by.get_full_name() or str(case.created_by.username),
        "created_at": case.created_at,
        "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
        "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
        # Timeline
        "events": enriched_events,
        "steps": steps,
        "current_step_idx": current_step_idx,
        # Communication
        "communication_messages": case.communication_messages.select_related("author").all(),
        "can_post_communication": can_post_communication,
        "communication_post_url": communication_post_url,
        "communication_next_url": communication_next_url,
        "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
        # Read-only detail flags
        "is_context_detail": True,
        "show_intake_nav": False,
        "back_url": back_url,
        "back_label": back_label,
        # Historical flags
        "is_historical_scheduler": is_historical,
        "show_historical_message_nir": can_message_nir,
        "historical_message_nir_url": reverse("scheduler:historical_message_nir", args=[case.case_id])
        if is_historical
        else "",
        # PDF link (only for processes hoje — never for historical/contextual)
        "pdf_url": pdf_url,
    }

    return context


@login_required
@role_required("scheduler")
def scheduler_context_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """GET: Detalhe contextual read-only para scheduler mencionado.

    Exige que o usuário logado possua UserNotification vinculada ao caso
    OU que o caso esteja no escopo histórico do scheduler.
    Não adquire lock, não altera FSM, não mostra ações de workflow.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )

    # Autorização: deve existir UserNotification para o usuário + caso,
    # OU o caso deve estar no escopo histórico do scheduler.
    if not _scheduler_has_context_notification(request.user, case) and not _is_scheduler_historical_case(case):
        raise Http404("Nenhuma notificação encontrada para este caso.")

    back_url = request.META.get("HTTP_REFERER", reverse("scheduler:queue"))
    back_label = "← Voltar"

    context = _build_scheduler_detail_context(
        request=request,
        case=case,
        back_url=back_url,
        back_label=back_label,
    )

    return render(request, "scheduler/context_detail.html", context)


# ── Immediate admission acknowledgement ────────────────────────────────────


@login_required
@role_required("scheduler")
def immediate_ack(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: scheduler acknowledges immediate admission operational notice.

    Uses select_for_update inside a transaction to guarantee idempotency
    under concurrent calls — only one SCHEDULER_IMMEDIATE_ACK is created.
    """
    if request.method != "POST":
        raise Http404

    from django.db import transaction

    case = get_object_or_404(
        Case,
        pk=case_id,
        doctor_admission_flow="immediate",
        events__event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
    )

    with transaction.atomic():
        # Lock the row to prevent race conditions
        locked_case = Case.objects.select_for_update().get(pk=case.case_id)

        already_acknowledged = locked_case.events.filter(event_type="SCHEDULER_IMMEDIATE_ACK").exists()

        if not already_acknowledged:
            locked_case._record_event("SCHEDULER_IMMEDIATE_ACK", user=request.user)
            locked_case.save()

    return redirect("scheduler:queue")


# ── Confirm helpers ────────────────────────────────────────────────────────


def _build_confirm_context(
    case: Case,
    form: SchedulerDecisionForm | PostScheduleIssueForm,
    request: HttpRequest | None = None,
) -> dict[str, Any]:
    """Build context dict for the confirm template."""
    ctx: dict[str, Any] = {
        "case": case,
        "form": form,
        "patient_name": _get_patient_name(case),
        "patient_age": _get_patient_age(case),
        "patient_gender": _get_patient_gender(case),
        "diagnosis": _get_diagnosis(case),
        "doctor_decision_display": _get_doctor_decision_display(case),
        "doctor_display": case.doctor_display,
        "support_flag_display": _get_support_flag_display(case),
        "admission_flow_display": _get_admission_flow_display(case),
        "origin_unit": case.get_origin_unit_display(compact=False),
        # Communication thread context
        "communication_messages": case.communication_messages.select_related("author").all(),
        "can_post_communication": case.status != CaseStatus.CLEANED,
        "communication_post_url": reverse("intake:post_case_communication", args=[case.case_id]),
        "communication_next_url": ((request.get_full_path() + "#case-communication") if request is not None else "#"),
        "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
    }
    # Include post-schedule issue info if applicable
    if case.post_schedule_issue_status == "opened":
        ctx["has_post_schedule_issue"] = True
        ctx["ps_issue_reason"] = case.post_schedule_issue_reason
        ctx["ps_issue_reason_label"] = get_post_schedule_issue_reason_label(case.post_schedule_issue_reason)
        ctx["ps_issue_message"] = case.post_schedule_issue_message
        ctx["ps_issue_opened_by"] = (
            case.post_schedule_issue_opened_by.display_name if case.post_schedule_issue_opened_by else ""
        )
        ctx["ps_issue_opened_at"] = case.post_schedule_issue_opened_at
    return ctx


# ── Confirm view ────────────────────────────────────────────────────────────


@login_required
@role_required("scheduler")
def scheduler_confirm(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """GET: Renderiza formulário de confirmação para um caso em WAIT_APPT.

    Acquires a lock on the case before rendering. If the lock cannot be
    acquired (another user has it), redirects to the queue with a warning.

    Se o caso tiver intercorrência pós-agendamento aberta, renderiza o
    formulário de resolução de intercorrência.
    """
    case = get_object_or_404(Case.objects.select_related("doctor"), pk=case_id)

    if case.status != CaseStatus.WAIT_APPT:
        raise Http404("Caso não está aguardando agendamento.")

    user = request.user

    # Detecta se é intercorrência ativa
    has_psi = case.post_schedule_issue_status == "opened"

    # Attempt to claim the lock
    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_APPT,
        context="scheduler_confirm",
        role="scheduler",
    )

    if not result.acquired:
        if result.locked_by_display:
            messages.warning(
                request,
                f"Este caso está reservado por {result.locked_by_display}. "
                f"Aguarde até que a reserva expire para acessá-lo.",
            )
        else:
            messages.warning(
                request,
                "Não foi possível acessar este caso no momento. Tente novamente.",
            )
        return redirect("scheduler:queue")

    # Fresh DB instance
    case = get_object_or_404(Case.objects.select_related("doctor"), pk=case_id)
    form = PostScheduleIssueForm() if has_psi else SchedulerDecisionForm()
    context = _build_confirm_context(case, form, request=request)
    context["lock_token"] = str(result.token)
    template = "scheduler/confirm_post_schedule_issue.html" if has_psi else "scheduler/confirm.html"
    return render(request, template, context)


@login_required
@role_required("scheduler")
def scheduler_submit(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Valida formulário, persiste decisão e executa transições FSM.

    Requires a valid lock_token to proceed. If the lock is invalid or
    expired, re-renders the form with an error message.

    Se o caso tiver intercorrência pós-agendamento aberta, processa a ação
    do agendador (cancel/reschedule/maintain/deny) via serviço de domínio.
    """
    if request.method != "POST":
        raise Http404

    case = get_object_or_404(Case.objects.select_related("doctor"), pk=case_id)

    if case.status != CaseStatus.WAIT_APPT:
        raise Http404("Caso não está aguardando agendamento.")

    # Detecta se é intercorrência ativa
    has_psi = case.post_schedule_issue_status == "opened"

    # Validate lock token
    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        form_cls = PostScheduleIssueForm if has_psi else SchedulerDecisionForm
        form = form_cls(request.POST)
        ctx = _build_confirm_context(case, form, request=request)
        ctx["lock_error"] = "Sua reserva para este caso expirou ou não é válida. Volte para a fila e tente novamente."
        messages.warning(request, "Token de reserva não encontrado. Volte para a fila.")
        template = "scheduler/confirm_post_schedule_issue.html" if has_psi else "scheduler/confirm.html"
        return render(request, template, ctx)

    # Check lock validity before proceeding
    try:
        assert_case_lock(
            case=case,
            user=request.user,
            token=token,
            context="scheduler_confirm",
        )
    except PermissionError as exc:
        form_cls = PostScheduleIssueForm if has_psi else SchedulerDecisionForm
        form = form_cls(request.POST)
        ctx = _build_confirm_context(case, form, request=request)
        ctx["lock_error"] = str(exc)
        messages.warning(request, str(exc))
        template = "scheduler/confirm_post_schedule_issue.html" if has_psi else "scheduler/confirm.html"
        return render(request, template, ctx)

    if has_psi:
        # ── Fluxo de intercorrência pós-agendamento ──────────────────
        form = PostScheduleIssueForm(request.POST)

        if not form.is_valid():
            ctx = _build_confirm_context(case, form, request=request)
            ctx["lock_token"] = raw_token
            return render(request, "scheduler/confirm_post_schedule_issue.html", ctx)

        psi_action = form.cleaned_data["psi_action"]
        psi_response_message = form.cleaned_data.get("psi_response_message", "")

        try:
            # Build kwargs for the domain service
            kwargs: dict[str, Any] = {
                "case": case,
                "user": request.user,
                "action": psi_action,
                "response_message": psi_response_message,
            }

            if psi_action == "reschedule":
                appt_date: date = form.cleaned_data["psi_appointment_date"]
                appt_time: time = form.cleaned_data["psi_appointment_time"]
                dt_naive = datetime.combine(appt_date, appt_time)
                dt_aware = dt_naive.replace(tzinfo=timezone.get_current_timezone())
                kwargs["appointment_at"] = dt_aware.isoformat()
                kwargs["appointment_location"] = form.cleaned_data.get("psi_appointment_location", "")
                kwargs["appointment_instructions"] = form.cleaned_data.get("psi_appointment_instructions", "")

            from apps.cases.services import respond_post_schedule_issue

            case = respond_post_schedule_issue(**kwargs)

        except ValueError as exc:
            form.add_error(None, str(exc))
            ctx = _build_confirm_context(case, form, request=request)
            ctx["lock_token"] = raw_token
            return render(request, "scheduler/confirm_post_schedule_issue.html", ctx)
    else:
        # ── Fluxo normal de agendamento ──────────────────────────────
        form = SchedulerDecisionForm(request.POST)

        if not form.is_valid():
            ctx = _build_confirm_context(case, form, request=request)
            ctx["lock_token"] = raw_token
            return render(request, "scheduler/confirm.html", ctx)

        decision = form.cleaned_data["decision"]

        # Persist scheduler decision fields
        case.scheduler = request.user  # type: ignore[assignment]  # guaranteed by @login_required
        case.appointment_decided_at = timezone.now()

        if decision == "confirm":
            appt_date = form.cleaned_data["appointment_date"]
            appt_time = form.cleaned_data["appointment_time"]
            case.appointment_status = "confirmed"
            case.appointment_at = datetime.combine(appt_date, appt_time).replace(tzinfo=timezone.get_current_timezone())
            case.appointment_location = form.cleaned_data.get("appointment_location", "")
            case.appointment_instructions = form.cleaned_data.get("notes", "")

            # FSM transition: WAIT_APPT → APPT_CONFIRMED
            case.scheduler_decide(appointment_status="confirmed", user=request.user)
        else:
            case.appointment_status = "denied"
            case.appointment_reason = form.cleaned_data.get("reason", "")

            # FSM transition: WAIT_APPT → APPT_DENIED
            case.scheduler_decide(appointment_status="denied", user=request.user)

        # Post final reply → WAIT_R1_CLEANUP_THUMBS (both confirm and deny)
        case.save()  # persiste decisão do scheduler e seu evento
        case.final_reply_posted(user=request.user)
        case.save()

    # Release lock deterministically after successful business logic
    release_lock_service(
        case_id=case.case_id,
        user=request.user,
        token=token,
        context="scheduler_confirm",
    )

    return redirect("scheduler:queue")


# ── Lock renew/release endpoints ──────────────────────────────────────────


@login_required
@role_required("scheduler")
def scheduler_lock_renew(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Renova a reserva de um caso (heartbeat).

    Requer lock_token no body do POST.
    Retorna JsonResponse com 'success' e 'locked_until' ou erro.
    """
    if request.method != "POST":
        raise Http404

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        return JsonResponse({"success": False, "error": "Token de reserva não fornecido."}, status=200)

    result = renew_lock_service(
        case_id=case_id,
        user=request.user,
        token=token,
        context="scheduler_confirm",
    )

    if result.acquired:
        return JsonResponse(
            {
                "success": True,
                "locked_until": result.locked_until.isoformat() if result.locked_until else None,
            }
        )
    return JsonResponse({"success": False, "error": result.reason}, status=200)


@login_required
@role_required("scheduler")
def scheduler_lock_release(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Libera a reserva de um caso explicitamente.

    Requer lock_token no body do POST.
    Retorna JsonResponse com 'success'.
    """
    if request.method != "POST":
        raise Http404

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        return JsonResponse({"success": False, "error": "Token de reserva não fornecido."}, status=200)

    released = release_lock_service(
        case_id=case_id,
        user=request.user,
        token=token,
        context="scheduler_confirm",
    )

    return JsonResponse({"success": released})


# ── Historical search ───────────────────────────────────────────────────────


@login_required
@role_required("scheduler")
def scheduler_historical_search(request: HttpRequest) -> HttpResponse:
    """Busca histórica Scheduler: casos aceitos/agendados/processados.

    Pesquisa por agency_record_number ou nome do paciente.
    Não limitada a processados hoje ou ao scheduler logado.
    """
    query = request.GET.get("q", "").strip()
    results: list[dict[str, Any]] = []

    if query:
        qs = (
            _scheduler_historical_queryset()
            .filter(
                models.Q(agency_record_number__icontains=query)
                | models.Q(structured_data__patient__name__icontains=query)
            )
            .order_by("-created_at")[:50]
        )

        for case in qs:
            results.append(
                {
                    "case": case,
                    "patient_name": _get_patient_name(case),
                    "patient_age": _get_patient_age(case),
                    "patient_gender": _get_patient_gender(case),
                    "diagnosis": _get_diagnosis(case),
                    "agency_record_number": case.agency_record_number or "",
                    "origin_unit": case.get_origin_unit_display(compact=True),
                    "status_label": case.get_status_display(),
                    "appointment_status_label": "Confirmado"
                    if case.appointment_status == "confirmed"
                    else ("Negado" if case.appointment_status == "denied" else "Cancelado"),
                    "appointment_at": case.appointment_at,
                    "doctor_display": case.doctor_display,
                }
            )

    return render(
        request,
        "scheduler/historical_search.html",
        {
            "query": query,
            "results": results,
            "active_tab": "historical",
        },
    )


# ── Historical message to NIR ───────────────────────────────────────────────


@login_required
@role_required("scheduler")
def scheduler_historical_message_nir(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: scheduler envia mensagem operacional ao NIR em caso histórico.

    Regras:
    - Aceita apenas POST.
    - Valida que o caso está no escopo histórico scheduler.
    - Body obrigatório, strip, limite CASE_COMMUNICATION_MAX_LENGTH.
    - Garante menção a @nir para notificar NIR.
    - Preserva menções adicionais do agendador.
    - Chama post_case_communication_message com allow_cleaned=True.
    - Não altera Case.status.
    """
    if request.method != "POST":
        messages.warning(request, "Método não permitido.")
        return redirect("scheduler:historical_search")

    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )

    # Validar escopo histórico
    if not _is_scheduler_historical_case(case):
        raise Http404("Caso não está no escopo histórico do scheduler.")

    body_raw = request.POST.get("body", "").strip()
    if not body_raw:
        messages.warning(request, "A mensagem não pode estar vazia.")
        return redirect("scheduler:context_detail", case_id=case.case_id)

    # Garantir menção a @nir
    from apps.accounts.services import parse_mentions

    parsed = parse_mentions(body_raw)
    if "nir" not in parsed.role_tokens:
        body_raw = f"@nir {body_raw}"

    active_role = request.session.get("active_role", "scheduler")

    try:
        post_case_communication_message(
            case=case,
            author=request.user,
            author_role=active_role,
            body=body_raw,
            allow_cleaned=True,
        )
        messages.success(request, "Mensagem enviada ao NIR com sucesso.")
    except CaseCommunicationError as exc:
        messages.warning(request, str(exc))
    except Exception:
        logger = logging.getLogger(__name__)
        logger.exception("Erro inesperado ao enviar mensagem histórica ao NIR.")
        messages.warning(request, "Erro inesperado ao enviar mensagem.")

    return redirect(f"{reverse('scheduler:context_detail', args=[case.case_id])}#case-communication")
