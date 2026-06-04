"""Views for the doctor app."""

import uuid
from datetime import date
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseStatus
from apps.cases.services import (
    assert_case_lock,
    claim_case_lock,
    compute_lock_display,
    expire_stale_locks_for_statuses,
)
from apps.cases.services import (
    release_case_lock as release_lock_service,
)
from apps.cases.services import (
    renew_case_lock as renew_lock_service,
)

from .forms import DoctorDecisionForm
from .presenters import DoctorReportPresenter


def _map_prior_decision_to_denial_type(decision: str) -> str:
    """Map PriorCaseSummary.decision to denial type for the presenter."""
    if decision == "doctor_denied":
        return "deny_triage"
    if decision == "appointment_denied":
        return "deny_appointment"
    return "deny_triage"


DOCTOR_DECISION_STATUSES = [
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.DOCTOR_DENIED,
]

# ── Helper mappers ───────────────────────────────────────────────────────

SUPPORT_RECOMMENDATION_MAP: dict[str, str] = {
    "none": "Nenhum",
    "anesthesist": "Anestesista",
    "anesthesist_icu": "Anestesista + UTI",
}

SUGGESTION_FLOW_MAP: dict[str, str] = {
    "accept": "Aceitar",
    "deny": "Negar",
    "manual_review_required": "Revisão Manual",
}

DOCTOR_DECISION_MAP: dict[str, str] = {
    "accept": "ACEITAR",
    "deny": "NEGAR",
}

# Prior case decision mapping for display on UI cards
PRIOR_DECISION_DISPLAY: dict[str, str] = {
    "doctor_denied": "Triagem Negada",
    "appointment_denied": "Agendamento Negado",
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
            # LLM1 schema uses "sex" — prefer it, with "gender" fallback
            sex = patient.get("sex")
            if isinstance(sex, str) and sex.strip():
                return sex.strip()
            gender = patient.get("gender")
            if isinstance(gender, str) and gender.strip():
                return gender.strip()
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


def _get_suggested_support(case: Case) -> str:
    """Read support_recommendation from suggested_action and map to Portuguese."""
    if case.suggested_action and isinstance(case.suggested_action, dict):
        raw = case.suggested_action.get("support_recommendation", "none")
        return SUPPORT_RECOMMENDATION_MAP.get(str(raw), str(raw))
    return "Nenhum"


def _get_suggested_flow(case: Case) -> str:
    """Read suggestion from suggested_action and map to display text."""
    if case.suggested_action and isinstance(case.suggested_action, dict):
        raw = case.suggested_action.get("suggestion", "")
        return SUGGESTION_FLOW_MAP.get(str(raw), "—")
    return "—"


def _get_doctor_decision_display(case: Case) -> str:
    """Map doctor_decision to display label."""
    if case.doctor_decision:
        return DOCTOR_DECISION_MAP.get(case.doctor_decision, case.doctor_decision.upper())
    return ""


# ── Card builder ─────────────────────────────────────────────────────────


def _build_case_card(case: Case, wait_minutes: int, user: Any = None) -> dict[str, Any]:
    """Build a dict with all display data for a case card."""
    card: dict[str, Any] = {
        "case_id": str(case.case_id),
        "patient_name": _get_patient_name(case),
        "patient_age": _get_patient_age(case),
        "patient_gender": _get_patient_gender(case),
        "agency_record_number": case.agency_record_number or "",
        "origin_unit": case.get_origin_unit_display(compact=True),
        "diagnosis": _get_diagnosis(case),
        "suggested_support": _get_suggested_support(case),
        "suggested_flow": _get_suggested_flow(case),
        "summary_text": case.summary_text or "",
        "doctor_decision": case.doctor_decision or "",
        "doctor_decision_display": _get_doctor_decision_display(case),
        "wait_minutes": wait_minutes,
        "is_urgent": wait_minutes <= 15,
    }

    # Lock info
    card.update(compute_lock_display(case, user=user))

    return card


# ── View ──────────────────────────────────────────────────────────────────


@login_required
@role_required("doctor")
def _doctor_queue_context(request: HttpRequest) -> dict[str, Any]:
    """Build context for full and HTMX doctor queue renders."""
    # Lazily expire stale locks before querying
    expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])

    pending_cases: QuerySet[Case] = (
        Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).select_related("locked_by").order_by("created_at")
    )

    today: date = date.today()

    doctor_user = request.user
    assert doctor_user.is_authenticated  # guaranteed by @login_required

    decided_qs: QuerySet[Case] = Case.objects.filter(
        status__in=DOCTOR_DECISION_STATUSES,
        doctor=doctor_user,
        events__event_type__startswith="DOCTOR_",
        events__timestamp__date=today,
    ).distinct()

    now = timezone.now()

    pending_cards: list[dict[str, Any]] = []
    for case in pending_cases:
        delta = now - case.created_at
        wait_minutes = int(delta.total_seconds() // 60)
        pending_cards.append(_build_case_card(case, wait_minutes, user=doctor_user))

    total_wait = sum(c["wait_minutes"] for c in pending_cards)
    avg_wait = int(total_wait / len(pending_cards)) if pending_cards else 0

    decided_cards: list[dict[str, Any]] = []
    for case in decided_qs:
        decided_cards.append(_build_case_card(case, 0))

    return {
        "pending_cases": pending_cards,
        "decided_today": decided_cards,
        "pending_count": len(pending_cards),
        "avg_wait_minutes": avg_wait,
    }


@login_required
@role_required("doctor")
def doctor_queue(request: HttpRequest) -> HttpResponse:
    """View da fila médica: casos pendentes e decididos hoje."""
    return render(request, "doctor/queue.html", _doctor_queue_context(request))


@login_required
@role_required("doctor")
def doctor_queue_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial for polling the doctor queue without full refresh."""
    return render(request, "doctor/_queue_content.html", _doctor_queue_context(request))


# ── Decision helpers ─────────────────────────────────────────────────────


def _build_decision_context(case: Case, form: DoctorDecisionForm) -> dict[str, Any]:
    """Build context dict for the decision template."""
    from apps.pipeline.prior_case import lookup_prior_case_context

    prior_context = None
    prior_decision_display = ""
    recent_denial_ctx = None
    if case.agency_record_number:
        pc = lookup_prior_case_context(
            case_id=case.case_id,
            agency_record_number=case.agency_record_number,
        )
        if pc.prior_case is not None:
            prior_context = pc
            prior_decision_display = PRIOR_DECISION_DISPLAY.get(pc.prior_case.decision, pc.prior_case.decision)
            recent_denial_ctx = {
                "decision": _map_prior_decision_to_denial_type(pc.prior_case.decision),
                "reason": pc.prior_case.reason,
                "decided_at": pc.prior_case.decided_at,
                "prior_denial_count_7d": pc.prior_denial_count_7d,
            }

    # Build 7-block report via presenter
    presenter = DoctorReportPresenter(
        structured_data=case.structured_data or {},
        summary_text=case.summary_text or "",
        suggested_action=case.suggested_action or {},
        recent_denial_context=recent_denial_ctx,
    )
    report = presenter.build_report()

    return {
        "case": case,
        "form": form,
        "patient_name": _get_patient_name(case),
        "patient_age": _get_patient_age(case),
        "patient_gender": _get_patient_gender(case),
        "diagnosis": _get_diagnosis(case),
        "suggested_support": _get_suggested_support(case),
        "suggested_flow": _get_suggested_flow(case),
        "summary_text": case.summary_text or "",
        "suggested_action": case.suggested_action or {},
        "structured_data": case.structured_data or {},
        "prior_context": prior_context,
        "prior_decision_display": prior_decision_display,
        "report": report,
    }


# ── Decision view ────────────────────────────────────────────────────────────


@login_required
@role_required("doctor")
def doctor_decision(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """GET: Renderiza formulário de decisão para um caso em WAIT_DOCTOR.

    Acquires a lock on the case before rendering. If the lock cannot be
    acquired (another user has it), redirects to the queue with a warning.
    """
    case = get_object_or_404(Case, pk=case_id)

    if case.status != CaseStatus.WAIT_DOCTOR:
        raise Http404("Caso não está aguardando decisão médica.")

    user = request.user

    # Attempt to claim the lock
    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_DOCTOR,
        context="doctor_decision",
        role="doctor",
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
        return redirect("doctor:queue")

    # Use fresh DB instance (refresh_from_db conflicts with django-fsm)
    case = get_object_or_404(Case, pk=case_id)
    form = DoctorDecisionForm()
    context = _build_decision_context(case, form)
    context["lock_token"] = str(result.token)
    return render(request, "doctor/decision.html", context)


@login_required
@role_required("doctor")
def doctor_submit(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Valida formulário, persiste decisão e executa transições FSM.

    Requires a valid lock_token to proceed. If the lock is invalid or
    expired, re-renders the form with an error message.
    """
    if request.method != "POST":
        raise Http404

    case = get_object_or_404(Case, pk=case_id)

    if case.status != CaseStatus.WAIT_DOCTOR:
        raise Http404("Caso não está aguardando decisão médica.")

    # Validate lock token
    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        form = DoctorDecisionForm(request.POST)
        ctx = _build_decision_context(case, form)
        ctx["lock_error"] = "Sua reserva para este caso expirou ou não é válida. Volte para a fila e tente novamente."
        messages.warning(request, "Token de reserva não encontrado. Volte para a fila.")
        return render(request, "doctor/decision.html", ctx)

    # Check lock validity before proceeding
    try:
        assert_case_lock(
            case=case,
            user=request.user,
            token=token,
            context="doctor_decision",
        )
    except PermissionError as exc:
        form = DoctorDecisionForm(request.POST)
        ctx = _build_decision_context(case, form)
        ctx["lock_error"] = str(exc)
        messages.warning(request, str(exc))
        return render(request, "doctor/decision.html", ctx)

    form = DoctorDecisionForm(request.POST)

    if not form.is_valid():
        ctx = _build_decision_context(case, form)
        ctx["lock_token"] = raw_token
        return render(request, "doctor/decision.html", ctx)

    decision = form.cleaned_data["decision"]

    # Persist decision fields
    case.doctor_observation = form.cleaned_data.get("observation", "")
    case.doctor_decision = decision
    case.doctor_support_flag = form.cleaned_data.get("support_flag", "") or "none"
    case.doctor_admission_flow = form.cleaned_data.get("admission_flow", "")
    case.doctor_reason = form.cleaned_data.get("reason", "")
    case.doctor = request.user  # type: ignore[assignment]  # guaranteed by @login_required
    case.doctor_decided_at = timezone.now()

    # FSM transition: WAIT_DOCTOR → DOCTOR_ACCEPTED or DOCTOR_DENIED
    case.doctor_decide(decision=decision, user=request.user)
    case.save()

    if decision == "accept" and case.doctor_admission_flow == "immediate":
        # Immediate admission does not open a scheduling gate. Room-3/scheduler is
        # only informed for operational awareness; NIR receives the final result.
        case._record_event(
            "IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            user=request.user,
            payload={
                "support_flag": case.doctor_support_flag,
                "admission_flow": case.doctor_admission_flow,
            },
        )
        case.save()
        case.final_reply_posted(user=request.user)
        case.save()
    # If accepted for scheduled admission, advance to WAIT_APPT
    elif decision == "accept":
        case.ready_for_scheduler(user=request.user)
        case.save()
        case.scheduler_request_posted(user=request.user)
        case.save()
    # If denied, post final reply → WAIT_R1_CLEANUP_THUMBS
    else:
        case.final_reply_posted(user=request.user)
        case.save()

    # Release lock deterministically after successful business logic
    release_lock_service(
        case_id=case.case_id,
        user=request.user,
        token=token,
        context="doctor_decision",
    )

    return redirect("doctor:queue")


@login_required
@role_required("doctor")
@xframe_options_sameorigin
def serve_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve o PDF original do caso para visualização inline no <embed>."""
    case = get_object_or_404(Case, pk=case_id)
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    return FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )


@login_required
@role_required("doctor")
def doctor_lock_renew(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
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
        context="doctor_decision",
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
@role_required("doctor")
def doctor_lock_release(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
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
        context="doctor_decision",
    )

    return JsonResponse({"success": released})
