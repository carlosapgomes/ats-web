"""Views for the doctor app."""

from datetime import date
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.cases.models import Case, CaseStatus

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


def _build_case_card(case: Case, wait_minutes: int) -> dict[str, Any]:
    """Build a dict with all display data for a case card."""
    return {
        "case_id": str(case.case_id),
        "patient_name": _get_patient_name(case),
        "patient_age": _get_patient_age(case),
        "patient_gender": _get_patient_gender(case),
        "agency_record_number": case.agency_record_number or "",
        "diagnosis": _get_diagnosis(case),
        "suggested_support": _get_suggested_support(case),
        "suggested_flow": _get_suggested_flow(case),
        "summary_text": case.summary_text or "",
        "doctor_decision": case.doctor_decision or "",
        "doctor_decision_display": _get_doctor_decision_display(case),
        "wait_minutes": wait_minutes,
        "is_urgent": wait_minutes <= 15,
    }


# ── View ──────────────────────────────────────────────────────────────────


@login_required
def doctor_queue(request: HttpRequest) -> HttpResponse:
    """View da fila médica: casos pendentes e decididos hoje."""

    pending_cases: QuerySet[Case] = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).order_by("created_at")

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
        pending_cards.append(_build_case_card(case, wait_minutes))

    total_wait = sum(c["wait_minutes"] for c in pending_cards)
    avg_wait = int(total_wait / len(pending_cards)) if pending_cards else 0

    decided_cards: list[dict[str, Any]] = []
    for case in decided_qs:
        decided_cards.append(_build_case_card(case, 0))

    context: dict[str, Any] = {
        "pending_cases": pending_cards,
        "decided_today": decided_cards,
        "pending_count": len(pending_cards),
        "avg_wait_minutes": avg_wait,
    }

    return render(request, "doctor/queue.html", context)
