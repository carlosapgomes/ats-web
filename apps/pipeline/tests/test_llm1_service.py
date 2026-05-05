"""Tests for LLM1 Service — structured data extraction."""

from __future__ import annotations

import json

import pytest

from apps.pipeline.json_parser import LlmJsonParseError
from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm1_service import Llm1Result, Llm1Service


class TestLlm1ReturnsStructuredData:
    """LLM1 deve retornar structured_data parseado da resposta do client."""

    def test_llm1_returns_structured_data(self) -> None:
        llm_response = json.dumps(
            {
                "schema_version": "1.0",
                "patient": {"age": 45, "gender": "F"},
                "clinical_history": "Paciente com dispepsia crônica.",
            }
        )
        client = StaticLlmClient(response_text=llm_response)
        service = Llm1Service(client)

        result = service.run(
            case_id="case-001",
            agency_record_number="AR12345",
            extracted_text="Paciente referiu dor epigástrica.",
            system_prompt="Extract structured data from the report.",
            user_prompt_template=("Case: {case_id}\nRecord: {agency_record_number}\nText: {extracted_text}"),
        )

        assert isinstance(result, Llm1Result)
        assert result.structured_data["schema_version"] == "1.0"
        assert result.structured_data["patient"] == {"age": 45, "gender": "F"}

    def test_llm1_structured_data_is_full_dict(self) -> None:
        llm_response = json.dumps(
            {
                "schema_version": "2.0",
                "findings": ["gastritis", "h_pylori"],
                "urgency": "elective",
            }
        )
        client = StaticLlmClient(response_text=llm_response)
        service = Llm1Service(client)

        result = service.run(
            case_id="case-002",
            agency_record_number="AR67890",
            extracted_text="...",
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        assert result.structured_data == {
            "schema_version": "2.0",
            "findings": ["gastritis", "h_pylori"],
            "urgency": "elective",
        }


class TestLlm1ExtractsSummaryText:
    """LLM1 deve extrair summary.one_liner como summary_text."""

    def test_llm1_extracts_summary_text(self) -> None:
        llm_response = json.dumps(
            {
                "schema_version": "1.0",
                "summary": {"one_liner": "Dispepsia crônica — EDA eletiva indicada."},
            }
        )
        client = StaticLlmClient(response_text=llm_response)
        service = Llm1Service(client)

        result = service.run(
            case_id="case-003",
            agency_record_number="AR99999",
            extracted_text="...",
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        assert result.summary_text == "Dispepsia crônica — EDA eletiva indicada."

    def test_llm1_summary_text_empty_when_missing(self) -> None:
        llm_response = json.dumps({"schema_version": "1.0"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm1Service(client)

        result = service.run(
            case_id="case-004",
            agency_record_number="AR00000",
            extracted_text="...",
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        assert result.summary_text == ""

    def test_llm1_summary_text_empty_when_summary_not_dict(self) -> None:
        llm_response = json.dumps({"schema_version": "1.0", "summary": "not a dict"})
        client = StaticLlmClient(response_text=llm_response)
        service = Llm1Service(client)

        result = service.run(
            case_id="case-005",
            agency_record_number="AR55555",
            extracted_text="...",
            system_prompt="...",
            user_prompt_template="{case_id}|{agency_record_number}|{extracted_text}",
        )

        assert result.summary_text == ""


class TestLlm1RaisesOnInvalidJson:
    """LLM1 deve levantar erro quando o client retorna JSON inválido."""

    def test_llm1_raises_on_plain_text_response(self) -> None:
        client = StaticLlmClient(response_text="just some random text")
        service = Llm1Service(client)

        with pytest.raises(LlmJsonParseError):
            service.run(
                case_id="case-006",
                agency_record_number="AR00001",
                extracted_text="...",
                system_prompt="...",
                user_prompt_template="{case_id}|{agency_record_number}|{extracted_text}",
            )

    def test_llm1_raises_on_empty_response(self) -> None:
        client = StaticLlmClient(response_text="")
        service = Llm1Service(client)

        with pytest.raises(LlmJsonParseError):
            service.run(
                case_id="case-007",
                agency_record_number="AR00002",
                extracted_text="...",
                system_prompt="...",
                user_prompt_template="{case_id}|{agency_record_number}|{extracted_text}",
            )


class TestLlm1UsesPrompts:
    """LLM1 deve passar system_prompt e user_prompt renderizado ao client."""

    def test_llm1_uses_prompts(self) -> None:
        llm_response = json.dumps({"schema_version": "1.0"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm1Service(client)

        service.run(
            case_id="case-008",
            agency_record_number="AR11111",
            extracted_text="Texto extraído do PDF.",
            system_prompt="You are a medical data extractor.",
            user_prompt_template=(
                "Case ID: {case_id}\nRecord #: {agency_record_number}\nReport text:\n{extracted_text}"
            ),
        )

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["system_prompt"] == "You are a medical data extractor."
        assert "Case ID: case-008" in call["user_prompt"]
        assert "Record #: AR11111" in call["user_prompt"]
        assert "Texto extraído do PDF." in call["user_prompt"]

    def test_llm1_template_substitution_is_exact(self) -> None:
        llm_response = json.dumps({"schema_version": "1.0"})
        client = RecordingLlmClient(responses=[llm_response])
        service = Llm1Service(client)

        service.run(
            case_id="CASE-X",
            agency_record_number="REC-Y",
            extracted_text="Some text",
            system_prompt="SP",
            user_prompt_template="case={case_id}, rec={agency_record_number}, txt={extracted_text}",
        )

        call = client.calls[0]
        assert call["user_prompt"] == "case=CASE-X, rec=REC-Y, txt=Some text"
