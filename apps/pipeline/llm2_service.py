"""LLM2 Service — decision suggestion based on LLM1 structured data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from apps.pipeline.json_parser import decode_llm_json_object
from apps.pipeline.llm import LlmClient


@dataclass
class Llm2Result:
    """Result from LLM2 decision suggestion."""

    suggested_action: dict[str, object]
    contradictions: list[dict[str, object]] = field(default_factory=list)


class Llm2Service:
    """Calls LLM2: suggests a clinical decision based on LLM1 output.

    The service receives LLM1 structured data, formats a prompt with it,
    calls the LLM, and returns a suggested action.

    contradictions starts empty — will be filled by the reconciliation step
    in a later slice.
    """

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        llm1_structured_data: dict[str, object],
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm2Result:
        """Execute LLM2 suggestion.

        Args:
            case_id: Unique case identifier.
            agency_record_number: Agency record number from PDF.
            llm1_structured_data: Structured data output from LLM1.
            system_prompt: System prompt for the LLM.
            user_prompt_template: Template with {case_id}, {agency_record_number},
                and {llm1_structured_data} placeholders.

        Returns:
            Llm2Result with suggested_action dict and empty contradictions list.

        Raises:
            LlmJsonParseError: If LLM response is not valid JSON.
        """
        # Serialize structured data to JSON string for template rendering
        llm1_json = json.dumps(llm1_structured_data, ensure_ascii=False, indent=2)

        user_prompt = user_prompt_template.format(
            case_id=case_id,
            agency_record_number=agency_record_number,
            llm1_structured_data=llm1_json,
        )

        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        suggested_action = decode_llm_json_object(raw_response)

        return Llm2Result(
            suggested_action=suggested_action,
            contradictions=[],
        )
