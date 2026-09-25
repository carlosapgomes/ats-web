"""Pydantic schema models for the LLM1 v4 procedure-neutral extraction contract.

Schema 4.0 (design D5/D6/D7 / ADR-0010): mantém a história/pré-operatório comuns
por caso (``common_preop`` com a coleção tipada de imagem abdominal) e amplia
``requested_procedures`` para as DEZ identidades atômicas do catálogo, cada
pacote ocupando um único item. Máximo de dez itens brutos para que a
reconciliação consiga explicar conjuntos incompatíveis.

Detalhes clínicos tipados:

- ``eda_dilation`` carrega ``dilation_detail`` (D6). O campo é definido e
  validado aqui; a extração orientada e a ancoragem determinística do excerpt
  pertencem ao Slice 003.
- ``eda_gastrostomy`` carrega ``infection_evidence`` (D7). A coleção é definida
  e validada aqui; a coleta orientada e o verificador pertencem ao Slice 004.

Contrato estrito: valores fora dos enums, proveniência inválida, excerpt de
achado vazio ou procedimento duplicado são rejeitados. Artefatos 1.1/2.0/3.0
permanecem legíveis pelos adapters e nunca são reescritos.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from apps.pipeline.schemas.llm1 import (
    Llm1ExtractionQuality,
    Llm1OriginContext,
    Llm1Patient,
    Llm1PolicyPrecheck,
    Llm1Summary,
    Llm1TrackedExam,
    Llm1Transfusion,
    StrictModel,
)
from apps.pipeline.schemas.llm1_v2 import (
    ColonoscopyIndicationCategoryV2,
    EdaIndicationCategoryV2,
    Llm1ColonoscopyProcedureV2,
    Llm1ProcedureEvidenceSpanV2,
)
from apps.pipeline.schemas.llm1_v3 import (
    MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    EdaProcedureSubtypeV3,
    Llm1CommonPreopV3,
    Llm1CpreProcedureV3,
    Llm1EchoendoscopyProcedureV3,
)

UrgencyV4 = Literal["eletivo", "urgente", "emergente", "indefinido"]
ColonoscopySubtypeV4 = Literal["standard", "unknown"]

MAX_REQUESTED_PROCEDURES_V4 = 10
MAX_DILATION_SITE_EXCERPT_LENGTH = 200
MAX_INFECTION_EVIDENCE_ITEMS = 20

# ── Detalhe de EDA + Dilatação (D6) ─────────────────────────────────────────

DilationAnatomicalSiteV4 = Literal[
    "esophagus",
    "pylorus",
    "duodenum",
    "anastomosis",
    "jejunum",
    "other",
    "unknown",
]


class DilationDetailV4(StrictModel):
    """Local anatômico informativo de EDA + Dilatação (D6).

    O local NÃO cria identidade nova nem altera profile/policy/sugestão. Quando
    documentado, exige trecho-fonte; a ancoragem determinística do excerpt no
    relatório principal ocorre no Slice 003. Ausência de informação permanece
    ``unknown``.
    """

    anatomical_site: DilationAnatomicalSiteV4 = "unknown"
    evidence_excerpt: str | None = Field(default=None, max_length=MAX_DILATION_SITE_EXCERPT_LENGTH)

    @field_validator("evidence_excerpt")
    @classmethod
    def _strip_excerpt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_evidence_excerpt(self) -> DilationDetailV4:
        """Sítio documentado exige trecho; ``unknown`` não exige evidência."""
        if self.anatomical_site != "unknown" and not self.evidence_excerpt:
            raise ValueError("evidence_excerpt obrigatório quando anatomical_site != 'unknown'")
        return self


# ── Coleção consultiva de EDA + GTT (D7) ────────────────────────────────────

InfectionCategoryV4 = Literal[
    "leukocytes",
    "crp",
    "procalcitonin",
    "lactate",
    "culture",
    "temperature_or_fever",
    "infectious_disease",
    "antibiotic",
]

InfectionAssessmentV4 = Literal[
    "normal_explicit",
    "abnormal_explicit",
    "positive_explicit",
    "negative_explicit",
    "febrile_explicit",
    "current_care_explicit",
    "antibiotic_in_use",
    "antibiotic_started",
    "antibiotic_escalated",
    "unclassified",
]

InfectionTemporalStatusV4 = Literal["current", "historical", "unknown"]


class InfectionEvidenceV4(StrictModel):
    """Evidência factual de possível infecção sistêmica em EDA + GTT (D7).

    ``evidence_excerpt`` é sempre o trecho-fonte real do relatório: o
    verificador determinístico (Slice 004) reancora o excerpt, rederiva a
    categoria e rebaixa classificação não comprovada para ``unclassified``.
    Nenhum threshold clínico é codificado aqui.
    """

    category: InfectionCategoryV4
    assessment: InfectionAssessmentV4
    temporal_status: InfectionTemporalStatusV4
    value_text: str | None = None
    evidence_excerpt: str = Field(min_length=1, max_length=MAX_DILATION_SITE_EXCERPT_LENGTH)

    @field_validator("evidence_excerpt")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence_excerpt não pode conter apenas espaços")
        return value


# ── Variantes de requested_procedures (uma por identidade atômica) ──────────


class Llm1EdaProcedureV4(StrictModel):
    """EDA própria (sem subtipo de pacote como identidade)."""

    procedure_type: Literal["eda"] = "eda"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: EdaIndicationCategoryV2 = "unknown"
    subtype: EdaProcedureSubtypeV3 = "standard"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


class Llm1EdaGastrostomyProcedureV4(StrictModel):
    """EDA + Gastrostomia (GTT) — pacote atômico indivisível (D2/D7)."""

    procedure_type: Literal["eda_gastrostomy"] = "eda_gastrostomy"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: EdaIndicationCategoryV2 = "unknown"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )
    infection_evidence: list[InfectionEvidenceV4] = Field(
        default_factory=list,
        max_length=MAX_INFECTION_EVIDENCE_ITEMS,
    )


class Llm1EdaCapsuleProcedureV4(StrictModel):
    """EDA + Cápsula — pacote atômico indivisível (D2)."""

    procedure_type: Literal["eda_capsule"] = "eda_capsule"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: EdaIndicationCategoryV2 = "unknown"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


class Llm1EdaDilationProcedureV4(StrictModel):
    """EDA + Dilatação — pacote atômico indivisível com local informativo (D2/D6)."""

    procedure_type: Literal["eda_dilation"] = "eda_dilation"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: EdaIndicationCategoryV2 = "unknown"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )
    dilation_detail: DilationDetailV4 = Field(default_factory=DilationDetailV4)


class Llm1RectosigmoidoscopyProcedureV4(StrictModel):
    """Retossigmoidoscopia — identidade atômica da família Colonoscopia."""

    procedure_type: Literal["rectosigmoidoscopy"] = "rectosigmoidoscopy"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: ColonoscopyIndicationCategoryV2 = "unknown"
    subtype: ColonoscopySubtypeV4 = "standard"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


class Llm1RectosigmoidoscopyDilationProcedureV4(StrictModel):
    """Retossigmoidoscopia + Dilatação — pacote atômico indivisível (D2)."""

    procedure_type: Literal["rectosigmoidoscopy_dilation"] = "rectosigmoidoscopy_dilation"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: ColonoscopyIndicationCategoryV2 = "unknown"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


class Llm1RectosigmoidoscopyArgonProcedureV4(StrictModel):
    """Retossigmoidoscopia + Argônio — pacote atômico indivisível (D2)."""

    procedure_type: Literal["rectosigmoidoscopy_argon"] = "rectosigmoidoscopy_argon"
    name: str | None = None
    urgency: UrgencyV4 = "indefinido"
    indication_category: ColonoscopyIndicationCategoryV2 = "unknown"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


Llm1RequestedProcedureV4 = Annotated[
    Llm1EdaProcedureV4
    | Llm1EdaGastrostomyProcedureV4
    | Llm1EdaCapsuleProcedureV4
    | Llm1EdaDilationProcedureV4
    | Llm1ColonoscopyProcedureV2
    | Llm1RectosigmoidoscopyProcedureV4
    | Llm1RectosigmoidoscopyDilationProcedureV4
    | Llm1RectosigmoidoscopyArgonProcedureV4
    | Llm1EchoendoscopyProcedureV3
    | Llm1CpreProcedureV3,
    Field(discriminator="procedure_type"),
]


class Llm1ResponseV4(StrictModel):
    """Resposta LLM1 schema 4.0 — contrato procedure-neutral com dez identidades.

    ``requested_procedures`` contém 1–10 itens únicos, com evidence spans
    obrigatórios. A matriz de conjuntos válidos é responsabilidade da
    reconciliação (D2/D3), que distingue mismatch de combinação não suportada.
    """

    schema_version: Literal["4.0"]
    language: Literal["pt-BR"]
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    patient: Llm1Patient
    common_preop: Llm1CommonPreopV3
    requested_procedures: list[Llm1RequestedProcedureV4] = Field(
        min_length=1,
        max_length=MAX_REQUESTED_PROCEDURES_V4,
    )
    policy_precheck: Llm1PolicyPrecheck
    summary: Llm1Summary
    extraction_quality: Llm1ExtractionQuality
    origin_context: Llm1OriginContext = Field(default_factory=Llm1OriginContext)
    transfusion: Llm1Transfusion = Field(
        default_factory=lambda: Llm1Transfusion(had_transfusion="no"),
    )
    tracked_exams: list[Llm1TrackedExam] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_procedure_types(self) -> Llm1ResponseV4:
        """Proíbe duplicatas de procedimento na solicitação atual (D2)."""
        seen: set[str] = set()
        for procedure in self.requested_procedures:
            if procedure.procedure_type in seen:
                raise ValueError(f"requested_procedures contém duplicata: {procedure.procedure_type!r}")
            seen.add(procedure.procedure_type)
        return self
