"""Prior case lookup — busca casos anteriores do mesmo paciente para contexto.

Porta a lógica do legado ``build_prior_case_context()``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.db.models import Q

from apps.cases.models import Case, CaseStatus

# Janela de busca: 7 dias corridos para trás
PRIOR_CASE_WINDOW_DAYS = 7


@dataclass
class PriorCaseSummary:
    """Resumo de um caso anterior com decisão de negação."""

    prior_case_id: str
    decided_at: str  # formato ISO
    decision: str  # "doctor_denied" | "appointment_denied"
    reason: str  # normalizado: "não informado" se vazio/None
    decided_by: str = ""  # nome + registro profissional de quem decidiu
    decided_by_role: str = ""  # "doctor" | "scheduler"


@dataclass
class PriorCaseContext:
    """Contexto de casos anteriores para enriquecer o prompt do LLM2."""

    prior_case: PriorCaseSummary | None = None
    prior_denial_count_7d: int = 0


def lookup_prior_case_context(
    case_id: uuid.UUID | str,
    agency_record_number: str,
    now: datetime | None = None,
) -> PriorCaseContext:
    """Busca casos anteriores do mesmo paciente (mesmo ``agency_record_number``).

    Retorna o caso de negação mais recente (últimos 7 dias) e a contagem
    total de negações no período.

    Args:
        case_id: UUID do caso atual (excluído da busca).
        agency_record_number: Número de protocolo da agência (chave de
            agrupamento do paciente).
        now: Referência temporal (útil em testes). Default: UTC now.

    Returns:
        PriorCaseContext com o caso anterior mais relevante (ou None) e
        a contagem de negações nos últimos 7 dias.
    """
    if not agency_record_number.strip():
        return PriorCaseContext()

    now = now or datetime.now(tz=UTC)
    window_start = now - timedelta(days=PRIOR_CASE_WINDOW_DAYS)

    # Normaliza case_id para string UUID para comparação
    current_case_id = str(case_id)

    # Busca casos com mesmo agency_record_number, excluindo o atual,
    # com status de negação, dentro da janela de 7 dias
    prior_cases: list[Case] = list(
        Case.objects.filter(
            agency_record_number=agency_record_number,
        )
        .exclude(case_id=current_case_id)
        .filter(
            Q(status=CaseStatus.DOCTOR_DENIED) | Q(status=CaseStatus.APPT_DENIED),
            created_at__gte=window_start,
        )
        .select_related("doctor", "scheduler")
        .order_by("-created_at")
    )

    if not prior_cases:
        return PriorCaseContext()

    # Constrói resumo para o caso mais recente
    most_recent = prior_cases[0]
    summary = _build_summary(most_recent)

    return PriorCaseContext(
        prior_case=summary,
        prior_denial_count_7d=len(prior_cases),
    )


def _build_summary(case: Case) -> PriorCaseSummary:
    """Converte um Case em PriorCaseSummary, normalizando o reason."""
    if case.status == CaseStatus.DOCTOR_DENIED:
        decision = "doctor_denied"
        decided_at = case.doctor_decided_at
        reason = _normalize_reason(case.doctor_reason)
        decided_by = case.doctor_display
        decided_by_role = "doctor"
    elif case.status == CaseStatus.APPT_DENIED:
        decision = "appointment_denied"
        decided_at = case.appointment_decided_at
        reason = _normalize_reason(case.appointment_reason)
        decided_by = case.scheduler_display
        decided_by_role = "scheduler"
    else:
        # Fallback — não deve acontecer dado o filtro acima
        decision = "unknown"
        decided_at = case.created_at
        reason = _normalize_reason(None)
        decided_by = ""
        decided_by_role = ""

    decided_at_str = decided_at.isoformat() if decided_at else ""

    return PriorCaseSummary(
        prior_case_id=str(case.case_id),
        decided_at=decided_at_str,
        decision=decision,
        reason=reason,
        decided_by=decided_by,
        decided_by_role=decided_by_role,
    )


def _normalize_reason(reason: str | None) -> str:
    """Normaliza reason: strings vazias/None viram 'não informado'."""
    if not reason or not reason.strip():
        return "não informado"
    return reason.strip()
