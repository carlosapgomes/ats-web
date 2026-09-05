"""Testes do serviço de follow-up de desfecho (registro do supervisor)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from apps.cases.followup import (
    ProcedureOutcomeInput,
    get_current_follow_up,
    record_case_follow_up,
)
from apps.cases.models import (
    Case,
    CaseEvent,
    CaseFollowUp,
    CaseProcedure,
    ProcedureFollowUp,
)

pytestmark = pytest.mark.django_db

# ── Helpers ──────────────────────────────────────────────────────────────


def _case_with_procedures(
    case_factory: Callable[..., Case],
    user: Any,
    types: tuple[str, ...] = ("eda",),
) -> Case:
    case = case_factory(user)
    for procedure_type in types:
        CaseProcedure.objects.create(case=case, procedure_type=procedure_type)
    return case


def _procedure_ids(case: Case) -> list[int]:
    return list(case.procedures.order_by("id").values_list("id", flat=True))


def _outcome(case: Case, *, performed: bool = True, reason: str = "", detail: str = "", other: str = ""):
    procedure_id = _procedure_ids(case)[0]
    return ProcedureOutcomeInput(
        procedure_id=procedure_id,
        performed=performed,
        non_performance_reason=reason,
        resource_shortage_detail=detail,
        other_reason=other,
    )


# ── R1: registro inicial ─────────────────────────────────────────────────


class TestRegistroInicial:
    def test_cria_versao1_outcomes_e_evento(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user, types=("eda", "colonoscopy"))
        eda_id, col_id = _procedure_ids(case)

        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[
                ProcedureOutcomeInput(procedure_id=eda_id, performed=True),
                ProcedureOutcomeInput(
                    procedure_id=col_id,
                    performed=False,
                    non_performance_reason="resource_shortage",
                    resource_shortage_detail="emergency_occupied",
                ),
            ],
        )

        assert follow_up.version == 1
        assert follow_up.patient_admitted is True
        assert follow_up.recorded_by == user

        eda_row = ProcedureFollowUp.objects.get(follow_up=follow_up, procedure_id=eda_id)
        assert eda_row.performed is True
        assert eda_row.non_performance_reason == ""

        col_row = ProcedureFollowUp.objects.get(follow_up=follow_up, procedure_id=col_id)
        assert col_row.performed is False
        assert col_row.non_performance_reason == "resource_shortage"
        assert col_row.resource_shortage_detail == "emergency_occupied"

        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert event.actor == user
        assert event.actor_type == "human"
        assert event.payload["version"] == 1
        assert event.payload["patient_admitted"] is True
        assert len(event.payload["outcomes"]) == 2

    def test_absenteismo_e_outras_causas_sao_gravados(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case, performed=False, reason="absenteeism"),
            ],
        )
        case2 = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case2,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case2, performed=False, reason="other", other="Paciente em jejum incompleto"),
            ],
        )
        row = ProcedureFollowUp.objects.get(follow_up__case=case)
        assert row.non_performance_reason == "absenteeism"
        row2 = ProcedureFollowUp.objects.get(follow_up__case=case2)
        assert row2.non_performance_reason == "other"
        assert row2.other_reason == "Paciente em jejum incompleto"


# ── R2: versionamento e evento de atualização ────────────────────────────


class TestVersionamento:
    def test_atualizacao_cria_versao2_preserva_v1_e_evento(self, user, case_factory) -> None:
        from django.contrib.auth import get_user_model

        other_user = get_user_model().objects.create_user(username="segundo", password="x")
        case = _case_with_procedures(case_factory, user)

        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        record_case_follow_up(
            case=case,
            performed_by=other_user,
            patient_admitted=True,
            procedure_outcomes=[_outcome(case, performed=False, reason="absenteeism")],
        )

        assert CaseFollowUp.objects.filter(case=case).count() == 2
        v1 = CaseFollowUp.objects.get(case=case, version=1)
        v2 = CaseFollowUp.objects.get(case=case, version=2)
        assert v1.recorded_by == user
        assert v1.patient_admitted is False
        assert v1.procedure_outcomes.get().performed is True
        assert v2.recorded_by == other_user
        assert v2.patient_admitted is True

        current = get_current_follow_up(case)
        assert current == v2

        updated_event = CaseEvent.objects.filter(case=case, event_type="FOLLOWUP_UPDATED")
        assert updated_event.count() == 1
        assert updated_event.get().payload["version"] == 2
        assert CaseEvent.objects.filter(case=case, event_type="FOLLOWUP_RECORDED").count() == 1

    def test_get_current_sem_followup_retorna_none(self, user, case_factory) -> None:
        case = case_factory(user)
        assert get_current_follow_up(case) is None


# ── R3: validações ───────────────────────────────────────────────────────


class TestValidacoes:
    def _assert_rejeitado(self, case, user, outcomes) -> None:
        with pytest.raises(ValueError):
            record_case_follow_up(
                case=case,
                performed_by=user,
                patient_admitted=False,
                procedure_outcomes=outcomes,
            )
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    def test_cobertura_todos_os_procedimentos(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user, types=("eda", "colonoscopy"))
        col_id = _procedure_ids(case)[1]
        self._assert_rejeitado(
            case,
            user,
            [ProcedureOutcomeInput(procedure_id=col_id, performed=True)],
        )

    def test_procedimento_estranho_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        outro = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(case, user, [_outcome(outro, performed=True)])

    def test_nao_realizado_sem_motivo_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(case, user, [_outcome(case, performed=False)])

    def test_resource_shortage_sem_submotivo_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(
            case,
            user,
            [_outcome(case, performed=False, reason="resource_shortage")],
        )

    def test_outras_causas_sem_texto_rejeitado(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        self._assert_rejeitado(case, user, [_outcome(case, performed=False, reason="other")])

    def test_performed_normaliza_campos_de_motivo(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                _outcome(case, performed=True, reason="absenteeism", detail="emergency_occupied", other="lixo"),
            ],
        )
        row = ProcedureFollowUp.objects.get(follow_up__case=case)
        assert row.non_performance_reason == ""
        assert row.resource_shortage_detail == ""
        assert row.other_reason == ""


# ── R4: constraints de integridade ───────────────────────────────────────


class TestConstraints:
    def test_unique_case_version(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CaseFollowUp.objects.create(case=case, version=1, patient_admitted=False)

    def test_unique_followup_procedure(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        procedure = case.procedures.get()
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(follow_up=follow_up, procedure=procedure, performed=True)

    def check_constraint_rejeita_nao_realizado_sem_motivo(self, user, case_factory) -> None:
        case = _case_with_procedures(case_factory, user)
        follow_up = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[_outcome(case, performed=True)],
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProcedureFollowUp.objects.create(
                    follow_up=follow_up,
                    procedure=case.procedures.get(),
                    performed=False,
                    non_performance_reason="",
                )
