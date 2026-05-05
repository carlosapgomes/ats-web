"""Tests for LLM2 Service — decision suggestion."""

from __future__ import annotations

import json

import pytest

from apps.pipeline.json_parser import LlmJsonParseError
from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm2_service import Llm2Result, Llm2Service


class TestLlm2ReturnsSuggestion:
    """LLM2 deve retornar suggested_action parseado da resposta do client."""

    def test_llm2_returns_suggestion(self) -> None:
        llm_response = json.dumps(
            {
                "decision": "accept",
                "priority": "elective",
                "reasoning": "Paciente com dispepsia crônica. EDA indicada.",
            }
        )
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        result = service.run(
            case_id="case-010",
            agency_record_number="AR12345",
            llm1_structured_data={"patient": {"age": 45}},
            system_prompt="Suggest clinical decision.",
            user_prompt_template=("Case: {case_id}\nRecord: {agency_record_number}\nData: {llm1_structured_data}"),
        )

        assert isinstance(result, Llm2Result)
        assert result.suggested_action["decision"] == "accept"
        assert result.suggested_action["priority"] == "elective"
        assert result.contradictions == []

    def test_llm2_suggested_action_is_full_dict(self) -> None:
        llm_response = json.dumps(
            {
                "decision": "deny",
                "reasoning": "Paciente não atende critérios para EDA.",
                "alternative": "Avaliação clínica ambulatorial.",
            }
        )
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        result = service.run(
            case_id="case-011",
            agency_record_number="AR67890",
            llm1_structured_data={"urgency": "immediate"},
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        assert result.suggested_action["decision"] == "deny"
        assert result.suggested_action["alternative"] == "Avaliação clínica ambulatorial."


class TestLlm2ReceivesLlm1Data:
    """LLM2 deve incluir llm1_structured_data serializado no user_prompt."""

    def test_llm2_receives_llm1_data(self) -> None:
        llm_response = json.dumps({"decision": "accept"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm2Service(client)

        llm1_data: dict[str, object] = {
            "patient": {"name": "João", "age": 50},
            "findings": ["gastritis", "h_pylori"],
        }

        service.run(
            case_id="case-012",
            agency_record_number="AR33333",
            llm1_structured_data=llm1_data,
            system_prompt="You are a clinical decision assistant.",
            user_prompt_template=(
                "Case: {case_id}\nRecord: {agency_record_number}\nExtracted data:\n{llm1_structured_data}"
            ),
        )

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["system_prompt"] == "You are a clinical decision assistant."
        assert "Case: case-012" in call["user_prompt"]
        assert "Record: AR33333" in call["user_prompt"]
        # Verify llm1 data is embedded as JSON
        assert '"patient"' in call["user_prompt"]
        assert '"gastritis"' in call["user_prompt"]

    def test_llm2_llm1_data_is_valid_json_in_prompt(self) -> None:
        llm_response = json.dumps({"decision": "accept"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm2Service(client)

        llm1_data: dict[str, object] = {"summary": {"one_liner": "Test summary"}}

        service.run(
            case_id="C-1",
            agency_record_number="R-1",
            llm1_structured_data=llm1_data,
            system_prompt="SP",
            user_prompt_template="{llm1_structured_data}",
        )

        call = client.calls[0]
        # The prompt should contain valid JSON for llm1 data
        assert "Test summary" in call["user_prompt"]
        # Verify it's valid JSON at the position of {llm1_structured_data}
        parsed = json.loads(call["user_prompt"])
        assert parsed == llm1_data


class TestLlm2RaisesOnInvalidJson:
    """LLM2 deve levantar erro quando o client retorna JSON inválido."""

    def test_llm2_raises_on_plain_text_response(self) -> None:
        client = StaticLlmClient(response_text="not json at all")
        service = Llm2Service(client)

        with pytest.raises(LlmJsonParseError):
            service.run(
                case_id="case-013",
                agency_record_number="AR00001",
                llm1_structured_data={"patient": {"age": 30}},
                system_prompt="...",
                user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
            )

    def test_llm2_raises_on_empty_response(self) -> None:
        client = StaticLlmClient(response_text="")
        service = Llm2Service(client)

        with pytest.raises(LlmJsonParseError):
            service.run(
                case_id="case-014",
                agency_record_number="AR00002",
                llm1_structured_data={},
                system_prompt="...",
                user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
            )


class TestLlm2Contradictions:
    """contradictions deve começar como lista vazia."""

    def test_llm2_contradictions_starts_empty(self) -> None:
        llm_response = json.dumps({"decision": "accept"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        result = service.run(
            case_id="case-015",
            agency_record_number="AR99999",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        assert result.contradictions == []
        assert isinstance(result.contradictions, list)
