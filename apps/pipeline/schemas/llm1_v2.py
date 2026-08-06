"""Pydantic schema models for the LLM1 v2 procedure-neutral extraction contract.

Schema 2.0 (design D5 / ADR-0004): uma história/pré-operatório comuns por caso
e ``requested_procedures[]`` tipado por procedimento (EDA/Colonoscopia), sem
duplicatas e com evidence spans limitados. Contrato estrito: valores fora dos
enums ou proveniência inválida são rejeitados. Artefatos 1.1 permanecem
legíveis e não são reescritos (adapter de leitura em ``adapters.py``).
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

EdaProcedureSubtypeV2 = Literal[
    "standard",
    "gastrostomy",
    "esophageal_dilation",
    "foreign_body",
    "echoendoscopy",
    "unknown",
]
ColonoscopyProcedureSubtypeV2 = Literal["standard", "unknown"]

EdaIndicationCategoryV2 = Literal[
    "foreign_body",
    "bleeding",
    "abdominal_pain",
    "dyspepsia",
    "other",
    "unknown",
]
ColonoscopyIndicationCategoryV2 = Literal["screening", "follow_up", "bleeding", "other", "unknown"]

# Limites dos evidence spans por procedimento (D5: spans limitados).
MAX_EVIDENCE_SPANS_PER_PROCEDURE = 3
MAX_EVIDENCE_FIELD_PATH_LENGTH = 120
MAX_EVIDENCE_EXCERPT_LENGTH = 200


class Llm1ProcedureEvidenceSpanV2(StrictModel):
    """Excerpt de evidência vinculado a um procedimento solicitado.

    Obrigatório por item de ``requested_procedures``: uma afirmação LLM sem
    span não entra no contrato (D7 — evidência forte exige proveniência).
    """

    field_path: str = Field(min_length=1, max_length=MAX_EVIDENCE_FIELD_PATH_LENGTH)
    excerpt: str = Field(min_length=1, max_length=MAX_EVIDENCE_EXCERPT_LENGTH)

    @field_validator("field_path", "excerpt")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("campo não pode conter apenas espaços")
        return value


class Llm1EdaProcedureV2(StrictModel):
    """Procedimento EDA tipado: subtipos suportados e indicação EDA."""

    procedure_type: Literal["eda"] = "eda"
    name: str | None = None
    urgency: Literal["eletivo", "urgente", "emergente", "indefinido"] = "indefinido"
    indication_category: EdaIndicationCategoryV2 = "unknown"
    subtype: EdaProcedureSubtypeV2 = "standard"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


class Llm1ColonoscopyProcedureV2(StrictModel):
    """Procedimento Colonoscopia tipado: sem subtipo especial (R4/D8).

    Não aceita subtype EDA (gastrostomy/foreign_body/...): colonoscopia não
    possui subtipo especial de triagem (sem preparo/biópsia/gate).
    """

    procedure_type: Literal["colonoscopy"] = "colonoscopy"
    name: str | None = None
    urgency: Literal["eletivo", "urgente", "emergente", "indefinido"] = "indefinido"
    indication_category: ColonoscopyIndicationCategoryV2 = "unknown"
    subtype: ColonoscopyProcedureSubtypeV2 = "standard"
    evidence_spans: list[Llm1ProcedureEvidenceSpanV2] = Field(
        min_length=1,
        max_length=MAX_EVIDENCE_SPANS_PER_PROCEDURE,
    )


Llm1RequestedProcedureV2 = Annotated[
    Llm1EdaProcedureV2 | Llm1ColonoscopyProcedureV2,
    Field(discriminator="procedure_type"),
]


class Llm1CommonPreopV2(StrictModel):
    """Pré-operatório comum ao caso (uma única extração por caso).

    Compartilhado entre todos os procedimentos detectados; as policies rodam
    por componente sobre este bloco (D8). Exceções específicas (corpo estranho)
    permanecem no item de procedimento EDA, nunca aqui.
    """

    labs: Llm1Labs
    ecg: Llm1Ecg = Field(
        default_factory=lambda: Llm1Ecg(report_present="unknown", abnormal_flag="unknown", source_text_hint=None)
    )
    asa: Llm1AsaAssessment | None = None
    cardiovascular_risk: Llm1CardiovascularRisk | None = None
    rulebook_signals: Llm1RulebookSignals = Field(default_factory=Llm1RulebookSignals)
    comorbidities_described: list[Llm1Comorbidity] = Field(default_factory=list, max_length=20)
    medications_described: list[Llm1Medication] = Field(default_factory=list, max_length=20)
    evidence_spans: list[Llm1EvidenceSpan] = Field(default_factory=list)


class Llm1ResponseV2(StrictModel):
    """Resposta LLM1 schema 2.0 — contrato procedure-neutral.

    ``requested_procedures`` contém 1–2 itens únicos (EDA/Colonoscopia) com
    evidence spans obrigatórios; vazio/duplicata/outro tipo são rejeitados.
    """

    schema_version: Literal["2.0"]
    language: Literal["pt-BR"]
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    patient: Llm1Patient
    common_preop: Llm1CommonPreopV2
    requested_procedures: list[Llm1RequestedProcedureV2] = Field(min_length=1, max_length=2)
    policy_precheck: Llm1PolicyPrecheck
    summary: Llm1Summary
    extraction_quality: Llm1ExtractionQuality
    origin_context: Llm1OriginContext = Field(default_factory=Llm1OriginContext)
    transfusion: Llm1Transfusion = Field(
        default_factory=lambda: Llm1Transfusion(had_transfusion="no"),
    )
    tracked_exams: list[Llm1TrackedExam] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_procedure_types(self) -> Llm1ResponseV2:
        """Proíbe duplicatas de procedimento na solicitação atual (D5)."""
        seen: set[str] = set()
        for procedure in self.requested_procedures:
            if procedure.procedure_type in seen:
                raise ValueError(f"requested_procedures contém duplicata: {procedure.procedure_type!r}")
            seen.add(procedure.procedure_type)
        return self
