"""Slice 002 — schemas e serviços LLM1/LLM2 procedure-neutral v2.

RED 1 (R1): Llm1ResponseV2 aceita EDA, Colon e ambos; rejeita vazio,
duplicata, outro tipo e evidence inválida.
RED 2 (R6): Llm2ResponseV2 exige um item por tipo detectado; igualdade exata
do conjunto; suporte global mais restritivo; uma análise conjunta por caso,
com retries corretivos limitados.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from django.core.management import call_command
from pydantic import ValidationError

from apps.cases.models import Case, CaseProcedure, CaseStatus
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.prior_case import PRIOR_CASE_WINDOW_DAYS, PriorCaseSummary, lookup_prior_case_context

# ── Sample builders ──────────────────────────────────────────────────────────


def _evidence_span(field_path: str = "requested_procedures.0", excerpt: str = "Solicito EDA") -> dict[str, str]:
    return {"field_path": field_path, "excerpt": excerpt}


def _eda_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "subtype": "standard",
        "evidence_spans": [_evidence_span(excerpt="Solicito EDA")],
    }
    item.update(overrides)
    return item


def _colon_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "colonoscopy",
        "name": "Colonoscopia",
        "urgency": "eletivo",
        "indication_category": "screening",
        "subtype": "standard",
        "evidence_spans": [_evidence_span(excerpt="Solicito colonoscopia")],
    }
    item.update(overrides)
    return item


def _common_preop(**overrides: Any) -> dict[str, Any]:
    common: dict[str, Any] = {
        "labs": {
            "hb_g_dl": 13.0,
            "platelets_per_mm3": 200000,
            "inr": 1.0,
            "source_text_hint": None,
        },
        "ecg": {"report_present": "unknown", "abnormal_flag": "unknown", "source_text_hint": None},
        "asa": {"bucket": "I-II", "source_text_hint": None},
        "cardiovascular_risk": {"level": "low", "source_text_hint": None},
        "rulebook_signals": {
            "eda_subtype": "standard",
            "minimum_exam_evidence": {
                "hb_numeric_present": "yes",
                "platelets_numeric_present": "yes",
                "tp_inr_rni_numeric_present": "yes",
                "ttpa_present": "yes",
                "urea_present": "yes",
                "creatinine_present": "yes",
            },
            "conditional_exam_requirements": {},
            "clinical_flags": {},
        },
        "comorbidities_described": [],
        "medications_described": [],
        "evidence_spans": [],
    }
    common.update(overrides)
    return common


def _llm1_v2_payload(*, procedures: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "2.0",
        "language": "pt-BR",
        "agency_record_number": "12345",
        "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
        "common_preop": _common_preop(),
        "requested_procedures": procedures,
        "policy_precheck": {
            "excluded_from_eda_flow": False,
            "exclusion_reason": None,
            "labs_required": True,
            "labs_pass": "yes",
            "labs_failed_items": [],
            "ecg_required": False,
            "ecg_present": "unknown",
            "pediatric_flag": False,
            "notes": None,
        },
        "summary": {"one_liner": "EDA e Colonoscopia indicadas.", "bullet_points": ["P1", "P2", "P3"]},
        "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        "origin_context": {"city": None, "hospital": None, "unit": None, "state_uf": None, "source_text_hint": None},
        "transfusion": {"had_transfusion": "no"},
        "tracked_exams": [],
    }
    payload.update(overrides)
    return payload


# ── RED 1: schema LLM1 v2 ───────────────────────────────────────────────────


class TestLlm1V2Schema:
    def test_accepts_eda_only(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        validated = Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_eda_procedure()]))
        assert validated.requested_procedures[0].procedure_type == "eda"

    def test_accepts_colonoscopy_only(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        validated = Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_colon_procedure()]))
        assert validated.requested_procedures[0].procedure_type == "colonoscopy"

    def test_accepts_both(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        validated = Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_eda_procedure(), _colon_procedure()]))
        types = {p.procedure_type for p in validated.requested_procedures}
        assert types == {"eda", "colonoscopy"}

    def test_rejects_empty_requested_procedures(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[]))

    def test_rejects_duplicate_procedure_type(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_eda_procedure(), _eda_procedure()]))

    def test_rejects_unsupported_procedure_type(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        cpre: dict[str, Any] = {
            "procedure_type": "cpre",
            "name": "CPRE",
            "urgency": "eletivo",
            "indication_category": "other",
            "subtype": "standard",
            "evidence_spans": [_evidence_span(excerpt="CPRE")],
        }
        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[cpre]))

    def test_rejects_eda_subtype_on_colonoscopy(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_colon_procedure(subtype="foreign_body")]))

    def test_rejects_missing_evidence_spans(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_eda_procedure(evidence_spans=[])]))

    def test_rejects_whitespace_only_excerpt(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(
                _llm1_v2_payload(procedures=[_eda_procedure(evidence_spans=[_evidence_span(excerpt="   ")])])
            )

    def test_evidence_spans_are_bounded(self) -> None:
        from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2

        long_excerpt = "X" * 500
        with pytest.raises(ValidationError):
            Llm1ResponseV2.model_validate(
                _llm1_v2_payload(procedures=[_eda_procedure(evidence_spans=[_evidence_span(excerpt=long_excerpt)])])
            )


# ── RED 1/2: uma chamada LLM1 em combinado (serviço) ───────────────────────


@pytest.mark.django_db
class TestLlm1ServiceV2SingleCall:
    def test_one_llm1_call_for_combined_case(self) -> None:
        from apps.pipeline.llm1_service_v2 import Llm1ServiceV2

        client = RecordingLlmClient(
            responses=[json.dumps(_llm1_v2_payload(procedures=[_eda_procedure(), _colon_procedure()]))]
        )
        service = Llm1ServiceV2(client)
        result = service.run(
            case_id="case-1",
            agency_record_number="12345",
            extracted_text="Solicito EDA e colonoscopia.",
            declared_procedure_types=("eda", "colonoscopy"),
            system_prompt="sp1",
            user_prompt_template="ut1",
        )
        assert len(client.calls) == 1
        assert result.structured_data["schema_version"] == "2.0"
        assert result.summary_text == "EDA e Colonoscopia indicadas."
        assert result.prompt_system_name == "exam_llm1_system"
        assert result.prompt_user_name == "exam_llm1_user"

    def test_llm1_v2_rejects_invalid_response_without_result(self) -> None:
        from apps.pipeline.llm1_service_v2 import Llm1ServiceV2, Llm1V2ValidationError

        client = RecordingLlmClient(responses=['{"schema_version": "1.1"}'])
        service = Llm1ServiceV2(client)
        with pytest.raises(Llm1V2ValidationError):
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                extracted_text="x",
                declared_procedure_types=("eda",),
                system_prompt="sp1",
                user_prompt_template="ut1",
            )


# ── RED 2: LLM2 v2 — análise conjunta + conjunto exato + suporte máximo ────


def _llm2_v2_payload(
    *,
    case_id: str = "case-1",
    recommendations: list[dict[str, Any]] | None = None,
    global_support: str = "none",
) -> str:
    if recommendations is None:
        recommendations = [
            {
                "procedure_type": "eda",
                "suggestion": "accept",
                "support_recommendation": "none",
                "rationale": {
                    "short_reason": "Criterios atendidos.",
                    "details": ["Sem contraindicacao.", "Exames compativeis."],
                    "missing_info_questions": [],
                },
                "policy_alignment": {
                    "excluded_request": False,
                    "labs_ok": "yes",
                    "ecg_ok": "yes",
                    "pediatric_flag": False,
                    "notes": None,
                },
                "confidence": "alta",
            },
            {
                "procedure_type": "colonoscopy",
                "suggestion": "accept",
                "support_recommendation": "anesthesist",
                "rationale": {
                    "short_reason": "Aprovado.",
                    "details": ["Sem contraindicacao.", "Exames compativeis."],
                    "missing_info_questions": [],
                },
                "policy_alignment": {
                    "excluded_request": False,
                    "labs_ok": "yes",
                    "ecg_ok": "yes",
                    "pediatric_flag": False,
                    "notes": None,
                },
                "confidence": "alta",
            },
        ]
    return json.dumps(
        {
            "schema_version": "2.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": recommendations,
            "global_support_recommendation": global_support,
            "summary": None,
        }
    )


def _single_recommendation(procedure_type: str, *, short_reason: str = "Criterios atendidos.") -> list[dict[str, Any]]:
    """Recomendação única para um procedimento (payload LLM2 v2 mínimo válido)."""
    return [
        {
            "procedure_type": procedure_type,
            "suggestion": "accept",
            "support_recommendation": "none",
            "rationale": {
                "short_reason": short_reason,
                "details": ["Sem contraindicacao.", "Exames compativeis."],
                "missing_info_questions": [],
            },
            "policy_alignment": {
                "excluded_request": False,
                "labs_ok": "yes",
                "ecg_ok": "yes",
                "pediatric_flag": False,
                "notes": None,
            },
            "confidence": "alta",
        }
    ]


def _prompt_closed_list(prompt: str) -> list[str]:
    """Extrai e faz parse da lista fechada declarada no envelope do prompt."""
    marker = "Procedimentos canônicos reconciliados (lista fechada): "
    start = prompt.index(marker) + len(marker)
    return cast("list[str]", json.loads(prompt[start:].split("\n", 1)[0]))


@pytest.mark.django_db
class TestLlm2ServiceV2:
    def test_one_call_exact_set_equal(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2

        client = RecordingLlmClient(responses=[_llm2_v2_payload()])
        service = Llm2ServiceV2(client)
        result = service.run(
            case_id="case-1",
            agency_record_number="12345",
            llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure(), _colon_procedure()]),
            detected_procedure_types=("eda", "colonoscopy"),
            policy_results={},
            prior_contexts={},
            system_prompt="sp2",
            user_prompt_template="ut2",
        )
        assert len(client.calls) == 1
        types = {r["procedure_type"] for r in result.procedure_recommendations}
        assert types == {"eda", "colonoscopy"}

    def test_omitted_item_fails(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2, Llm2V2ValidationError

        payload = _llm2_v2_payload(recommendations=[])
        client = RecordingLlmClient(responses=[payload])
        service = Llm2ServiceV2(client)
        with pytest.raises(Llm2V2ValidationError):
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure(), _colon_procedure()]),
                detected_procedure_types=("eda", "colonoscopy"),
                policy_results={},
                prior_contexts={},
                system_prompt="sp2",
                user_prompt_template="ut2",
            )

    def test_duplicate_item_fails(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2, Llm2V2ValidationError

        duplicated = [
            {
                "procedure_type": "eda",
                "suggestion": "accept",
                "support_recommendation": "none",
                "rationale": {
                    "short_reason": "A.",
                    "details": ["1", "2"],
                    "missing_info_questions": [],
                },
                "policy_alignment": {
                    "excluded_request": False,
                    "labs_ok": "yes",
                    "ecg_ok": "yes",
                    "pediatric_flag": False,
                    "notes": None,
                },
                "confidence": "alta",
            }
        ] * 2
        client = RecordingLlmClient(responses=[_llm2_v2_payload(recommendations=duplicated)])
        service = Llm2ServiceV2(client)
        with pytest.raises(Llm2V2ValidationError):
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure(), _colon_procedure()]),
                detected_procedure_types=("eda", "colonoscopy"),
                policy_results={},
                prior_contexts={},
                system_prompt="sp2",
                user_prompt_template="ut2",
            )

    def test_added_item_fails(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2, Llm2V2ValidationError

        # LLM2 adds colonoscopy while only EDA was detected.
        client = RecordingLlmClient(responses=[_llm2_v2_payload()])
        service = Llm2ServiceV2(client)
        with pytest.raises(Llm2V2ValidationError):
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
                detected_procedure_types=("eda",),
                policy_results={},
                prior_contexts={},
                system_prompt="sp2",
                user_prompt_template="ut2",
            )

    def test_support_global_max_is_explicit(self) -> None:
        from apps.pipeline.llm2_service_v2 import (
            GLOBAL_SUPPORT_ORDER,
            strictest_global_support,
        )

        assert strictest_global_support(("none", "anesthesist")) == "anesthesist"
        assert strictest_global_support(("anesthesist", "anesthesist_icu")) == "anesthesist_icu"
        assert strictest_global_support(("none", "anesthesist_icu")) == "anesthesist_icu"
        assert (
            GLOBAL_SUPPORT_ORDER["none"] < GLOBAL_SUPPORT_ORDER["anesthesist"] < GLOBAL_SUPPORT_ORDER["anesthesist_icu"]
        )


# ── fix-llm2-reconciled-procedure-set: conjunto canônico + retry fail-closed ──


class TestLlm2ReconciledProcedureContext:
    """Lista fechada no prompt, retry único de mismatch tipado e budgets finitos."""

    def test_prompt_declares_reconciled_procedure_context_closed_list(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2

        client = RecordingLlmClient(responses=[_llm2_v2_payload(recommendations=_single_recommendation("eda"))])
        service = Llm2ServiceV2(client)
        service.run(
            case_id="case-1",
            agency_record_number="12345",
            llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
            detected_procedure_types=("eda",),
            policy_results={},
            prior_contexts={},
            system_prompt="sp2",
            user_prompt_template="ut2",
        )
        prompt = client.calls[0]["user_prompt"]
        assert _prompt_closed_list(prompt) == ["eda"]
        assert "exatamente um item em procedure_recommendations" in prompt

    def test_procedure_set_retry_recovers_with_exactly_one_extra_call(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2

        client = RecordingLlmClient(
            responses=[
                _llm2_v2_payload(),  # 1ª resposta: conjunto divergente (eda + colonoscopy)
                _llm2_v2_payload(recommendations=_single_recommendation("eda")),
            ]
        )
        service = Llm2ServiceV2(client)
        result = service.run(
            case_id="case-1",
            agency_record_number="12345",
            llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
            detected_procedure_types=("eda",),
            policy_results={},
            prior_contexts={},
            system_prompt="sp2",
            user_prompt_template="ut2",
        )
        assert len(client.calls) == 2
        retry_prompt = client.calls[1]["user_prompt"]
        assert _prompt_closed_list(retry_prompt) == ["eda"]
        assert "resposta anterior" in retry_prompt
        assert {r["procedure_type"] for r in result.procedure_recommendations} == {"eda"}

    def test_persistent_procedure_set_mismatch_raises_after_two_llm2_calls(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2, Llm2V2ValidationError

        divergent = _llm2_v2_payload()
        client = RecordingLlmClient(responses=[divergent, divergent])
        service = Llm2ServiceV2(client)
        with pytest.raises(Llm2V2ValidationError) as excinfo:
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
                detected_procedure_types=("eda",),
                policy_results={},
                prior_contexts={},
                system_prompt="sp2",
                user_prompt_template="ut2",
            )
        assert len(client.calls) == 2  # tentativa inicial + o único retry de conjunto
        # Erro tipado (subclasse dedicada); o controle de retry não faz matching textual.
        assert type(excinfo.value).__name__ == "Llm2V2ProcedureSetMismatchError"
        assert isinstance(excinfo.value, Llm2V2ValidationError)
        assert "procedure set mismatch" in str(excinfo.value)

    def test_non_set_validation_error_does_not_trigger_procedure_set_retry(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2, Llm2V2ValidationError

        client = RecordingLlmClient(responses=[_llm2_v2_payload(case_id="case-999")])
        service = Llm2ServiceV2(client)
        with pytest.raises(Llm2V2ValidationError) as excinfo:
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
                detected_procedure_types=("eda",),
                policy_results={},
                prior_contexts={},
                system_prompt="sp2",
                user_prompt_template="ut2",
            )
        assert len(client.calls) == 1  # erro de ID não consome retry de conjunto
        assert type(excinfo.value).__name__ != "Llm2V2ProcedureSetMismatchError"

    def test_language_retry_remains_functional_and_one_shot(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2

        client = RecordingLlmClient(
            responses=[
                _llm2_v2_payload(recommendations=_single_recommendation("eda", short_reason="Patient liberado.")),
                _llm2_v2_payload(recommendations=_single_recommendation("eda")),
            ]
        )
        service = Llm2ServiceV2(client)
        result = service.run(
            case_id="case-1",
            agency_record_number="12345",
            llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
            detected_procedure_types=("eda",),
            policy_results={},
            prior_contexts={},
            system_prompt="sp2",
            user_prompt_template="ut2",
        )
        assert len(client.calls) == 2
        assert "portugues brasileiro" in client.calls[1]["user_prompt"]
        assert {r["procedure_type"] for r in result.procedure_recommendations} == {"eda"}

    def test_language_retry_exhausts_budget_after_two_llm2_calls(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2, Llm2V2ValidationError

        forbidden = _llm2_v2_payload(recommendations=_single_recommendation("eda", short_reason="Patient liberado."))
        client = RecordingLlmClient(responses=[forbidden, forbidden])
        service = Llm2ServiceV2(client)
        with pytest.raises(Llm2V2ValidationError, match="non-ptbr"):
            service.run(
                case_id="case-1",
                agency_record_number="12345",
                llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
                detected_procedure_types=("eda",),
                policy_results={},
                prior_contexts={},
                system_prompt="sp2",
                user_prompt_template="ut2",
            )
        assert len(client.calls) == 2

    def test_language_retry_and_procedure_set_retry_combine_within_three_calls(self) -> None:
        from apps.pipeline.llm2_service_v2 import Llm2ServiceV2

        client = RecordingLlmClient(
            responses=[
                _llm2_v2_payload(),  # conjunto divergente
                # Conjunto correto + narrativo em inglês → consome o retry de idioma.
                _llm2_v2_payload(recommendations=_single_recommendation("eda", short_reason="Patient liberado.")),
                _llm2_v2_payload(recommendations=_single_recommendation("eda")),
            ]
        )
        service = Llm2ServiceV2(client)
        result = service.run(
            case_id="case-1",
            agency_record_number="12345",
            llm1_structured_data=_llm1_v2_payload(procedures=[_eda_procedure()]),
            detected_procedure_types=("eda",),
            policy_results={},
            prior_contexts={},
            system_prompt="sp2",
            user_prompt_template="ut2",
        )
        assert len(client.calls) == 3  # máximo físico: inicial + retry de conjunto + retry de idioma
        assert {r["procedure_type"] for r in result.procedure_recommendations} == {"eda"}


# ── Prompts neutros e prior-case por procedimento (D10) ─────────────────────
#
# RED 3 (R2): quatro prompts neutros seed/admin/fallback idempotentes.
# RED 10/11 (R6/D10): contexto anterior por componente sem cruzar decisão;
# negativa global de agendamento só para row aprovada; janela/dedup mantidos;
# aprovação não aumenta prior_denial_count_7d.


NEUTRAL_NAMES = [
    "exam_llm1_system",
    "exam_llm1_user",
    "exam_llm2_system",
    "exam_llm2_user",
]


# ── RED 3: prompts neutros ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestNeutralPrompts:
    def test_seed_creates_four_neutral_prompts_idempotently(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            template = PromptTemplate.get_active(name)
            assert template is not None, f"Missing neutral prompt: {name}"
            assert template.content.strip()

        count1 = PromptTemplate.objects.count()
        call_command("seed_prompts")
        assert PromptTemplate.objects.count() == count1

    def test_seed_total_count_after_neutral_prompts(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        # Slice 007: seed cria SOMENTE os 4 neutros (versões ativas); os 8
        # nomes legados não são criados pelo seed.
        assert PromptTemplate.objects.count() == 4
        assert not PromptTemplate.objects.filter(name="llm1_system").exists()
        assert not PromptTemplate.objects.filter(name="colonoscopy_llm1_system").exists()

    def test_admin_ui_exposes_four_neutral_prompt_names(self) -> None:
        from apps.admin_ui.forms import PROMPT_NAME_CHOICES

        names = {name for name, _ in PROMPT_NAME_CHOICES}
        for name in NEUTRAL_NAMES:
            assert name in names, f"Admin UI missing neutral prompt choice: {name}"

    @pytest.mark.django_db
    def test_fallback_contents_exist_for_neutral_names(self) -> None:
        from apps.pipeline.orchestrator import _get_prompt_content

        for name in NEUTRAL_NAMES:
            content = _get_prompt_content(name)
            assert content.strip(), f"Missing fallback content for {name}"

    def test_neutral_prompts_do_not_encode_thresholds_nor_authorize_invention(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            template = PromptTemplate.get_active(name)
            assert template is not None
            content = template.content.lower()
            # Thresholds numéricos clínicos não pertencem ao prompt.
            assert "hb <" not in content and "100000" not in content
            # O LLM não pode inventar procedimentos sem evidência.
            assert "nao invente" in content or "não invente" in content or "evidencia" in content


# ── Helpers D10 ─────────────────────────────────────────────────────────────


def _make_user(django_user_model, username: str):
    return django_user_model.objects.create_user(username=username, password="pw")


def _case(user, *, arn: str, procedure_rows: list[tuple[str, str]], **fields: object) -> Case:
    """Cria Case com rows CaseProcedure com disposição por componente."""
    case = Case.objects.create(created_by=user, agency_record_number=arn, **fields)
    for procedure_type, disposition in procedure_rows:
        CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=True,
            doctor_disposition=disposition,
        )
    return case


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── RED 10: contexto anterior por componente sem cruzar decisão ─────────────


@pytest.mark.django_db
class TestPriorContextPerComponent:
    def test_eda_denied_and_colon_approved_do_not_cross(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p1")
        now = _now()
        # EDA negada com razão própria; Colonoscopia aprovada.
        _case(
            user,
            arn="AR900",
            procedure_rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_reason="razão global",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        current = _case(user, arn="AR900", procedure_rows=[])

        eda_ctx = lookup_prior_case_context(current.case_id, "AR900", now=now, procedure_type="eda")
        colon_ctx = lookup_prior_case_context(current.case_id, "AR900", now=now, procedure_type="colonoscopy")

        assert eda_ctx.prior_case is not None
        assert eda_ctx.prior_case.decision == "doctor_denied"
        assert eda_ctx.prior_case.reason == "não informado"  # reason da row, não global
        assert eda_ctx.prior_denial_count_7d == 1

        assert colon_ctx.prior_case is not None
        assert colon_ctx.prior_case.decision == "doctor_approved"
        # Aprovação nunca aumenta o contador de negativas.
        assert colon_ctx.prior_denial_count_7d == 0

    def test_prior_case_summary_accepts_approval(self) -> None:
        summary = PriorCaseSummary(
            prior_case_id="abc",
            decided_at="2026-08-01T10:00:00+00:00",
            decision="doctor_approved",
            reason="",
        )
        assert summary.decision == "doctor_approved"

    def test_prior_denied_row_reason_used_from_row(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p2")
        now = _now()
        _case(
            user,
            arn="AR901",
            procedure_rows=[("eda", "denied")],
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="razão global diferente",
            doctor_decided_at=now - timedelta(days=1),
        )
        # Preenche razão da row (D10: razão vem da row).
        prior = Case.objects.get(agency_record_number="AR901")
        row = prior.procedures.get(procedure_type="eda")
        row.doctor_reason = "razão do componente EDA"
        row.save(update_fields=["doctor_reason"])

        current = _case(user, arn="AR901", procedure_rows=[])
        eda_ctx = lookup_prior_case_context(current.case_id, "AR901", now=now, procedure_type="eda")
        assert eda_ctx.prior_case is not None
        assert eda_ctx.prior_case.decision == "doctor_denied"
        assert eda_ctx.prior_case.reason == "razão do componente EDA"


# ── RED 11: negativa de agendamento global, janela e dedup ──────────────────


@pytest.mark.django_db
class TestPriorWindowAndAppointment:
    def test_appointment_denial_applies_only_to_approved_row(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p3")
        now = _now()
        # EDA medicamente negada; Colonoscopia aprovada mas agendamento global negado.
        _case(
            user,
            arn="AR902",
            procedure_rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.APPT_DENIED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            appointment_status="denied",
            appointment_reason="sem vaga",
            appointment_decided_at=now - timedelta(hours=12),
        )
        current = _case(user, arn="AR902", procedure_rows=[])

        eda_ctx = lookup_prior_case_context(current.case_id, "AR902", now=now, procedure_type="eda")
        colon_ctx = lookup_prior_case_context(current.case_id, "AR902", now=now, procedure_type="colonoscopy")

        # EDA segue negativa médica (não vira appointment_denied).
        assert eda_ctx.prior_case is not None
        assert eda_ctx.prior_case.decision == "doctor_denied"
        # Colonoscopia (aprovada) recebe a negativa de agendamento global.
        assert colon_ctx.prior_case is not None
        assert colon_ctx.prior_case.decision == "appointment_denied"
        assert colon_ctx.prior_case.reason == "sem vaga"
        assert colon_ctx.prior_denial_count_7d == 1
        assert eda_ctx.prior_denial_count_7d == 1

    def test_window_and_approval_never_counts(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p4")
        now = _now()
        # Aprovação fora da janela não conta; dentro da janela também não conta.
        _case(
            user,
            arn="AR903",
            procedure_rows=[("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        current = _case(user, arn="AR903", procedure_rows=[])
        colon_ctx = lookup_prior_case_context(current.case_id, "AR903", now=now, procedure_type="colonoscopy")
        assert colon_ctx.prior_case is not None
        assert colon_ctx.prior_case.decision == "doctor_approved"
        assert colon_ctx.prior_denial_count_7d == 0

    def test_outside_window_not_included(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p5")
        now = _now()
        _case(
            user,
            arn="AR904",
            procedure_rows=[("eda", "denied")],
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=PRIOR_CASE_WINDOW_DAYS + 1),
        )
        current = _case(user, arn="AR904", procedure_rows=[])
        eda_ctx = lookup_prior_case_context(current.case_id, "AR904", now=now, procedure_type="eda")
        assert eda_ctx.prior_case is None
        assert eda_ctx.prior_denial_count_7d == 0

    def test_approved_later_denied_picks_most_recent_and_counts_once(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p6")
        now = _now()
        # Duas decisões do mesmo componente: aprovação (mais antiga) + negativa (recente).
        _case(
            user,
            arn="AR905",
            procedure_rows=[("eda", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=2),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        _case(
            user,
            arn="AR905",
            procedure_rows=[("eda", "denied")],
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=1),
        )
        current = _case(user, arn="AR905", procedure_rows=[])
        eda_ctx = lookup_prior_case_context(current.case_id, "AR905", now=now, procedure_type="eda")
        assert eda_ctx.prior_case is not None
        assert eda_ctx.prior_case.decision == "doctor_denied"
        assert eda_ctx.prior_denial_count_7d == 1

    def test_pending_row_not_included(self, django_user_model) -> None:
        user = _make_user(django_user_model, "nir_p7")
        now = _now()
        _case(
            user,
            arn="AR906",
            procedure_rows=[("eda", "pending")],
            status=CaseStatus.NEW,
        )
        current = _case(user, arn="AR906", procedure_rows=[])
        eda_ctx = lookup_prior_case_context(current.case_id, "AR906", now=now, procedure_type="eda")
        assert eda_ctx.prior_case is None
        assert eda_ctx.prior_denial_count_7d == 0

    def test_same_prior_case_id_can_appear_in_both_sections(self, django_user_model) -> None:
        """D10: o mesmo caso combinado anterior aparece nas duas consultas lógicas."""
        user = _make_user(django_user_model, "nir_p8")
        now = _now()
        prior = _case(
            user,
            arn="AR907",
            procedure_rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        current = _case(user, arn="AR907", procedure_rows=[])

        eda_ctx = lookup_prior_case_context(current.case_id, "AR907", now=now, procedure_type="eda")
        colon_ctx = lookup_prior_case_context(current.case_id, "AR907", now=now, procedure_type="colonoscopy")

        assert eda_ctx.prior_case is not None and colon_ctx.prior_case is not None
        assert eda_ctx.prior_case.prior_case_id == str(prior.case_id)
        assert colon_ctx.prior_case.prior_case_id == str(prior.case_id)
        assert eda_ctx.prior_case.decision == "doctor_denied"
        assert colon_ctx.prior_case.decision == "doctor_approved"
