"""Views do dashboard de monitoramento para manager e admin."""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q, QuerySet
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseEvent, CaseStatus, SupervisorSummary
from apps.cases.services import (
    ADMINISTRATIVE_CLOSURE_REASON_CHOICES,
    administratively_close_case,
)

# Reaproveita mapeamentos definidos no intake para consistência visual
from apps.intake.views import (
    ADMISSION_FLOW_MAP,
    EVENT_DOT_CSS,
    EVENT_LABELS,
    STATUS_CSS_CLASS,
    STATUS_LABELS,
    STEP_STATUS_INDEX,
    STEPS,
    SUPPORT_FLAG_MAP,
)


def _local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    """Retorna início e fim do dia local (timezone-aware) para filtros ORM.

    Usa o fuso horário configurado no Django (TIME_ZONE), não a data UTC
    de timezone.now().date(). Isso evita o bug de fronteira UTC/local
    onde timezone.now() já está no dia seguinte UTC enquanto o fuso local
    ainda está no dia anterior.

    Exemplo:
        timezone.now()  = 2026-06-01 01:00 UTC
        localdate(Bahia)= 2026-05-31 22:00 BRT
        day=None        → bounds de 2026-05-31 00:00 até 2026-06-01 00:00 BRT
    """
    local_day = day or timezone.localdate()
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(local_day, time.min), current_tz)
    end = start + timedelta(days=1)
    return start, end


def _compute_summary(day: date | None = None) -> dict[str, int]:
    """Computa métricas resumidas do dashboard.

    Usa campos de decisão imutáveis (doctor_decision, appointment_status)
    em vez do status FSM transitório, garantindo que:
    - Casos negados e já limpos (CLEANED) ainda são contados como negados.
    - Casos aceitos pelo médico mas negados pelo scheduler são contados
      como negados, não como aceitos.
    - Aceitos e Negados são mutuamente exclusivos.

    Usa _local_day_bounds() para filtrar casos do dia local em vez de
    timezone.now().date() que retorna data UTC.

    Se day for fornecido (ex: metrics_date), as métricas refletem
    aquele dia em vez de hoje.
    """
    start, end = _local_day_bounds(day)
    today_cases = Case.objects.filter(created_at__gte=start, created_at__lt=end)

    total_today = today_cases.count()

    # Casos administrativamente encerrados (via CASE_ADMINISTRATIVELY_CLOSED)
    admin_closed_ids = set(
        CaseEvent.objects.filter(
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
            case__in=today_cases,
        )
        .values_list("case_id", flat=True)
        .distinct()
    )
    admin_closed_count = len(admin_closed_ids)

    # Excluir admin-closed de accepted e denied
    accepted = (
        today_cases.filter(doctor_decision="accept")
        .exclude(appointment_status="denied")
        .exclude(pk__in=admin_closed_ids)
        .count()
    )
    denied = (
        today_cases.filter(Q(doctor_decision="deny") | Q(appointment_status="denied"))
        .exclude(pk__in=admin_closed_ids)
        .count()
    )

    in_progress = total_today - accepted - denied - admin_closed_count

    return {
        "total_today": total_today,
        "accepted": accepted,
        "denied": denied,
        "administratively_closed": admin_closed_count,
        "in_progress": in_progress,
    }


def _compute_stage_waiting() -> dict[str, int]:
    """Contagem de casos aguardando por etapa."""
    return {
        "waiting_doctor": Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count(),
        "waiting_appt": Case.objects.filter(status=CaseStatus.WAIT_APPT).count(),
        "waiting_confirm": Case.objects.filter(status=CaseStatus.WAIT_R1_CLEANUP_THUMBS).count(),
    }


def _compute_admission_flow(day: date | None = None) -> dict[str, int]:
    """Fluxo de admissão (agendado vs imediato) para casos aceitos no dia.

    Usa _local_day_bounds() em vez de timezone.now().date() para
    consistência com _compute_summary() na definição do dia local.

    Se day for fornecido (ex: metrics_date), o fluxo reflete
    aquele dia em vez de hoje.
    """
    start, end = _local_day_bounds(day)
    base = Case.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
        doctor_decision="accept",
    )
    return {
        "scheduled": base.filter(doctor_admission_flow="scheduled").count(),
        "immediate": base.filter(doctor_admission_flow="immediate").count(),
    }


def _fmt_duration(td: timedelta | None) -> str:
    """Formata timedelta para minutos ou horas/minutos.

    Retorna:
        valor ausente    → "—"
        < 60 min         → "N min"
        60 min           → "1 h"
        65 min           → "1 h 05 min"
        1100 min         → "18 h 20 min"
        timedelta(0)     → "0 min"
    """
    if td is None:
        return "—"
    total_minutes = int(td.total_seconds() // 60)
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if minutes == 0:
        return f"{hours} h"
    return f"{hours} h {minutes:02d} min"


def _compute_average_times(day: date | None = None) -> dict[str, str]:
    """Tempos médios do fluxo.

    Calcula médias apenas quando há dados suficientes.
    Se day for fornecido (ex: metrics_date), filtra casos criados
    naquele dia.
    """
    cases_qs = Case.objects.all()
    if day is not None:
        start, end = _local_day_bounds(day)
        cases_qs = cases_qs.filter(created_at__gte=start, created_at__lt=end)

    # Upload → Decisão Médica
    decided_qs = cases_qs.exclude(doctor_decided_at=None).annotate(
        decision_time=ExpressionWrapper(
            F("doctor_decided_at") - F("created_at"),
            output_field=DurationField(),
        ),
    )
    avg_decision = decided_qs.aggregate(avg=Avg("decision_time"))["avg"]

    # Decisão → Agendamento
    scheduled_qs = cases_qs.filter(
        appointment_decided_at__isnull=False,
        doctor_decided_at__isnull=False,
    ).annotate(
        sched_time=ExpressionWrapper(
            F("appointment_decided_at") - F("doctor_decided_at"),
            output_field=DurationField(),
        ),
    )
    avg_sched = scheduled_qs.aggregate(avg=Avg("sched_time"))["avg"]

    # Ciclo Total
    completed_qs = cases_qs.exclude(cleanup_completed_at=None).annotate(
        cycle_time=ExpressionWrapper(
            F("cleanup_completed_at") - F("created_at"),
            output_field=DurationField(),
        ),
    )
    avg_cycle = completed_qs.aggregate(avg=Avg("cycle_time"))["avg"]

    return {
        "upload_to_decision": _fmt_duration(avg_decision),
        "decision_to_schedule": _fmt_duration(avg_sched),
        "total_cycle": _fmt_duration(avg_cycle),
    }


def _has_admin_close_event(case: Case) -> bool:
    """Verifica se o caso tem evento de encerramento administrativo."""
    return case.events.filter(event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()


def _compute_result(case: Case) -> tuple[str, str]:
    """Computa label e classe CSS (Bootstrap badge) do resultado final.

    Prioridade:
    1. Encerramento administrativo (tem precedência sobre todos)
    2. Scope-gated manual review
    3. Doctor denied
    4. Appointment denied
    5. Accepted scheduled confirmed
    6. Immediate admission
    7. Failed
    8. Awaiting scheduler
    9. In progress step
    """
    # Administrative closure has top priority
    if _has_admin_close_event(case):
        return ("🔒 Encerrado administrativamente", "bg-secondary")

    # Scope-gated manual review
    if (
        case.suggested_action
        and isinstance(case.suggested_action, dict)
        and case.suggested_action.get("decision") == "manual_review_required"
    ):
        return ("⚠ Revisão Manual", "bg-warning text-dark")

    # Doctor denied
    if case.doctor_decision == "deny":
        return ("✗ Negado pelo Médico", "bg-danger")

    # Appointment cancelled after post-schedule intercurrence
    if case.appointment_status == "cancelled":
        return ("↯ Agendamento cancelado após intercorrência", "bg-warning text-dark")

    # Appointment denied
    if case.appointment_status == "denied":
        return ("✗ Agendamento Negado", "bg-danger")

    # Accepted — scheduled confirmed
    if case.doctor_decision == "accept" and case.appointment_status == "confirmed":
        return ("✓ Agendamento Confirmado", "bg-success")

    # Accepted — immediate admission
    if case.doctor_decision == "accept" and case.doctor_admission_flow == "immediate":
        return ("✓ Vinda Imediata", "bg-success")

    # Failed
    if case.status == CaseStatus.FAILED:
        return ("✗ Falha no Processamento", "bg-danger")

    # Accepted by doctor — awaiting scheduler
    if case.doctor_decision == "accept":
        return ("⏳ Aguardando Agendamento", "bg-secondary")

    # In progress — show current pipeline step
    step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    step_label = STEPS[step_idx]["label"] if step_idx < len(STEPS) else "..."
    return (f"⏳ {step_label}", "bg-secondary")


# ── Attention filter constants ─────────────────────────────────────────

ATTENTION_PROCESSING_STUCK_AFTER = timedelta(minutes=30)
ATTENTION_WAITING_STUCK_AFTER = timedelta(hours=48)

ATTENTION_PROCESSING_STATUSES: tuple[str, ...] = (
    CaseStatus.NEW,
    CaseStatus.R1_ACK_PROCESSING,
    CaseStatus.EXTRACTING,
    CaseStatus.LLM_STRUCT,
    CaseStatus.LLM_SUGGEST,
    CaseStatus.R2_POST_WIDGET,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.DOCTOR_DENIED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.APPT_DENIED,
    CaseStatus.R1_FINAL_REPLY_POSTED,
    CaseStatus.CLEANUP_RUNNING,
)

ATTENTION_WAITING_STATUSES: tuple[str, ...] = (
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.WAIT_APPT,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
)


def _attention_q(now: datetime) -> Q:
    """Retorna Q object com os critérios de atenção para filtrar casos suspeitos."""
    processing_cutoff = now - ATTENTION_PROCESSING_STUCK_AFTER
    waiting_cutoff = now - ATTENTION_WAITING_STUCK_AFTER
    return (
        Q(status=CaseStatus.FAILED)
        | Q(locked_by__isnull=False, locked_until__isnull=False, locked_until__lte=now)
        | Q(status__in=ATTENTION_PROCESSING_STATUSES, updated_at__lte=processing_cutoff)
        | Q(status__in=ATTENTION_WAITING_STATUSES, updated_at__lte=waiting_cutoff)
    )


def _get_attention_reason(case: Case, *, now: datetime | None = None) -> str:
    """Retorna motivo compacto de atenção para exibição no card do dashboard.

    Retorna string vazia se o caso não necessita atenção.
    """
    if now is None:
        now = timezone.now()

    # Falha sempre é motivo de atenção
    if case.status == CaseStatus.FAILED:
        return "Falha no processamento"

    # Lock expirado
    if case.locked_by_id is not None and case.locked_until is not None and case.locked_until <= now:
        return "Lock expirado"

    # Processamento parado há mais de 30 min
    if case.status in ATTENTION_PROCESSING_STATUSES:
        cutoff = now - ATTENTION_PROCESSING_STUCK_AFTER
        if case.updated_at <= cutoff:
            return "Processamento parado há mais de 30 min"

    # Espera humana há mais de 48h
    if case.status in ATTENTION_WAITING_STATUSES:
        cutoff = now - ATTENTION_WAITING_STUCK_AFTER
        if case.updated_at <= cutoff:
            return "Aguardando ação humana há mais de 48 h"

    return ""


def _enrich_case(case: Case, *, now: datetime | None = None, attention_filter: bool = False) -> dict[str, Any]:
    """Enriquece um Case com dados de apresentação para cards do dashboard."""
    if now is None:
        now = timezone.now()

    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    result_label, result_css = _compute_result(case)

    attention_reason = _get_attention_reason(case, now=now) if attention_filter else ""

    return {
        "case": case,
        "patient_name": patient_name,
        "patient_age": case.patient_age,
        "patient_gender": case.patient_gender,
        "result_label": result_label,
        "result_css": result_css,
        "origin_unit": case.get_origin_unit_display(compact=True),
        "attention_reason": attention_reason,
    }


def _apply_case_search(cases_qs: QuerySet[Case], search_term: str) -> QuerySet[Case]:
    """Aplica busca server-side alinhada aos índices GIN trigram.

    Filtra por nome do paciente (structured_data -> patient -> name) e por
    agency_record_number. As expressões ``lower(...)`` casam com os índices
    da migration ``cases.0011`` (``cases_case_arn_trgm_idx`` e
    ``cases_case_patient_name_trgm_idx``), permitindo Bitmap Index Scan em
    vez de seq scan em tabelas grandes.

    Observação: ``__icontains`` seria compilado como ``UPPER(col) LIKE
    UPPER(p)``, expressão incompatível com o índice ``lower(col)`` e que
    portanto não seria acelerada por ele.
    """
    search_lower = search_term.lower()
    patient_name = KeyTextTransform("name", "structured_data__patient")
    return cases_qs.annotate(
        search_arn=Lower("agency_record_number"),
        search_patient_name=Lower(patient_name),
    ).filter(Q(search_arn__contains=search_lower) | Q(search_patient_name__contains=search_lower))


def _dashboard_case_list_context(request: HttpRequest) -> dict[str, Any]:
    """Monta o contexto para a lista de casos do dashboard.

    Extraído para ser compartilhado entre a renderização completa e a
    renderização parcial (X-ATS-Partial: case-list).
    """
    now = timezone.now()

    # Filtro de atenção
    attention_filter: bool = request.GET.get("attention") == "1"

    # Busca server-side
    search_raw = request.GET.get("search", "")
    search_term = search_raw.strip()[:100]
    search_min_chars_help = False

    # Tabela de casos — todos, sem filtro de usuario
    cases_qs = Case.objects.select_related("created_by").order_by("-created_at")

    # Filtro de atenção (exclui CLEANED, aplica critérios de atenção)
    if attention_filter:
        cases_qs = cases_qs.exclude(status=CaseStatus.CLEANED).filter(_attention_q(now))

    # Busca: só filtra com 3+ caracteres. A expressão usada no helper
    # _apply_case_search é alinhada aos índices trigram para evitar seq scan.
    if len(search_term) >= 3:
        cases_qs = _apply_case_search(cases_qs, search_term)
    elif len(search_term) in (1, 2):
        search_min_chars_help = True

    # Filtros
    status_filter = request.GET.get("status", "")
    if status_filter:
        cases_qs = cases_qs.filter(status=status_filter)

    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if date_from:
        cases_qs = cases_qs.filter(created_at__date__gte=date_from)
    if date_to:
        cases_qs = cases_qs.filter(created_at__date__lte=date_to)

    # Contador de atenção (total de casos suspeitos, sem paginação)
    attention_count: int | None = None
    if attention_filter:
        attention_count = cases_qs.count()
    else:
        attention_count = Case.objects.exclude(status=CaseStatus.CLEANED).filter(_attention_q(now)).count()

    # Paginação
    paginator = Paginator(cases_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    enriched_cases = [_enrich_case(c, now=now, attention_filter=attention_filter) for c in page_obj]

    metrics_date_str = ""
    raw_metrics_date = request.GET.get("metrics_date", "")
    if raw_metrics_date:
        try:
            date.fromisoformat(raw_metrics_date)
            metrics_date_str = raw_metrics_date
        except (ValueError, TypeError):
            pass

    return {
        "cases": enriched_cases,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "date_from": date_from,
        "date_to": date_to,
        "search": search_raw,
        "search_term": search_term,
        "search_min_chars_help": search_min_chars_help,
        "attention_filter": attention_filter,
        "attention_count": attention_count,
        "metrics_date": metrics_date_str,
    }


@login_required
@role_required("manager", "admin")
def dashboard_index(request: HttpRequest) -> HttpResponse:
    """Dashboard com métricas e tabela de todos os casos.

    Se o header ``X-ATS-Partial: case-list`` estiver presente, retorna
    apenas o partial ``dashboard/_case_list.html`` para busca dinâmica
    via Vanilla JS. Caso contrário, renderiza a página completa.
    """
    # Data das métricas — usa query string metrics_date, padrão hoje
    raw_metrics_date = request.GET.get("metrics_date", "")
    metrics_date: date | None = None
    if raw_metrics_date:
        try:
            metrics_date = date.fromisoformat(raw_metrics_date)
        except (ValueError, TypeError):
            metrics_date = None  # inválido → cai para hoje

    summary = _compute_summary(day=metrics_date)
    stage_waiting = _compute_stage_waiting()
    admission_flow = _compute_admission_flow(day=metrics_date)
    avg_times = _compute_average_times(day=metrics_date)

    # Label para o card de total
    if metrics_date is not None:
        total_label = f"Total em {metrics_date.strftime('%d/%m/%Y')}"
    else:
        total_label = "Total Hoje"

    # Último resumo para o card no dashboard
    latest_summary = SupervisorSummary.objects.order_by("-window_end").first()

    # Contexto da lista de casos (compartilhado entre renderização completa e parcial)
    case_list_context = _dashboard_case_list_context(request)

    # Renderização parcial para busca dinâmica (X-ATS-Partial: case-list)
    if request.headers.get("X-ATS-Partial") == "case-list":
        return render(
            request,
            "dashboard/_case_list.html",
            case_list_context,
        )

    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
            "stage_waiting": stage_waiting,
            "admission_flow": admission_flow,
            "avg_times": avg_times,
            "latest_summary": latest_summary,
            "total_label": total_label,
            "status_choices": CaseStatus.choices,
            "STATUS_LABELS": STATUS_LABELS,
            **case_list_context,
        },
    )


@login_required
@role_required("manager", "admin")
@require_POST
def dashboard_administrative_close(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Encerra um caso administrativamente.

    Apenas manager/admin podem encerrar. Exige reason_code e reason_text.
    """
    case = get_object_or_404(Case, case_id=case_id)

    reason_code = request.POST.get("reason_code", "")
    reason_text = request.POST.get("reason_text", "")
    active_role = request.session.get("active_role", "")

    try:
        administratively_close_case(
            case=case,
            user=request.user,
            reason_code=reason_code,
            reason_text=reason_text,
            active_role=active_role,
        )
        messages.success(
            request,
            "Caso encerrado administrativamente. O caso foi removido das filas operacionais e permanece na auditoria.",
        )
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dashboard:case_detail", case_id=case.case_id)


@login_required
@role_required("manager", "admin")
@xframe_options_sameorigin
def dashboard_case_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve o PDF do caso para manager/admin (dashboard gerencial).

    Diferente da rota NIR (intake:serve_pdf), esta rota:
    - Aceita casos em qualquer status, incluindo CLEANED.
    - É restrita a manager/admin.
    - Retorna 404 quando não há pdf_file.
    """
    case = get_object_or_404(Case, case_id=case_id)
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")
    return FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )


@login_required
@role_required("manager", "admin")
def dashboard_case_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhe de qualquer caso (admin) — sem botão 'Confirmar Recebimento'."""
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    events = case.events.all()

    current_step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    steps = STEPS
    terminal_without_scheduling = case.status in (
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        CaseStatus.CLEANED,
    ) and (case.doctor_decision == "deny" or case.doctor_admission_flow == "immediate")
    is_doctor_denied_final = terminal_without_scheduling and case.doctor_decision == "deny"
    is_immediate_final = terminal_without_scheduling and case.doctor_admission_flow == "immediate"
    if terminal_without_scheduling:
        steps = [step for step in STEPS if step["label"] != "Agendamento"]
        current_step_idx = len(steps) - 1

    enriched_events = []
    for e in events:
        enriched_events.append(
            {
                "event": e,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
            }
        )

    result_info: dict[str, object] | None = None

    # Administrative closure has top priority (before any other result)
    if _has_admin_close_event(case):
        # Busca o evento administrativo para extrair payload
        admin_event = case.events.filter(event_type="CASE_ADMINISTRATIVELY_CLOSED").first()
        reason_text = ""
        reason_code = ""
        previous_status = ""
        if admin_event and admin_event.payload:
            reason_text = admin_event.payload.get("reason_text", "")
            reason_code = admin_event.payload.get("reason_code", "")
            previous_status = admin_event.payload.get("previous_status", "")
        result_info = {
            "type": "administratively_closed",
            "reason_text": reason_text,
            "reason_code": reason_code,
            "previous_status": previous_status,
        }

    terminal_with_result = case.status in (
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        CaseStatus.CLEANED,
    )
    # Scope-gated manual review takes priority for WAIT_R1_CLEANUP_THUMBS
    is_scope_gated = (
        case.suggested_action
        and isinstance(case.suggested_action, dict)
        and case.suggested_action.get("decision") == "manual_review_required"
    )
    if result_info is None and is_scope_gated:
        reason_code = case.suggested_action.get("reason_code", "") if isinstance(case.suggested_action, dict) else ""
        reason_text = case.suggested_action.get("reason_text", "") if isinstance(case.suggested_action, dict) else ""
        result_info = {
            "type": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": reason_text,
        }
    elif result_info is None and (is_doctor_denied_final or case.status == CaseStatus.DOCTOR_DENIED):
        result_info = {
            "type": "doctor_denied",
            "reason": case.doctor_reason,
            "doctor_display": case.doctor_display,
        }
    elif result_info is None and is_immediate_final:
        result_info = {
            "type": "accepted_immediate",
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "doctor_display": case.doctor_display,
        }
    elif result_info is None and case.appointment_status == "cancelled":
        result_info = {
            "type": "appt_cancelled",
            "appointment_at": case.appointment_at,
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif result_info is None and (
        case.status == CaseStatus.APPT_DENIED or (terminal_with_result and case.appointment_status == "denied")
    ):
        result_info = {
            "type": "appt_denied",
            "reason": case.appointment_reason,
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif result_info is None and (case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result):
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
        }
    elif result_info is None and case.status == CaseStatus.FAILED:
        result_info = {"type": "failed"}

    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    origin_unit = case.get_origin_unit_display(compact=False)

    return render(
        request,
        "intake/case_detail.html",
        {
            "case": case,
            "events": enriched_events,
            "steps": steps,
            "current_step_idx": current_step_idx,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "can_confirm_receipt": False,
            "result_info": result_info,
            "patient_name": patient_name,
            "origin_unit": origin_unit,
            "can_administratively_close": case.status != CaseStatus.CLEANED,
            "administrative_close_url": reverse("dashboard:administrative_close", args=[case.case_id]),
            "administrative_close_reason_choices": ADMINISTRATIVE_CLOSURE_REASON_CHOICES,
            # Parametrização para template compartilhado
            "show_intake_nav": False,
            "back_url": reverse("dashboard:index"),
            "back_label": "← Voltar ao dashboard",
            "pdf_url": reverse("dashboard:case_pdf", args=[case.case_id]),
        },
    )


@login_required
@role_required("manager", "admin")
def dashboard_summaries(request: HttpRequest) -> HttpResponse:
    """Página com histórico paginado de resumos de supervisão."""
    summaries_qs = SupervisorSummary.objects.order_by("-window_end")
    paginator = Paginator(summaries_qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "dashboard/summaries.html",
        {
            "page_obj": page_obj,
            "summaries": page_obj,
        },
    )
