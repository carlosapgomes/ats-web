"""Deterministic synthesis helpers for rewritten EDA ASA and support outputs.

Ported faithfully from the legacy augmented-triage-system:
  triage_automation/domain/policy/eda_recommendation_synthesis.py

Every rule, display text, and type preserved exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

AsaBucketValue = Literal["I-II", "III ou mais", "insufficient_data"]
SupportRecommendationValue = Literal["none", "anesthesist", "anesthesist_icu"]
CardiovascularRiskValue = Literal["low", "moderate_high", "unknown"]

_INSUFFICIENT_ASA_DISPLAY = "não foi possível estimar com os dados apresentados"


@dataclass(frozen=True)
class EdaSupportContext:
    """Derived ASA and support context persisted with rewritten EDA recommendations."""

    asa_bucket: AsaBucketValue
    asa_display: str
    support_recommendation: SupportRecommendationValue


def synthesize_eda_support_context(*, structured_data: dict[str, object]) -> EdaSupportContext:
    """Derive practical ASA display and deterministic support recommendation."""

    asa_bucket = _extract_asa_bucket(structured_data=structured_data)
    cardiovascular_risk = _extract_cardiovascular_risk(structured_data=structured_data)

    if cardiovascular_risk == "moderate_high":
        support_recommendation: SupportRecommendationValue = "anesthesist_icu"
    elif asa_bucket == "III ou mais":
        support_recommendation = "anesthesist"
    else:
        support_recommendation = "none"

    asa_display = asa_bucket if asa_bucket != "insufficient_data" else _INSUFFICIENT_ASA_DISPLAY
    return EdaSupportContext(
        asa_bucket=asa_bucket,
        asa_display=asa_display,
        support_recommendation=support_recommendation,
    )


def _extract_asa_bucket(*, structured_data: dict[str, object]) -> AsaBucketValue:
    eda_payload = _extract_dict(structured_data, "eda")
    asa_payload = _extract_dict(eda_payload, "asa")
    bucket = asa_payload.get("bucket")
    if bucket in {"I-II", "III ou mais", "insufficient_data"}:
        return cast(AsaBucketValue, bucket)
    return "insufficient_data"


def _extract_cardiovascular_risk(*, structured_data: dict[str, object]) -> CardiovascularRiskValue:
    eda_payload = _extract_dict(structured_data, "eda")
    cardiovascular_risk_payload = _extract_dict(eda_payload, "cardiovascular_risk")
    level = cardiovascular_risk_payload.get("level")
    if level in {"low", "moderate_high", "unknown"}:
        return cast(CardiovascularRiskValue, level)
    return "unknown"


def _extract_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    return {}
