"""Pydantic schema models for the LLM2 v2 suggestion contract.

Schema 2.0 (design D8 / ADR-0004): uma chamada LLM2 por caso devolve
``procedure_recommendations[]`` com exatamente um item por procedimento
detectado — sem omissão, duplicata ou adição (igualdade exata validada no
serviço) — e ``global_support_recommendation`` com o nível mais restritivo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from apps.pipeline.schemas.llm2 import Llm2PolicyAlignment, Llm2Rationale, StrictModel

GlobalSupportRecommendation = Literal["none", "anesthesist", "anesthesist_icu"]
ProcedureSuggestionV2 = Literal["accept", "deny"]


class Llm2ProcedureRecommendationV2(StrictModel):
    """Recomendação para exatamente um procedimento detectado."""

    procedure_type: Literal["eda", "colonoscopy"]
    suggestion: ProcedureSuggestionV2
    support_recommendation: GlobalSupportRecommendation = "none"
    rationale: Llm2Rationale
    policy_alignment: Llm2PolicyAlignment
    confidence: Literal["alta", "media", "baixa"]


class Llm2ResponseV2(StrictModel):
    """Resposta LLM2 schema 2.0 — um item por procedimento detectado."""

    schema_version: Literal["2.0"]
    language: Literal["pt-BR"]
    case_id: str
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    procedure_recommendations: list[Llm2ProcedureRecommendationV2] = Field(min_length=1, max_length=2)
    global_support_recommendation: GlobalSupportRecommendation = "none"
    summary: str | None = None

    @model_validator(mode="after")
    def validate_unique_recommendations(self) -> Llm2ResponseV2:
        """Proíbe duplicatas de procedimento nas recomendações."""
        seen: set[str] = set()
        for recommendation in self.procedure_recommendations:
            if recommendation.procedure_type in seen:
                raise ValueError(f"procedure_recommendations contém duplicata: {recommendation.procedure_type!r}")
            seen.add(recommendation.procedure_type)
        return self
