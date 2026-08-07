"""Slice 003 — Colonoscopia percorre pipeline e decisão médica.

Tests focused on the colonoscopy vertical path: strict schema contract,
managed prompts, conservative scope detection (aliases/EDB/mixed/mismatch),
type-aware policy, prior-case and priority signals, and the full pipeline
through WAIT_DOCTOR with the intake flag irrelevant after creation.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.management import call_command
from pydantic import ValidationError

from apps.cases.models import Case, CaseStatus
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.scope_detection import classify_exam_scope


def _evaluate_preop_policy(*, structured_data: dict[str, object], exam_type: str) -> dict[str, object]:
    """Profile-dispatched preop policy (R4) — resolved lazily for RED collection."""
    from apps.pipeline.policy.eda_preop_policy import evaluate_preop_policy

    return evaluate_preop_policy(structured_data=structured_data, exam_type=exam_type)


# ── Scope helper ────────────────────────────────────────────────────────────


def _classify(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str = "",
    case_id: str = "test-case-id",
    agency_record_number: str = "test-agency-record",
    expected_exam_type: str = "eda",
) -> dict[str, object] | None:
    """Invoke classify_exam_scope with an explicit expected (declared) type."""
    result = classify_exam_scope(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
        case_id=case_id,
        agency_record_number=agency_record_number,
        expected_exam_type=expected_exam_type,
    )
    if result is None:
        return None
    return result


# ── RED 1: schema estrito aceita colonoscopy e rejeita valor desconhecido ──


def _colonoscopy_llm1_response() -> str:
    """LLM1 structured data 1.1 para colonoscopia (validação do schema histórico)."""
    return json.dumps(
        {
            "schema_version": "1.1",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 35, "sex": "M"},
            "summary": {
                "one_liner": "Colonoscopia eletiva indicada.",
                "bullet_points": ["Ponto 1", "Ponto 2", "Ponto 3"],
            },
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
            "preop_screening": {
                "exam_type": "colonoscopy",
                "has_cardiovascular_disease": "no",
                "has_active_respiratory_symptoms": "no",
                "has_prior_respiratory_disease": "no",
                "has_ecg_report": "unknown",
                "has_chest_xray_report": "unknown",
                "hb_g_dl": 13.0,
                "platelets_per_mm3": 200000,
                "inr": 1.0,
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
            },
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
            "eda": {
                "indication_category": "other",
                "exclusion_type": "none",
                "is_pediatric": False,
                "foreign_body_suspected": False,
                "requested_procedure": {
                    "name": "Colonoscopia",
                    "urgency": "eletivo",
                    "subtype": "standard",
                },
                "labs": {
                    "hb_g_dl": 13.0,
                    "platelets_per_mm3": 200000,
                    "inr": 1.0,
                    "source_text_hint": None,
                },
                "ecg": {"report_present": "unknown", "abnormal_flag": "unknown", "source_text_hint": None},
            },
        }
    )


class TestLlm1SchemaColonoscopy:
    def test_preop_screening_accepts_colonoscopy(self) -> None:
        from apps.pipeline.schemas.llm1 import Llm1PreopScreening

        validated = Llm1PreopScreening.model_validate(
            {
                "exam_type": "colonoscopy",
                "has_cardiovascular_disease": "no",
                "has_active_respiratory_symptoms": "no",
                "has_prior_respiratory_disease": "no",
                "has_ecg_report": "unknown",
                "has_chest_xray_report": "unknown",
                "hb_g_dl": None,
                "platelets_per_mm3": None,
                "inr": None,
            }
        )
        assert validated.exam_type == "colonoscopy"

    def test_preop_screening_rejects_unknown_exam_value(self) -> None:
        from apps.pipeline.schemas.llm1 import Llm1PreopScreening

        with pytest.raises(ValidationError):
            Llm1PreopScreening.model_validate(
                {
                    "exam_type": "cpre",
                    "has_cardiovascular_disease": "no",
                    "has_active_respiratory_symptoms": "no",
                    "has_prior_respiratory_disease": "no",
                    "has_ecg_report": "unknown",
                    "has_chest_xray_report": "unknown",
                    "hb_g_dl": None,
                    "platelets_per_mm3": None,
                    "inr": None,
                }
            )

    def test_full_llm1_response_validates_with_colonoscopy(self) -> None:
        from apps.pipeline.schemas.llm1 import Llm1Response

        payload = json.loads(_colonoscopy_llm1_response())
        validated = Llm1Response.model_validate(payload)
        assert validated.preop_screening.exam_type == "colonoscopy"
        assert validated.eda.requested_procedure.subtype == "standard"


# ── RED 2: seed/admin expõem quatro prompts colonoscopy e são idempotentes ──


@pytest.mark.django_db
class TestColonoscopyPromptsSeedAdmin:
    """Slice 007: oito nomes legados não são criados/ativos pelo seed; admin
    expõe somente os quatro neutros. O conteúdo 1.1 permanece nas constantes."""

    COLONOSCOPY_LEGACY_NAMES = [
        "colonoscopy_llm1_system",
        "colonoscopy_llm1_user",
        "colonoscopy_llm2_system",
        "colonoscopy_llm2_user",
    ]

    def test_seed_does_not_create_colonoscopy_legacy_names(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        for name in self.COLONOSCOPY_LEGACY_NAMES:
            assert PromptTemplate.get_active(name) is None, f"{name} must not be active"
            assert not PromptTemplate.objects.filter(name=name).exists(), f"{name} must not be created"

    def test_seed_deactivates_preexisting_colonoscopy_legacy_prompts(self) -> None:
        """R4: versões ativas pré-existentes dos nomes antigos são desativadas."""
        from apps.llm.models import PromptTemplate

        for name in self.COLONOSCOPY_LEGACY_NAMES:
            PromptTemplate.objects.create(name=name, version=1, content="legacy active", is_active=True)

        call_command("seed_prompts")

        for name in self.COLONOSCOPY_LEGACY_NAMES:
            assert PromptTemplate.get_active(name) is None, f"{name} still active"
            assert PromptTemplate.objects.filter(name=name).exists(), f"{name} history deleted"

    def test_seed_is_idempotent_with_four_neutral_prompts(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        count1 = PromptTemplate.objects.count()
        call_command("seed_prompts")
        count2 = PromptTemplate.objects.count()
        # Slice 007: seed cria somente os 4 neutros.
        assert count1 == count2 == 4

    def test_legacy_colonoscopy_llm1_user_still_requires_medications_and_ptbr(self) -> None:
        """Conteúdo 1.1 da colonoscopia permanece na constante (rollback)."""
        from apps.pipeline.llm1_service import COLONOSCOPY_LLM1_DEFAULT_USER_PROMPT

        content = COLONOSCOPY_LLM1_DEFAULT_USER_PROMPT
        assert "medications_described" in content
        assert "portugues brasileiro" in content.lower() or "pt-BR" in content

    def test_admin_ui_exposes_only_four_neutral_prompt_names(self) -> None:
        from apps.admin_ui.forms import PROMPT_NAME_CHOICES

        names = {name for name, _ in PROMPT_NAME_CHOICES}
        for neutral in ("exam_llm1_system", "exam_llm1_user", "exam_llm2_system", "exam_llm2_user"):
            assert neutral in names, f"Admin UI missing neutral prompt choice: {neutral}"
        for name in self.COLONOSCOPY_LEGACY_NAMES + [
            "llm1_system",
            "llm1_user",
            "llm2_system",
            "llm2_user",
        ]:
            assert name not in names, f"Admin UI must not expose legacy prompt choice: {name}"

    def test_neutral_prompts_become_canonical(self) -> None:
        from apps.llm.models import PromptTemplate

        call_command("seed_prompts")
        for name in ("exam_llm1_system", "exam_llm1_user", "exam_llm2_system", "exam_llm2_user"):
            assert PromptTemplate.get_active(name) is not None


# ── RED 3-7: scope conservador ──────────────────────────────────────────────


class TestScopeColonoscopyAliases:
    @pytest.mark.parametrize(
        "alias_text",
        [
            "Solicito colonoscopia.",
            "Solicito endoscopia digestiva baixa.",
            "Solicito videocolonoendoscopia.",
            "Solicito colonoscopia diagnostica.",
            "Solicito colonoscopia terapeutica.",
        ],
    )
    def test_positive_alias_current_request_proceeds(self, alias_text: str) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(llm1_structured_data=llm1, cleaned_text=alias_text, expected_exam_type="colonoscopy")
        assert result is None, f"Alias should proceed as colonoscopy: {alias_text!r}"

    def test_edb_contextual_with_label_proceeds(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Procedimento: EDB.",
            expected_exam_type="colonoscopy",
        )
        assert result is None

    def test_edb_isolated_without_context_does_not_confirm(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Paciente com EDB em acompanhamento ambulatorial.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        assert result["decision"] == "manual_review_required"


class TestScopeColonoscopyHistoryNoMixed:
    def test_eda_historical_and_colonoscopy_current_passes(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "colonoscopy"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="EDA realizada em 2024. Solicito colonoscopia.",
            expected_exam_type="colonoscopy",
        )
        assert result is None

    def test_colonoscopy_historical_and_eda_current_passes(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Colonoscopia realizada em 2024. Solicito EDA.",
            expected_exam_type="eda",
        )
        assert result is None

    def test_eda_current_with_historical_colonoscopy_mention_passes(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "eda"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text=(
                "Motivo da Solicitacao: EDA para avaliacao de dispepsia. "
                "Complemento da Solicitacao: colonoscopia previa em 2023 sem alteracoes."
            ),
            expected_exam_type="eda",
        )
        assert result is None


class TestScopeHistoricalWrapperNoMixed:
    """F2: wrappers históricos com verbo de solicitação não criam mixed.

    'histórico de solicitação/indicação de' e 'histórico de encaminhamento
    para' percorrem a MESMA cadeia fechada do request matcher (C22), então um
    verbo interno não vira pedido atual.
    """

    @pytest.mark.parametrize(
        "historical_text",
        [
            "Historico de solicitacao de EDA. Solicito colonoscopia.",
            "Historico de indicacao de EDA. Solicito colonoscopia.",
            "Historico de encaminhamento para EDA. Solicito colonoscopia.",
        ],
    )
    def test_historical_wrapper_eda_does_not_create_mixed(self, historical_text: str) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text=historical_text,
            expected_exam_type="colonoscopy",
        )
        assert result is None, f"wrapper histórico não pode virar mixed: {historical_text!r}"

    @pytest.mark.parametrize(
        "historical_text",
        [
            "Historico de solicitacao de colonoscopia. Solicito EDA.",
            "Historico de indicacao de colonoscopia. Solicito EDA.",
            "Historico de encaminhamento para colonoscopia. Solicito EDA.",
        ],
    )
    def test_historical_wrapper_colon_does_not_create_mixed(self, historical_text: str) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text=historical_text,
            expected_exam_type="eda",
        )
        assert result is None, f"wrapper histórico não pode virar mixed: {historical_text!r}"


class TestScopeNegatedListNoMixed:
    """F3: negação/ausência em lista fechada não cria mixed.

    Os matchers de negação percorrem a MESMA cadeia fechada do request (C21),
    ancorados à ocorrência, nas duas direções EDA ↔ colonoscopia.
    """

    @pytest.mark.parametrize(
        "negated_text,expected",
        [
            ("Nega indicacao de ecoendoscopia e colonoscopia. Solicito EDA.", "eda"),
            ("Sem indicacao de gastrostomia e colonoscopia. Solicito EDA.", "eda"),
            ("Ausencia de indicacao de EDA e gastrostomia. Solicito colonoscopia.", "colonoscopy"),
            ("Nega indicacao de EDA e ecoendoscopia. Solicito colonoscopia.", "colonoscopy"),
            ("Sem indicacao de EDA e gastrostomia. Solicito colonoscopia.", "colonoscopy"),
            ("Ausencia de indicacao de colonoscopia. Solicito EDA.", "eda"),
        ],
    )
    def test_negated_list_does_not_create_mixed(self, negated_text: str, expected: str) -> None:
        """Lista negada/ausente do outro exame não cria mixed, nas duas direções."""
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text=negated_text,
            expected_exam_type=expected,
        )
        assert result is None, f"lista negada não pode virar mixed: {negated_text!r}"


class TestScopeManualReviewPayloadBounds:
    """F4: payload de manual review projeta spans com limites explícitos."""

    def test_bounded_scope_payload_truncates_long_excerpt_and_caps_count(self) -> None:
        from apps.pipeline.scope_detection import (
            MAX_MANUAL_REVIEW_EXCERPT_LENGTH,
            MAX_MANUAL_REVIEW_FIELD_PATH_LENGTH,
            MAX_MANUAL_REVIEW_SPANS,
        )

        long_excerpt = "DADO_CLINICO_" * 1000
        spans = [{"field_path": f"campo.longo.{i}", "excerpt": long_excerpt} for i in range(10)]
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown", "evidence_spans": spans}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Relatorio generico sem exame especifico.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        projected = result["evidence_spans"]
        assert isinstance(projected, list)
        assert len(projected) <= MAX_MANUAL_REVIEW_SPANS
        for span in projected:
            assert len(span["excerpt"]) <= MAX_MANUAL_REVIEW_EXCERPT_LENGTH
            assert len(span["field_path"]) <= MAX_MANUAL_REVIEW_FIELD_PATH_LENGTH
        assert long_excerpt not in str(result)

    def test_bounded_scope_payload_keeps_short_spans_identical(self) -> None:
        spans = [{"field_path": "preop_screening.exam_type", "excerpt": "colonoscopia solicitada"}]
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown", "evidence_spans": spans}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Relatorio generico sem exame especifico.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        assert result["evidence_spans"] == spans

    def test_bounded_scope_payload_preserves_types_and_reason(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Relatorio generico sem exame especifico.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        assert result["reason_code"] == "unknown_exam_type"
        assert result["declared_exam_type"] == "colonoscopy"
        assert result["detected_exam_type"] == "unknown"


class TestScopeColonoscopyMixed:
    @pytest.mark.parametrize("expected", ["eda", "colonoscopy"])
    def test_current_eda_and_colonoscopy_blocks_with_mixed(self, expected: str) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Solicito EDA e colonoscopia para avaliacao.",
            expected_exam_type=expected,
        )
        assert result is not None
        assert result["decision"] == "manual_review_required"
        assert result["reason_code"] == "mixed_exam_request"
        assert result["declared_exam_type"] == expected
        assert result["detected_exam_type"] == "mixed"

    def test_mixed_non_eda_llm1_still_blocks(self) -> None:
        """F1: duas solicitações atuais são mixed mesmo com LLM1 non_eda.

        A autoridade/fallback do LLM1 não pode apagar uma solicitação textual
        atual ao decidir mixed (D7).
        """
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Solicito EDA e colonoscopia.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        assert result["decision"] == "manual_review_required"
        assert result["reason_code"] == "mixed_exam_request"
        assert result["declared_exam_type"] == "colonoscopy"
        assert result["detected_exam_type"] == "mixed"

    def test_mixed_in_motivo_blocks(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
        cleaned_text = """
        Motivo da Solicitacao:
        EDA diagnostica e colonoscopia de rastreamento
        Unid. Origem:
        HSA - HOSPITAL SANTO ANTONIO
        """
        result = _classify(llm1_structured_data=llm1, cleaned_text=cleaned_text, expected_exam_type="eda")
        assert result is not None
        assert result["reason_code"] == "mixed_exam_request"


class TestScopeColonoscopyMismatchAndUnknown:
    def test_declared_colonoscopy_but_detected_eda_blocks(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Solicito EDA para avaliacao de dispepsia.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        assert result["decision"] == "manual_review_required"
        assert result["reason_code"] == "exam_type_mismatch"
        assert result["declared_exam_type"] == "colonoscopy"
        assert result["detected_exam_type"] == "eda"

    def test_declared_eda_but_detected_colonoscopy_blocks(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Solicito colonoscopia para rastreamento.",
            expected_exam_type="eda",
        )
        assert result is not None
        assert result["reason_code"] == "exam_type_mismatch"
        assert result["declared_exam_type"] == "eda"
        assert result["detected_exam_type"] == "colonoscopy"

    def test_unknown_blocks_with_declared_and_detected(self) -> None:
        llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
        result = _classify(
            llm1_structured_data=llm1,
            cleaned_text="Relatorio generico sem exame especifico.",
            expected_exam_type="colonoscopy",
        )
        assert result is not None
        assert result["reason_code"] == "unknown_exam_type"
        assert result["declared_exam_type"] == "colonoscopy"
        assert result["detected_exam_type"] == "unknown"


# ── RED 8-10: policy por tipo ───────────────────────────────────────────────


def _min_exam_evidence_ok() -> dict[str, str]:
    return {
        "hb_numeric_present": "yes",
        "platelets_numeric_present": "yes",
        "tp_inr_rni_numeric_present": "yes",
        "ttpa_present": "yes",
        "urea_present": "yes",
        "creatinine_present": "yes",
    }


def _colonoscopy_structured(*, subtype: str = "standard", min_exam: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "patient": {"age": 35},
        "preop_screening": {
            "exam_type": "colonoscopy",
            "rulebook_signals": {
                "eda_subtype": subtype,
                "minimum_exam_evidence": min_exam or _min_exam_evidence_ok(),
                "conditional_exam_requirements": {},
                "clinical_flags": {},
            },
        },
        "eda": {
            "indication_category": "other",
            "requested_procedure": {"name": "Colonoscopia", "subtype": subtype},
        },
    }


class TestColonoscopyPreopPolicy:
    def test_colonoscopy_criteria_met_with_all_minimum_exams(self) -> None:
        decision = _evaluate_preop_policy(
            structured_data=_colonoscopy_structured(),
            exam_type="colonoscopy",
        )
        assert decision["decision"] == "accept"
        assert decision["reason_code"] == "criteria_met"

    def test_colonoscopy_denies_when_minimum_exam_missing(self) -> None:
        missing = dict(_min_exam_evidence_ok())
        missing["platelets_numeric_present"] = "no"
        decision = _evaluate_preop_policy(
            structured_data=_colonoscopy_structured(min_exam=missing),
            exam_type="colonoscopy",
        )
        assert decision["decision"] == "deny"
        assert decision["reason_code"] == "missing_minimum_exam_platelets"

    def test_colonoscopy_never_foreign_body_exception(self) -> None:
        """Foreign-body subtype noise must NOT bypass minimum exams for colonoscopy."""
        missing = dict(_min_exam_evidence_ok())
        missing["hb_numeric_present"] = "no"
        decision = _evaluate_preop_policy(
            structured_data=_colonoscopy_structured(subtype="foreign_body", min_exam=missing),
            exam_type="colonoscopy",
        )
        assert decision["decision"] == "deny"
        assert decision["reason_code"] != "foreign_body_exception"

    def test_colonoscopy_text_does_not_assert_eda_rulebook(self) -> None:
        decision = _evaluate_preop_policy(
            structured_data=_colonoscopy_structured(),
            exam_type="colonoscopy",
        )
        reason_text = str(decision["reason_text"])
        assert "rulebook EDA" not in reason_text
        assert "Colonoscopia" in reason_text or "colonoscopia" in reason_text

    def test_eda_foreign_body_still_bypasses(self) -> None:
        eda_data: dict[str, object] = {
            "patient": {"age": 35},
            "preop_screening": {
                "exam_type": "eda",
                "rulebook_signals": {"eda_subtype": "foreign_body"},
            },
            "eda": {
                "indication_category": "foreign_body",
                "requested_procedure": {"name": "EDA", "subtype": "foreign_body"},
            },
        }
        decision = _evaluate_preop_policy(structured_data=eda_data, exam_type="eda")
        assert decision["decision"] == "accept"
        assert decision["reason_code"] == "foreign_body_exception"

    def test_eda_minimum_exam_denial_preserved(self) -> None:
        missing = dict(_min_exam_evidence_ok())
        missing["creatinine_present"] = "no"
        eda_data: dict[str, object] = {
            "patient": {"age": 35},
            "preop_screening": {
                "exam_type": "eda",
                "rulebook_signals": {
                    "eda_subtype": "standard",
                    "minimum_exam_evidence": missing,
                },
            },
            "eda": {
                "indication_category": "dyspepsia",
                "requested_procedure": {"name": "EDA", "subtype": "standard"},
            },
        }
        decision = _evaluate_preop_policy(structured_data=eda_data, exam_type="eda")
        assert decision["decision"] == "deny"


# ── RED 11: prior case mesmo tipo apenas ────────────────────────────────────


class TestPriorCaseColonoscopyTypeAware:
    def test_prior_lookup_filters_same_exam_type(self, django_user_model) -> None:
        from datetime import UTC, datetime, timedelta

        from apps.pipeline.prior_case import lookup_prior_case_context

        user = django_user_model.objects.create_user(username="prior_colon", password="pw")
        now = datetime.now(tz=UTC)

        # EDA denial (prior, same agency) — must NOT appear for colonoscopy lookup.
        Case.objects.create(
            created_by=user,
            agency_record_number="AR800",
            exam_type="eda",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=1),
        )
        # Colonoscopy denial (prior) — must appear for colonoscopy lookup.
        colon_prior = Case.objects.create(
            created_by=user,
            agency_record_number="AR800",
            exam_type="colonoscopy",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_decided_at=now - timedelta(days=2),
        )
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR800",
            exam_type="colonoscopy",
        )

        colon_ctx = lookup_prior_case_context(
            current.case_id,
            "AR800",
            now=now,
            exam_type="colonoscopy",
        )
        assert colon_ctx.prior_case is not None
        assert colon_ctx.prior_case.prior_case_id == str(colon_prior.case_id)
        assert colon_ctx.prior_denial_count_7d == 1

        eda_ctx = lookup_prior_case_context(
            current.case_id,
            "AR800",
            now=now,
            exam_type="eda",
        )
        assert eda_ctx.prior_case is not None
        assert eda_ctx.prior_case.prior_case_id != str(colon_prior.case_id)
        assert eda_ctx.prior_denial_count_7d == 1


# ── RED 12: sinais colonoscopia apenas pediatric ────────────────────────────


class TestColonoscopyPrioritySignals:
    def test_colonoscopy_persists_only_pediatric(self) -> None:
        from apps.cases.priority_signals import resolve_priority_signals

        structured: dict[str, object] = {
            "patient": {"age": 10},
            "eda": {
                "requested_procedure": {"subtype": "foreign_body"},
                "indication_category": "foreign_body",
                "foreign_body_suspected": True,
            },
        }
        codes = [
            str(s["code"])
            for s in resolve_priority_signals(
                structured_data=structured,
                source_text="Crianca com corpo estranho. Solicito colonoscopia.",
                exam_type="colonoscopy",
            )
        ]
        assert codes == ["pediatric"]

    def test_eda_keeps_all_signals(self) -> None:
        from apps.cases.priority_signals import resolve_priority_signals

        structured: dict[str, object] = {
            "patient": {"age": 10},
            "eda": {
                "requested_procedure": {"subtype": "foreign_body"},
                "indication_category": "foreign_body",
                "foreign_body_suspected": True,
            },
        }
        codes = [
            str(s["code"])
            for s in resolve_priority_signals(
                structured_data=structured,
                source_text="Crianca com corpo estranho.",
                exam_type="eda",
            )
        ]
        assert "foreign_body" in codes
        assert "pediatric" in codes


# ── Pipeline helpers (RED 13/16 + mixed gate) ───────────────────────────────


def _make_v2_case(user, *, exam_type: str = "colonoscopy", extracted_text: str = "Solicito colonoscopia.") -> Case:
    """Cria um Case com projeção declarada pronto para o pipeline v2."""
    from apps.cases.procedures import set_declared_procedures

    case = Case.objects.create(created_by=user, agency_record_number="12345", extracted_text=extracted_text)
    types = ("eda", "colonoscopy") if exam_type == "eda_colonoscopy" else (exam_type,)
    set_declared_procedures(case=case, procedure_types=types, actor=user)
    case.start_processing(user=user)
    case.save()
    case.start_extraction(user=user)
    case.save()
    case.extraction_complete(success=True, user=user)
    case.save()
    return case


def _v2_llm1(procedures: list[dict[str, Any]], *, one_liner: str = "Colonoscopia indicada.") -> str:
    """LLM1 v2 (procedure-neutral) com os procedimentos informados."""
    return json.dumps(
        {
            "schema_version": "2.0",
            "language": "pt-BR",
            "agency_record_number": "12345",
            "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
            "common_preop": {
                "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0, "source_text_hint": None},
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
            },
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
            "summary": {"one_liner": one_liner, "bullet_points": ["P1", "P2", "P3"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
            "origin_context": {
                "city": None,
                "hospital": None,
                "unit": None,
                "state_uf": None,
                "source_text_hint": None,
            },
            "transfusion": {"had_transfusion": "no"},
            "tracked_exams": [],
        }
    )


def _colon_procedure() -> dict[str, Any]:
    return {
        "procedure_type": "colonoscopy",
        "name": "Colonoscopia",
        "urgency": "eletivo",
        "indication_category": "screening",
        "subtype": "standard",
        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito colonoscopia"}],
    }


def _eda_procedure() -> dict[str, Any]:
    return {
        "procedure_type": "eda",
        "name": "EDA",
        "urgency": "eletivo",
        "indication_category": "dyspepsia",
        "subtype": "standard",
        "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito EDA"}],
    }


def _v2_llm2_single(case_id: str, *, procedure_type: str = "colonoscopy", suggestion: str = "accept") -> str:
    """LLM2 v2 com uma recomendação para o procedimento detectado."""
    return json.dumps(
        {
            "schema_version": "2.0",
            "language": "pt-BR",
            "case_id": case_id,
            "agency_record_number": "12345",
            "procedure_recommendations": [
                {
                    "procedure_type": procedure_type,
                    "suggestion": suggestion,
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
                }
            ],
            "global_support_recommendation": "none",
            "summary": None,
        }
    )


def _reload(case: Case) -> Case:
    return Case.objects.get(case_id=case.case_id)


class TestColonoscopyPipeline:
    """R5: colonoscopia percorre o pipeline v2 (uma chamada por estágio) e chega
    ao médico com prompt neutro; mismatch retorna ao NIR sem LLM2."""

    def test_pipeline_colonoscopy_reaches_wait_doctor_with_neutral_prompt(self, django_user_model) -> None:
        from apps.llm.models import PromptTemplate

        for name, content in (
            ("exam_llm1_system", "NEUTRAL_SYS_1"),
            ("exam_llm2_system", "NEUTRAL_SYS_2"),
        ):
            PromptTemplate.objects.create(name=name, version=1, content=content, is_active=True)

        user = django_user_model.objects.create_user(username="nir_colon1", password="pw")
        case = _make_v2_case(user, exam_type="colonoscopy", extracted_text="Solicito colonoscopia.")

        client = RecordingLlmClient(responses=[_v2_llm1([_colon_procedure()]), _v2_llm2_single(str(case.case_id))])

        run_pipeline(case.case_id, llm_client=client)

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert len(client.calls) == 2
        # Dispatch v2 usa somente os quatro nomes neutros (R3).
        assert client.calls[0]["system_prompt"] == "NEUTRAL_SYS_1"
        assert client.calls[1]["system_prompt"] == "NEUTRAL_SYS_2"
        assert case.suggested_action is not None
        recs = case.suggested_action["procedure_recommendations"]
        assert [r["procedure_type"] for r in recs] == ["colonoscopy"]
        assert recs[0]["suggestion"] == "accept"

    def test_declared_colonoscopy_detected_eda_blocks_without_llm2(self, django_user_model) -> None:
        """Mismatch (declarado colonoscopia, detectado EDA) retorna ao NIR sem LLM2."""
        from apps.cases.models import CaseEvent

        user = django_user_model.objects.create_user(username="nir_colon2", password="pw")
        # Texto extraído longo/distinto do excerpt de evidência: o payload de
        # revisão carrega somente spans curtos limitados, nunca o texto integral.
        case = _make_v2_case(
            user,
            exam_type="colonoscopy",
            extracted_text=(
                "Relatorio clinico extenso com historico detalhado do paciente que "
                "nao deve vazar para o evento de auditoria. Solicito EDA."
            ),
        )

        client = RecordingLlmClient(responses=[_v2_llm1([_eda_procedure()], one_liner="EDA indicada.")])
        run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert len(client.calls) == 1  # LLM2 nunca roda
        assert case.suggested_action is not None
        assert case.suggested_action["reason_code"] == "exam_type_mismatch"
        assert case.suggested_action["detected_procedures"] == ["eda"]

        event = CaseEvent.objects.filter(case=case, event_type="EDA_SCOPE_GATED_MANUAL_REVIEW").latest("timestamp")
        payload: dict[str, Any] = event.payload or {}
        assert payload.get("reason_code") == "exam_type_mismatch"
        serialized = json.dumps(payload)
        assert "extracted_text" not in serialized
        # O texto clínico integral (histórico) não vaza; somente o excerpt curto
        # de evidência permanece (limitado pelo schema 2.0).
        assert "Relatorio clinico extenso" not in serialized
        assert "historico detalhado" not in serialized

    def test_flag_off_after_creation_does_not_block_pipeline(self, django_user_model, settings) -> None:
        """Flag web-only não é consultada pelo pipeline após a criação (D15)."""
        settings.COLONOSCOPY_INTAKE_ENABLED = False
        user = django_user_model.objects.create_user(username="nir_colon3", password="pw")
        case = _make_v2_case(user, exam_type="colonoscopy", extracted_text="Solicito colonoscopia.")

        client = RecordingLlmClient(responses=[_v2_llm1([_colon_procedure()]), _v2_llm2_single(str(case.case_id))])
        run_pipeline(
            case.case_id,
            llm_client=client,
            llm1_system_prompt="sp1",
            llm1_user_template="ut1",
            llm2_system_prompt="sp2",
            llm2_user_template="ut2",
        )

        case = _reload(case)
        assert case.status == CaseStatus.WAIT_DOCTOR
