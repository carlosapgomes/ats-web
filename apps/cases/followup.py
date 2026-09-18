"""Registro de desfecho de agendamento (follow-up do Supervisor).

Follow-up é registro puro (informativo/métrica): não altera a FSM do caso,
não abre intercorrência e não gera mensagem operacional. Cada gravação cria
uma nova versão append-only (``CaseFollowUp`` + ``ProcedureFollowUp`` por
procedimento autorizado) espelhada em ``CaseEvent`` (``FOLLOWUP_RECORDED``
quando versão 1, ``FOLLOWUP_UPDATED`` nas seguintes). A cobertura é restrita
às rows ``doctor_disposition == "approved"`` (ADR-0007). A leitura analítica
(Histórico) projeta as causas legadas para a taxonomia oficial por
``project_non_performance_reason``, sem tocar rows nem eventos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.db import models, transaction
from django.db.models import OuterRef, Subquery

from apps.cases.admission import is_operational_notice_flow
from apps.cases.models import (
    CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES,
    Case,
    CaseEvent,
    CaseFollowUp,
    DoctorDisposition,
    FollowUpNonPerformanceReason,
    FollowUpResourceShortageDetail,
    ProcedureFollowUp,
)


@dataclass(frozen=True)
class ProcedureOutcomeInput:
    """Desfecho informado para um procedimento do caso.

    ``resource_shortage_detail`` sobrevive apenas como entrada legada: o
    service rejeita qualquer submotivo em novas gravações.
    """

    procedure_id: int
    performed: bool
    non_performance_reason: str = ""
    resource_shortage_detail: str = ""
    other_reason: str = ""


# Categoria técnica de leitura (design D5): agrupa causa/detalhe persistido
# fora dos quatro mapeamentos confirmados. Não é causa de negócio — nunca
# integra choices de model/form nem as opções do filtro oficial.
LEGACY_UNMAPPED_REASON = "legacy_unmapped"
LEGACY_UNMAPPED_REASON_LABEL = "Causa legada não mapeada"

# Mapeamento aprovado (design D5): par persistido → causa oficial equivalente.
_LEGACY_REASON_PROJECTIONS: dict[tuple[str, str], str] = {
    (FollowUpNonPerformanceReason.ABSENTEEISM.value, ""): FollowUpNonPerformanceReason.PATIENT_NO_SHOW.value,
    (
        FollowUpNonPerformanceReason.RESOURCE_SHORTAGE.value,
        FollowUpResourceShortageDetail.EMERGENCY_OCCUPIED.value,
    ): FollowUpNonPerformanceReason.EMERGENCY_PRIORITY.value,
    (
        FollowUpNonPerformanceReason.RESOURCE_SHORTAGE.value,
        FollowUpResourceShortageDetail.INSUFFICIENT_TIME.value,
    ): FollowUpNonPerformanceReason.TIME_EXCEEDED.value,
    (
        FollowUpNonPerformanceReason.RESOURCE_SHORTAGE.value,
        FollowUpResourceShortageDetail.EQUIPMENT_UNAVAILABLE.value,
    ): FollowUpNonPerformanceReason.MISSING_EQUIPMENT.value,
}


def project_non_performance_reason(*, non_performance_reason: str, resource_shortage_detail: str = "") -> str:
    """Código oficial de leitura do desfecho não realizado (design D5).

    Projeção canônica única consumida por tabela, cards, filtro e CSV do
    Histórico: lê os dois campos persistidos e devolve a causa oficial
    equivalente. Causa do catálogo atual passa sem mudança somente com detalhe
    vazio (design D5) e os quatro mapeamentos legados confirmados são
    convertidos; qualquer outro estado persistido — inclusive causa atual com
    detalhe não vazio ou causa vazia — devolve ``legacy_unmapped``.

    Função pura: não grava nem consulta nada — rows e ``CaseEvent`` históricos
    permanecem intactos por construção.
    """
    if resource_shortage_detail == "" and non_performance_reason in CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES:
        return non_performance_reason
    return _LEGACY_REASON_PROJECTIONS.get(
        (non_performance_reason, resource_shortage_detail),
        LEGACY_UNMAPPED_REASON,
    )


def is_unmapped_legacy_follow_up(*, non_performance_reason: str, resource_shortage_detail: str = "") -> bool:
    """Causa/detalhe persistido fora dos mapeamentos da projeção (preflight R7).

    Decide o fail-closed do preflight delegando a
    ``project_non_performance_reason``: o preflight aceita exatamente as
    combinações que a projeção lê como causa oficial, sem um conjunto paralelo
    que possa divergir (ex.: ``absenteeism`` com detalhe técnico não vazio cai
    fora do par mapeado e é sinalizado). Puro: não grava nem consulta nada.
    """
    return (
        project_non_performance_reason(
            non_performance_reason=non_performance_reason,
            resource_shortage_detail=resource_shortage_detail,
        )
        == LEGACY_UNMAPPED_REASON
    )


def unmapped_legacy_follow_up_ids() -> list[int]:
    """IDs de desfechos ``performed=False`` sem equivalente na projeção (R7).

    Fonte única do preflight fail-closed de rollout: percorre as rows
    persistidas aplicando ``is_unmapped_legacy_follow_up``, de modo que o
    preflight nunca divirja da leitura do Histórico. Lista vazia libera o
    rollout; qualquer id bloqueia até análise humana. Read-only: não altera
    rows nem ``CaseEvent``.
    """
    return [
        follow_up_id
        for follow_up_id, reason, detail in ProcedureFollowUp.objects.filter(performed=False).values_list(
            "pk", "non_performance_reason", "resource_shortage_detail"
        )
        if is_unmapped_legacy_follow_up(non_performance_reason=reason, resource_shortage_detail=detail)
    ]


def get_current_follow_up(case: Case) -> CaseFollowUp | None:
    """Versão corrente do follow-up do caso (maior ``version``) ou ``None``."""
    return case.follow_ups.order_by("-version").first()


def current_follow_ups() -> models.QuerySet[CaseFollowUp]:
    """Versões correntes de follow-up: 1 row por caso com follow-up (maior ``version``).

    Traz ``select_related("case", "recorded_by")`` e
    ``prefetch_related("procedure_outcomes__procedure")`` para leitura sem
    N+1 na página de histórico e nos agregados do período (design D2).
    """
    latest_by_case = CaseFollowUp.objects.filter(case=OuterRef("case")).order_by("-version").values("pk")[:1]
    return (
        CaseFollowUp.objects.filter(pk=Subquery(latest_by_case))
        .select_related("case", "recorded_by")
        .prefetch_related("procedure_outcomes__procedure")
    )


def is_followup_eligible(case: Case) -> bool:
    """Predicado combinado de elegibilidade para follow-up (design D4).

    Grupo agendado: ``appointment_status="confirmed"`` com ``appointment_at``
    presente. Grupo vinda imediata (fluxo operacional): ``doctor_admission_flow``
    em ``OPERATIONAL_NOTICE_FLOWS`` com ``doctor_decided_at`` presente. Sem
    fallback para ``created_at``: caso operacional sem timestamp de decisão
    permanece conservadoramente fora do follow-up.

    Independe da data — a listagem combina o predicado com o dia local dos
    timestamps relevantes; o formulário (Slice 003) o revalida por caso.
    """
    if case.appointment_status == "confirmed" and case.appointment_at is not None:
        return True
    return is_operational_notice_flow(case.doctor_admission_flow) and case.doctor_decided_at is not None


def _validate_outcomes(case: Case, outcomes: Sequence[ProcedureOutcomeInput]) -> dict[int, Any]:
    """Valida cobertura, pertencimento e regras condicionais de causa.

    O universo do follow-up é o subconjunto autorizado
    (``doctor_disposition == "approved"``, ADR-0007): rows negadas/pendentes
    ficam isentas de desfecho e um desfecho informado para elas é rejeitado
    (fail-closed). Sem rows autorizadas (estado defensivo) a gravação é
    rejeitada. Retorna o mapa ``procedure_id -> CaseProcedure`` autorizado
    para reuso na gravação.

    A causa é obrigatória e restrita ao catálogo oficial atual (design D2):
    os códigos legados são reconhecidos pelo storage, mas rejeitados em novas
    versões, assim como qualquer submotivo de falta de recursos.
    """
    procedures_by_id = {procedure.id: procedure for procedure in case.procedures.all()}
    approved_by_id = {
        procedure_id: procedure
        for procedure_id, procedure in procedures_by_id.items()
        if procedure.doctor_disposition == DoctorDisposition.APPROVED
    }
    if not approved_by_id:
        raise ValueError("Caso não possui procedimentos autorizados para pós-procedimento.")

    seen: set[int] = set()
    for outcome in outcomes:
        if outcome.procedure_id not in approved_by_id:
            if outcome.procedure_id in procedures_by_id:
                raise ValueError("Procedimento informado não está autorizado para pós-procedimento.")
            raise ValueError("Procedimento informado não pertence ao caso.")
        if outcome.procedure_id in seen:
            raise ValueError("Procedimento duplicado no pós-procedimento.")
        seen.add(outcome.procedure_id)

    missing = set(approved_by_id) - seen
    if missing:
        raise ValueError("O pós-procedimento deve cobrir todos os procedimentos autorizados do caso.")

    for outcome in outcomes:
        if outcome.performed:
            continue
        reason = outcome.non_performance_reason
        if reason not in CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_VALUES:
            raise ValueError("Informe a causa do procedimento não realizado.")
        if outcome.resource_shortage_detail:
            raise ValueError("Submotivo de falta de recursos não é aceito em novas gravações.")
        if reason == FollowUpNonPerformanceReason.OTHER:
            if not outcome.other_reason.strip():
                raise ValueError("Descreva a outra causa da não realização.")
        elif outcome.other_reason.strip():
            raise ValueError("Texto de outras causas só deve ser informado quando a causa é 'Outras causas'.")

    return approved_by_id


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
