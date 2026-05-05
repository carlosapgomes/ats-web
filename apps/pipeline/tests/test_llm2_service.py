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


class TestLlm2IdentityValidation:
    """LLM2 deve validar case_id e agency_record_number na resposta."""

    def test_case_id_mismatch_raises_value_error(self) -> None:
        llm_response = json.dumps({"case_id": "wrong-id", "decision": "accept"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        with pytest.raises(ValueError, match="case_id mismatch"):
            service.run(
                case_id="expected-id",
                agency_record_number="AR12345",
                llm1_structured_data={},
                system_prompt="...",
                user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
            )

    def test_agency_record_number_mismatch_raises_value_error(self) -> None:
        llm_response = json.dumps({"agency_record_number": "WRONG", "decision": "accept"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        with pytest.raises(ValueError, match="agency_record_number mismatch"):
            service.run(
                case_id="case-001",
                agency_record_number="AR99999",
                llm1_structured_data={},
                system_prompt="...",
                user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
            )

    def test_matching_case_id_passes(self) -> None:
        llm_response = json.dumps({"case_id": "case-001", "decision": "accept"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        result = service.run(
            case_id="case-001",
            agency_record_number="AR12345",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        assert result.suggested_action["decision"] == "accept"

    def test_missing_case_id_in_response_passes(self) -> None:
        """Se response não tem case_id, a validação é skipada."""
        llm_response = json.dumps({"decision": "accept"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        result = service.run(
            case_id="case-001",
            agency_record_number="AR12345",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        assert result.suggested_action["decision"] == "accept"

    def test_case_id_integer_matches_string(self) -> None:
        """case_id como int no JSON deve ser comparado como string."""
        llm_response = json.dumps({"case_id": 42, "decision": "accept"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm2Service(client)

        result = service.run(
            case_id="42",
            agency_record_number="AR12345",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{llm1_structured_data}",
        )

        assert result.suggested_action["decision"] == "accept"


class TestLlm2PriorCase:
    """LLM2 deve incluir prior_case_json no prompt quando fornecido."""

    def test_prior_case_included_in_prompt(self) -> None:
        llm_response = json.dumps({"decision": "accept"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm2Service(client)

        prior_case: dict[str, object] = {
            "previous_decision": "deny",
            "previous_reasoning": "Exames insuficientes",
        }

        service.run(
            case_id="case-020",
            agency_record_number="AR55555",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="Prior: {prior_case}\nCase: {case_id}",
            prior_case_json=prior_case,
        )

        call = client.calls[0]
        assert "previous_decision" in call["user_prompt"]
        assert "deny" in call["user_prompt"]
        assert 'Exames insuficientes"' in call["user_prompt"]

    def test_prior_case_none_renders_null(self) -> None:
        llm_response = json.dumps({"decision": "accept"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm2Service(client)

        service.run(
            case_id="case-021",
            agency_record_number="AR66666",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="Prior: {prior_case}",
            prior_case_json=None,
        )

        call = client.calls[0]
        assert "null" in call["user_prompt"]

    def test_prior_case_omitted_renders_null(self) -> None:
        """Quando prior_case_json não é passado, default None → 'null'."""
        llm_response = json.dumps({"decision": "accept"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm2Service(client)

        service.run(
            case_id="case-022",
            agency_record_number="AR77777",
            llm1_structured_data={},
            system_prompt="...",
            user_prompt_template="Prior: {prior_case}",
        )

        call = client.calls[0]
        assert "null" in call["user_prompt"]


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
