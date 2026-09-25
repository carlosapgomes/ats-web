"""Cutover 4.0 (R3/R4) — contrato strict 4.0, detalhes tipados e adapters.

Cobre:
- R3: ``Llm1ResponseV4``/``Llm2ResponseV4`` aceitam as dez identidades atômicas,
  proíbem duplicatas e definem/validam os detalhes clínicos tipados (local de
  dilatação e coleção de evidências infecciosas); o dispatch de produção
  vincula o strict schema 4.0 (``schema_version`` fixado em ``"4.0"``) e o JSON
  Schema é compatível com o strict mode (``additionalProperties: false`` e
  ``required`` completo em todo nó objeto);
- R4: os adapters continuam lendo 1.1/2.0/3.0 sem reescrita e reconhecem 4.0.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pydantic import ValidationError

from apps.cases.procedures import (
    PROCEDURE_NEUTRAL_SCHEMA_VERSIONS,
    is_procedure_neutral_structured_data,
)
from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2
from apps.pipeline.schemas.llm1_v3 import Llm1ResponseV3
from apps.pipeline.schemas.llm1_v4 import Llm1EdaGastrostomyProcedureV4, Llm1ResponseV4
from apps.pipeline.schemas.llm2_v3 import Llm2ResponseV3
from apps.pipeline.schemas.llm2_v4 import Llm2ResponseV4
from apps.pipeline.tests.test_slice_002_contracts import (
    _colon_procedure,
    _common_preop,
    _eda_procedure,
    _llm1_v2_payload,
)

ATOMIC_CODES: tuple[str, ...] = (
    "eda",
    "eda_gastrostomy",
    "eda_capsule",
    "eda_dilation",
    "colonoscopy",
    "rectosigmoidoscopy",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
    "echoendoscopy",
    "cpre",
)


# ── Builders v4 ─────────────────────────────────────────────────────────────


def _evidence(excerpt: str = "Solicito procedimento") -> dict[str, str]:
    return {"field_path": "requested_procedures.0", "excerpt": excerpt}


def _simple_procedure(code: str, *, excerpt: str | None = None) -> dict[str, Any]:
    return {
        "procedure_type": code,
        "name": code,
        "urgency": "eletivo",
        "evidence_spans": [_evidence(excerpt or f"Solicito {code}")],
    }


def _dilation_procedure(*, site: str = "unknown", excerpt: str | None = None) -> dict[str, Any]:
    return {
        **_simple_procedure("eda_dilation", excerpt="Solicito EDA com dilatacao"),
        "indication_category": "other",
        "dilation_detail": {"anatomical_site": site, "evidence_excerpt": excerpt},
    }


def _gastrostomy_procedure(*, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        **_simple_procedure("eda_gastrostomy", excerpt="Solicito EDA com GTT"),
        "indication_category": "other",
        "infection_evidence": evidence or [],
    }


def _llm1_v4_payload(*, procedures: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "4.0",
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


def _recommendation(procedure_type: str) -> dict[str, Any]:
    return {
        "procedure_type": procedure_type,
        "suggestion": "accept",
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


def _llm2_v4_payload(*, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "4.0",
        "language": "pt-BR",
        "case_id": "c1",
        "agency_record_number": "12345",
        "procedure_recommendations": recommendations,
        "global_support_recommendation": "none",
        "summary": None,
    }


# ── R3: schema LLM1 v4 ──────────────────────────────────────────────────────


class TestLlm1V4Schema:
    def test_accepts_all_ten_atomic_identities(self) -> None:
        procedures = [
            _eda_procedure(),
            _gastrostomy_procedure(),
            _simple_procedure("eda_capsule"),
            _dilation_procedure(),
            _colon_procedure(),
            _simple_procedure("rectosigmoidoscopy"),
            _simple_procedure("rectosigmoidoscopy_dilation"),
            _simple_procedure("rectosigmoidoscopy_argon"),
            _simple_procedure("echoendoscopy"),
            _simple_procedure("cpre"),
        ]
        validated = Llm1ResponseV4.model_validate(_llm1_v4_payload(procedures=procedures))
        assert tuple(item.procedure_type for item in validated.requested_procedures) == ATOMIC_CODES

    def test_rejects_duplicate_procedure_types(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(
                _llm1_v4_payload(
                    procedures=[_simple_procedure("rectosigmoidoscopy"), _simple_procedure("rectosigmoidoscopy")]
                )
            )

    def test_rejects_empty_unknown_and_old_version(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(_llm1_v4_payload(procedures=[]))
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(_llm1_v4_payload(procedures=[_simple_procedure("rectosigmoidoscopy_x")]))
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(_llm1_v4_payload(procedures=[_eda_procedure()], schema_version="3.0"))

    def test_rejects_more_than_ten_items(self) -> None:
        procedures = [_simple_procedure(code) for code in ATOMIC_CODES] + [_simple_procedure("eda")]
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(_llm1_v4_payload(procedures=procedures))

    def test_dilation_detail_accepts_closed_anatomical_vocabulary(self) -> None:
        for site in ("esophagus", "pylorus", "duodenum", "anastomosis", "jejunum", "other", "unknown"):
            excerpt = None if site == "unknown" else "dilatacao de piloro"
            payload = _llm1_v4_payload(procedures=[_dilation_procedure(site=site, excerpt=excerpt)])
            validated = Llm1ResponseV4.model_validate(payload)
            assert validated.requested_procedures[0].procedure_type == "eda_dilation"
            assert validated.requested_procedures[0].dilation_detail.anatomical_site == site

    def test_dilation_detail_requires_excerpt_when_site_is_documented(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(
                _llm1_v4_payload(procedures=[_dilation_procedure(site="pylorus", excerpt=None)])
            )

    def test_dilation_detail_rejects_unknown_site_value(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(
                _llm1_v4_payload(
                    procedures=[_dilation_procedure()],
                    # anatomical_site fora do vocabulário fechado.
                    requested_procedures=[{**_dilation_procedure(), "dilation_detail": {"anatomical_site": "colon"}}],
                )
            )

    def test_gastrostomy_carries_typed_infection_evidence(self) -> None:
        evidence: list[dict[str, Any]] = [
            {
                "category": "crp",
                "assessment": "abnormal_explicit",
                "temporal_status": "current",
                "value_text": "PCR 120 mg/L",
                "evidence_excerpt": "PCR 120 mg/L",
            },
            {
                "category": "culture",
                "assessment": "negative_explicit",
                "temporal_status": "current",
                "value_text": None,
                "evidence_excerpt": "hemoculturas negativas",
            },
        ]
        validated = Llm1ResponseV4.model_validate(
            _llm1_v4_payload(procedures=[_gastrostomy_procedure(evidence=evidence)])
        )
        item = validated.requested_procedures[0]
        assert isinstance(item, Llm1EdaGastrostomyProcedureV4)
        assert item.procedure_type == "eda_gastrostomy"
        assert [entry.category for entry in item.infection_evidence] == ["crp", "culture"]

    def test_infection_evidence_rejects_unknown_category_or_empty_excerpt(self) -> None:
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(
                _llm1_v4_payload(
                    procedures=[
                        _gastrostomy_procedure(
                            evidence=[
                                {
                                    "category": "xray",
                                    "assessment": "unclassified",
                                    "temporal_status": "unknown",
                                    "value_text": None,
                                    "evidence_excerpt": "algo",
                                }
                            ]
                        )
                    ]
                )
            )
        with pytest.raises(ValidationError):
            Llm1ResponseV4.model_validate(
                _llm1_v4_payload(
                    procedures=[
                        _gastrostomy_procedure(
                            evidence=[
                                {
                                    "category": "lactate",
                                    "assessment": "unclassified",
                                    "temporal_status": "unknown",
                                    "value_text": None,
                                    "evidence_excerpt": "   ",
                                }
                            ]
                        )
                    ]
                )
            )

    def test_infection_evidence_defaults_to_empty_collection(self) -> None:
        validated = Llm1ResponseV4.model_validate(_llm1_v4_payload(procedures=[_gastrostomy_procedure()]))
        item = validated.requested_procedures[0]
        assert isinstance(item, Llm1EdaGastrostomyProcedureV4)
        assert item.infection_evidence == []


class TestLlm2V4Schema:
    def test_accepts_all_ten_atomic_identities(self) -> None:
        validated = Llm2ResponseV4.model_validate(
            _llm2_v4_payload(recommendations=[_recommendation(code) for code in ATOMIC_CODES])
        )
        assert tuple(item.procedure_type for item in validated.procedure_recommendations) == ATOMIC_CODES

    def test_rejects_duplicates_unknown_and_old_version(self) -> None:
        with pytest.raises(ValidationError):
            Llm2ResponseV4.model_validate(
                _llm2_v4_payload(recommendations=[_recommendation("eda"), _recommendation("eda")])
            )
        with pytest.raises(ValidationError):
            Llm2ResponseV4.model_validate(_llm2_v4_payload(recommendations=[_recommendation("foo")]))
        with pytest.raises(ValidationError):
            Llm2ResponseV4.model_validate(
                {**_llm2_v4_payload(recommendations=[_recommendation("eda")]), "schema_version": "3.0"}
            )


# ── R3: dispatch de produção e compatibilidade strict ───────────────────────


class TestProductionDispatchBindsV4:
    def _bound_schema(self, factory: Any) -> dict[str, Any]:
        from unittest.mock import MagicMock, patch

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_completion = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = '{"schema_version": "4.0"}'
            mock_completion.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_completion

            client = factory()
            client.complete(system_prompt="sys", user_prompt="usr")
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            return cast("dict[str, Any]", call_kwargs["response_format"])

    def test_llm1_production_client_binds_v4_strict_schema(self, settings: Any) -> None:
        from apps.pipeline.llm1_service_v4 import create_openai_llm1_v4_client

        response_format = self._bound_schema(create_openai_llm1_v4_client)
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        schema = response_format["json_schema"]["schema"]
        schema_version = schema["properties"]["schema_version"]
        if "const" in schema_version:
            assert schema_version["const"] == "4.0"
        else:
            assert schema_version["enum"] == ["4.0"]
        serialized = json.dumps(schema)
        for code in ATOMIC_CODES:
            assert code in serialized

    def test_llm2_production_client_binds_v4_strict_schema(self, settings: Any) -> None:
        from apps.pipeline.llm2_service_v4 import create_openai_llm2_v4_client

        response_format = self._bound_schema(create_openai_llm2_v4_client)
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True
        serialized = json.dumps(response_format["json_schema"]["schema"])
        for code in ATOMIC_CODES:
            assert code in serialized

    @pytest.mark.parametrize("model", [Llm1ResponseV4, Llm2ResponseV4])
    def test_strict_schema_is_compatible_with_openai_strict_mode(self, model: Any) -> None:
        from apps.pipeline.llm import _normalize_openai_strict_schema

        normalized = _normalize_openai_strict_schema(model.model_json_schema())

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                    assert node.get("additionalProperties") is False
                    assert set(node["required"]) == set(node["properties"])
                assert "oneOf" not in node
                assert "discriminator" not in node
                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for value in node:
                    _walk(value)

        _walk(normalized)


# ── R4: adapters históricos e reconhecimento do 4.0 ─────────────────────────


class TestAdaptersRecognizeV4:
    def test_detect_schema_version_recognizes_four_contracts(self) -> None:
        from apps.pipeline.schemas.adapters import detect_schema_version

        assert detect_schema_version({"schema_version": "4.0"}) == "4.0"
        assert detect_schema_version({"schema_version": "3.0"}) == "3.0"
        assert detect_schema_version({"schema_version": "2.0"}) == "2.0"
        assert detect_schema_version({"schema_version": "1.1"}) == "1.1"
        assert detect_schema_version({}) == "1.1"

    def test_requested_types_v4_is_ordered_and_catalog_bounded(self) -> None:
        from apps.pipeline.schemas.adapters import requested_procedure_types_v4

        payload = _llm1_v4_payload(
            procedures=[_simple_procedure("cpre"), _simple_procedure("eda_capsule"), _simple_procedure("unknown_thing")]
        )
        assert requested_procedure_types_v4(payload) == ("eda_capsule", "cpre")
        assert requested_procedure_types_v4({}) == ()

    def test_project_v4_to_llm1_shape_feeds_policy_readers(self) -> None:
        from apps.pipeline.schemas.adapters import project_v4_to_llm1_shape

        payload = _llm1_v4_payload(procedures=[_eda_procedure()])
        projection = project_v4_to_llm1_shape(v4_data=payload, procedure_type="eda")
        assert projection["schema_version"] == "1.1"
        preop = cast("dict[str, Any]", projection["preop_screening"])
        assert preop["exam_type"] == "eda"

    def test_historical_payloads_still_validate(self) -> None:
        assert (
            Llm1ResponseV3.model_validate(
                {**_llm1_v4_payload(procedures=[_eda_procedure()]), "schema_version": "3.0"}
            ).schema_version
            == "3.0"
        )
        assert Llm1ResponseV2.model_validate(_llm1_v2_payload(procedures=[_eda_procedure()])).schema_version == "2.0"
        assert (
            Llm2ResponseV3.model_validate(
                {
                    "schema_version": "3.0",
                    "language": "pt-BR",
                    "case_id": "c1",
                    "agency_record_number": "12345",
                    "procedure_recommendations": [_recommendation("eda")],
                    "global_support_recommendation": "none",
                    "summary": None,
                }
            ).schema_version
            == "3.0"
        )

    def test_procedure_neutral_gate_recognizes_v4(self) -> None:
        assert "4.0" in PROCEDURE_NEUTRAL_SCHEMA_VERSIONS
        assert is_procedure_neutral_structured_data({"schema_version": "4.0"}) is True
        assert is_procedure_neutral_structured_data({"schema_version": "3.0"}) is True
        assert is_procedure_neutral_structured_data({"schema_version": "1.1"}) is False
