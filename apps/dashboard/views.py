"""Views do dashboard de monitoramento para manager e admin."""

from datetime import date, datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseStatus, SupervisorSummary

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


def _compute_summary() -> dict[str, int]:
    """Computa métricas resumidas do dashboard.

    Usa campos de decisão imutáveis (doctor_decision, appointment_status)
    em vez do status FSM transitório, garantindo que:
    - Casos negados e já limpos (CLEANED) ainda são contados como negados.
    - Casos aceitos pelo médico mas negados pelo scheduler são contados
      como negados, não como aceitos.
    - Aceitos e Negados são mutuamente exclusivos.

    Usa _local_day_bounds() para filtrar casos do dia local em vez de
    timezone.now().date() que retorna data UTC.
    """
    start, end = _local_day_bounds()
    today_cases = Case.objects.filter(created_at__gte=start, created_at__lt=end)

    total_today = today_cases.count()

    accepted = today_cases.filter(doctor_decision="accept").exclude(appointment_status="denied").count()

    denied = today_cases.filter(Q(doctor_decision="deny") | Q(appointment_status="denied")).count()

    in_progress = total_today - accepted - denied

    return {
        "total_today": total_today,
        "accepted": accepted,
        "denied": denied,
        "in_progress": in_progress,
    }


def _compute_stage_waiting() -> dict[str, int]:
    """Contagem de casos aguardando por etapa."""
    return {
        "waiting_doctor": Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count(),
        "waiting_appt": Case.objects.filter(status=CaseStatus.WAIT_APPT).count(),
        "waiting_confirm": Case.objects.filter(status=CaseStatus.WAIT_R1_CLEANUP_THUMBS).count(),
    }


def _compute_admission_flow() -> dict[str, int]:
    """Fluxo de admissão (agendado vs imediato) para casos aceitos hoje.

    Usa _local_day_bounds() em vez de timezone.now().date() para
    consistência com _compute_summary() na definição do dia local.
    """
    start, end = _local_day_bounds()
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
    """Formata timedelta para minutos."""
    if td:
        return f"{int(td.total_seconds() // 60)} min"
    return "—"


def _compute_average_times() -> dict[str, str]:
    """Tempos médios do fluxo.

    Calcula médias apenas quando há dados suficientes.
    """
    # Upload → Decisão Médica
    decided_qs = Case.objects.exclude(doctor_decided_at=None).annotate(
        decision_time=ExpressionWrapper(
            F("doctor_decided_at") - F("created_at"),
            output_field=DurationField(),
        ),
    )
    avg_decision = decided_qs.aggregate(avg=Avg("decision_time"))["avg"]

    # Decisão → Agendamento
    scheduled_qs = Case.objects.filter(
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
    completed_qs = Case.objects.exclude(cleanup_completed_at=None).annotate(
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


def _compute_result(case: Case) -> tuple[str, str]:
    """Computa label e classe CSS (Bootstrap badge) do resultado final."""
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


def _enrich_case(case: Case) -> dict[str, object]:
    """Enriquece um Case com dados de apresentação para cards do dashboard."""
    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    result_label, result_css = _compute_result(case)

    return {
        "case": case,
        "patient_name": patient_name,
        "patient_age": case.patient_age,
        "patient_gender": case.patient_gender,
        "result_label": result_label,
        "result_css": result_css,
        "origin_unit": case.get_origin_unit_display(compact=True),
    }


@login_required
@role_required("manager", "admin")
def dashboard_index(request: HttpRequest) -> HttpResponse:
    """Dashboard com métricas e tabela de todos os casos."""
    summary = _compute_summary()
    stage_waiting = _compute_stage_waiting()
    admission_flow = _compute_admission_flow()
    avg_times = _compute_average_times()

    # Tabela de casos — todos, sem filtro de usuario
    cases_qs = Case.objects.select_related("created_by").order_by("-created_at")

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

    # Paginação
    paginator = Paginator(cases_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    enriched_cases = [_enrich_case(c) for c in page_obj]

    # Último resumo para o card no dashboard
    latest_summary = SupervisorSummary.objects.order_by("-window_end").first()

    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
            "stage_waiting": stage_waiting,
            "admission_flow": admission_flow,
            "avg_times": avg_times,
            "cases": enriched_cases,
            "page_obj": page_obj,
            "status_filter": status_filter,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": CaseStatus.choices,
            "STATUS_LABELS": STATUS_LABELS,
            "latest_summary": latest_summary,
        },
    )


@login_required
@role_required("manager", "admin")
def dashboard_case_detail(request: HttpRequest, case_id: str) -> HttpResponse:
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

    result_info = None
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
    if is_scope_gated:
        reason_code = case.suggested_action.get("reason_code", "") if isinstance(case.suggested_action, dict) else ""
        reason_text = case.suggested_action.get("reason_text", "") if isinstance(case.suggested_action, dict) else ""
        result_info = {
            "type": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": reason_text,
        }
    elif is_doctor_denied_final or case.status == CaseStatus.DOCTOR_DENIED:
        result_info = {
            "type": "doctor_denied",
            "reason": case.doctor_reason,
            "doctor_display": case.doctor_display,
        }
    elif is_immediate_final:
        result_info = {
            "type": "accepted_immediate",
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "doctor_display": case.doctor_display,
        }
    elif case.status == CaseStatus.APPT_DENIED or (terminal_with_result and case.appointment_status == "denied"):
        result_info = {
            "type": "appt_denied",
            "reason": case.appointment_reason,
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result:
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
        }
    elif case.status == CaseStatus.FAILED:
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
