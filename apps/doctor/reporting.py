"""Shared report preparation for the doctor presenter.

Centralizes the logic to prepare a ``DoctorReportPresenter`` from a ``Case``,
avoiding duplication between the doctor decision view and the dashboard audit view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.cases.models import Case
from apps.pipeline.prior_case import lookup_prior_case_context

from .presenters import DoctorReportPresenter

# Prior case decision mapping for display on UI cards
PRIOR_DECISION_DISPLAY: dict[str, str] = {
    "doctor_denied": "Regulação Negada",
    "appointment_denied": "Agendamento Negado",
}


def _map_prior_decision_to_denial_type(decision: str) -> str:
    """Map PriorCaseSummary.decision to denial type for the presenter."""
    if decision == "doctor_denied":
        return "deny_triage"
    if decision == "appointment_denied":
        return "deny_appointment"
    return "deny_triage"


@dataclass
class PreparedDoctorReport:
    """Prepared inputs and presenter for doctor report."""

    presenter: DoctorReportPresenter
    prior_context: Any = None
    prior_decision_display: str = ""


def prepare_doctor_case_report(case: Case) -> PreparedDoctorReport:
    """Prepare a ``DoctorReportPresenter`` and denial context from a ``Case``.

    Centralizes the logic that was duplicated between the doctor decision
    view and the dashboard. Returns a ``PreparedDoctorReport`` with:
    - The fully initialized ``DoctorReportPresenter``
    - ``prior_context``: ``PriorCaseContext`` (or ``None``)
    - ``prior_decision_display``: human-readable label for the prior decision
    """
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

    presenter = DoctorReportPresenter(
        structured_data=case.structured_data or {},
        summary_text=case.summary_text or "",
        suggested_action=case.suggested_action or {},
        recent_denial_context=recent_denial_ctx,
        source_text=case.extracted_text or "",
    )

    return PreparedDoctorReport(
        presenter=presenter,
        prior_context=prior_context,
        prior_decision_display=prior_decision_display,
    )
