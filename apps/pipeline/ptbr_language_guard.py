"""Utilities for detecting obvious English residue in narrative pt-BR outputs.

Ported from the legacy augmented-triage-system:
  src/triage_automation/application/services/ptbr_language_guard.py
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_FORBIDDEN_ENGLISH_TERMS_PATTERN = re.compile(
    r"\b("
    r"accept|accepted|deny|denied|support|reason|because|therefore|however|"
    r"patient|summary|recommendation|recommended|required|insufficient|"
    r"unknown|none|dinai|die"
    r")\b",
    re.IGNORECASE,
)


def collect_forbidden_terms(*, texts: Iterable[str]) -> list[str]:
    """Return sorted unique forbidden English tokens found across narrative texts."""

    found: set[str] = set()
    for text in texts:
        for match in _FORBIDDEN_ENGLISH_TERMS_PATTERN.finditer(text):
            found.add(match.group(0).lower())
    return sorted(found)
