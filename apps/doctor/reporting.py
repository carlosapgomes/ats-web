"""Shared report preparation for the doctor presenter.

Centralizes the logic to prepare a ``DoctorReportPresenter`` from a ``Case``,
avoiding duplication between the doctor decision view and the dashboard audit view.

Slice 003 (R6/D10): casos do contrato 2.0 consomem o lookup procedure-aware
(``lookup_prior_case_context(procedure_type=...)``) e produzem ``prior_sections``
separadas por procedimento — EDA e Colonoscopia têm decisão/razão próprias da
row (``CaseProcedure.doctor_disposition/doctor_reason``), nunca
``Case.doctor_decision`` isolado. Aprovação anterior permanece representável
(``doctor_approved``) e não incrementa ``prior_denial_count_7d``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.cases.models import Case, ProcedureType
from apps.pipeline.prior_case import lookup_prior_case_context

from .presenters import DoctorReportPresenter

# Prior case decision mapping for display on UI cards
PRIOR_DECISION_DISPLAY: dict[str, str] = {
    "doctor_denied": "Regulação Negada",
    "appointment_denied": "Agendamento Negado",
    "doctor_approved": "Aprovado anteriormente",
}

# Ordem canônica de exibição das seções de histórico por procedimento.
_PROCEDURE_ORDER: dict[str, int] = {
    ProcedureType.EDA: 0,
    ProcedureType.COLONOSCOPY: 1,
}


def _is_v2_structured(structured_data: Any) -> bool:
    """True quando o structured_data é contrato 2.0 procedure-neutral."""
    return isinstance(structured_data, dict) and structured_data.get("schema_version") == "2.0"


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
    prior_sections: list[dict[str, Any]] = field(default_factory=list)


def _build_prior_sections(case: Case) -> list[dict[str, Any]]:
    """Consulta o histórico anterior por componente (D10, modo 2.0).

    Para cada procedimento presente no caso (rows), usa
    ``lookup_prior_case_context(procedure_type=...)``; apenas candidatos
    dentro da janela de sete dias entram. O mesmo ``prior_case_id`` pode
    aparecer em ambas as seções com decisão/razão próprias por row.
    """
    if not case.agency_record_number:
        return []

    procedure_types = sorted(
        {row.procedure_type for row in case.procedures.all()},
        key=lambda t: _PROCEDURE_ORDER[t],
    )
    sections: list[dict[str, Any]] = []
    for procedure_type in procedure_types:
        context = lookup_prior_case_context(
            case_id=case.case_id,
            agency_record_number=case.agency_record_number,
            procedure_type=procedure_type,
        )
        if context.prior_case is None:
            continue
        decision = context.prior_case.decision
        sections.append(
            {
                "procedure_type": procedure_type,
                "procedure_label": ProcedureType(procedure_type).label,
                "decision": decision,
                "decision_display": PRIOR_DECISION_DISPLAY.get(decision, decision),
                "reason": context.prior_case.reason,
                "decided_at": context.prior_case.decided_at,
                "decided_by": context.prior_case.decided_by,
                "decided_by_role": context.prior_case.decided_by_role,
                "prior_case_id": context.prior_case.prior_case_id,
                "prior_denial_count_7d": context.prior_denial_count_7d,
            }
        )
    return sections


def prepare_doctor_case_report(case: Case) -> PreparedDoctorReport:
    """Prepare a ``DoctorReportPresenter`` and denial context from a ``Case``.

    Centralizes the logic that was duplicated between the doctor decision
    view and the dashboard. Returns a ``PreparedDoctorReport`` with:
    - The fully initialized ``DoctorReportPresenter``
    - ``prior_context``: ``PriorCaseContext`` (or ``None``) — modo legado 1.1
    - ``prior_decision_display``: human-readable label for the prior decision
    - ``prior_sections``: seções por procedimento (modo 2.0, R6/D10)
    """
    prior_context = None
    prior_decision_display = ""
    recent_denial_ctx = None
    prior_sections: list[dict[str, Any]] = []

    if _is_v2_structured(case.structured_data):
        prior_sections = _build_prior_sections(case)
    elif case.agency_record_number:
        pc = lookup_prior_case_context(
            case_id=case.case_id,
            agency_record_number=case.agency_record_number,
            exam_type=case.exam_type,
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
        priority_signals=case.priority_signals or [],
        exam_type=case.exam_type,
        prior_sections=prior_sections,
    )

    return PreparedDoctorReport(
        presenter=presenter,
        prior_context=prior_context,
        prior_decision_display=prior_decision_display,
        prior_sections=prior_sections,
    )
