"""Reconciliação de detecção procedure-neutral v2 (design D7 / ADR-0004).

Aplica a matriz declarado × detectado com gate de evidência forte para
upgrade automático. Histórico/negação nunca combinam (detecção por ocorrência
em ``scope_detection``); o payload de revisão NIR é enxuto (conjuntos + reason
code), sem texto clínico integral.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.cases.models import EDA_COLONOSCOPY, ProcedureType

_PROCEDURE_ORDER: dict[str, int] = {
    ProcedureType.EDA: 0,
    ProcedureType.COLONOSCOPY: 1,
}


def _ordered(procedure_types: Any) -> tuple[str, ...]:
    seen: list[str] = []
    for raw in procedure_types or ():
        value = str(raw)
        if value in _PROCEDURE_ORDER and value not in seen:
            seen.append(value)
    seen.sort(key=lambda t: _PROCEDURE_ORDER[t])
    return tuple(seen)


@dataclass(frozen=True)
class ProcedureReconciliationResult:
    """Desfecho da matriz D7 para um caso."""

    action: str  # "proceed" | "auto_upgrade" | "nir_review"
    detected_procedure_types: tuple[str, ...]
    reason_code: str
    reason_text: str
    upgraded: bool = False


def _proceed(detected: tuple[str, ...]) -> ProcedureReconciliationResult:
    return ProcedureReconciliationResult(
        action="proceed",
        detected_procedure_types=detected,
        reason_code="",
        reason_text="",
    )


def _auto_upgrade(detected: tuple[str, ...]) -> ProcedureReconciliationResult:
    return ProcedureReconciliationResult(
        action="auto_upgrade",
        detected_procedure_types=detected,
        reason_code="auto_upgrade_strong_evidence",
        reason_text=("Solicitações atuais de EDA e Colonoscopia com evidência forte; upgrade automático auditado."),
        upgraded=True,
    )


def _nir_review(*, reason_code: str, reason_text: str, detected: tuple[str, ...]) -> ProcedureReconciliationResult:
    return ProcedureReconciliationResult(
        action="nir_review",
        detected_procedure_types=detected,
        reason_code=reason_code,
        reason_text=reason_text,
    )


def reconcile_detected_procedures(
    *,
    declared: Any,
    strong: Any,
    any_evidence: Any,
) -> ProcedureReconciliationResult:
    """Matriz D7 completa (declarado × detectado) com gate de evidência forte.

    Args:
        declared: conjunto declarado pelo NIR (ordem canônica aplicada).
        strong: procedimentos com evidência forte de solicitação atual.
        any_evidence: procedimentos com qualquer evidência de solicitação atual.

    Returns:
        ``proceed`` (conjunto detectado = declarado), ``auto_upgrade``
        (declarado único + ambos detectados com evidência forte do segundo)
        ou ``nir_review`` (combined→single, mismatch único, unknown/non-supported
        ou evidência insuficiente para upgrade).
    """
    declared_set = set(_ordered(declared))
    strong_set = set(_ordered(strong))
    any_set = set(_ordered(any_evidence))

    if not any_set:
        return _nir_review(
            reason_code="unknown_exam_type",
            reason_text="Nenhum procedimento suportado detectado na solicitação atual; revisão manual obrigatória.",
            detected=(),
        )

    if any_set == declared_set:
        # EDA | EDA, Colon | Colon, Ambos | Ambos → prossegue.
        return _proceed(_ordered(any_set))

    if len(declared_set) == 2 and len(any_set) == 1:
        # Combinado declarado, somente um detectado → revisão NIR.
        return _nir_review(
            reason_code="exam_type_mismatch",
            reason_text=(
                "Declarado EDA + Colonoscopia, mas apenas um procedimento foi "
                "detectado na solicitação atual; revisão manual obrigatória."
            ),
            detected=_ordered(any_set),
        )

    if len(declared_set) == 1 and len(any_set) == 2:
        # Declarado único, ambos detectados → upgrade exige evidência forte do
        # segundo procedimento; sem ela, revisão NIR (D7).
        extra = any_set - declared_set
        if extra.issubset(strong_set):
            return _auto_upgrade(_ordered(any_set))
        return _nir_review(
            reason_code="mixed_exam_request",
            reason_text=(
                "Solicitação atual contém dois procedimentos, mas o segundo não "
                "possui evidência forte; revisão manual obrigatória."
            ),
            detected=_ordered(any_set),
        )

    if len(declared_set) == 1 and len(any_set) == 1 and any_set != declared_set:
        # Contradição entre tipos únicos → revisão NIR (sem swap silencioso).
        return _nir_review(
            reason_code="exam_type_mismatch",
            reason_text=(
                "Tipo de procedimento declarado difere do detectado na solicitação atual; revisão manual obrigatória."
            ),
            detected=_ordered(any_set),
        )

    # Fallback conservador: qualquer outra divergência retorna ao NIR.
    return _nir_review(
        reason_code="exam_type_mismatch",
        reason_text="Conjunto detectado diverge do declarado; revisão manual obrigatória.",
        detected=_ordered(any_set),
    )


def _project_review_evidence_spans(evidence_spans: list[dict[str, str]]) -> list[dict[str, str]]:
    """Projeta spans com limites explícitos para o payload de revisão (F4/R8)."""
    projected: list[dict[str, str]] = []
    for span in evidence_spans[:5]:
        projected.append(
            {
                "field_path": span["field_path"][:120],
                "excerpt": span["excerpt"][:200],
            }
        )
    return projected


def build_v2_review_payload(
    *,
    case_id: str,
    agency_record_number: str,
    reason_code: str,
    reason_text: str,
    declared: tuple[str, ...],
    detected: tuple[str, ...],
    evidence_spans: list[dict[str, str]],
) -> dict[str, object]:
    """Payload enxuto de revisão NIR para contrato 2.0 (conjuntos + reason).

    Mantém campos legados (``declared_exam_type``/``detected_exam_type``)
    apenas para compatibilidade de exibição; a informação canônica são os
    conjuntos ``declared_procedures``/``detected_procedures``.
    """
    declared_types = _ordered(declared)
    detected_types = _ordered(detected)
    detected_label = "mixed" if len(detected_types) == 2 else (detected_types[0] if detected_types else "unknown")
    declared_label = EDA_COLONOSCOPY if len(declared_types) == 2 else (declared_types[0] if declared_types else "")
    return {
        "schema_version": "2.0",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "decision": "manual_review_required",
        "suggestion": "manual_review_required",
        "reason_code": reason_code,
        "reason_text": reason_text,
        "declared_procedures": list(declared_types),
        "detected_procedures": list(detected_types),
        "exam_type": detected_label,
        "declared_exam_type": declared_label,
        "detected_exam_type": detected_label,
        "evidence_spans": _project_review_evidence_spans(evidence_spans),
    }
