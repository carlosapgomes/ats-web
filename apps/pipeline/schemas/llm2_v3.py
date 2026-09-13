"""Pydantic schema models for the LLM2 v3 suggestion contract.

Schema 3.0 (design D5 / ADR-0006): uma chamada LLM2 por caso devolve
``procedure_recommendations[]`` com exatamente um item por procedimento
reconciliado (igualdade exata validada no serviço) sobre os QUATRO tipos
suportados, e ``global_support_recommendation`` com o nível mais restritivo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from apps.pipeline.schemas.llm2 import Llm2PolicyAlignment, Llm2Rationale, StrictModel
from apps.pipeline.schemas.llm2_v2 import GlobalSupportRecommendation, ProcedureSuggestionV2

ProcedureTypeV3 = Literal["eda", "colonoscopy", "echoendoscopy", "cpre"]


class Llm2ProcedureRecommendationV3(StrictModel):
    """Recomendação para exatamente um procedimento reconciliado."""

    procedure_type: ProcedureTypeV3
    suggestion: ProcedureSuggestionV2
    support_recommendation: GlobalSupportRecommendation = "none"
    rationale: Llm2Rationale
    policy_alignment: Llm2PolicyAlignment
    confidence: Literal["alta", "media", "baixa"]


class Llm2ResponseV3(StrictModel):
    """Resposta LLM2 schema 3.0 — um item por procedimento reconciliado."""

    schema_version: Literal["3.0"]
    language: Literal["pt-BR"]
    case_id: str
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    procedure_recommendations: list[Llm2ProcedureRecommendationV3] = Field(min_length=1, max_length=4)
    global_support_recommendation: GlobalSupportRecommendation = "none"
    summary: str | None = None

    @model_validator(mode="after")
    def validate_unique_recommendations(self) -> Llm2ResponseV3:
        """Proíbe duplicatas de procedimento nas recomendações."""
        seen: set[str] = set()
        for recommendation in self.procedure_recommendations:
            if recommendation.procedure_type in seen:
                raise ValueError(f"procedure_recommendations contém duplicata: {recommendation.procedure_type!r}")
            seen.add(recommendation.procedure_type)
        return self
