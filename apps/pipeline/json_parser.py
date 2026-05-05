"""LLM JSON response parser.

Handles common LLM response quirks: markdown code blocks, trailing commas,
and other minor formatting issues.
"""

from __future__ import annotations

import json
import re


class LlmJsonParseError(RuntimeError):
    """Raised when LLM response cannot be parsed as JSON."""


def decode_llm_json_object(raw_response: str) -> dict[str, object]:
    """Extract JSON object from LLM response.

    Handles:
    - Raw JSON strings
    - JSON inside markdown code blocks (```json ... ```)
    - Trailing commas (stripped)
    """
    text = raw_response.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fenced lines (```json and ```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Remove trailing commas (common LLM formatting issue)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise LlmJsonParseError(f"Failed to parse LLM response as JSON: {exc}") from exc
