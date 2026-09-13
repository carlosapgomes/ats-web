"""Pydantic schema models for the LLM1 v3 procedure-neutral extraction contract.

Schema 3.0 (design D5/D6 / ADR-0006): mantém a história/pré-operatório comuns
por caso e ``requested_procedures[]`` tipado, agora com os QUATRO procedimentos
suportados (EDA, Colonoscopia, Ecoendoscopia, CPRE). Ecoendoscopia deixa de ser
subtipo/sinal de EDA em artefatos 3.0.

``common_preop`` ganha a coleção tipada ``abdominal_imaging`` (D6): modalidade,
sítio anatômico, presença de conclusão/achado e os excerpts que ancoram a
evidência no relatório principal. O schema apenas transporta e valida a FORMA;
a ancoragem determinística do excerpt em ``Case.extracted_text`` e a hard rule
clínica especializada pertencem ao verificador/policy dos slices verticais
próprios (Slice 002/004).

Contrato estrito: valores fora dos enums, proveniência inválida ou excerpt de
achado vazio são rejeitados. Artefatos 1.1/2.0 permanecem legíveis e nunca são
reescritos.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from apps.pipeline.schemas.llm1 import (
    Llm1AsaAssessment,
    Llm1CardiovascularRisk,
    Llm1Comorbidity,
    Llm1Ecg,
    Llm1EvidenceSpan,
    Llm1ExtractionQuality,
    Llm1Labs,
    Llm1Medication,
    Llm1OriginContext,
    Llm1Patient,
    Llm1PolicyPrecheck,
    Llm1RulebookSignals,
    Llm1Summary,
    Llm1TrackedExam,
    Llm1Transfusion,
    StrictModel,
)
from apps.pipeline.schemas.llm1_v2 import (
    Llm1ColonoscopyProcedureV2,
    Llm1EdaProcedureV2,
    Llm1ProcedureEvidenceSpanV2,
)

MAX_EVIDENCE_SPANS_PER_PROCEDURE = 3

AbdominalImagingModalityV3 = Literal["ultrasound", "ct", "mri", "mrcp", "other"]
AbdominalAnatomicalSiteV3 = Literal["abdomen", "upper_abdomen", "hepatobiliary", "unspecified", "other"]
FindingPresentV3 = Literal["yes", "no", "unknown"]

MAX_EVIDENCE_CONTEXT_EXCERPT_LENGTH = 400
MAX_FINDING_EXCERPT_LENGTH = 200


class AbdominalImagingEvidenceV3(StrictModel):
    """Evidência tipada de imagem abdominal do relatório principal (D6).

    ``source_document`` é sempre ``main_report``: anexos e ``tracked_exams``
    nunca sustentam a hard rule. Quando ``report_finding_present="yes"`` os dois
    excerpts são obrigatórios — o verificador determinístico ainda reancorará
    ``evidence_context_excerpt`` no texto persistido antes da policy.
    """

    modality: AbdominalImagingModalityV3
    anatomical_site: AbdominalAnatomicalSiteV3
    report_finding_present: FindingPresentV3
    source_document: Literal["main_report"] = "main_report"
    evidence_context_excerpt: str = Field(default="", max_length=MAX_EVIDENCE_CONTEXT_EXCERPT_LENGTH)
    finding_excerpt: str | None = Field(default=None, max_length=MAX_FINDING_EXCERPT_LENGTH)
    exam_datetime_iso: str | None = None

    @field_validator("evidence_context_excerpt", "finding_excerpt")
    @classmethod
    def _strip_excerpt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_finding_excerpts(self) -> AbdominalImagingEvidenceV3:
        """Exige contexto e achado não vazios quando o achado está presente."""
        if self.report_finding_present == "yes":
            if not self.evidence_context_excerpt:
                raise ValueError("evidence_context_excerpt obrigatório quando report_finding_present='yes'")
            if not self.finding_excerpt:
                raise ValueError("finding_excerpt obrigatório quando report_finding_present='yes'")
        return self


class Llm1EchoendoscopyProcedureV3(StrictModel):
    """Ecoendoscopia como procedimento independente (nunca subtipo de EDA)."""

    procedure_type: Literal["echoendoscopy"] = "echoendoscopy"
    name: str | None = None
    urgency: Literal["eletivo", "urgente", "emergente", "indefinido"] = "indefinido"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


class Llm1CpreProcedureV3(StrictModel):
    """CPRE como procedimento independente (nunca subtipo/sinal de EDA)."""

    procedure_type: Literal["cpre"] = "cpre"
    name: str | None = None
    urgency: Literal["eletivo", "urgente", "emergente", "indefinido"] = "indefinido"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


Llm1RequestedProcedureV3 = Annotated[
    Llm1EdaProcedureV2 | Llm1ColonoscopyProcedureV2 | Llm1EchoendoscopyProcedureV3 | Llm1CpreProcedureV3,
    Field(discriminator="procedure_type"),
]


class Llm1CommonPreopV3(StrictModel):
    """Pré-operatório comum ao caso, acrescido da imagem abdominal tipada (D6)."""

    labs: Llm1Labs
    ecg: Llm1Ecg = Field(
        default_factory=lambda: Llm1Ecg(report_present="unknown", abnormal_flag="unknown", source_text_hint=None)
    )
    asa: Llm1AsaAssessment | None = None
    cardiovascular_risk: Llm1CardiovascularRisk | None = None
    rulebook_signals: Llm1RulebookSignals = Field(default_factory=Llm1RulebookSignals)
    comorbidities_described: list[Llm1Comorbidity] = Field(default_factory=list, max_length=20)
    medications_described: list[Llm1Medication] = Field(default_factory=list, max_length=20)
    abdominal_imaging: list[AbdominalImagingEvidenceV3] = Field(default_factory=list, max_length=10)
    evidence_spans: list[Llm1EvidenceSpan] = Field(default_factory=list)


class Llm1ResponseV3(StrictModel):
    """Resposta LLM1 schema 3.0 — contrato procedure-neutral com quatro tipos.

    ``requested_procedures`` contém 1–4 itens únicos, com evidence spans
    obrigatórios. A matriz de combinações válidas é responsabilidade da
    reconciliação (D2/D3), que distingue mismatch de combinação não suportada.
    """

    schema_version: Literal["3.0"]
    language: Literal["pt-BR"]
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    patient: Llm1Patient
    common_preop: Llm1CommonPreopV3
    requested_procedures: list[Llm1RequestedProcedureV3] = Field(min_length=1, max_length=4)
    policy_precheck: Llm1PolicyPrecheck
    summary: Llm1Summary
    extraction_quality: Llm1ExtractionQuality
    origin_context: Llm1OriginContext = Field(default_factory=Llm1OriginContext)
    transfusion: Llm1Transfusion = Field(
        default_factory=lambda: Llm1Transfusion(had_transfusion="no"),
    )
    tracked_exams: list[Llm1TrackedExam] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_procedure_types(self) -> Llm1ResponseV3:
        """Proíbe duplicatas de procedimento na solicitação atual (D5)."""
        seen: set[str] = set()
        for procedure in self.requested_procedures:
            if procedure.procedure_type in seen:
                raise ValueError(f"requested_procedures contém duplicata: {procedure.procedure_type!r}")
            seen.add(procedure.procedure_type)
        return self
