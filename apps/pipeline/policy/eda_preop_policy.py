"""Deterministic pre-procedure EDA policy evaluation rules.

Ported faithfully from:
  triage_automation/domain/policy/eda_preop_policy.py

Every clinical threshold, conditional gate, and profile is preserved exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

DecisionValue = Literal["accept", "deny", "excluded", "manual_review_required"]
SupportedEdaSubtype = Literal[
    "standard",
    "gastrostomy",
    "esophageal_dilation",
    "foreign_body",
]

_REQUIRED_MINIMUM_EXAMS: tuple[tuple[str, str, str], ...] = (
    ("hb_numeric_present", "missing_minimum_exam_hb_or_ht", "Hb/Ht"),
    ("platelets_numeric_present", "missing_minimum_exam_platelets", "plaquetas"),
    ("tp_inr_rni_numeric_present", "missing_minimum_exam_tp_inr_rni", "TP/INR/RNI"),
    ("ttpa_present", "missing_minimum_exam_ttpa", "TTPa"),
    ("urea_present", "missing_minimum_exam_urea", "ureia"),
    ("creatinine_present", "missing_minimum_exam_creatinine", "creatinina"),
)


@dataclass(frozen=True)
class EdaPreopDecision:
    """Deterministic pre-procedure decision with explicit reason metadata."""

    decision: DecisionValue
    reason_code: str
    reason_text: str
    evidence_spans: list[dict[str, str]]
    pediatric_flag: bool

    def to_dict(self) -> dict[str, object]:
        """Serialize deterministic decision payload for persistence and downstream use."""

        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason_text": self.reason_text,
            "evidence_spans": self.evidence_spans,
            "pediatric_flag": self.pediatric_flag,
        }


@dataclass(frozen=True)
class ContraindicationThresholds:
    """Numeric contraindication thresholds derived from the rewritten rulebook."""

    hb_min: float
    platelets_min: int
    rni_max: float
    profile_name: str


def evaluate_eda_preop_policy(*, structured_data: dict[str, object]) -> dict[str, object]:
    """Evaluate deterministic EDA pre-procedure criteria from structured extraction."""

    preop_payload = _extract_dict(structured_data, "preop_screening")
    pediatric_flag = _is_pediatric(structured_data)
    subtype = _extract_supported_eda_subtype(structured_data=structured_data)

    if subtype == "foreign_body":
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

    minimum_exam_failure = _find_missing_minimum_exam(structured_data=structured_data)
    if minimum_exam_failure is not None:
        reason_code, exam_label = minimum_exam_failure
        return _deny(
            reason_code=reason_code,
            reason_text=(f"Exame mínimo obrigatório ausente ou insuficiente para EDA: {exam_label}."),
            structured_data=structured_data,
        )

    thresholds = _resolve_contraindication_thresholds(structured_data=structured_data)
    hb = _extract_hb_value(structured_data=structured_data)
    if hb is not None and hb < thresholds.hb_min:
        return _deny(
            reason_code="hb_below_threshold",
            reason_text=(f"HB < {thresholds.hb_min:g} para perfil {thresholds.profile_name} do rulebook EDA."),
            structured_data=structured_data,
        )

    platelets = _extract_platelets_value(structured_data=structured_data)
    if platelets is not None and platelets < thresholds.platelets_min:
        return _deny(
            reason_code="platelets_below_threshold",
            reason_text=(
                f"Plaquetas < {thresholds.platelets_min} para perfil {thresholds.profile_name} do rulebook EDA."
            ),
            structured_data=structured_data,
        )

    rni = _extract_rni_value(structured_data=structured_data)
    if rni is not None and rni > thresholds.rni_max:
        return _deny(
            reason_code="inr_above_threshold",
            reason_text=(f"RNI/INR > {thresholds.rni_max:g} para perfil {thresholds.profile_name} do rulebook EDA."),
            structured_data=structured_data,
        )

    conditional_exam_failure = _find_missing_conditional_exam_gate(
        structured_data=structured_data,
    )
    if conditional_exam_failure is not None:
        reason_code, reason_text = conditional_exam_failure
        return _deny(
            reason_code=reason_code,
            reason_text=reason_text,
            structured_data=structured_data,
        )

    return EdaPreopDecision(
        decision="accept",
        reason_code="criteria_met",
        reason_text=_with_pediatric_signal(
            "Critérios determinísticos do rulebook EDA atendidos nesta etapa.",
            pediatric_flag,
        ),
        evidence_spans=_extract_evidence_spans(preop_payload),
        pediatric_flag=pediatric_flag,
    ).to_dict()


def _deny(
    *,
    reason_code: str,
    reason_text: str,
    structured_data: dict[str, object],
) -> dict[str, object]:
    preop_payload = _extract_dict(structured_data, "preop_screening")
    pediatric_flag = _is_pediatric(structured_data)
    return EdaPreopDecision(
        decision="deny",
        reason_code=reason_code,
        reason_text=_with_pediatric_signal(reason_text, pediatric_flag),
        evidence_spans=_extract_evidence_spans(preop_payload),
        pediatric_flag=pediatric_flag,
    ).to_dict()


def _find_missing_minimum_exam(
    *,
    structured_data: dict[str, object],
) -> tuple[str, str] | None:
    minimum_exam_evidence = _extract_minimum_exam_evidence(structured_data=structured_data)
    for field_name, reason_code, exam_label in _REQUIRED_MINIMUM_EXAMS:
        if _extract_text(minimum_exam_evidence, field_name) != "yes":
            return reason_code, exam_label
    return None


def _find_missing_conditional_exam_gate(
    *,
    structured_data: dict[str, object],
) -> tuple[str, str] | None:
    conditional_exam_requirements = _extract_conditional_exam_requirements(
        structured_data=structured_data,
    )

    if _is_ecg_gate_required(structured_data=structured_data):
        if (
            _extract_text(
                conditional_exam_requirements,
                "ecg_report_finding_present",
            )
            != "yes"
        ):
            return (
                "missing_ecg_with_cardiovascular_disease",
                "Critério cardiovascular exige laudo mínimo de ECG no relatório; "
                "mera menção do exame não satisfaz a completude.",
            )

    if _is_chest_xray_gate_required(structured_data=structured_data):
        if (
            _extract_text(
                conditional_exam_requirements,
                "chest_xray_report_finding_present",
            )
            != "yes"
        ):
            return (
                "missing_chest_xray_with_respiratory_risk",
                "Critério respiratório exige laudo mínimo de RX de tórax no "
                "relatório; mera menção do exame não satisfaz a completude.",
            )

    if _is_echocardiogram_gate_required(structured_data=structured_data):
        if (
            _extract_text(
                conditional_exam_requirements,
                "echocardiogram_report_finding_present",
            )
            != "yes"
        ):
            return (
                "missing_echocardiogram_with_structural_heart_risk",
                "Critério cardíaco estrutural exige laudo mínimo de ecocardiograma "
                "no relatório; mera menção do exame não satisfaz a completude.",
            )

    return None


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
    if subtype in {"standard", "gastrostomy", "esophageal_dilation", "foreign_body"}:
        return cast(SupportedEdaSubtype, subtype)

    rulebook_signals = _extract_rulebook_signals(structured_data=structured_data)
    rulebook_subtype = _extract_text(rulebook_signals, "eda_subtype")
    if rulebook_subtype in {
        "standard",
        "gastrostomy",
        "esophageal_dilation",
        "foreign_body",
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
