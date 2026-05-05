"""LLM JSON response parser.

Handles common LLM response quirks: markdown code blocks, trailing commas,
embedded JSON in text, and other minor formatting issues.

Parsing strategies (tried in order):
1. json.loads directly
2. Strip markdown code fences + json.loads
3. Remove trailing commas + json.loads
4. Scan for first embedded JSON object via JSONDecoder.raw_decode
"""

from __future__ import annotations

import json
import re


class LlmJsonParseError(ValueError):
    """Raised when LLM response cannot be parsed as JSON."""


def decode_llm_json_object(raw_response: str) -> dict[str, object]:
    """Extract JSON object from LLM response.

    Handles:
    - Raw JSON strings
    - JSON inside markdown code blocks (```json ... ```)
    - Trailing commas (stripped)
    - JSON embedded in arbitrary text (last-resort scan)
    """
    # Strategy 1: direct json.loads
    stripped = raw_response.strip()
    try:
        return json.loads(stripped)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown code blocks
    text = stripped
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Strategy 3: remove trailing commas
    clean = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(clean)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Strategy 4: scan for first embedded JSON object
    return _extract_first_embedded_json_object(text)


def _extract_first_embedded_json_object(text: str) -> dict[str, object]:
    """Scan for the first JSON object embedded in arbitrary text.

    Uses JSONDecoder.raw_decode() to find and parse the first complete
    JSON object starting with '{'.  Raises LlmJsonParseError if none found.
    """
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        if text[idx] == "{":
            try:
                obj, _end = decoder.raw_decode(text, idx)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        idx += 1
    raise LlmJsonParseError("Failed to parse LLM response as JSON: no JSON object found")
