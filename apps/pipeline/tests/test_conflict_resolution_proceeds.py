"""Slice 002 (R6) — resolução declarado-aware: beco sem saída end-to-end.

Regressão do caso real 26/09 (ADR-0011 decisão 2/D2): o Motivo pede EDA ATUAL,
o corpo só traz dilatação NÃO-atual e o LLM1 reporta o item estruturado
``eda_dilation``. Na 1ª passada o gate de conflito mantém o caso em revisão NIR
(declarado ``eda`` ≠ cobertura máxima do union ``{eda, eda_dilation}``). Após a
correção do NIR para ``eda_dilation`` o reprocessamento PROSSEGUE até o médico,
pois há evidência atual (``any_set ≠ ∅``) e a declaração é a seleção canônica
mais completa que cobre o union — com a união bruta preservada no evento de
auditoria (D3/R5).
"""

from __future__ import annotations

import uuid

import pytest

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    ProcedureType,
)
from apps.cases.services import claim_case_lock
from apps.intake.services import correct_case_exam_type
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.tests.test_eda_package_pipeline_v4 import (
    _dilation_procedure,
    _make_declared_case,
    _recommendations,
    _suggested_action,
)
from apps.pipeline.tests.test_slice_002_pipeline import (
    _llm1_json,
    _llm2_json,
    _single_procedure_recommendation,
)

pytestmark = pytest.mark.django_db

# Fixture SINTÉTICA (sem dados de paciente): Motivo com EDA atual e corpo apenas
# com dilatação NÃO-atual; o LLM1 reporta o pacote ``eda_dilation``.
MOTIVE_EDA_HISTORICAL_DILATION_TEXT = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Governo do Estado da Bahia\n"
    "Motivo da Solicitação: Endoscopia Digestiva Alta - EDA\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferência: Paciente com dispepsia. Dilatação esofágica realizada em 2022.\n"
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Informado por: Dra. Fulana\n"
)

# União bruta do ponto de conflito (any={eda} ∪ conflicting={eda_dilation}).
RAW_UNION = {"eda", "eda_dilation"}


def _nir_user(django_user_model, username: str = "nir-s2-proceeds@test.com"):
    """Usuário com o papel NIR atribuído (sem sessão HTTP)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username)
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _llm1() -> str:
    return _llm1_json(
        procedures=[_dilation_procedure(site="unknown", excerpt=None)],
        one_liner="EDA + Dilatação indicada.",
    )


def _run_pass(user, *, procedure_types: tuple[str, ...]) -> tuple[Case, RecordingLlmClient]:
    case = _make_declared_case(
        user, procedure_types=procedure_types, extracted_text=MOTIVE_EDA_HISTORICAL_DILATION_TEXT
    )
    client = RecordingLlmClient(
        responses=[
            _llm1(),
            _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("eda_dilation")),
        ]
    )
    run_pipeline(case.case_id, llm_client=client)
    return Case.objects.get(case_id=case.case_id), client


def _detection_event(case: Case) -> CaseEvent:
    return CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")


def _claim(case: Case, user) -> uuid.UUID:
    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        context="nir_receipt",
        role="nir",
    )
    assert result.acquired
    assert result.token is not None
    return result.token


class TestDeclaredAwareResolutionProceeds:
    def test_correction_to_best_covering_package_proceeds_to_the_doctor(self, django_user_model, monkeypatch) -> None:
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model)

        # ── 1ª passada: revisão NIR por conflito (beco sem saída) ──────────
        case, client1 = _run_pass(user, procedure_types=(ProcedureType.EDA,))

        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert len(client1.calls) == 1
        payload = _suggested_action(case)
        assert payload["reason_code"] == "conflicting_procedure_evidence"
        # R4: o payload normaliza o union fora da matriz para a cobertura máxima.
        assert payload["detected_procedures"] == ["eda_dilation"]
        # R8: a origem da detecção (Motivo) permanece no motivo da revisão.
        assert str(payload["reason_text"]).endswith("Origem da detecção: Motivo da Solicitação.")
        # R5: o evento registra a união BRUTA, não o payload normalizado.
        assert set(_detection_event(case).payload["detected_procedures"]) == RAW_UNION

        # ── correção NIR para o pacote mais completo sustentado ────────────
        token = _claim(case, user)
        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ProcedureType.EDA_DILATION,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        # ── 2ª passada: a resolução declarado-aware prossegue até o médico ─
        case = Case.objects.get(pk=case.pk)
        client2 = RecordingLlmClient(
            responses=[
                _llm1(),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("eda_dilation")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client2)

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client2.calls) == 2
        # Sem novo ``nir_review`` pelo mesmo conflito (nenhum evento de gate novo).
        assert CaseEvent.objects.filter(case=case, event_type="EDA_SCOPE_GATED_MANUAL_REVIEW").count() == 1
        assert [item["procedure_type"] for item in _recommendations(case)] == ["eda_dilation"]
        detected_rows = {
            row.procedure_type
            for row in CaseProcedure.objects.filter(case=case, detection_status=DetectionStatus.DETECTED)
        }
        assert detected_rows == {ProcedureType.EDA_DILATION}
        # R5: a 2ª passada também grava a união bruta no evento de auditoria.
        assert set(_detection_event(case).payload["detected_procedures"]) == RAW_UNION
