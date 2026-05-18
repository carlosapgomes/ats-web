"""Pydantic schema models for the LLM1 structured extraction contract.

Ported from the legacy augmented-triage-system:
  src/triage_automation/application/dto/llm1_models.py
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvidenceFlag = Literal["yes", "no", "unknown"]

BrazilStateUf = Literal[
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]
EdaRequestedProcedureSubtype = Literal[
    "standard",
    "gastrostomy",
    "esophageal_dilation",
    "foreign_body",
    "unknown",
]
AsaBucket = Literal["I-II", "III ou mais", "insufficient_data"]
CardiovascularRiskLevel = Literal["low", "moderate_high", "unknown"]


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


class Llm1Patient(StrictModel):
    """Patient identity and demographic fields extracted by LLM1."""

    name: str | None
    age: int | None = Field(default=None, ge=0, le=130)
    sex: Literal["M", "F", "Outro"] | None
    document_id: str | None = None


class Llm1RequestedProcedure(StrictModel):
    """Requested procedure metadata, urgency, and normalized EDA subtype."""

    name: str | None
    urgency: Literal["eletivo", "urgente", "emergente", "indefinido"]
    subtype: EdaRequestedProcedureSubtype = "unknown"


class Llm1Labs(StrictModel):
    """Laboratory values and provenance hints extracted for rulebook evaluation."""

    hb_g_dl: float | None
    hct_percent: float | None = None
    platelets_per_mm3: int | None
    tp_seconds: float | None = None
    inr: float | None
    rni: float | None = None
    ttpa_seconds: float | None = None
    urea_mg_dl: float | None = None
    creatinine_mg_dl: float | None = None
    source_text_hint: str | None


class Llm1Ecg(StrictModel):
    """ECG availability and abnormality signal."""

    report_present: EvidenceFlag
    abnormal_flag: EvidenceFlag
    source_text_hint: str | None


class Llm1AsaAssessment(StrictModel):
    """Practical ASA estimate extracted for downstream recommendation synthesis."""

    bucket: AsaBucket
    source_text_hint: str | None = None


class Llm1CardiovascularRisk(StrictModel):
    """Structured cardiovascular risk signal used to refine support mapping."""

    level: CardiovascularRiskLevel
    source_text_hint: str | None = None


class Llm1Eda(StrictModel):
    """EDA-focused structured clinical extraction fields."""

    indication_category: Literal[
        "foreign_body",
        "bleeding",
        "abdominal_pain",
        "dyspepsia",
        "other",
        "unknown",
    ]
    exclusion_type: Literal["none", "gastrostomy", "esophageal_dilation", "unknown"]
    is_pediatric: bool
    foreign_body_suspected: bool
    requested_procedure: Llm1RequestedProcedure
    labs: Llm1Labs
    ecg: Llm1Ecg
    asa: Llm1AsaAssessment | None = None
    cardiovascular_risk: Llm1CardiovascularRisk | None = None


class Llm1EvidenceSpan(StrictModel):
    """Source excerpt linked to an extracted field for deterministic explainability."""

    field_path: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class Llm1MinimumExamEvidence(StrictModel):
    """Structured evidence availability for the rewritten EDA minimum exam set."""

    hb_or_hct_present: EvidenceFlag = "unknown"
    hb_numeric_present: EvidenceFlag = "unknown"
    platelets_numeric_present: EvidenceFlag = "unknown"
    tp_inr_rni_numeric_present: EvidenceFlag = "unknown"
    ttpa_present: EvidenceFlag = "unknown"
    urea_present: EvidenceFlag = "unknown"
    creatinine_present: EvidenceFlag = "unknown"
    coagulogram_normal_supports_ttpa: EvidenceFlag = "unknown"
    renal_function_preserved_supports_urea_and_creatinine: EvidenceFlag = "unknown"


class Llm1ConditionalExamRequirements(StrictModel):
    """Applicability and completeness signals for ECG, chest X-ray, and echo gates."""

    ecg_required: EvidenceFlag = "unknown"
    chest_xray_required: EvidenceFlag = "unknown"
    echocardiogram_required: EvidenceFlag = "unknown"
    ecg_report_finding_present: EvidenceFlag = "unknown"
    chest_xray_report_finding_present: EvidenceFlag = "unknown"
    echocardiogram_report_finding_present: EvidenceFlag = "unknown"


class Llm1ClinicalFlags(StrictModel):
    """Clinical flags needed by the rewritten EDA rulebook and subtype logic."""

    hepatopathy_explicit: EvidenceFlag = "unknown"
    cardiopathy_explicit: EvidenceFlag = "unknown"
    known_cardiovascular_disease: EvidenceFlag = "unknown"
    active_respiratory_symptoms: EvidenceFlag = "unknown"
    prior_respiratory_disease: EvidenceFlag = "unknown"
    multiple_comorbidities: EvidenceFlag = "unknown"
    qt_prolonging_medications: EvidenceFlag = "unknown"
    diabetes_mellitus: EvidenceFlag = "unknown"
    explicit_obesity: EvidenceFlag = "unknown"
    recent_chest_pain: EvidenceFlag = "unknown"
    recent_dyspnea: EvidenceFlag = "unknown"
    recent_palpitations: EvidenceFlag = "unknown"
    recent_syncope: EvidenceFlag = "unknown"
    unexplained_dyspnea: EvidenceFlag = "unknown"
    heart_failure_signs: EvidenceFlag = "unknown"
    new_or_unevaluated_murmur: EvidenceFlag = "unknown"
    moderate_or_severe_valvulopathy_without_recent_echo: EvidenceFlag = "unknown"
    worsening_cardiomyopathy: EvidenceFlag = "unknown"
    pulmonary_hypertension: EvidenceFlag = "unknown"
    prior_myocardial_infarction: EvidenceFlag = "unknown"
    prior_coronary_bypass: EvidenceFlag = "unknown"
    prior_coronary_angioplasty: EvidenceFlag = "unknown"


class Llm1RulebookSignals(StrictModel):
    """Grouped rulebook signals added for the rewritten supported EDA flow."""

    eda_subtype: EdaRequestedProcedureSubtype = "unknown"
    minimum_exam_evidence: Llm1MinimumExamEvidence = Field(default_factory=Llm1MinimumExamEvidence)
    conditional_exam_requirements: Llm1ConditionalExamRequirements = Field(
        default_factory=Llm1ConditionalExamRequirements
    )
    clinical_flags: Llm1ClinicalFlags = Field(default_factory=Llm1ClinicalFlags)


class Llm1PreopScreening(StrictModel):
    """Objective pre-procedure screening signals extracted from textual evidence."""

    exam_type: Literal["eda", "non_eda", "unknown"]
    has_cardiovascular_disease: EvidenceFlag
    has_active_respiratory_symptoms: EvidenceFlag
    has_prior_respiratory_disease: EvidenceFlag
    has_ecg_report: EvidenceFlag
    has_chest_xray_report: EvidenceFlag
    has_echocardiogram_report: EvidenceFlag = "unknown"
    hb_g_dl: float | None
    platelets_per_mm3: int | None
    inr: float | None
    evidence_spans: list[Llm1EvidenceSpan] = Field(default_factory=list)
    rulebook_signals: Llm1RulebookSignals = Field(default_factory=Llm1RulebookSignals)


class Llm1PolicyPrecheck(StrictModel):
    """Precheck flags used by deterministic policy reconciliation."""

    excluded_from_eda_flow: bool
    exclusion_reason: str | None
    labs_required: bool
    labs_pass: Literal["yes", "no", "unknown"]
    labs_failed_items: list[str]
    ecg_required: bool
    ecg_present: Literal["yes", "no", "unknown"]
    pediatric_flag: bool
    notes: str | None


class Llm1Summary(StrictModel):
    """Human-readable one-liner and supporting bullets."""

    one_liner: str
    bullet_points: list[str] = Field(min_length=3, max_length=8)


class Llm1ExtractionQuality(StrictModel):
    """Quality/confidence metadata for extraction completeness."""

    confidence: Literal["alta", "media", "baixa"]
    missing_fields: list[str]
    notes: str | None


class Llm1OriginContext(StrictModel):
    """Structured provenance/origin context extracted from the medical report."""

    city: str | None = None
    hospital: str | None = None
    unit: str | None = None
    state_uf: BrazilStateUf | None = None
    source_text_hint: str | None = None


class Llm1Transfusion(StrictModel):
    """Binary transfusion evidence with optional unit count and hemocomponent."""

    had_transfusion: Literal["yes", "no"]
    total_units: int | None = Field(default=None, ge=0)
    hemocomponent: str | None = None
    source_text_hint: str | None = None


class Llm1TrackedExam(StrictModel):
    """A single tracked exam with recency marker and optional datetime."""

    exam_type: str = Field(min_length=1)
    exam_label: str | None = None
    result_value: str | None = None
    exam_datetime_iso: str | None = None
    is_most_recent: bool
    source_text_hint: str | None = None


class Llm1Response(StrictModel):
    """Top-level LLM1 response schema."""

    schema_version: Literal["1.1"]
    language: Literal["pt-BR"]
    agency_record_number: str = Field(pattern=r"^[0-9]{5,}$")
    patient: Llm1Patient
    eda: Llm1Eda
    preop_screening: Llm1PreopScreening
    policy_precheck: Llm1PolicyPrecheck
    summary: Llm1Summary
    extraction_quality: Llm1ExtractionQuality
    origin_context: Llm1OriginContext = Field(default_factory=Llm1OriginContext)
    transfusion: Llm1Transfusion = Field(
        default_factory=lambda: Llm1Transfusion(had_transfusion="no"),
    )
    tracked_exams: list[Llm1TrackedExam] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rulebook_consistency(self) -> Llm1Response:
        """Enforce cross-field consistency required by the rewritten EDA contract."""

        self._validate_pediatric_flags()
        self._validate_eda_subtype_alignment()
        return self

    def _validate_pediatric_flags(self) -> None:
        """Ensure pediatric markers stay aligned with the extracted patient age."""

        age = self.patient.age
        if age is None:
            return

        expected_pediatric = age < 16
        if self.eda.is_pediatric != expected_pediatric:
            raise ValueError("eda.is_pediatric must match patient.age < 16")
        if self.policy_precheck.pediatric_flag != expected_pediatric:
            raise ValueError("policy_precheck.pediatric_flag must match patient.age < 16")

    def _validate_eda_subtype_alignment(self) -> None:
        """Keep duplicated subtype fields aligned when both are explicitly populated."""

        requested_subtype = self.eda.requested_procedure.subtype
        rulebook_subtype = self.preop_screening.rulebook_signals.eda_subtype
        if requested_subtype == "unknown" or rulebook_subtype == "unknown":
            return
        if requested_subtype != rulebook_subtype:
            raise ValueError("eda.requested_procedure.subtype must match preop_screening.rulebook_signals.eda_subtype")
