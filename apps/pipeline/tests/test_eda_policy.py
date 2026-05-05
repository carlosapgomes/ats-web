"""Tests for deterministic EDA policy reconciliation engine.

Ported faithfully from:
  tests/unit/test_eda_policy_crosscheck.py

Every test case and assertion preserved. Only the import path changed.
"""

from __future__ import annotations

import importlib
from typing import cast


def _base_precheck() -> dict[str, object]:
    """Build a base EdaPolicyPrecheckInput-equivalent dict for reconciliation."""
    return {
        "excluded_from_eda_flow": False,
        "indication_category": "dyspepsia",
        "labs_required": True,
        "labs_pass": "yes",
        "ecg_required": True,
        "ecg_present": "yes",
        "pediatric_flag": False,
    }


def _base_llm2() -> dict[str, object]:
    """Build a base Llm2SuggestionInput-equivalent dict for reconciliation."""
    return {
        "suggestion": "accept",
        "policy_alignment": {
            "excluded_request": False,
            "labs_ok": "yes",
            "ecg_ok": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
    }


def _reconcile(*, precheck: dict[str, object], llm2: dict[str, object]) -> dict[str, object]:
    """Dynamically import and invoke reconcile_eda_policy to avoid import errors."""
    module = importlib.import_module("apps.pipeline.policy.eda_policy")
    EdaPolicyPrecheckInput = getattr(module, "EdaPolicyPrecheckInput")  # noqa: N806
    Llm2PolicyAlignmentInput = getattr(module, "Llm2PolicyAlignmentInput")  # noqa: N806
    Llm2SuggestionInput = getattr(module, "Llm2SuggestionInput")  # noqa: N806
    reconcile = getattr(module, "reconcile_eda_policy")

    precheck_obj = EdaPolicyPrecheckInput(**precheck)
    alignment_dict = cast(dict[str, object], llm2["policy_alignment"])
    alignment_obj = Llm2PolicyAlignmentInput(**alignment_dict)
    llm2_obj = Llm2SuggestionInput(
        suggestion=llm2["suggestion"],
        policy_alignment=alignment_obj,
    )
    result = reconcile(precheck=precheck_obj, llm2=llm2_obj)

    return {
        "suggestion": cast(str, result.suggestion),
        "policy_alignment": cast(
            dict[str, object],
            {
                "excluded_request": result.policy_alignment.excluded_request,
                "labs_ok": result.policy_alignment.labs_ok,
                "ecg_ok": result.policy_alignment.ecg_ok,
                "pediatric_flag": result.policy_alignment.pediatric_flag,
                "notes": result.policy_alignment.notes,
            },
        ),
        "contradictions": cast(
            list[dict[str, str]], [{"rule": c.rule, "field": c.field} for c in result.contradictions]
        ),
    }


def test_accept_accepted_without_contradictions() -> None:
    """Accept suggestion passes through without any contradictions."""
    result = _reconcile(precheck=_base_precheck(), llm2=_base_llm2())
    assert result["suggestion"] == "accept"
    assert result["contradictions"] == []


def test_excluded_request_forces_deny() -> None:
    precheck = _base_precheck()
    precheck["excluded_from_eda_flow"] = True

    result = _reconcile(precheck=precheck, llm2=_base_llm2())
    alignment = cast(dict[str, object], result["policy_alignment"])

    assert result["suggestion"] == "deny"
    assert alignment["excluded_request"] is True
    # Contradiction must be recorded for excluded_request rule
    contradictions = cast(list[dict[str, str]], result["contradictions"])
    assert any(c["rule"] == "excluded_request_forces_deny" for c in contradictions)


def test_foreign_body_sets_labs_and_ecg_to_not_required() -> None:
    precheck = _base_precheck()
    precheck["indication_category"] = "foreign_body"
    precheck["labs_required"] = False
    precheck["labs_pass"] = "unknown"
    precheck["ecg_required"] = False
    precheck["ecg_present"] = "unknown"

    result = _reconcile(precheck=precheck, llm2=_base_llm2())
    alignment = cast(dict[str, object], result["policy_alignment"])

    assert alignment["labs_ok"] == "not_required"
    assert alignment["ecg_ok"] == "not_required"


def test_missing_required_labs_and_ecg_force_deny_aligned_output() -> None:
    precheck = _base_precheck()
    precheck["labs_pass"] = "unknown"
    precheck["ecg_present"] = "unknown"

    result = _reconcile(precheck=precheck, llm2=_base_llm2())
    alignment = cast(dict[str, object], result["policy_alignment"])

    assert result["suggestion"] == "deny"
    assert alignment["labs_ok"] == "unknown"
    assert alignment["ecg_ok"] == "unknown"


def test_labs_pass_with_foreign_body_not_deny() -> None:
    """Foreign body: labs and ECG become not_required but suggestion stays accept."""
    precheck = _base_precheck()
    precheck["indication_category"] = "foreign_body"
    precheck["labs_required"] = True
    precheck["labs_pass"] = "yes"
    precheck["ecg_required"] = True
    precheck["ecg_present"] = "yes"

    result = _reconcile(precheck=precheck, llm2=_base_llm2())
    alignment = cast(dict[str, object], result["policy_alignment"])

    # foreign_body overrides labs and ecg to not_required
    assert alignment["labs_ok"] == "not_required"
    assert alignment["ecg_ok"] == "not_required"
    # But it does not force deny (foreign_body bypass is at preop level)
    # Suggestion stays as-is (accept in this case)
    assert result["suggestion"] == "accept"


def test_contradictions_are_reported_when_policy_forces_changes() -> None:
    precheck = _base_precheck()
    precheck["excluded_from_eda_flow"] = True
    precheck["labs_pass"] = "no"
    precheck["ecg_present"] = "no"

    result = _reconcile(precheck=precheck, llm2=_base_llm2())
    contradictions = cast(list[dict[str, str]], result["contradictions"])

    assert contradictions
    assert any(item["field"] == "suggestion" for item in contradictions)


def test_multiple_contradictions_recorded() -> None:
    """Multiple rules firing should all be recorded."""
    precheck = _base_precheck()
    precheck["excluded_from_eda_flow"] = True

    result = _reconcile(precheck=precheck, llm2=_base_llm2())
    contradictions = cast(list[dict[str, str]], result["contradictions"])

    # Should have at least suggestion change and excluded_request alignment
    assert contradictions
    fields = {c["field"] for c in contradictions}
    assert "suggestion" in fields
    assert "policy_alignment.excluded_request" in fields
