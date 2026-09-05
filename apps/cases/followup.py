"""Registro de desfecho de agendamento (follow-up do Supervisor).

Follow-up é registro puro (informativo/métrica): não altera a FSM do caso,
não abre intercorrência e não gera mensagem operacional. Cada gravação cria
uma nova versão append-only (``CaseFollowUp`` + ``ProcedureFollowUp`` por
procedimento) espelhada em ``CaseEvent`` (``FOLLOWUP_RECORDED`` quando
versão 1, ``FOLLOWUP_UPDATED`` nas seguintes).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.db import models, transaction

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseFollowUp,
    FollowUpNonPerformanceReason,
    ProcedureFollowUp,
)


@dataclass(frozen=True)
class ProcedureOutcomeInput:
    """Desfecho informado para um procedimento do caso."""

    procedure_id: int
    performed: bool
    non_performance_reason: str = ""
    resource_shortage_detail: str = ""
    other_reason: str = ""


def get_current_follow_up(case: Case) -> CaseFollowUp | None:
    """Versão corrente do follow-up do caso (maior ``version``) ou ``None``."""
    return case.follow_ups.order_by("-version").first()


def _validate_outcomes(case: Case, outcomes: Sequence[ProcedureOutcomeInput]) -> dict[int, Any]:
    """Valida cobertura, pertencimento e regras condicionais de causa.

    Retorna o mapa ``procedure_id -> CaseProcedure`` para reuso na gravação.
    """
    procedures_by_id = {procedure.id: procedure for procedure in case.procedures.all()}
    if not procedures_by_id:
        raise ValueError("Caso não possui procedimentos declarados para follow-up.")

    seen: set[int] = set()
    for outcome in outcomes:
        if outcome.procedure_id not in procedures_by_id:
            raise ValueError("Procedimento informado não pertence ao caso.")
        if outcome.procedure_id in seen:
            raise ValueError("Procedimento duplicado no follow-up.")
        seen.add(outcome.procedure_id)

    missing = set(procedures_by_id) - seen
    if missing:
        raise ValueError("O follow-up deve cobrir todos os procedimentos do caso.")

    for outcome in outcomes:
        if outcome.performed:
            continue
        reason = outcome.non_performance_reason
        if reason not in FollowUpNonPerformanceReason.values:
            raise ValueError("Informe a causa do procedimento não realizado.")
        if reason == FollowUpNonPerformanceReason.RESOURCE_SHORTAGE and not outcome.resource_shortage_detail:
            raise ValueError("Informe o submotivo da falta de recursos.")
        if reason == FollowUpNonPerformanceReason.OTHER and not outcome.other_reason.strip():
            raise ValueError("Descreva a outra causa da não realização.")

    return procedures_by_id


def record_case_follow_up(
    *,
    case: Case,
    performed_by: Any,
    patient_admitted: bool,
    procedure_outcomes: Sequence[ProcedureOutcomeInput],
) -> CaseFollowUp:
    """Grava uma nova versão do follow-up do caso com espelho em ``CaseEvent``.

    Raises:
        ValueError: cobertura incompleta, procedimento estranho/duplicado ou
            causa estruturada inválida/ausente. Nada é gravado nesse caso.
    """
    procedures_by_id = _validate_outcomes(case, procedure_outcomes)

    next_version = (case.follow_ups.aggregate(models.Max("version"))["version__max"] or 0) + 1

    with transaction.atomic():
        follow_up = CaseFollowUp.objects.create(
            case=case,
            version=next_version,
            patient_admitted=patient_admitted,
            recorded_by=performed_by,
        )

        payload_outcomes: list[dict[str, Any]] = []
        for outcome in procedure_outcomes:
            procedure = procedures_by_id[outcome.procedure_id]
            if outcome.performed:
                reason = detail = ""
                other_text = ""
            else:
                reason = outcome.non_performance_reason
                detail = outcome.resource_shortage_detail
                other_text = outcome.other_reason.strip()

            ProcedureFollowUp.objects.create(
                follow_up=follow_up,
                procedure=procedure,
                performed=outcome.performed,
                non_performance_reason=reason,
                resource_shortage_detail=detail,
                other_reason=other_text,
            )
            payload_outcomes.append(
                {
                    "procedure_id": procedure.id,
                    "procedure_type": procedure.procedure_type,
                    "performed": outcome.performed,
                    "non_performance_reason": reason,
                    "resource_shortage_detail": detail,
                    "other_reason": other_text,
                }
            )

        CaseEvent.objects.create(
            case=case,
            actor=performed_by,
            actor_type="human",
            event_type="FOLLOWUP_RECORDED" if next_version == 1 else "FOLLOWUP_UPDATED",
            payload={
                "version": next_version,
                "patient_admitted": patient_admitted,
                "outcomes": payload_outcomes,
            },
        )

    return follow_up
