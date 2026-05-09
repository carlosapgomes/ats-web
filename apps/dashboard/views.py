"""Views do dashboard de monitoramento para manager e admin."""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, DurationField, ExpressionWrapper, F
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


def _compute_summary() -> dict[str, int]:
    """Computa métricas resumidas do dashboard."""
    today = timezone.now().date()
    today_cases = Case.objects.filter(created_at__date=today)

    total_today = today_cases.count()

    accepted = (
        today_cases.filter(
            doctor_decision="accept",
        )
        .exclude(
            status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.FAILED],
        )
        .count()
    )

    denied = today_cases.filter(
        status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.APPT_DENIED],
    ).count()

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
    """Fluxo de admissão (agendado vs imediato) para casos aceitos hoje."""
    today = timezone.now().date()
    base = Case.objects.filter(
        created_at__date=today,
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


def _enrich_case(case: Case) -> dict[str, object]:
    """Enriquece um Case com labels e dados do paciente."""
    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    status_label = STATUS_LABELS.get(case.status, case.get_status_display())
    status_css = STATUS_CSS_CLASS.get(case.status, "status-pending")
    step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    step_label = STEPS[step_idx]["label"] if step_idx < len(STEPS) else "—"

    return {
        "case": case,
        "patient_name": patient_name,
        "status_label": status_label,
        "status_css": status_css,
        "step_label": step_label,
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
    if case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result:
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
        }
    elif case.status == CaseStatus.APPT_DENIED:
        result_info = {"type": "appt_denied", "reason": case.appointment_reason}
    elif case.status == CaseStatus.DOCTOR_DENIED:
        result_info = {"type": "doctor_denied", "reason": case.doctor_reason}
    elif case.status == CaseStatus.FAILED:
        result_info = {"type": "failed"}

    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    return render(
        request,
        "intake/case_detail.html",
        {
            "case": case,
            "events": enriched_events,
            "steps": STEPS,
            "current_step_idx": current_step_idx,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "can_confirm_receipt": False,
            "result_info": result_info,
            "patient_name": patient_name,
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
