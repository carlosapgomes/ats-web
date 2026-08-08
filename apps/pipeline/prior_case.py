"""Prior case lookup — busca casos anteriores do mesmo paciente para contexto.

Porta a lógica do legado ``build_prior_case_context()``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from apps.cases.models import Case, CaseProcedure

# Janela de busca: 7 dias corridos para trás
PRIOR_CASE_WINDOW_DAYS = 7


@dataclass
class PriorCaseSummary:
    """Resumo de um caso anterior com decisão do componente solicitado."""

    prior_case_id: str
    decided_at: str  # formato ISO
    decision: str  # "doctor_denied" | "appointment_denied" | "doctor_approved"
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
    *,
    procedure_type: str,
    now: datetime | None = None,
) -> PriorCaseContext:
    """Busca casos anteriores do mesmo paciente por componente (D10/ADR-0004).

    Slice 009 (R3): ``procedure_type`` é keyword-only obrigatório. O caminho
    legado ``exam_type``/``filter(exam_type=...)`` foi removido — casos
    históricos já foram backfillados para ``CaseProcedure`` no Slice 001, e os
    artefatos 1.1 derivam o ``procedure_type`` no caller (``reporting``).

    Seleciona candidatos pela row ``CaseProcedure`` correspondente e decide por
    componente na ordem fechada D10:

    1. row ``doctor_disposition=denied`` → ``doctor_denied`` (razão da row);
    2. row ``approved`` + ``Case.appointment_status=denied`` →
       ``appointment_denied`` (razão/instante do agendamento global);
    3. row ``approved`` → ``doctor_approved``;
    4. row ``pending`` ou timestamps fora da janela → fora do contexto.

    ``prior_denial_count_7d`` conta somente negativas do procedimento
    (médica ou de agenda); ``doctor_approved`` nunca aumenta o contador. A
    identificação usa campos semânticos de decisão, não ``Case.status``
    (transitório). A negativa global de agendamento aplica-se apenas a rows
    aprovadas — nunca a componente medicamente negado (D10).

    Args:
        case_id: UUID do caso atual (excluído da busca).
        agency_record_number: Número de protocolo da agência (chave de
            agrupamento do paciente).
        procedure_type: componente solicitado (``eda`` | ``colonoscopy``) —
            consulta por row ``CaseProcedure`` correspondente.
        now: Referência temporal (útil em testes). Default: UTC now.

    Returns:
        PriorCaseContext com o caso anterior mais relevante (ou None) e a
        contagem de negações nos últimos 7 dias do componente solicitado.
    """
    if not agency_record_number.strip():
        return PriorCaseContext()

    return _lookup_prior_procedure_context(
        case_id=case_id,
        agency_record_number=agency_record_number,
        procedure_type=procedure_type,
        now=now,
    )


def _lookup_prior_procedure_context(
    *,
    case_id: uuid.UUID | str,
    agency_record_number: str,
    procedure_type: str,
    now: datetime | None,
) -> PriorCaseContext:
    """Modo D10 (contrato 2.0): consulta por componente ``CaseProcedure``.

    Para cada candidato, a decisão contextual é determinada na ordem fechada:
    1. row ``doctor_disposition=denied`` → ``doctor_denied`` (razão da row);
    2. row ``approved`` + ``Case.appointment_status=denied`` → ``appointment_denied``;
    3. row ``approved`` → ``doctor_approved``;
    4. row pending ou fora da janela → fora do contexto.

    ``prior_denial_count_7d`` conta somente negativas (médica ou de agenda) do
    procedimento solicitado; ``doctor_approved`` nunca aumenta o contador.
    """
    now = now or datetime.now(tz=UTC)
    window_start = now - timedelta(days=PRIOR_CASE_WINDOW_DAYS)
    current_case_id = str(case_id)

    candidate_cases: list[Case] = list(
        Case.objects.filter(
            agency_record_number=agency_record_number,
            procedures__procedure_type=procedure_type,
            procedures__doctor_disposition__in=("denied", "approved"),
        )
        .exclude(case_id=current_case_id)
        .prefetch_related("procedures")
        .select_related("doctor", "scheduler")
    )

    entries: list[tuple[datetime, Case, str, str]] = []  # (decided_at, case, kind, reason)
    for case in candidate_cases:
        row = _procedure_row_for(case, procedure_type)
        if row is None:
            continue
        if row.doctor_disposition == "denied":
            if case.doctor_decided_at is not None and window_start <= case.doctor_decided_at <= now:
                entries.append((case.doctor_decided_at, case, "doctor", row.doctor_reason))
            continue
        if row.doctor_disposition == "approved":
            if (
                case.appointment_status == "denied"
                and case.appointment_decided_at is not None
                and window_start <= case.appointment_decided_at <= now
            ):
                entries.append((case.appointment_decided_at, case, "appointment", case.appointment_reason))
            elif case.doctor_decided_at is not None and window_start <= case.doctor_decided_at <= now:
                entries.append((case.doctor_decided_at, case, "approved", ""))

    if not entries:
        return PriorCaseContext()

    entries.sort(key=lambda entry: entry[0], reverse=True)
    most_recent = entries[0]
    summary = _build_procedure_summary(case=most_recent[1], kind=most_recent[2], reason=most_recent[3])
    denial_count = sum(1 for entry in entries if entry[2] in ("doctor", "appointment"))
    return PriorCaseContext(
        prior_case=summary,
        prior_denial_count_7d=denial_count,
    )


def _procedure_row_for(case: Case, procedure_type: str) -> CaseProcedure | None:
    """Retorna a row ``CaseProcedure`` do componente (prefetch-aware)."""
    for row in case.procedures.all():
        if row.procedure_type == procedure_type:
            return row
    return None


def _build_procedure_summary(*, case: Case, kind: str, reason: str | None) -> PriorCaseSummary:
    """Converte Case + tipo de decisão por componente em PriorCaseSummary (D10)."""
    if kind == "doctor":
        decision = "doctor_denied"
        decided_at = case.doctor_decided_at
        normalized_reason = _normalize_reason(reason)
        decided_by = case.doctor_display
        decided_by_role = "doctor"
    elif kind == "appointment":
        decision = "appointment_denied"
        decided_at = case.appointment_decided_at
        normalized_reason = _normalize_reason(reason)
        decided_by = case.scheduler_display
        decided_by_role = "scheduler"
    else:
        decision = "doctor_approved"
        decided_at = case.doctor_decided_at
        normalized_reason = ""
        decided_by = case.doctor_display
        decided_by_role = "doctor"

    decided_at_str = decided_at.isoformat() if decided_at else ""
    return PriorCaseSummary(
        prior_case_id=str(case.case_id),
        decided_at=decided_at_str,
        decision=decision,
        reason=normalized_reason,
        decided_by=decided_by,
        decided_by_role=decided_by_role,
    )


def _normalize_reason(reason: str | None) -> str:
    """Normaliza reason: strings vazias/None viram 'não informado'."""
    if not reason or not reason.strip():
        return "não informado"
    return reason.strip()
