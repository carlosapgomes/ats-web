"""Hard-rule policy reconciliation for LLM2 triage suggestions.

Ported faithfully from the legacy augmented-triage-system:
  triage_automation/domain/policy/eda_policy.py

Every dataclass field, rule, and contradiction entry preserved exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PolicyAlignmentValue = Literal["yes", "no", "unknown", "not_required"]
PolicyPrecheckValue = Literal["yes", "no", "unknown"]
SuggestionValue = Literal["accept", "deny"]


@dataclass(frozen=True)
class EdaPolicyPrecheckInput:
    """Normalized LLM1 precheck inputs used by deterministic policy rules."""

    excluded_from_eda_flow: bool
    indication_category: str
    labs_required: bool
    labs_pass: PolicyPrecheckValue
    ecg_required: bool
    ecg_present: PolicyPrecheckValue
    pediatric_flag: bool


@dataclass(frozen=True)
class Llm2PolicyAlignmentInput:
    """LLM2-provided policy alignment values prior to reconciliation."""

    excluded_request: bool
    labs_ok: PolicyAlignmentValue
    ecg_ok: PolicyAlignmentValue
    pediatric_flag: bool
    notes: str | None


@dataclass(frozen=True)
class Llm2SuggestionInput:
    """Minimal LLM2 suggestion payload consumed by reconciliation."""

    suggestion: SuggestionValue
    policy_alignment: Llm2PolicyAlignmentInput


@dataclass(frozen=True)
class EdaPolicyContradiction:
    """Recorded field override produced by a deterministic policy rule."""

    rule: str
    field: str
    previous_value: str | bool
    reconciled_value: str | bool


@dataclass(frozen=True)
class EdaPolicyResult:
    """Final reconciled policy output and contradiction audit entries."""

    suggestion: SuggestionValue
    policy_alignment: Llm2PolicyAlignmentInput
    contradictions: tuple[EdaPolicyContradiction, ...]


def reconcile_eda_policy(
    *,
    precheck: EdaPolicyPrecheckInput,
    llm2: Llm2SuggestionInput,
) -> EdaPolicyResult:
    """Apply deterministic hard rules so LLM2 output stays policy-consistent."""

    suggestion: SuggestionValue = llm2.suggestion
    excluded_request = llm2.policy_alignment.excluded_request
    labs_ok = llm2.policy_alignment.labs_ok
    ecg_ok = llm2.policy_alignment.ecg_ok
    contradictions: list[EdaPolicyContradiction] = []

    def set_field(*, rule: str, field: str, previous: str | bool, updated: str | bool) -> None:
        if previous == updated:
            return
        contradictions.append(
            EdaPolicyContradiction(
                rule=rule,
                field=field,
                previous_value=previous,
                reconciled_value=updated,
            )
        )

    if precheck.excluded_from_eda_flow:
        set_field(
            rule="excluded_request_forces_deny",
            field="suggestion",
            previous=suggestion,
            updated="deny",
        )
        suggestion = "deny"

        set_field(
            rule="excluded_request_forces_alignment",
            field="policy_alignment.excluded_request",
            previous=excluded_request,
            updated=True,
        )
        excluded_request = True

    if precheck.indication_category == "foreign_body":
        set_field(
            rule="foreign_body_overrides_labs",
            field="policy_alignment.labs_ok",
            previous=labs_ok,
            updated="not_required",
        )
        labs_ok = "not_required"

        set_field(
            rule="foreign_body_overrides_ecg",
            field="policy_alignment.ecg_ok",
            previous=ecg_ok,
            updated="not_required",
        )
        ecg_ok = "not_required"
    else:
        if precheck.labs_required and precheck.labs_pass != "yes":
            target_labs = _map_required_alignment(precheck.labs_pass)
            set_field(
                rule="required_labs_must_align",
                field="policy_alignment.labs_ok",
                previous=labs_ok,
                updated=target_labs,
            )
            labs_ok = target_labs

            set_field(
                rule="required_labs_missing_or_failed_forces_deny",
                field="suggestion",
                previous=suggestion,
                updated="deny",
            )
            suggestion = "deny"

        if precheck.ecg_required and precheck.ecg_present != "yes":
            target_ecg = _map_required_alignment(precheck.ecg_present)
            set_field(
                rule="required_ecg_must_align",
                field="policy_alignment.ecg_ok",
                previous=ecg_ok,
                updated=target_ecg,
            )
            ecg_ok = target_ecg

            set_field(
                rule="required_ecg_missing_forces_deny",
                field="suggestion",
                previous=suggestion,
                updated="deny",
            )
            suggestion = "deny"

    return EdaPolicyResult(
        suggestion=suggestion,
        policy_alignment=Llm2PolicyAlignmentInput(
            excluded_request=excluded_request,
            labs_ok=labs_ok,
            ecg_ok=ecg_ok,
            pediatric_flag=llm2.policy_alignment.pediatric_flag,
            notes=llm2.policy_alignment.notes,
        ),
        contradictions=tuple(contradictions),
    )


def _map_required_alignment(value: PolicyPrecheckValue) -> PolicyAlignmentValue:
    if value == "no":
        return "no"
    return "unknown"
