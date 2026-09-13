"""Slice 001 (R4/R5) — contrato strict 3.0, adapters e agregação de policy.

Cobre:
- R4: ``Llm1ResponseV3``/``Llm2ResponseV3`` aceitam os quatro tipos e a
  evidência abdominal tipada; duplicatas/vazio/desconhecido e excerpt de achado
  ausente são rejeitados; leitores 1.1/2.0 permanecem legíveis.
- R5: a policy determinística agrega TODAS as pendências em ordem estável
  (``failed_requirements[]``) preservando ``reason_code`` primário, sem alterar
  o comportamento de EDA/Colonoscopia.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from apps.pipeline.policy import evaluate_procedure_policy
from apps.pipeline.schemas.adapters import (
    detect_schema_version,
    project_v2_to_llm1_shape,
    project_v3_to_llm1_shape,
    requested_procedure_types_v3,
)
from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2
from apps.pipeline.schemas.llm1_v3 import Llm1ResponseV3
from apps.pipeline.schemas.llm2_v3 import Llm2ResponseV3
from apps.pipeline.tests.test_slice_002_contracts import (
    _colon_procedure,
    _common_preop,
    _eda_procedure,
    _llm1_v2_payload,
)

# ── Builders v3 ─────────────────────────────────────────────────────────────


def _echo_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "echoendoscopy",
        "name": "Ecoendoscopia",
        "urgency": "eletivo",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": "Solicito ecoendoscopia"}],
    }
    item.update(overrides)
    return item


def _cpre_procedure(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "procedure_type": "cpre",
        "name": "CPRE",
        "urgency": "eletivo",
        "evidence_spans": [{"field_path": "requested_procedures.0", "excerpt": "Solicito CPRE"}],
    }
    item.update(overrides)
    return item


def _imaging(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "modality": "ct",
        "anatomical_site": "abdomen",
        "report_finding_present": "yes",
        "source_document": "main_report",
        "evidence_context_excerpt": "Conclusão: TC de abdome demonstrou espessamento parietal.",
        "finding_excerpt": "demonstrou espessamento parietal",
        "exam_datetime_iso": None,
    }
    item.update(overrides)
    return item


def _llm1_v3_payload(*, procedures: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "3.0",
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
        "summary": {"one_liner": "Procedimentos indicados.", "bullet_points": ["P1", "P2", "P3"]},
        "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        "origin_context": {"city": None, "hospital": None, "unit": None, "state_uf": None, "source_text_hint": None},
        "transfusion": {"had_transfusion": "no"},
        "tracked_exams": [],
    }
    payload.update(overrides)
    return payload


def _decision(*, structured_data: dict[str, Any], procedure_type: str) -> dict[str, Any]:
    """Wrapper tipado do resultado determinístico (payload é heterogêneo)."""
    result: dict[str, Any] = evaluate_procedure_policy(structured_data=structured_data, procedure_type=procedure_type)
    return result


def _recommendation(procedure_type: str, *, suggestion: str = "accept") -> dict[str, Any]:
    return {
        "procedure_type": procedure_type,
        "suggestion": suggestion,
        "support_recommendation": "none",
        "rationale": {"short_reason": "OK.", "details": ["1", "2"], "missing_info_questions": []},
        "policy_alignment": {
            "excluded_request": False,
            "labs_ok": "yes",
            "ecg_ok": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
        "confidence": "alta",
    }


def _projection(
    *, subtype: str = "standard", minimum: dict[str, str] | None = None, **preop_overrides: Any
) -> dict[str, Any]:
    """Projeta um payload v3 mínimo para a forma 1.1 consumida pela policy."""
    rulebook = {
        "eda_subtype": subtype,
        "minimum_exam_evidence": minimum
        or {
            "hb_numeric_present": "yes",
            "platelets_numeric_present": "yes",
            "tp_inr_rni_numeric_present": "yes",
            "ttpa_present": "yes",
            "urea_present": "yes",
            "creatinine_present": "yes",
        },
        "conditional_exam_requirements": preop_overrides.pop("conditional_exam_requirements", {}),
        "clinical_flags": preop_overrides.pop("clinical_flags", {}),
    }
    payload = _llm1_v3_payload(
        procedures=[_eda_procedure(subtype=subtype)],
        common_preop=_common_preop(rulebook_signals=rulebook),
    )
    return project_v3_to_llm1_shape(v3_data=payload, procedure_type="eda")


# ── R4: schema LLM1 v3 ──────────────────────────────────────────────────────


class TestLlm1V3Schema:
    def test_accepts_all_four_procedure_types(self) -> None:
        payload = _llm1_v3_payload(
            procedures=[_eda_procedure(), _colon_procedure(), _echo_procedure(), _cpre_procedure()]
        )
        validated = Llm1ResponseV3.model_validate(payload)
        assert {item.procedure_type for item in validated.requested_procedures} == {
            "eda",
            "colonoscopy",
            "echoendoscopy",
            "cpre",
        }

    def test_rejects_duplicate_procedure_types(self) -> None:
        payload = _llm1_v3_payload(procedures=[_eda_procedure(), _eda_procedure()])
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(payload)

    def test_rejects_empty_and_unknown_procedure(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(_llm1_v3_payload(procedures=[]))
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(
                _llm1_v3_payload(procedures=[{"procedure_type": "unknown", "evidence_spans": [{}]}])
            )

    def test_rejects_v2_schema_version(self) -> None:
        payload = _llm1_v3_payload(procedures=[_eda_procedure()], schema_version="2.0")
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(payload)

    def test_common_preop_accepts_typed_abdominal_imaging(self) -> None:
        payload = _llm1_v3_payload(
            procedures=[_echo_procedure()],
            common_preop=_common_preop(abdominal_imaging=[_imaging()]),
        )
        validated = Llm1ResponseV3.model_validate(payload)
        evidence = validated.common_preop.abdominal_imaging[0]
        assert evidence.modality == "ct"
        assert evidence.anatomical_site == "abdomen"
        assert evidence.source_document == "main_report"

    def test_finding_present_requires_both_excerpts(self) -> None:
        # D6: o schema exige contexto e achado; a ancoragem real é do verificador.
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(
                _llm1_v3_payload(
                    procedures=[_echo_procedure()],
                    common_preop=_common_preop(
                        abdominal_imaging=[{**_imaging(), "finding_excerpt": None}],
                    ),
                )
            )
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(
                _llm1_v3_payload(
                    procedures=[_echo_procedure()],
                    common_preop=_common_preop(
                        abdominal_imaging=[{**_imaging(), "evidence_context_excerpt": "   "}],
                    ),
                )
            )

    def test_finding_absent_allows_missing_excerpts(self) -> None:
        payload = _llm1_v3_payload(
            procedures=[_echo_procedure()],
            common_preop=_common_preop(
                abdominal_imaging=[
                    {
                        **_imaging(),
                        "report_finding_present": "no",
                        "finding_excerpt": None,
                        "evidence_context_excerpt": "",
                    }
                ]
            ),
        )
        assert Llm1ResponseV3.model_validate(payload).common_preop.abdominal_imaging[0].finding_excerpt is None

    def test_rejects_other_source_document(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV3.model_validate(
                _llm1_v3_payload(
                    procedures=[_echo_procedure()],
                    common_preop=_common_preop(abdominal_imaging=[{**_imaging(), "source_document": "attachment"}]),
                )
            )


class TestLlm2V3Schema:
    def test_accepts_four_types(self) -> None:
        payload = {
            "schema_version": "3.0",
            "language": "pt-BR",
            "case_id": "c1",
            "agency_record_number": "12345",
            "procedure_recommendations": [_recommendation(t) for t in ("eda", "colonoscopy", "echoendoscopy", "cpre")],
            "global_support_recommendation": "none",
            "summary": None,
        }
        validated = Llm2ResponseV3.model_validate(payload)
        assert len(validated.procedure_recommendations) == 4

    def test_rejects_duplicates_and_v2_version(self) -> None:
        base = {
            "language": "pt-BR",
            "case_id": "c1",
            "agency_record_number": "12345",
            "global_support_recommendation": "none",
            "summary": None,
        }
        with pytest.raises(ValidationError):
            Llm2ResponseV3.model_validate(
                {
                    **base,
                    "schema_version": "3.0",
                    "procedure_recommendations": [_recommendation("eda"), _recommendation("eda")],
                }
            )
        with pytest.raises(ValidationError):
            Llm2ResponseV3.model_validate(
                {**base, "schema_version": "2.0", "procedure_recommendations": [_recommendation("eda")]}
            )


class TestHistoricalReadersRemain:
    def test_v2_payload_still_validates(self) -> None:
        assert Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_eda_procedure()])).schema_version == "2.0"

    def test_detect_schema_version_recognizes_three_contracts(self) -> None:
        assert detect_schema_version({"schema_version": "3.0"}) == "3.0"
        assert detect_schema_version({"schema_version": "2.0"}) == "2.0"
        assert detect_schema_version({"schema_version": "1.1"}) == "1.1"
        assert detect_schema_version({}) == "1.1"

    def test_v2_projection_still_available(self) -> None:
        v2_data = _llm1_v2_payload(procedures=[_eda_procedure()])
        projection = cast("dict[str, Any]", project_v2_to_llm1_shape(v2_data=v2_data, procedure_type="eda"))
        assert projection["preop_screening"]["exam_type"] == "eda"


class TestV3Adapter:
    def test_requested_types_ordered_and_specialized_aware(self) -> None:
        payload = _llm1_v3_payload(procedures=[_cpre_procedure(), _eda_procedure()])
        assert requested_procedure_types_v3(payload) == ("eda", "cpre")

    def test_projection_carries_abdominal_imaging(self) -> None:
        payload = _llm1_v3_payload(
            procedures=[_echo_procedure()],
            common_preop=_common_preop(abdominal_imaging=[_imaging()]),
        )
        projection = cast("dict[str, Any]", project_v3_to_llm1_shape(v3_data=payload, procedure_type="echoendoscopy"))
        assert projection["preop_screening"]["abdominal_imaging"][0]["modality"] == "ct"


# ── R5: agregação determinística ────────────────────────────────────────────


class TestPolicyAggregation:
    def test_accept_has_no_failed_requirements(self) -> None:
        decision = evaluate_procedure_policy(structured_data=_projection(), procedure_type="eda")
        assert decision["decision"] == "accept"
        assert decision["reason_code"] == "criteria_met"
        assert decision["failed_requirements"] == []

    def test_aggregates_all_minimum_failures_in_stable_order(self) -> None:
        projection = _projection(
            minimum={
                "hb_numeric_present": "yes",
                "platelets_numeric_present": "no",
                "tp_inr_rni_numeric_present": "yes",
                "ttpa_present": "yes",
                "urea_present": "yes",
                "creatinine_present": "no",
            }
        )
        decision = _decision(structured_data=projection, procedure_type="eda")
        assert decision["decision"] == "deny"
        # reason_code primário = primeira pendência (contrato legado preservado).
        assert decision["reason_code"] == "missing_minimum_exam_platelets"
        codes = [item["code"] for item in decision["failed_requirements"]]
        assert codes == ["missing_minimum_exam_platelets", "missing_minimum_exam_creatinine"]
        assert [item["category"] for item in decision["failed_requirements"]] == ["minimum", "minimum"]

    def test_orders_categories_minimum_then_threshold(self) -> None:
        projection = _projection(
            minimum={
                "hb_numeric_present": "no",
                "platelets_numeric_present": "yes",
                "tp_inr_rni_numeric_present": "yes",
                "ttpa_present": "yes",
                "urea_present": "yes",
                "creatinine_present": "yes",
            }
        )
        labs = projection["eda"]["labs"]
        labs["hb_g_dl"] = 5.0
        decision = _decision(structured_data=projection, procedure_type="eda")
        codes = [item["code"] for item in decision["failed_requirements"]]
        assert codes[0] == "missing_minimum_exam_hb_or_ht"
        assert "hb_below_threshold" in codes
        assert decision["reason_code"] == "missing_minimum_exam_hb_or_ht"

    def test_reason_text_matches_primary_requirement(self) -> None:
        projection = _projection(
            minimum={
                "hb_numeric_present": "yes",
                "platelets_numeric_present": "yes",
                "tp_inr_rni_numeric_present": "yes",
                "ttpa_present": "yes",
                "urea_present": "no",
                "creatinine_present": "yes",
            }
        )
        decision = _decision(structured_data=projection, procedure_type="eda")
        assert "ureia" in decision["reason_text"]

    def test_foreign_body_bypass_unchanged_for_eda(self) -> None:
        projection = _projection(subtype="foreign_body")
        decision = _decision(structured_data=projection, procedure_type="eda")
        assert decision["decision"] == "accept"
        assert decision["reason_code"] == "foreign_body_exception"
        assert decision["failed_requirements"] == []

    def test_colonoscopy_does_not_inherit_foreign_body_bypass(self) -> None:
        payload = _llm1_v3_payload(
            procedures=[_colon_procedure(subtype="standard")],
            common_preop=_common_preop(
                rulebook_signals={
                    "eda_subtype": "foreign_body",
                    "minimum_exam_evidence": {
                        "hb_numeric_present": "no",
                        "platelets_numeric_present": "yes",
                        "tp_inr_rni_numeric_present": "yes",
                        "ttpa_present": "yes",
                        "urea_present": "yes",
                        "creatinine_present": "yes",
                    },
                    "conditional_exam_requirements": {},
                    "clinical_flags": {},
                }
            ),
        )
        projection = project_v3_to_llm1_shape(v3_data=payload, procedure_type="colonoscopy")
        decision = _decision(structured_data=projection, procedure_type="colonoscopy")
        assert decision["decision"] == "deny"
        assert decision["reason_code"] == "missing_minimum_exam_hb_or_ht"

    def test_procedure_policy_covers_four_types(self) -> None:
        for procedure_type in ("eda", "colonoscopy", "echoendoscopy", "cpre"):
            projection = project_v3_to_llm1_shape(
                v3_data=_llm1_v3_payload(procedures=[_eda_procedure()]),
                procedure_type=procedure_type,
            )
            decision = _decision(structured_data=projection, procedure_type=procedure_type)
            assert decision["decision"] in {"accept", "deny"}
            assert "failed_requirements" in decision
