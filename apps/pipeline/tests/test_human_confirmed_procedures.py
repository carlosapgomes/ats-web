"""S2 RED — conjunto confirmado dirige o pipeline ate o medico (R4–R6).

Contrato: openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/
slices/slice-002-human-confirmation-to-doctor-with-timeline.md.

Seeds sinteticas de evidence.md (sem PII/PDF real):
- argonio: EDA atual + plasma de argonio SEM vinculo local com a base
  (item estruturado contraditado) — 1a passada vai a revisao; sem
  confirmacao humana a divergencia REPETE o gate (loop do caso 5073320).
- eco+cpre: EDA administrativa + Eco atual + CPRE — uniao incompativel
  (caso 5075227); confirmar um singleton permitido resolve.
- item ausente: conjunto confirmado sem item correspondente no array LLM1.

Estado RED (baseline S1): nao existe autoridade humana; a 2a passada repete
o gate para a mesma uniao e a mesma selecao nao pode sequer ser reafirmada.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.test import override_settings

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    ProcedureType,
)
from apps.cases.services import claim_case_lock
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.tests.test_eda_package_pipeline_v4 import (
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

# ── Textos sinteticos (evidence.md seeds 2–4) ─────────────────────────────

# Argonio SEM vinculo local: disponibilidade mencionada em trecho isolado +
# retossigmoidoscopia solicitada em outro trecho + cabecalho EDA atual.
ARGON_TEXT = (
    "RELATORIO DE OCORRENCIAS\n"
    "Governo do Estado da Bahia\n"
    "Motivo da Solicitacao: Endoscopia Digestiva Alta - EDA\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferencia: Paciente com sangramento retal. "
    "Servico com disponibilidade de plasma de argonio. "
    "Solicito Retossigmoidoscopia para avaliacao.\n"
    "RELATORIO DE OCORRENCIAS\n"
    "Informado por: Dra. Fulana\n"
)

# Eco atual + CPRE mencionada + EDA administrativa (uniao incompativel).
ECO_CPRE_TEXT = (
    "RELATORIO DE OCORRENCIAS\n"
    "Governo do Estado da Bahia\n"
    "Motivo da Solicitacao: EDA administrativa para regulacao\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferencia: Solicito regulacao para ecoendoscopia. "
    "Servico com disponibilidade de ecoendoscopia e CPRE.\n"
    "RELATORIO DE OCORRENCIAS\n"
    "Informado por: Dr. Fulano\n"
)


def _argon_item() -> dict[str, object]:
    return {
        "procedure_type": "rectosigmoidoscopy_argon",
        "name": "Retossigmoidoscopia + Argonio",
        "urgency": "eletivo",
        "indication_category": "bleeding",
        "evidence_spans": [{"field_path": "requested_procedures.1", "excerpt": "plasma de argonio"}],
    }


def _eda_item() -> dict[str, object]:
    return {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": "Endoscopia Digestiva Alta"}],
    }


def _nir_user(django_user_model, username: str = "nir-pipe@test.com"):
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username)
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _run(user, *, procedure_types, extracted_text, llm1_procedures, llm2_procedures) -> tuple[Case, RecordingLlmClient]:
    case = _make_declared_case(user, procedure_types=procedure_types, extracted_text=extracted_text)
    client = RecordingLlmClient(
        responses=[
            _llm1_json(procedures=llm1_procedures, one_liner="Achados sinteticos."),
            _llm2_json(
                str(case.case_id),
                recommendations=[
                    rec
                    for procedure_type in llm2_procedures
                    for rec in _single_procedure_recommendation(procedure_type)
                ],
            ),
        ]
    )
    run_pipeline(case.case_id, llm_client=client)
    return Case.objects.get(case_id=case.case_id), client


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


def _review_event(case: Case) -> CaseEvent:
    return CaseEvent.objects.filter(case=case, event_type="EDA_SCOPE_GATED_MANUAL_REVIEW").latest("timestamp")


def _confirm_kwargs(case: Case, user, token, *, exam_type: str) -> Any:
    from apps.cases.procedure_review import source_fingerprint_for_case

    return {
        "case_id": case.case_id,
        "exam_type": exam_type,
        "user": user,
        "active_role": "nir",
        "lock_token": token,
        "review_acknowledged": "on",
        "review_justification": "Revisei o relatorio principal e confirmo a selecao.",
        "review_event_id": _review_event(case).pk,
        "source_fingerprint": source_fingerprint_for_case(case),
    }


# ═══════════════════════════════════════════════════════════════════════════
# R5 — argonio: divergencia repetida nao reabre identificacao apos confirmar
# ═══════════════════════════════════════════════════════════════════════════


class TestArgonConfirmationResolves:
    def test_repeated_divergence_loop_without_confirmation(self, django_user_model, monkeypatch) -> None:
        """Caracterizacao do loop: sem confirmacao, a 2a passada volta a revisao.

        Passa no baseline E no S2 (regressao do fail-closed automatico).
        """
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-argon-loop@test.com")
        case, _ = _run(
            user,
            procedure_types=(ProcedureType.EDA,),
            extracted_text=ARGON_TEXT,
            llm1_procedures=[_eda_item(), _argon_item()],
            llm2_procedures=["eda"],
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_argon_confirmation_reaches_doctor(self, django_user_model, monkeypatch) -> None:
        """RED: confirmar argonio apos revisao leva a WAIT_DOCTOR.

        Baseline: sem autoridade humana a 2a passada repete o gate; alem
        disso a mesma selecao sequer e reafirmavel. Falha ate o S2.
        """
        from apps.intake.services import confirm_case_procedure_review

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-argon@test.com")
        case, _ = _run(
            user,
            procedure_types=(ProcedureType.EDA,),
            extracted_text=ARGON_TEXT,
            llm1_procedures=[_eda_item(), _argon_item()],
            llm2_procedures=["eda"],
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        review_count = CaseEvent.objects.filter(case=case, event_type="EDA_SCOPE_GATED_MANUAL_REVIEW").count()

        token = _claim(case, user)
        confirm_case_procedure_review(
            **_confirm_kwargs(case, user, token, exam_type=ProcedureType.RECTOSIGMOIDOSCOPY_ARGON)
        )

        client2 = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_item(), _argon_item()], one_liner="Achados sinteticos."),
                _llm2_json(
                    str(case.case_id),
                    recommendations=_single_procedure_recommendation("rectosigmoidoscopy_argon"),
                ),
            ]
        )
        run_pipeline(case.case_id, llm_client=client2)
        case = Case.objects.get(pk=case.pk)

        assert case.status == CaseStatus.WAIT_DOCTOR
        # Sem reabertura da identificacao pela mesma divergencia.
        assert CaseEvent.objects.filter(case=case, event_type="EDA_SCOPE_GATED_MANUAL_REVIEW").count() == review_count
        # Evento humano com actor e selection_changed, uniao bruta preservada.
        confirmed = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").latest(
            "timestamp"
        )
        assert confirmed.actor_id == user.pk
        assert confirmed.payload["selection_changed"] is True
        assert confirmed.payload["confirmed_procedures"] == ["rectosigmoidoscopy_argon"]
        detected = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        assert set(detected.payload["detected_procedures"]) >= {"eda", "rectosigmoidoscopy_argon"}
        # Raw LLM1 intacto; projecao efetiva nao fabrica consenso.
        structured = case.structured_data
        assert isinstance(structured, dict)
        assert {item["procedure_type"] for item in structured["requested_procedures"]} >= {
            "eda",
            "rectosigmoidoscopy_argon",
        }
        applied = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_APPLIED").latest("timestamp")
        assert applied.payload["confirmation_event_id"] == confirmed.pk
        assert applied.payload["effective_procedures"] == ["rectosigmoidoscopy_argon"]
        assert [item["procedure_type"] for item in _recommendations(case)] == ["rectosigmoidoscopy_argon"]
        detected_rows = {
            row.procedure_type
            for row in CaseProcedure.objects.filter(case=case, detection_status=DetectionStatus.DETECTED)
        }
        assert detected_rows == {ProcedureType.RECTOSIGMOIDOSCOPY_ARGON}
        # Proveniencia aditiva no artefato final para leitores legados.
        provenance = _suggested_action(case).get("nir_procedure_review")
        assert isinstance(provenance, dict)
        assert provenance["confirmation_event_id"] == confirmed.pk


# ═══════════════════════════════════════════════════════════════════════════
# R5/R6 — eco+cpre: singleton confirmado resolve; item ausente nao bloqueia
# ═══════════════════════════════════════════════════════════════════════════


class TestSpecializedConfirmationResolves:
    def _cpre_item(self) -> dict[str, object]:
        # Item v3/v4 estrito de CPRE: sem indication_category (StrictModel).
        return {
            "procedure_type": "cpre",
            "name": "CPRE",
            "urgency": "eletivo",
            "evidence_spans": [{"field_path": "requested_procedures.2", "excerpt": "CPRE"}],
        }

    @override_settings(CPRE_INTAKE_ENABLED=True)
    def test_same_selection_cpre_confirmed_reaches_doctor(self, django_user_model, monkeypatch) -> None:
        """RED: confirmar a MESMA selecao (CPRE) resolve mismatch incompativel."""
        from apps.intake.services import confirm_case_procedure_review

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-cpre@test.com")
        case, _ = _run(
            user,
            procedure_types=(ProcedureType.CPRE,),
            extracted_text=ECO_CPRE_TEXT,
            llm1_procedures=[_eda_item(), self._cpre_item()],
            llm2_procedures=["cpre"],
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        token = _claim(case, user)
        confirm_case_procedure_review(**_confirm_kwargs(case, user, token, exam_type=ProcedureType.CPRE))

        client2 = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_item(), self._cpre_item()], one_liner="Achados sinteticos."),
                _llm2_json(
                    str(case.case_id),
                    recommendations=_single_procedure_recommendation("cpre"),
                ),
            ]
        )
        run_pipeline(case.case_id, llm_client=client2)
        case = Case.objects.get(pk=case.pk)

        assert case.status == CaseStatus.WAIT_DOCTOR
        confirmed = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").latest(
            "timestamp"
        )
        assert confirmed.payload["selection_changed"] is False
        assert [item["procedure_type"] for item in _recommendations(case)] == ["cpre"]

    @override_settings(CPRE_INTAKE_ENABLED=True)
    def test_confirmed_absent_from_llm1_uses_common_without_fabrication(self, django_user_model, monkeypatch) -> None:
        """RED (R6): CPRE confirmada sem item no array LLM1 funciona.

        Policy usa dados comuns/unknown, LLM2 recomenda exatamente CPRE e
        nenhum evidence_span/item clinico e fabricado no JSON original.
        """
        from apps.intake.services import confirm_case_procedure_review

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-absent@test.com")
        case, _ = _run(
            user,
            procedure_types=(ProcedureType.CPRE,),
            extracted_text=ECO_CPRE_TEXT,
            llm1_procedures=[_eda_item()],
            llm2_procedures=["cpre"],
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        token = _claim(case, user)
        confirm_case_procedure_review(**_confirm_kwargs(case, user, token, exam_type=ProcedureType.CPRE))

        client2 = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_item()], one_liner="Achados sinteticos."),
                _llm2_json(
                    str(case.case_id),
                    recommendations=_single_procedure_recommendation("cpre"),
                ),
            ]
        )
        run_pipeline(case.case_id, llm_client=client2)
        case = Case.objects.get(pk=case.pk)

        assert case.status == CaseStatus.WAIT_DOCTOR
        assert [item["procedure_type"] for item in _recommendations(case)] == ["cpre"]
        # JSON original intacto: nenhum item CPRE fabricado.
        structured = case.structured_data
        assert isinstance(structured, dict)
        assert {item["procedure_type"] for item in structured["requested_procedures"]} == {"eda"}


# ═══════════════════════════════════════════════════════════════════════════
# R6 prova complementar (round-2 P1): policy negativa preservada após
# confirmação + par confirmado com item ausente mantém policies locais
# ═══════════════════════════════════════════════════════════════════════════


def _cpre_item_detached() -> dict[str, object]:
    # Item v4 estrito de CPRE: sem indication_category (StrictModel).
    return {
        "procedure_type": "cpre",
        "name": "CPRE",
        "urgency": "eletivo",
        "evidence_spans": [{"field_path": "requested_procedures.2", "excerpt": "CPRE"}],
    }


def _eda_foreign_body_item() -> dict[str, object]:
    return {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "foreign_body",
        "subtype": "foreign_body",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": "corpo estranho"}],
    }


def _latest_policy_decision(case: Case, procedure_type: str) -> dict[str, Any]:
    event = (
        CaseEvent.objects.filter(case=case, event_type="EDA_PREOP_POLICY_DECISION")
        .order_by("-timestamp", "-id")
        .filter(payload__procedure_type=procedure_type)
        .first()
    )
    assert event is not None
    assert isinstance(event.payload, dict)
    return event.payload


def _failed_codes(decision: dict[str, Any]) -> list[str]:
    failed = decision.get("failed_requirements")
    assert isinstance(failed, list)
    return [str(item["code"]) for item in failed]


PAIR_FB_TEXT = (
    "RELATORIO DE OCORRENCIAS\n"
    "Governo do Estado da Bahia\n"
    "Motivo da Solicitacao: Endoscopia Digestiva Alta - EDA\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferencia: Paciente com suspeita de corpo estranho. "
    "Solicito EDA para retirada.\n"
    "RELATORIO DE OCORRENCIAS\n"
    "Informado por: Dra. Fulana\n"
)


class TestConfirmedCpreKeepsImagingDenial:
    """R6/D5: CPRE confirmada sem imagem verificada mantém negativa determinística.

    A confirmação humana resolve a identificação (caso chega à avaliação
    médica), mas NÃO dispensa a hard rule de imagem: a policy nega, a
    sugestão clínica permanece negativa e o NIR nunca aprova clinicamente.
    """

    @override_settings(CPRE_INTAKE_ENABLED=True)
    def test_confirmed_cpre_without_verified_imaging_stays_denied_for_doctor(
        self, django_user_model, monkeypatch
    ) -> None:
        from apps.intake.services import confirm_case_procedure_review

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-cpre-nimg@test.com")
        case, _ = _run(
            user,
            procedure_types=(ProcedureType.CPRE,),
            extracted_text=ECO_CPRE_TEXT,
            llm1_procedures=[_eda_item(), _cpre_item_detached()],
            llm2_procedures=["cpre"],
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        token = _claim(case, user)
        confirm_case_procedure_review(**_confirm_kwargs(case, user, token, exam_type=ProcedureType.CPRE))

        client2 = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_eda_item(), _cpre_item_detached()], one_liner="Achados sinteticos."),
                _llm2_json(
                    str(case.case_id),
                    recommendations=_single_procedure_recommendation("cpre"),
                ),
            ]
        )
        run_pipeline(case.case_id, llm_client=client2)
        case = Case.objects.get(pk=case.pk)

        # Chega à avaliação médica — sem aprovação clínica pelo NIR.
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert not case.doctor_decision
        # Lista fechada exata do conjunto confirmado.
        recommendations = _recommendations(case)
        assert [item["procedure_type"] for item in recommendations] == ["cpre"]
        # Negativa determinística preservada (policy vence o LLM).
        assert recommendations[0]["suggestion"] == "deny"
        preop = recommendations[0]["preop_decision"]
        assert isinstance(preop, dict)
        assert preop["decision"] == "deny"
        assert any(code.startswith("abdominal_imaging") for code in _failed_codes(preop))
        # Evento de policy confirma a pendência de imagem para CPRE.
        policy = _latest_policy_decision(case, "cpre")
        assert policy["decision"] == "deny"
        assert any(code.startswith("abdominal_imaging") for code in _failed_codes(policy))
        # Raw LLM1 intacto: nenhum item clínico fabricado.
        structured = case.structured_data
        assert isinstance(structured, dict)
        assert {item["procedure_type"] for item in structured["requested_procedures"]} == {"eda", "cpre"}
        # Proveniência: união bruta preservada, efetivo é o confirmado.
        detected = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        assert set(detected.payload["detected_procedures"]) >= {"eda", "cpre"}
        applied = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_APPLIED").latest("timestamp")
        assert applied.payload["effective_procedures"] == ["cpre"]


class TestConfirmedCombinedKeepsLocalPolicies:
    """R6/D5: par EDA+Colonoscopia confirmado com só item EDA (exceção local).

    Ambos são analisados a partir de comuns/unknowns com o par fechado no
    LLM2; a exceção corpo-estranho da EDA não é herdada pela Colonoscopia
    (policy local com HB baixo nega só a Colonoscopia); raw e união bruta
    seguem intactos.
    """

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_confirmed_pair_with_only_eda_item_keeps_exception_local(self, django_user_model, monkeypatch) -> None:
        from apps.cases.models import EDA_COLONOSCOPY
        from apps.intake.services import confirm_case_procedure_review

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-pair-local@test.com")
        case, _ = _run(
            user,
            procedure_types=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            extracted_text=PAIR_FB_TEXT,
            llm1_procedures=[_eda_foreign_body_item()],
            llm2_procedures=["eda", "colonoscopy"],
        )
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        token = _claim(case, user)
        confirm_case_procedure_review(**_confirm_kwargs(case, user, token, exam_type=EDA_COLONOSCOPY))

        pair_recommendations = [
            rec for procedure_type in ("eda", "colonoscopy") for rec in _single_procedure_recommendation(procedure_type)
        ]
        client2 = RecordingLlmClient(
            responses=[
                _llm1_json(
                    procedures=[_eda_foreign_body_item()],
                    one_liner="Achados sinteticos.",
                    hb_g_dl=6.5,
                ),
                _llm2_json(str(case.case_id), recommendations=pair_recommendations),
            ]
        )
        run_pipeline(case.case_id, llm_client=client2)
        case = Case.objects.get(pk=case.pk)

        assert case.status == CaseStatus.WAIT_DOCTOR
        recommendations = _recommendations(case)
        # Par fechado exato, sem procedimento adicionado.
        assert [item["procedure_type"] for item in recommendations] == ["eda", "colonoscopy"]
        by_type = {item["procedure_type"]: item for item in recommendations}
        # EDA aceita pela exceção local de corpo estranho.
        eda_preop = by_type["eda"]["preop_decision"]
        assert isinstance(eda_preop, dict)
        assert eda_preop["decision"] == "accept"
        assert eda_preop["reason_code"] == "foreign_body_exception"
        assert by_type["eda"]["suggestion"] == "accept"
        # Colonoscopia NÃO herda a exceção: policy local nega pelo HB.
        colon_preop = by_type["colonoscopy"]["preop_decision"]
        assert isinstance(colon_preop, dict)
        assert colon_preop["decision"] == "deny"
        assert colon_preop["reason_code"] != "foreign_body_exception"
        assert "hb_below_threshold" in _failed_codes(colon_preop)
        assert by_type["colonoscopy"]["suggestion"] == "deny"
        # Eventos de policy confirmam o par de resultados locais.
        assert _latest_policy_decision(case, "eda")["reason_code"] == "foreign_body_exception"
        assert _latest_policy_decision(case, "colonoscopy")["decision"] == "deny"
        # Raw JSON intacto: nenhum item Colonoscopia fabricado, sem evidence emprestada.
        structured = case.structured_data
        assert isinstance(structured, dict)
        raw_types = [item["procedure_type"] for item in structured["requested_procedures"]]
        assert raw_types == ["eda"]
        assert structured["requested_procedures"][0].get("subtype") == "foreign_body"
        # União bruta preservada (só EDA detectado); efetivo é o par confirmado.
        detected = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
        assert list(detected.payload["detected_procedures"]) == ["eda"]
        applied = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_APPLIED").latest("timestamp")
        assert applied.payload["effective_procedures"] == ["eda", "colonoscopy"]
        provenance = _suggested_action(case).get("nir_procedure_review")
        assert isinstance(provenance, dict)
        assert provenance["effective_procedures"] == ["eda", "colonoscopy"]
