"""Prior case lookup — busca casos anteriores do mesmo paciente para contexto.

Porta a lógica do legado ``build_prior_case_context()``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.db.models import Q

from apps.cases.models import Case

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

    A identificação de negação usa campos semânticos de decisão
    (``doctor_decision``/``doctor_decided_at`` e
    ``appointment_status``/``appointment_decided_at``), não
    ``Case.status`` que é transitório.

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

    # Busca candidatos com mesmo agency_record_number, excluindo o atual.
    # Usa campos semânticos de decisão (não Case.status) e janela por
    # decided_at (não created_at). A sobreposição das Q é intencional:
    # o banco pode incluir candidatos com decided_at no passado, e o
    # filtro determinístico em Python resolve ambiguidades.
    prior_case_qs: list[Case] = list(
        Case.objects.filter(
            agency_record_number=agency_record_number,
        )
        .exclude(case_id=current_case_id)
        .filter(
            Q(doctor_decision="deny", doctor_decided_at__gte=window_start)
            | Q(appointment_status="denied", appointment_decided_at__gte=window_start),
        )
        .select_related("doctor", "scheduler")
    )

    # Filtra candidatos: verifica deterministicamente cada um
    candidates = _build_denial_candidates(prior_case_qs, window_start, now)

    if not candidates:
        return PriorCaseContext()

    # Ordena por decided_at descendente e pega o mais recente
    candidates.sort(key=lambda x: x[0], reverse=True)
    most_recent_decided_at, most_recent_case, denial_type = candidates[0]

    summary = _build_summary(most_recent_case, denial_type)

    return PriorCaseContext(
        prior_case=summary,
        prior_denial_count_7d=len(candidates),
    )


def _is_doctor_denial(case: Case, window_start: datetime, now: datetime) -> bool:
    """Retorna True se o caso é uma negação médica válida dentro da janela."""
    return (
        case.doctor_decision == "deny"
        and case.doctor_decided_at is not None
        and window_start <= case.doctor_decided_at <= now
    )


def _is_appointment_denial(case: Case, window_start: datetime, now: datetime) -> bool:
    """Retorna True se o caso é uma negação de agendamento válida dentro da janela."""
    return (
        case.appointment_status == "denied"
        and case.appointment_decided_at is not None
        and window_start <= case.appointment_decided_at <= now
    )


def _build_denial_candidates(
    cases: list[Case],
    window_start: datetime,
    now: datetime,
) -> list[tuple[datetime, Case, str]]:
    """Constrói lista de (decided_at, case, denial_type) para candidatos válidos.

    Para casos com ambas as negativas preenchidas, a negação de agendamento
    tem precedência (comportamento determinístico definido no requisito R7).
    """
    candidates: list[tuple[datetime, Case, str]] = []
    for case in cases:
        # R7: appointment tem precedência sobre doctor
        if _is_appointment_denial(case, window_start, now):
            candidates.append((case.appointment_decided_at, case, "appointment"))  # type: ignore[arg-type]
        elif _is_doctor_denial(case, window_start, now):
            candidates.append((case.doctor_decided_at, case, "doctor"))  # type: ignore[arg-type]
    return candidates


def _build_summary(case: Case, denial_type: str) -> PriorCaseSummary:
    """Converte um Case + tipo de negação em PriorCaseSummary."""
    if denial_type == "doctor":
        decision = "doctor_denied"
        decided_at = case.doctor_decided_at
        reason = _normalize_reason(case.doctor_reason)
        decided_by = case.doctor_display
        decided_by_role = "doctor"
    elif denial_type == "appointment":
        decision = "appointment_denied"
        decided_at = case.appointment_decided_at
        reason = _normalize_reason(case.appointment_reason)
        decided_by = case.scheduler_display
        decided_by_role = "scheduler"
    else:
        # Fallback — não deve acontecer
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
