"""LLM2 Service — decision suggestion based on LLM1 structured data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from apps.pipeline.json_parser import decode_llm_json_object
from apps.pipeline.llm import LlmClient
from apps.pipeline.ptbr_language_guard import collect_forbidden_terms
from apps.pipeline.schemas.llm2 import Llm2Response

# ── Language retry instruction ──────────────────────────────────────────

_LANGUAGE_RETRY_INSTRUCTION = (
    "Regra obrigatoria adicional: todo texto narrativo deve estar em portugues "
    "brasileiro (pt-BR), sem palavras em ingles."
)


@dataclass
class Llm2Result:
    """Result from LLM2 decision suggestion."""

    suggested_action: dict[str, object]
    contradictions: list[dict[str, object]] = field(default_factory=list)


class Llm2Service:
    """Calls LLM2: suggests a clinical decision based on LLM1 output.

    The service receives LLM1 structured data, formats a prompt with it,
    calls the LLM, and returns a suggested action.

    Includes language retry: if validated output contains forbidden
    English terms in narrative fields (rationale, policy_alignment.notes),
    a single retry with an additional pt-BR instruction is attempted.

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
                supplied values (hallucination guard), or if language
                retry fails after two attempts.
            LlmJsonParseError: If LLM response is not valid JSON.
        """
        user_prompt = _render_user_prompt(
            template=user_prompt_template,
            case_id=case_id,
            agency_record_number=agency_record_number,
            llm1_structured_data=llm1_structured_data,
            prior_case_json=prior_case_json,
        )

        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        decoded = decode_llm_json_object(raw_response)

        try:
            validated = Llm2Response.model_validate(decoded)
        except ValidationError as exc:
            raise ValueError(f"LLM2 schema validation failed: {exc}") from exc

        if validated.case_id != str(case_id):
            raise ValueError(f"LLM2 case_id mismatch: expected {case_id!r}, got {validated.case_id!r}")
        if validated.agency_record_number != str(agency_record_number):
            raise ValueError(
                "LLM2 agency_record_number mismatch: "
                f"expected {agency_record_number!r}, got {validated.agency_record_number!r}"
            )

        # Language guard: retry once with pt-BR instruction if needed
        forbidden_terms = _collect_llm2_forbidden_terms(validated=validated)
        if forbidden_terms:
            retry_user_prompt = f"{user_prompt}\n\n{_LANGUAGE_RETRY_INSTRUCTION}"
            retry_response = self._client.complete(
                system_prompt=system_prompt,
                user_prompt=retry_user_prompt,
            )
            retry_decoded = decode_llm_json_object(retry_response)
            try:
                validated = Llm2Response.model_validate(retry_decoded)
            except ValidationError as exc:
                raise ValueError(f"LLM2 schema validation failed on retry: {exc}") from exc

            if validated.case_id != str(case_id):
                raise ValueError(f"LLM2 case_id mismatch on retry: expected {case_id!r}, got {validated.case_id!r}")
            if validated.agency_record_number != str(agency_record_number):
                raise ValueError(
                    "LLM2 agency_record_number mismatch on retry: "
                    f"expected {agency_record_number!r}, got {validated.agency_record_number!r}"
                )

            forbidden_terms = _collect_llm2_forbidden_terms(validated=validated)
            if forbidden_terms:
                joined_terms = ", ".join(forbidden_terms)
                raise ValueError(f"LLM2 output contains non-ptbr narrative terms after retry: {joined_terms}")

        return Llm2Result(
            suggested_action=validated.model_dump(mode="json"),
            contradictions=[],
        )


def _render_user_prompt(
    *,
    template: str,
    case_id: str,
    agency_record_number: str,
    llm1_structured_data: dict[str, object],
    prior_case_json: dict[str, object] | None,
) -> str:
    prior_case = json.dumps(
        prior_case_json if prior_case_json is not None else None,
        ensure_ascii=False,
    )
    llm1_json = json.dumps(llm1_structured_data, ensure_ascii=False)
    return (
        f"{template}\n\n"
        f"case_id: {case_id}\n"
        f"agency_record_number: {agency_record_number}\n\n"
        f"Dados extraídos (JSON LLM1):\n{llm1_json}\n\n"
        f"Decisão anterior (se houver):\n{prior_case}\n\n"
        "Retorne JSON schema_version 1.1 com policy_alignment e confidence.\n"
        "Todos os campos narrativos devem estar em português brasileiro (pt-BR).\n"
        "Não use palavras em inglês nos campos narrativos."
    )


def _collect_llm2_forbidden_terms(*, validated: Llm2Response) -> list[str]:
    """Collect forbidden English terms across all LLM2 narrative fields.

    Ported from the legacy _collect_llm2_forbidden_terms() in llm2_service.py.
    """
    texts: list[str] = [
        validated.rationale.short_reason,
        *validated.rationale.details,
        *validated.rationale.missing_info_questions,
    ]
    if validated.policy_alignment.notes is not None:
        texts.append(validated.policy_alignment.notes)
    return collect_forbidden_terms(texts=texts)
