"""Tests for deterministic EDA recommendation synthesis.

Ported faithfully from:
  tests/unit/test_eda_recommendation_synthesis.py

Every test case and assertion preserved. Only the import path changed.
"""

from __future__ import annotations

import importlib
from typing import cast


def _base_structured_data() -> dict[str, object]:
    return {
        "eda": {
            "asa": {
                "bucket": "I-II",
                "source_text_hint": "bom estado clinico",
            },
            "cardiovascular_risk": {
                "level": "low",
                "source_text_hint": "sem alto risco",
            },
        }
    }


def _synthesize(*, structured_data: dict[str, object]) -> dict[str, object]:
    """Dynamically import and invoke synthesize_eda_support_context."""
    module = importlib.import_module("apps.pipeline.policy.eda_recommendation_synthesis")
    synthesize = getattr(module, "synthesize_eda_support_context")
    result = synthesize(structured_data=structured_data)
    return {
        "asa_bucket": result.asa_bucket,
        "asa_display": result.asa_display,
        "support_recommendation": result.support_recommendation,
    }


def test_low_risk_asa_maps_to_no_additional_support() -> None:
    result = _synthesize(structured_data=_base_structured_data())

    assert result["asa_bucket"] == "I-II"
    assert result["asa_display"] == "I-II"
    assert result["support_recommendation"] == "none"


def test_higher_asa_maps_to_anesthesist_support() -> None:
    payload = _base_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    asa = cast(dict[str, object], eda["asa"])
    asa["bucket"] = "III ou mais"

    result = _synthesize(structured_data=payload)

    assert result["asa_bucket"] == "III ou mais"
    assert result["asa_display"] == "III ou mais"
    assert result["support_recommendation"] == "anesthesist"


def test_moderate_high_cardiovascular_risk_maps_to_anesthesist_icu() -> None:
    payload = _base_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    cardiovascular_risk = cast(dict[str, object], eda["cardiovascular_risk"])
    cardiovascular_risk["level"] = "moderate_high"

    result = _synthesize(structured_data=payload)

    assert result["asa_bucket"] == "I-II"
    assert result["support_recommendation"] == "anesthesist_icu"


def test_insufficient_asa_uses_explicit_fallback_text_without_escalating_support() -> None:
    payload = _base_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    asa = cast(dict[str, object], eda["asa"])
    asa["bucket"] = "insufficient_data"
    cardiovascular_risk = cast(dict[str, object], eda["cardiovascular_risk"])
    cardiovascular_risk["level"] = "unknown"

    result = _synthesize(structured_data=payload)

    assert result["asa_bucket"] == "insufficient_data"
    assert result["asa_display"] == "não foi possível estimar com os dados apresentados"
    assert result["support_recommendation"] == "none"


def test_asa_III_low_cardiovascular_maps_to_anesthesist() -> None:  # noqa: N802
    """ASA III + low cardiovascular → anesthesist (not ICU)."""
    payload = _base_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    asa = cast(dict[str, object], eda["asa"])
    asa["bucket"] = "III ou mais"
    cardiovascular_risk = cast(dict[str, object], eda["cardiovascular_risk"])
    cardiovascular_risk["level"] = "low"

    result = _synthesize(structured_data=payload)

    assert result["asa_bucket"] == "III ou mais"
    assert result["support_recommendation"] == "anesthesist"


def test_asa_I_II_moderate_high_maps_to_anesthesist_icu() -> None:  # noqa: N802
    """ASA I-II + moderate_high cardiovascular → anesthesist_icu."""
    payload = _base_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    cardiovascular_risk = cast(dict[str, object], eda["cardiovascular_risk"])
    cardiovascular_risk["level"] = "moderate_high"

    result = _synthesize(structured_data=payload)

    assert result["asa_bucket"] == "I-II"
    assert result["support_recommendation"] == "anesthesist_icu"


def test_cardiovascular_unknown_no_asa_III_plus_maps_to_none() -> None:  # noqa: N802
    """Unknown cardiovascular + ASA I-II → none."""
    payload = _base_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    cardiovascular_risk = cast(dict[str, object], eda["cardiovascular_risk"])
    cardiovascular_risk["level"] = "unknown"

    result = _synthesize(structured_data=payload)

    assert result["asa_bucket"] == "I-II"
    assert result["support_recommendation"] == "none"
