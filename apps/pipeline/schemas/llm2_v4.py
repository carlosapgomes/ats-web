"""Pydantic schema models for the LLM2 v4 suggestion contract.

Schema 4.0 (design D5 / ADR-0010): uma chamada LLM2 por caso devolve
``procedure_recommendations[]`` com exatamente um item por procedimento
reconciliado (igualdade exata validada no serviço) sobre as DEZ identidades
atômicas do catálogo, e ``global_support_recommendation`` com o nível mais
restritivo. Nenhuma regra de policy muda: a coleção consultiva de EDA + GTT
(D7) nunca entra neste contrato.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from apps.pipeline.schemas.llm2 import Llm2PolicyAlignment, Llm2Rationale, StrictModel
from apps.pipeline.schemas.llm2_v2 import GlobalSupportRecommendation, ProcedureSuggestionV2

ProcedureTypeV4 = Literal[
    "eda",
    "eda_gastrostomy",
    "eda_capsule",
    "eda_dilation",
    "colonoscopy",
    "rectosigmoidoscopy",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
    "echoendoscopy",
    "cpre",
]

MAX_PROCEDURE_RECOMMENDATIONS_V4 = 10


class Llm2ProcedureRecommendationV4(StrictModel):
    """Recomendação para exatamente um procedimento reconciliado."""

    procedure_type: ProcedureTypeV4
    suggestion: ProcedureSuggestionV2
    support_recommendation: GlobalSupportRecommendation = "none"
    rationale: Llm2Rationale
    policy_alignment: Llm2PolicyAlignment
    confidence: Literal["alta", "media", "baixa"]


class Llm2ResponseV4(StrictModel):
    """Resposta LLM2 schema 4.0 — um item por procedimento reconciliado."""

    schema_version: Literal["4.0"]
    language: Literal["pt-BR"]
    case_id: str
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    procedure_recommendations: list[Llm2ProcedureRecommendationV4] = Field(
        min_length=1,
        max_length=MAX_PROCEDURE_RECOMMENDATIONS_V4,
    )
    global_support_recommendation: GlobalSupportRecommendation = "none"
    summary: str | None = None

    @model_validator(mode="after")
    def validate_unique_recommendations(self) -> Llm2ResponseV4:
        """Proíbe duplicatas de procedimento nas recomendações."""
        seen: set[str] = set()
        for recommendation in self.procedure_recommendations:
            if recommendation.procedure_type in seen:
                raise ValueError(f"procedure_recommendations contém duplicata: {recommendation.procedure_type!r}")
            seen.add(recommendation.procedure_type)
        return self
