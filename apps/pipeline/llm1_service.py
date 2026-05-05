"""LLM1 Service — structured data extraction from medical reports."""

from __future__ import annotations

from dataclasses import dataclass

from apps.pipeline.json_parser import decode_llm_json_object
from apps.pipeline.llm import LlmClient


@dataclass
class Llm1Result:
    """Result from LLM1 structured extraction."""

    structured_data: dict[str, object]
    summary_text: str


class Llm1Service:
    """Calls LLM1: extracts structured data from raw medical text.

    Simplifications vs legacy (Fase 2):
    - No Pydantic validation — only checks valid JSON + schema_version
    - No language guard — will be added in a future phase
    - No interaction repository — audit events handled via CaseEvent
    """

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        extracted_text: str,
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm1Result:
        """Execute LLM1 extraction.

        Args:
            case_id: Unique case identifier.
            agency_record_number: Agency record number from PDF.
            extracted_text: Raw text extracted from the medical report.
            system_prompt: System prompt for the LLM.
            user_prompt_template: Template with {case_id}, {agency_record_number},
                and {extracted_text} placeholders.

        Returns:
            Llm1Result with structured_data dict and one-liner summary.

        Raises:
            LlmJsonParseError: If LLM response is not valid JSON.
        """
        user_prompt = user_prompt_template.format(
            case_id=case_id,
            agency_record_number=agency_record_number,
            extracted_text=extracted_text,
        )

        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        structured_data = decode_llm_json_object(raw_response)

        # Extract summary one-liner
        summary = structured_data.get("summary", {})
        if isinstance(summary, dict):
            summary_text = str(summary.get("one_liner", ""))
        else:
            summary_text = ""

        return Llm1Result(
            structured_data=structured_data,
            summary_text=summary_text,
        )
