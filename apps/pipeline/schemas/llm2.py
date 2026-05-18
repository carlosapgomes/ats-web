"""Pydantic schema models for the LLM2 suggestion response contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


class Llm2Rationale(StrictModel):
    short_reason: str = Field(max_length=280)
    details: list[str] = Field(min_length=2, max_length=6)
    missing_info_questions: list[str] = Field(max_length=6)


class Llm2PolicyAlignment(StrictModel):
    excluded_request: bool
    labs_ok: Literal["yes", "no", "unknown", "not_required"]
    ecg_ok: Literal["yes", "no", "unknown", "not_required"]
    pediatric_flag: bool
    notes: str | None


class Llm2Response(StrictModel):
    schema_version: Literal["1.1"]
    language: Literal["pt-BR"]
    case_id: str
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    suggestion: Literal["accept", "deny"]
    support_recommendation: Literal["none", "anesthesist", "anesthesist_icu", "unknown"]
    rationale: Llm2Rationale
    policy_alignment: Llm2PolicyAlignment
    confidence: Literal["alta", "media", "baixa"]
