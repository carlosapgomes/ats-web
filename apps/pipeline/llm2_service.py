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
        prior_case_json: dict[str, object] | None = None,
    ) -> Llm2Result:
        """Execute LLM2 suggestion.

        Args:
            case_id: Unique case identifier.
            agency_record_number: Agency record number from PDF.
            llm1_structured_data: Structured data output from LLM1.
            system_prompt: System prompt for the LLM.
            user_prompt_template: Template with {case_id}, {agency_record_number},
                {llm1_structured_data}, and optionally {prior_case} placeholders.
            prior_case_json: Optional prior case data for context. Serialized
                as JSON and included in the prompt via {prior_case} placeholder.

        Returns:
            Llm2Result with suggested_action dict and empty contradictions list.

        Raises:
            ValueError: If the LLM response contains a ``case_id`` or
                ``agency_record_number`` field that doesn't match the
                supplied values (hallucination guard).
            LlmJsonParseError: If LLM response is not valid JSON.
        """
        # Serialize structured data to JSON string for template rendering
        llm1_json = json.dumps(llm1_structured_data, ensure_ascii=False, indent=2)

        # Serialize prior case (if any)
        prior_case = json.dumps(
            prior_case_json if prior_case_json is not None else None,
            ensure_ascii=False,
            indent=2,
        )

        user_prompt = user_prompt_template.format(
            case_id=case_id,
            agency_record_number=agency_record_number,
            llm1_structured_data=llm1_json,
            prior_case=prior_case,
        )

        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        suggested_action = decode_llm_json_object(raw_response)

        # Hallucination guard: validate case_id and agency_record_number
        _validate_identity(suggested_action, case_id, agency_record_number)

        return Llm2Result(
            suggested_action=suggested_action,
            contradictions=[],
        )


def _validate_identity(
    response: dict[str, object],
    expected_case_id: str,
    expected_arn: str,
) -> None:
    """Validate that the LLM response matches the expected case identity.

    If the response includes case_id or agency_record_number fields and
    they don't match the expected values, raise ValueError (hallucination).
    """
    response_case_id = response.get("case_id")
    if response_case_id is not None and str(response_case_id) != str(expected_case_id):
        raise ValueError(f"LLM2 case_id mismatch: expected {expected_case_id!r}, got {response_case_id!r}")

    response_arn = response.get("agency_record_number")
    if response_arn is not None and str(response_arn) != str(expected_arn):
        raise ValueError(f"LLM2 agency_record_number mismatch: expected {expected_arn!r}, got {response_arn!r}")
