"""Views for the scheduler app."""

from datetime import date, datetime, time
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.cases.models import Case, CaseStatus

from .forms import SchedulerDecisionForm

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


def _build_case_card(case: Case, wait_minutes: int) -> dict[str, Any]:
    """Build a dict with all display data for a scheduler case card."""
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
        "wait_minutes": wait_minutes,
    }


# ── View ──────────────────────────────────────────────────────────────────


def _scheduler_queue_context() -> dict[str, Any]:
    """Build context for full and HTMX scheduler queue renders."""
    pending_cases: QuerySet[Case] = (
        Case.objects.filter(status=CaseStatus.WAIT_APPT).select_related("doctor").order_by("created_at")
    )

    today: date = date.today()

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

    confirmed_qs: QuerySet[Case] = (
        Case.objects.filter(
            status__in=[CaseStatus.APPT_CONFIRMED, CaseStatus.APPT_DENIED],
            events__event_type__startswith="APPT_",
            events__timestamp__date=today,
        )
        .select_related("doctor")
        .distinct()
    )

    now = timezone.now()

    pending_cards: list[dict[str, Any]] = []
    for case in pending_cases:
        delta = now - case.created_at
        wait_minutes = int(delta.total_seconds() // 60)
        pending_cards.append(_build_case_card(case, wait_minutes))

    immediate_notice_cards: list[dict[str, Any]] = []
    for case in immediate_notice_qs:
        delta = now - (case.doctor_decided_at or case.created_at)
        wait_minutes = int(delta.total_seconds() // 60)
        immediate_notice_cards.append(_build_case_card(case, wait_minutes))

    pending_count = len(pending_cards)
    immediate_notice_count = len(immediate_notice_cards)

    confirmed_cards: list[dict[str, Any]] = []
    for case in confirmed_qs:
        confirmed_cards.append(_build_case_card(case, 0))

    context: dict[str, Any] = {
        "pending_cases": pending_cards,
        "confirmed_today": confirmed_cards,
        "pending_count": pending_count,
        "immediate_notice_cases": immediate_notice_cards,
        "immediate_notice_count": immediate_notice_count,
        "total_notice_count": pending_count + immediate_notice_count,
    }

    return context


@login_required
def scheduler_queue(request: HttpRequest) -> HttpResponse:
    """View da fila de agendamento: casos WAIT_APPT e confirmados hoje."""
    return render(request, "scheduler/queue.html", _scheduler_queue_context())


@login_required
def scheduler_queue_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial for polling the scheduler queue without full refresh."""
    return render(request, "scheduler/_queue_content.html", _scheduler_queue_context())


# ── Immediate admission acknowledgement ────────────────────────────────────


@login_required
def immediate_ack(request: HttpRequest, case_id: str) -> HttpResponse:
    """POST: scheduler acknowledges immediate admission operational notice."""
    if request.method != "POST":
        raise Http404

    case = get_object_or_404(
        Case,
        pk=case_id,
        doctor_admission_flow="immediate",
        events__event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
    )

    already_acknowledged = case.events.filter(event_type="SCHEDULER_IMMEDIATE_ACK").exists()
    if not already_acknowledged:
        case._record_event("SCHEDULER_IMMEDIATE_ACK", user=request.user)
        case.save()

    return redirect("scheduler:queue")


# ── Confirm helpers ────────────────────────────────────────────────────────


def _build_confirm_context(case: Case, form: SchedulerDecisionForm) -> dict[str, Any]:
    """Build context dict for the confirm template."""
    return {
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
    }


# ── Confirm view ────────────────────────────────────────────────────────────


@login_required
def scheduler_confirm(request: HttpRequest, case_id: str) -> HttpResponse:
    """GET: Renderiza formulário de confirmação para um caso em WAIT_APPT."""
    case = get_object_or_404(Case.objects.select_related("doctor"), pk=case_id)

    if case.status != CaseStatus.WAIT_APPT:
        raise Http404("Caso não está aguardando agendamento.")

    form = SchedulerDecisionForm()
    return render(request, "scheduler/confirm.html", _build_confirm_context(case, form))


@login_required
def scheduler_submit(request: HttpRequest, case_id: str) -> HttpResponse:
    """POST: Valida formulário, persiste decisão e executa transições FSM."""
    if request.method != "POST":
        raise Http404

    case = get_object_or_404(Case.objects.select_related("doctor"), pk=case_id)

    if case.status != CaseStatus.WAIT_APPT:
        raise Http404("Caso não está aguardando agendamento.")

    form = SchedulerDecisionForm(request.POST)

    if not form.is_valid():
        return render(
            request,
            "scheduler/confirm.html",
            _build_confirm_context(case, form),
        )

    decision = form.cleaned_data["decision"]

    # Persist scheduler decision fields
    case.scheduler = request.user  # type: ignore[assignment]  # guaranteed by @login_required
    case.appointment_decided_at = timezone.now()

    if decision == "confirm":
        appt_date: date = form.cleaned_data["appointment_date"]
        appt_time: time = form.cleaned_data["appointment_time"]
        case.appointment_status = "confirmed"
        case.appointment_at = datetime.combine(appt_date, appt_time).replace(tzinfo=timezone.get_current_timezone())
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

    return redirect("scheduler:queue")
