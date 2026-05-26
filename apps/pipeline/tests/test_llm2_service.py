from __future__ import annotations

import json
from typing import Any

import pytest

from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm2_service import Llm2Service


def _valid_llm2_payload(case_id: str = "case-001", arn: str = "12345") -> dict[str, Any]:
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


# ── Language retry LLM2 ─────────────────────────────────────────────────────


class TestLlm2LanguageRetry:
    """LLM2 deve fazer retry de linguagem em campos narrativos."""

    def test_no_retry_when_all_ptbr(self) -> None:
        """Sem termos proibidos, apenas uma chamada."""
        payload = _valid_llm2_payload()
        client = RecordingLlmClient(responses=[json.dumps(payload)])
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={"summary": {"one_liner": "ok"}},
            system_prompt="sp",
            user_prompt_template="x",
        )
        assert len(client.calls) == 1

    def test_retries_once_when_rationale_has_english(self) -> None:
        """Primeira resposta com 'patient' no rationale → retry é chamado."""
        payload1 = _valid_llm2_payload()
        payload1["rationale"]["short_reason"] = "Patient meets criteria for accept."
        payload2 = _valid_llm2_payload()
        payload2["rationale"]["short_reason"] = "Paciente atende aos critérios."

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={"summary": {"one_liner": "ok"}},
            system_prompt="sp",
            user_prompt_template="x",
        )
        assert len(client.calls) == 2
        assert "Regra obrigatoria adicional" in client.calls[1]["user_prompt"]

    def test_raises_when_both_have_forbidden_terms(self) -> None:
        """Ambas as respostas com termos proibidos → ValueError."""
        payload1 = _valid_llm2_payload()
        payload1["rationale"]["short_reason"] = "Patient accepted for EDA."
        payload2 = _valid_llm2_payload()
        payload2["rationale"]["details"] = ["Patient denied.", "Reason unknown."]

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        with pytest.raises(ValueError, match="non-ptbr"):
            Llm2Service(client).run(
                case_id="case-001",
                agency_record_number="12345",
                llm1_structured_data={"summary": {"one_liner": "ok"}},
                system_prompt="sp",
                user_prompt_template="x",
            )
        assert len(client.calls) == 2

    def test_forbidden_term_in_policy_notes_triggers_retry(self) -> None:
        """Termo proibido em policy_alignment.notes também dispara retry."""
        payload1 = _valid_llm2_payload()
        payload1["policy_alignment"]["notes"] = "Patient has no reason for denial."
        payload2 = _valid_llm2_payload()
        payload2["policy_alignment"]["notes"] = None

        client = RecordingLlmClient(
            responses=[
                json.dumps(payload1),
                json.dumps(payload2),
            ]
        )
        Llm2Service(client).run(
            case_id="case-001",
            agency_record_number="12345",
            llm1_structured_data={"summary": {"one_liner": "ok"}},
            system_prompt="sp",
            user_prompt_template="x",
        )
        assert len(client.calls) == 2
