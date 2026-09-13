"""Reconciliação de detecção procedure-neutral (design D2/D3 / ADR-0006).

Aplica a matriz declarado × detectado com gate de evidência forte para
upgrade automático. Histórico/negação nunca combinam (detecção por ocorrência
em ``scope_detection``); o payload de revisão NIR é enxuto (conjuntos + reason
code), sem texto clínico integral.

R3: a validação ocorre ANTES de ordenar/filtrar — tipos desconhecidos,
duplicatas ou conjuntos fora da matriz fechada falham fechado com motivo
explícito e nunca são descartados para fazer o restante parecer válido. A
precedência ``EDA com/e Ecoendoscopia/CPRE → especializado`` (D3) depende de
proveniência por ocorrência e é implementada no slice vertical de Ecoendoscopia;
até então qualquer conjunto contendo especializado segue para revisão NIR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.cases.models import EDA_COLONOSCOPY
from apps.cases.procedures import (
    ALLOWED_PROCEDURE_SETS,
    PAIRED_APPOINTMENT_SET,
    PROCEDURE_ORDER,
    is_paired_appointment_set,
)


@dataclass(frozen=True)
class ProcedurePartition:
    """Separação explícita entre valores conhecidos do catálogo e desconhecidos."""

    ordered: tuple[str, ...]
    unknown: tuple[str, ...]
    had_duplicates: bool


def _partition_procedures(procedure_types: Any) -> ProcedurePartition:
    """Particiona valores preservando ordem canônica sem descartar desconhecidos.

    Nunca filtra em silêncio (R3): valores fora do catálogo são devolvidos em
    ``unknown`` e duplicatas são sinalizadas em ``had_duplicates``.
    """
    seen: list[str] = []
    unknown: list[str] = []
    had_duplicates = False
    for raw in procedure_types or ():
        value = str(raw)
        if value not in PROCEDURE_ORDER:
            if value not in unknown:
                unknown.append(value)
            continue
        if value in seen:
            had_duplicates = True
            continue
        seen.append(value)
    seen.sort(key=lambda t: PROCEDURE_ORDER[t])
    return ProcedurePartition(ordered=tuple(seen), unknown=tuple(unknown), had_duplicates=had_duplicates)


def _ordered(procedure_types: Any) -> tuple[str, ...]:
    """Compatibilidade: ordem canônica dos valores conhecidos (sem validar)."""
    return _partition_procedures(procedure_types).ordered


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
    """Matriz D2/D3 completa (declarado × detectado) com gate de evidência forte.

    Args:
        declared: conjunto declarado pelo NIR (ordem canônica aplicada).
        strong: procedimentos com evidência forte de solicitação atual.
        any_evidence: procedimentos com qualquer evidência de solicitação atual.

    Returns:
        ``proceed`` (conjunto detectado = declarado), ``auto_upgrade``
        (declarado único EDA/Colon + ambos detectados com evidência forte do
        segundo) ou ``nir_review`` (tipo desconhecido, combinação não
        suportada, combined→single, mismatch único ou evidência insuficiente).
    """
    declared_partition = _partition_procedures(declared)
    strong_partition = _partition_procedures(strong)
    any_partition = _partition_procedures(any_evidence)

    # R3 — validação antes de qualquer ordenação/matriz: nenhum valor
    # desconhecido ou duplicata pode ser descartado em silêncio.
    if declared_partition.unknown or strong_partition.unknown or any_partition.unknown:
        return _nir_review(
            reason_code="unknown_exam_type",
            reason_text="Procedimento fora do catálogo suportado na solicitação; revisão manual obrigatória.",
            detected=any_partition.ordered,
        )

    if declared_partition.had_duplicates or any_partition.had_duplicates or strong_partition.had_duplicates:
        return _nir_review(
            reason_code="unsupported_procedure_combination",
            reason_text="Solicitação com procedimento duplicado; revisão manual obrigatória.",
            detected=any_partition.ordered,
        )

    declared_set = set(declared_partition.ordered)
    strong_set = set(strong_partition.ordered)
    any_set = set(any_partition.ordered)

    if declared_set and frozenset(declared_set) not in ALLOWED_PROCEDURE_SETS:
        return _nir_review(
            reason_code="unsupported_procedure_combination",
            reason_text="Conjunto declarado fora da matriz suportada; revisão manual obrigatória.",
            detected=_ordered(any_set),
        )

    if any_set and frozenset(any_set) not in ALLOWED_PROCEDURE_SETS:
        return _nir_review(
            reason_code="unsupported_procedure_combination",
            reason_text="Combinação de procedimentos não suportada; revisão manual obrigatória.",
            detected=_ordered(any_set),
        )

    if not any_set:
        return _nir_review(
            reason_code="unknown_exam_type",
            reason_text="Nenhum procedimento suportado detectado na solicitação atual; revisão manual obrigatória.",
            detected=(),
        )

    if any_set == declared_set:
        # EDA | Colon | Eco | CPRE | Ambos | Ambos → prossegue.
        return _proceed(_ordered(any_set))

    if declared_set == PAIRED_APPOINTMENT_SET and len(any_set) == 1:
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
        # Declarado único, ambos detectados → upgrade automático SOMENTE para o
        # par EDA+Colonoscopia com evidência forte do segundo procedimento.
        # Qualquer conjunto contendo especializado retorna ao NIR (D3: a
        # precedência ``EDA com/e Eco/CPRE`` exige proveniência por ocorrência
        # e é implementada no slice vertical de Ecoendoscopia).
        if any_set == PAIRED_APPOINTMENT_SET and (any_set - declared_set).issubset(strong_set):
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
    declared_label = (
        EDA_COLONOSCOPY if is_paired_appointment_set(declared_types) else (declared_types[0] if declared_types else "")
    )
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
