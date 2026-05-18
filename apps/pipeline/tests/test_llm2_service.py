from __future__ import annotations

import json

import pytest

from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm2_service import Llm2Service


def _valid_llm2_payload(case_id: str = "case-001", arn: str = "12345") -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": arn,
        "suggestion": "accept",
        "support_recommendation": "none",
        "rationale": {
            "short_reason": "Critérios atendidos.",
            "details": ["Sem contraindicação relevante.", "Exames compatíveis."],
            "missing_info_questions": [],
        },
        "policy_alignment": {
            "excluded_request": False,
            "labs_ok": "yes",
            "ecg_ok": "not_required",
            "pediatric_flag": False,
            "notes": None,
        },
        "confidence": "alta",
    }


def test_valid_legacy_payload_passes() -> None:
    client = StaticLlmClient(response_text=json.dumps(_valid_llm2_payload()))
    result = Llm2Service(client).run(
        case_id="case-001",
        agency_record_number="12345",
        llm1_structured_data={"summary": {"one_liner": "ok"}},
        system_prompt="sp",
        user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}|{prior_case}",
    )
    assert result.suggested_action["schema_version"] == "1.1"


def test_missing_case_id_fails() -> None:
    payload = _valid_llm2_payload()
    payload.pop("case_id")
    client = StaticLlmClient(response_text=json.dumps(payload))
    with pytest.raises(ValueError, match="schema validation failed"):
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={},
            system_prompt="sp",
            user_prompt_template="{llm1_structured_data}",
        )


def test_case_id_mismatch_fails() -> None:
    client = StaticLlmClient(response_text=json.dumps(_valid_llm2_payload(case_id="other")))
    with pytest.raises(ValueError, match="case_id mismatch"):
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={},
            system_prompt="sp",
            user_prompt_template="x",
        )


def test_agency_record_number_mismatch_fails() -> None:
    client = StaticLlmClient(response_text=json.dumps(_valid_llm2_payload(arn="99999")))
    with pytest.raises(ValueError, match="agency_record_number mismatch"):
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={},
            system_prompt="sp",
            user_prompt_template="x",
        )


def test_invalid_support_recommendation_fails() -> None:
    payload = _valid_llm2_payload()
    payload["support_recommendation"] = "doctor"
    client = StaticLlmClient(response_text=json.dumps(payload))
    with pytest.raises(ValueError, match="schema validation failed"):
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={},
            system_prompt="sp",
            user_prompt_template="x",
        )


def test_extra_field_fails() -> None:
    payload = _valid_llm2_payload()
    payload["extra"] = "nope"
    client = StaticLlmClient(response_text=json.dumps(payload))
    with pytest.raises(ValueError, match="schema validation failed"):
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={},
            system_prompt="sp",
            user_prompt_template="x",
        )


def test_prompt_includes_llm1_and_prior_case_json() -> None:
    client = RecordingLlmClient(responses=[json.dumps(_valid_llm2_payload())])
    Llm2Service(client).run(
        case_id="case-001",
        agency_record_number="12345",
        llm1_structured_data={"summary": {"one_liner": "Resumo"}},
        prior_case_json={"decision": "deny"},
        system_prompt="sp",
        user_prompt_template="template simples sem placeholders",
    )
    prompt = client.calls[0]["user_prompt"]
    assert "case_id: case-001" in prompt
    assert "agency_record_number: 12345" in prompt
    assert "Dados extraídos (JSON LLM1):" in prompt
    assert '"summary"' in prompt
    assert "Decisão anterior (se houver):" in prompt
    assert '"decision": "deny"' in prompt
    assert "schema_version 1.1" in prompt
    assert "policy_alignment" in prompt
    assert "confidence" in prompt
    assert "português brasileiro (pt-BR)" in prompt
