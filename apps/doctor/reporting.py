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


# Tipos de procedimento aceitos na derivação 1.1 (R2).
_LEGACY_PROCEDURE_TYPES: tuple[str, ...] = ("eda", "colonoscopy")


def _derive_legacy_procedure_type(case: Case) -> str:
    """Deriva o ``procedure_type`` de um caso 1.1 SEM ler a ponte ``Case.exam_type``.

    Slice 009 (R2): o relatório histórico 1.1 deriva o tipo do payload
    validado (``preop_screening.exam_type``) e, se ausente, de uma única row
    ``declared_by_nir`` inequívoca. Ambíguo/ausente → ``""`` (fail-closed:
    sem lookup anterior e label neutro no presenter, nunca default EDA).
    """
    structured = case.structured_data
    if isinstance(structured, dict):
        preop = structured.get("preop_screening")
        if isinstance(preop, dict):
            raw = preop.get("exam_type")
            if raw in _LEGACY_PROCEDURE_TYPES:
                return str(raw)
    declared = [
        row.procedure_type
        for row in case.procedures.all()
        if row.declared_by_nir and row.procedure_type in _LEGACY_PROCEDURE_TYPES
    ]
    if len(declared) == 1:
        return declared[0]
    return ""


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

    Slice 009 (R2): nenhum caminho passa a coluna ``Case.exam_type`` ao
    presenter/lookup. Contrato 2.0 produz ``prior_sections`` por componente;
    contrato 1.1 deriva ``procedure_type`` do payload histórico (ou row
    inequívoca) e, se derivável, consulta o histórico por componente. Tipo
    ambíguo/ausente é fail-closed (sem lookup, presenter neutro).
    """
    prior_context = None
    prior_decision_display = ""
    recent_denial_ctx = None
    prior_sections: list[dict[str, Any]] = []
    presenter_exam_type = ""  # fail-closed default; v2 ignora este campo

    if _is_v2_structured(case.structured_data):
        prior_sections = _build_prior_sections(case)
    else:
        derived_type = _derive_legacy_procedure_type(case)
        presenter_exam_type = derived_type
        if case.agency_record_number and derived_type:
            pc = lookup_prior_case_context(
                case_id=case.case_id,
                agency_record_number=case.agency_record_number,
                procedure_type=derived_type,
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
        exam_type=presenter_exam_type,
        prior_sections=prior_sections,
    )

    return PreparedDoctorReport(
        presenter=presenter,
        prior_context=prior_context,
        prior_decision_display=prior_decision_display,
        prior_sections=prior_sections,
    )
