"""Deterministic pre-procedure EDA policy evaluation rules.

Ported faithfully from:
  triage_automation/domain/policy/eda_preop_policy.py

Every clinical threshold, conditional gate, and profile is preserved exactly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from apps.cases.exam_profiles import get_exam_profile
from apps.pipeline.imaging_evidence import ImagingEvidenceOutcome, ImagingVerificationReport

DecisionValue = Literal["accept", "deny", "excluded", "manual_review_required"]
SupportedEdaSubtype = Literal[
    "standard",
    "gastrostomy",
    "esophageal_dilation",
    "foreign_body",
    "echoendoscopy",
]

# Ordem estável das categorias de pendência (design D8): exames mínimos,
# thresholds, exames condicionais e imagem especializada. O ``reason_code``
# primário é sempre a primeira pendência desta ordem.
REQUIREMENT_CATEGORIES: tuple[str, ...] = ("minimum", "threshold", "conditional", "imaging")

# Evidência de imagem já verificada deterministicamente (D6): a policy aceita a
# sequência de outcomes ou o relatório completo do verificador.
VerifiedImaging = Sequence[ImagingEvidenceOutcome] | ImagingVerificationReport

_REQUIRED_MINIMUM_EXAMS: tuple[tuple[str, str, str], ...] = (
    ("hb_numeric_present", "missing_minimum_exam_hb_or_ht", "Hb/Ht"),
    ("platelets_numeric_present", "missing_minimum_exam_platelets", "plaquetas"),
    ("tp_inr_rni_numeric_present", "missing_minimum_exam_tp_inr_rni", "TP/INR/RNI"),
    ("ttpa_present", "missing_minimum_exam_ttpa", "TTPa"),
    ("urea_present", "missing_minimum_exam_urea", "ureia"),
    ("creatinine_present", "missing_minimum_exam_creatinine", "creatinina"),
)


@dataclass(frozen=True)
class FailedRequirement:
    """Pendência documental/clínica determinística (design D8).

    ``text`` carrega a mensagem legada da pendência; ``code``/``label``/
    ``category`` são o contrato aditivo consumido por LLM2, relatório médico e
    correção NIR.
    """

    code: str
    label: str
    category: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "label": self.label, "category": self.category}


@dataclass(frozen=True)
class EdaPreopDecision:
    """Deterministic pre-procedure decision with explicit reason metadata."""

    decision: DecisionValue
    reason_code: str
    reason_text: str
    evidence_spans: list[dict[str, str]]
    pediatric_flag: bool
    failed_requirements: list[FailedRequirement] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize deterministic decision payload for persistence and downstream use.

        Contrato aditivo (D8): ``reason_code``/``reason_text`` preservam o
        motivo primário legado e ``failed_requirements[]`` expõe TODAS as
        pendências em ordem estável.
        """

        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason_text": self.reason_text,
            "evidence_spans": self.evidence_spans,
            "pediatric_flag": self.pediatric_flag,
            "failed_requirements": [requirement.to_dict() for requirement in self.failed_requirements],
        }


@dataclass(frozen=True)
class ContraindicationThresholds:
    """Numeric contraindication thresholds derived from the rewritten rulebook."""

    hb_min: float
    platelets_min: int
    rni_max: float
    profile_name: str


def evaluate_preop_policy(
    *,
    structured_data: dict[str, object],
    exam_type: str,
    verified_imaging: VerifiedImaging | None = None,
) -> dict[str, object]:
    """Evaluate deterministic pre-procedure criteria for a declared exam type.

    Profile-dispatched (design D3 / ADR-0003): EDA and colonoscopy share the
    same minimum exams, thresholds and conditional gates. The foreign-body
    exception is exclusive to EDA (R4).

    ``verified_imaging`` são os outcomes do verificador determinístico de
    imagem (design D6): a policy consome SOMENTE evidência aprovada, nunca o
    payload bruto do LLM. Perfis sem ``accepted_imaging`` (EDA/Colonoscopia)
    ignoram o parâmetro e mantêm o comportamento anterior exatamente.
    """
    profile = get_exam_profile(exam_type)
    return _evaluate_common_preop_policy(
        structured_data=structured_data,
        allow_foreign_body_exception=profile.allows_foreign_body_exception,
        procedure_label=profile.label,
        accepted_imaging=profile.accepted_imaging,
        imaging_requirement_label=profile.imaging_requirement_label,
        verified_imaging=verified_imaging,
    )


def evaluate_eda_preop_policy(*, structured_data: dict[str, object]) -> dict[str, object]:
    """Legacy entry point: EDA profile."""
    return evaluate_preop_policy(structured_data=structured_data, exam_type="eda")


def _evaluate_common_preop_policy(
    *,
    structured_data: dict[str, object],
    allow_foreign_body_exception: bool,
    procedure_label: str,
    accepted_imaging: tuple[tuple[str, str], ...] = (),
    imaging_requirement_label: str = "",
    verified_imaging: VerifiedImaging | None = None,
) -> dict[str, object]:
    """Shared deterministic pre-procedure evaluation across profiles (R4/D8).

    ``procedure_label`` is used only in persisted reason texts so a
    colonoscopy case never asserts the EDA rulebook (R4). A avaliação deixa de
    retornar na primeira falha (exceto o bypass de corpo estranho em EDA):
    coleta TODAS as pendências em ordem estável e expõe ``failed_requirements[]``
    mantendo ``reason_code``/``reason_text`` do primeiro item (D8).
    """

    preop_payload = _extract_dict(structured_data, "preop_screening")
    pediatric_flag = _is_pediatric(structured_data)
    subtype = _extract_supported_eda_subtype(structured_data=structured_data)

    if subtype == "foreign_body" and allow_foreign_body_exception:
        return EdaPreopDecision(
            decision="accept",
            reason_code="foreign_body_exception",
            reason_text=_with_pediatric_signal(
                "EDA para retirada de corpo estranho: bypass de exames mínimos nesta etapa.",
                pediatric_flag,
            ),
            evidence_spans=_extract_evidence_spans(preop_payload),
            pediatric_flag=pediatric_flag,
        ).to_dict()

    failures = _collect_failed_requirements(
        structured_data=structured_data,
        procedure_label=procedure_label,
        accepted_imaging=accepted_imaging,
        imaging_requirement_label=imaging_requirement_label,
        verified_imaging=verified_imaging,
    )
    if failures:
        primary = failures[0]
        return EdaPreopDecision(
            decision="deny",
            reason_code=primary.code,
            reason_text=_with_pediatric_signal(primary.text, pediatric_flag),
            evidence_spans=_extract_evidence_spans(preop_payload),
            pediatric_flag=pediatric_flag,
            failed_requirements=failures,
        ).to_dict()

    return EdaPreopDecision(
        decision="accept",
        reason_code="criteria_met",
        reason_text=_with_pediatric_signal(
            f"Critérios determinísticos pré-operatórios de {procedure_label} atendidos nesta etapa.",
            pediatric_flag,
        ),
        evidence_spans=_extract_evidence_spans(preop_payload),
        pediatric_flag=pediatric_flag,
    ).to_dict()


def _collect_failed_requirements(
    *,
    structured_data: dict[str, object],
    procedure_label: str,
    accepted_imaging: tuple[tuple[str, str], ...] = (),
    imaging_requirement_label: str = "",
    verified_imaging: VerifiedImaging | None = None,
) -> list[FailedRequirement]:
    """Coleta TODAS as pendências em ordem estável (D8).

    Ordem: exames mínimos → thresholds → exames condicionais → imagem. A
    categoria de imagem só é avaliada quando o perfil declara
    ``accepted_imaging`` (Ecoendoscopia/CPRE) e recebe SOMENTE a evidência
    aprovada pelo verificador determinístico (D6); perfis EDA/Colonoscopia
    permanecem exatamente como antes, sem pendência de imagem.
    """
    failures: list[FailedRequirement] = []
    failures.extend(_collect_missing_minimum_exams(structured_data=structured_data, procedure_label=procedure_label))
    failures.extend(_collect_threshold_failures(structured_data=structured_data, procedure_label=procedure_label))
    failures.extend(_collect_missing_conditional_exam_gates(structured_data=structured_data))
    failures.extend(
        _collect_imaging_failures(
            accepted_imaging=accepted_imaging,
            verified_imaging=verified_imaging,
            procedure_label=procedure_label,
            imaging_requirement_label=imaging_requirement_label,
        )
    )
    return failures


# Códigos de imagem estáveis e específicos (D8): distinguem ausência de
# modalidade aceita, localização não aceita e ausência de conclusão/achado.
IMAGING_MODALITY_ABSENT = "abdominal_imaging_modality_absent"
IMAGING_SITE_NOT_ACCEPTED = "abdominal_imaging_site_not_accepted"
IMAGING_FINDING_ABSENT = "abdominal_imaging_finding_absent"


def _collect_imaging_failures(
    *,
    accepted_imaging: tuple[tuple[str, str], ...],
    verified_imaging: VerifiedImaging | None,
    procedure_label: str,
    imaging_requirement_label: str = "",
) -> list[FailedRequirement]:
    """Avalia a imagem abdominal adicional de perfis especializados (D7/D8).

    Recebe os outcomes do verificador determinístico. A classificação usa as
    dimensões rederivadas (determinísticas), mas a SATISFAÇÃO exige
    ``verified=True`` com ``report_finding_present="yes"``: excerpt inventado,
    trecho de solicitação/agendamento, ambiguidade ou anexo apenas nunca aceitam.

    ``imaging_requirement_label`` vem do perfil do procedimento (D7) para que o
    motivo exibido descreva o requisito REAL do perfil (CPRE aceita USG e CPRM,
    além de TC/RM; Ecoendoscopia aceita TC/RM).
    """
    if not accepted_imaging:
        return []

    requirement = imaging_requirement_label or "imagem abdominal qualificante"
    outcomes = list(_iter_verified_outcomes(verified_imaging))
    accepted_modalities = {modality for modality, _ in accepted_imaging}
    accepted_pairs = set(accepted_imaging)

    candidates = [outcome for outcome in outcomes if outcome.modality in accepted_modalities]
    if not candidates:
        return [
            FailedRequirement(
                code=IMAGING_MODALITY_ABSENT,
                label="Imagem abdominal",
                category="imaging",
                text=(
                    "Imagem abdominal qualificante ausente no relatório principal para "
                    f"{procedure_label}: é exigida {requirement}."
                ),
            )
        ]

    paired = [outcome for outcome in candidates if (outcome.modality, outcome.anatomical_site) in accepted_pairs]
    if not paired:
        return [
            FailedRequirement(
                code=IMAGING_SITE_NOT_ACCEPTED,
                label="Imagem abdominal (localização)",
                category="imaging",
                text=(
                    "Imagem abdominal com localização anatômica não aceita para "
                    f"{procedure_label}: é exigida {requirement}."
                ),
            )
        ]

    if any(outcome.verified and outcome.report_finding_present == "yes" for outcome in paired):
        return []

    return [
        FailedRequirement(
            code=IMAGING_FINDING_ABSENT,
            label="Imagem abdominal (conclusão/achado)",
            category="imaging",
            text=(
                "Imagem abdominal sem conclusão/achado comprovado no relatório principal "
                f"para {procedure_label}: solicitação, agendamento ou menção não satisfazem."
            ),
        )
    ]


def _iter_verified_outcomes(verified_imaging: VerifiedImaging | None) -> list[ImagingEvidenceOutcome]:
    """Itera os outcomes verificados recebidos da camada de verificação."""
    if verified_imaging is None:
        return []
    if isinstance(verified_imaging, (list, tuple)):
        return list(verified_imaging)
    outcomes = getattr(verified_imaging, "outcomes", None)
    if isinstance(outcomes, (list, tuple)):
        return list(outcomes)
    return []


def _collect_missing_minimum_exams(
    *,
    structured_data: dict[str, object],
    procedure_label: str,
) -> list[FailedRequirement]:
    minimum_exam_evidence = _extract_minimum_exam_evidence(structured_data=structured_data)
    failures: list[FailedRequirement] = []
    for field_name, reason_code, exam_label in _REQUIRED_MINIMUM_EXAMS:
        if _extract_text(minimum_exam_evidence, field_name) != "yes":
            failures.append(
                FailedRequirement(
                    code=reason_code,
                    label=exam_label,
                    category="minimum",
                    text=f"Exame mínimo obrigatório ausente ou insuficiente para {procedure_label}: {exam_label}.",
                )
            )
    return failures


def _collect_threshold_failures(
    *,
    structured_data: dict[str, object],
    procedure_label: str,
) -> list[FailedRequirement]:
    thresholds = _resolve_contraindication_thresholds(structured_data=structured_data)
    failures: list[FailedRequirement] = []

    hb = _extract_hb_value(structured_data=structured_data)
    if hb is not None and hb < thresholds.hb_min:
        failures.append(
            FailedRequirement(
                code="hb_below_threshold",
                label="HB",
                category="threshold",
                text=(
                    f"HB < {thresholds.hb_min:g} para perfil {thresholds.profile_name} "
                    f"dos critérios de {procedure_label}."
                ),
            )
        )

    platelets = _extract_platelets_value(structured_data=structured_data)
    if platelets is not None and platelets < thresholds.platelets_min:
        failures.append(
            FailedRequirement(
                code="platelets_below_threshold",
                label="Plaquetas",
                category="threshold",
                text=(
                    f"Plaquetas < {thresholds.platelets_min} para perfil {thresholds.profile_name} "
                    f"dos critérios de {procedure_label}."
                ),
            )
        )

    rni = _extract_rni_value(structured_data=structured_data)
    if rni is not None and rni > thresholds.rni_max:
        failures.append(
            FailedRequirement(
                code="inr_above_threshold",
                label="RNI/INR",
                category="threshold",
                text=(
                    f"RNI/INR > {thresholds.rni_max:g} para perfil {thresholds.profile_name} "
                    f"dos critérios de {procedure_label}."
                ),
            )
        )

    return failures


def _collect_missing_conditional_exam_gates(
    *,
    structured_data: dict[str, object],
) -> list[FailedRequirement]:
    conditional_exam_requirements = _extract_conditional_exam_requirements(
        structured_data=structured_data,
    )
    failures: list[FailedRequirement] = []

    if _is_ecg_gate_required(structured_data=structured_data):
        if _extract_text(conditional_exam_requirements, "ecg_report_finding_present") != "yes":
            failures.append(
                FailedRequirement(
                    code="missing_ecg_with_cardiovascular_disease",
                    label="ECG",
                    category="conditional",
                    text=(
                        "Critério cardiovascular exige laudo mínimo de ECG no relatório; "
                        "mera menção do exame não satisfaz a completude."
                    ),
                )
            )

    if _is_chest_xray_gate_required(structured_data=structured_data):
        if _extract_text(conditional_exam_requirements, "chest_xray_report_finding_present") != "yes":
            failures.append(
                FailedRequirement(
                    code="missing_chest_xray_with_respiratory_risk",
                    label="RX de tórax",
                    category="conditional",
                    text=(
                        "Critério respiratório exige laudo mínimo de RX de tórax no "
                        "relatório; mera menção do exame não satisfaz a completude."
                    ),
                )
            )

    if _is_echocardiogram_gate_required(structured_data=structured_data):
        if _extract_text(conditional_exam_requirements, "echocardiogram_report_finding_present") != "yes":
            failures.append(
                FailedRequirement(
                    code="missing_echocardiogram_with_structural_heart_risk",
                    label="Ecocardiograma",
                    category="conditional",
                    text=(
                        "Critério cardíaco estrutural exige laudo mínimo de ecocardiograma "
                        "no relatório; mera menção do exame não satisfaz a completude."
                    ),
                )
            )

    return failures


def _resolve_contraindication_thresholds(
    *,
    structured_data: dict[str, object],
) -> ContraindicationThresholds:
    clinical_flags = _extract_clinical_flags(structured_data=structured_data)
    hepatopathy = _extract_text(clinical_flags, "hepatopathy_explicit") == "yes"
    cardiopathy = _extract_text(clinical_flags, "cardiopathy_explicit") == "yes"

    if hepatopathy and cardiopathy:
        return ContraindicationThresholds(
            hb_min=8.0,
            platelets_min=50000,
            rni_max=1.5,
            profile_name="hepatopatia+cardiopatia",
        )
    if cardiopathy:
        return ContraindicationThresholds(
            hb_min=8.0,
            platelets_min=100000,
            rni_max=1.5,
            profile_name="cardiopatia",
        )
    if hepatopathy:
        return ContraindicationThresholds(
            hb_min=7.0,
            platelets_min=50000,
            rni_max=1.5,
            profile_name="hepatopatia",
        )
    return ContraindicationThresholds(
        hb_min=7.0,
        platelets_min=100000,
        rni_max=1.5,
        profile_name="geral",
    )


def _extract_supported_eda_subtype(*, structured_data: dict[str, object]) -> SupportedEdaSubtype:
    eda_payload = _extract_dict(structured_data, "eda")
    requested_procedure = _extract_dict(eda_payload, "requested_procedure")
    subtype = _extract_text(requested_procedure, "subtype")
    if subtype in {"standard", "gastrostomy", "esophageal_dilation", "foreign_body", "echoendoscopy"}:
        return cast(SupportedEdaSubtype, subtype)

    rulebook_signals = _extract_rulebook_signals(structured_data=structured_data)
    rulebook_subtype = _extract_text(rulebook_signals, "eda_subtype")
    if rulebook_subtype in {
        "standard",
        "gastrostomy",
        "esophageal_dilation",
        "foreign_body",
        "echoendoscopy",
    }:
        return cast(SupportedEdaSubtype, rulebook_subtype)

    indication_category = _extract_text(eda_payload, "indication_category")
    if indication_category == "foreign_body":
        return "foreign_body"
    return "standard"


def _extract_hb_value(*, structured_data: dict[str, object]) -> float | None:
    labs_payload = _extract_labs_payload(structured_data=structured_data)
    hb = _extract_float(labs_payload, "hb_g_dl")
    if hb is not None:
        return hb
    preop_payload = _extract_dict(structured_data, "preop_screening")
    return _extract_float(preop_payload, "hb_g_dl")


def _extract_platelets_value(*, structured_data: dict[str, object]) -> int | None:
    labs_payload = _extract_labs_payload(structured_data=structured_data)
    platelets = _extract_int(labs_payload, "platelets_per_mm3")
    if platelets is not None:
        return platelets
    preop_payload = _extract_dict(structured_data, "preop_screening")
    return _extract_int(preop_payload, "platelets_per_mm3")


def _extract_rni_value(*, structured_data: dict[str, object]) -> float | None:
    labs_payload = _extract_labs_payload(structured_data=structured_data)
    for key in ("rni", "inr"):
        value = _extract_float(labs_payload, key)
        if value is not None:
            return value
    preop_payload = _extract_dict(structured_data, "preop_screening")
    return _extract_float(preop_payload, "inr")


def _is_ecg_gate_required(*, structured_data: dict[str, object]) -> bool:
    conditional_exam_requirements = _extract_conditional_exam_requirements(
        structured_data=structured_data,
    )
    if _extract_text(conditional_exam_requirements, "ecg_required") == "yes":
        return True

    clinical_flags = _extract_clinical_flags(structured_data=structured_data)
    preop_payload = _extract_dict(structured_data, "preop_screening")
    return _age_is_above_40(structured_data) or _any_yes(
        _extract_text(clinical_flags, "known_cardiovascular_disease"),
        _extract_text(preop_payload, "has_cardiovascular_disease"),
        _extract_text(clinical_flags, "cardiopathy_explicit"),
        _extract_text(clinical_flags, "recent_chest_pain"),
        _extract_text(clinical_flags, "recent_dyspnea"),
        _extract_text(clinical_flags, "recent_palpitations"),
        _extract_text(clinical_flags, "recent_syncope"),
        _extract_text(clinical_flags, "multiple_comorbidities"),
        _extract_text(clinical_flags, "qt_prolonging_medications"),
        _extract_text(clinical_flags, "diabetes_mellitus"),
        _extract_text(clinical_flags, "explicit_obesity"),
    )


def _is_chest_xray_gate_required(*, structured_data: dict[str, object]) -> bool:
    conditional_exam_requirements = _extract_conditional_exam_requirements(
        structured_data=structured_data,
    )
    if _extract_text(conditional_exam_requirements, "chest_xray_required") == "yes":
        return True

    clinical_flags = _extract_clinical_flags(structured_data=structured_data)
    preop_payload = _extract_dict(structured_data, "preop_screening")
    return _any_yes(
        _extract_text(clinical_flags, "active_respiratory_symptoms"),
        _extract_text(preop_payload, "has_active_respiratory_symptoms"),
        _extract_text(clinical_flags, "prior_respiratory_disease"),
        _extract_text(preop_payload, "has_prior_respiratory_disease"),
    )


def _is_echocardiogram_gate_required(*, structured_data: dict[str, object]) -> bool:
    conditional_exam_requirements = _extract_conditional_exam_requirements(
        structured_data=structured_data,
    )
    if _extract_text(conditional_exam_requirements, "echocardiogram_required") == "yes":
        return True

    clinical_flags = _extract_clinical_flags(structured_data=structured_data)
    return _any_yes(
        _extract_text(clinical_flags, "unexplained_dyspnea"),
        _extract_text(clinical_flags, "heart_failure_signs"),
        _extract_text(clinical_flags, "new_or_unevaluated_murmur"),
        _extract_text(clinical_flags, "moderate_or_severe_valvulopathy_without_recent_echo"),
        _extract_text(clinical_flags, "worsening_cardiomyopathy"),
        _extract_text(clinical_flags, "pulmonary_hypertension"),
        _extract_text(clinical_flags, "prior_myocardial_infarction"),
        _extract_text(clinical_flags, "prior_coronary_bypass"),
        _extract_text(clinical_flags, "prior_coronary_angioplasty"),
    )


def _extract_rulebook_signals(*, structured_data: dict[str, object]) -> dict[str, object]:
    preop_payload = _extract_dict(structured_data, "preop_screening")
    return _extract_dict(preop_payload, "rulebook_signals")


def _extract_minimum_exam_evidence(
    *,
    structured_data: dict[str, object],
) -> dict[str, object]:
    rulebook_signals = _extract_rulebook_signals(structured_data=structured_data)
    return _extract_dict(rulebook_signals, "minimum_exam_evidence")


def _extract_conditional_exam_requirements(
    *,
    structured_data: dict[str, object],
) -> dict[str, object]:
    rulebook_signals = _extract_rulebook_signals(structured_data=structured_data)
    return _extract_dict(rulebook_signals, "conditional_exam_requirements")


def _extract_clinical_flags(*, structured_data: dict[str, object]) -> dict[str, object]:
    rulebook_signals = _extract_rulebook_signals(structured_data=structured_data)
    return _extract_dict(rulebook_signals, "clinical_flags")


def _extract_labs_payload(*, structured_data: dict[str, object]) -> dict[str, object]:
    eda_payload = _extract_dict(structured_data, "eda")
    return _extract_dict(eda_payload, "labs")


def _extract_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _extract_text(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _extract_float(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _extract_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _extract_evidence_spans(preop_payload: dict[str, object]) -> list[dict[str, str]]:
    raw = preop_payload.get("evidence_spans")
    if not isinstance(raw, list):
        return []

    spans: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        field_path = item.get("field_path")
        excerpt = item.get("excerpt")
        if not isinstance(field_path, str) or not isinstance(excerpt, str):
            continue
        normalized_path = field_path.strip()
        normalized_excerpt = excerpt.strip()
        if not normalized_path or not normalized_excerpt:
            continue
        spans.append({"field_path": normalized_path, "excerpt": normalized_excerpt})
    return spans


def _with_pediatric_signal(reason_text: str, pediatric_flag: bool) -> str:
    if not pediatric_flag:
        return reason_text
    return f"{reason_text} Sinalização pediátrica: paciente com idade < 16 anos."


def _any_yes(*values: str | None) -> bool:
    return any(value == "yes" for value in values)


def _age_is_above_40(structured_data: dict[str, object]) -> bool:
    patient_payload = _extract_dict(structured_data, "patient")
    age = patient_payload.get("age")
    if isinstance(age, bool):
        return False
    if isinstance(age, int):
        return age > 40
    return False


def _is_pediatric(structured_data: dict[str, object]) -> bool:
    patient_payload = _extract_dict(structured_data, "patient")
    age = patient_payload.get("age")
    if isinstance(age, bool):
        return False
    if isinstance(age, int):
        return age < 16
    return False
