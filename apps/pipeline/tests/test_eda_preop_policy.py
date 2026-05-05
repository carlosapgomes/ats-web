"""Tests for deterministic EDA preop policy engine.

Ported faithfully from:
  tests/unit/test_eda_preop_policy.py

Every test case, fixture, and assertion preserved. Only the import path changed.
"""

from __future__ import annotations

import importlib
from typing import cast

import pytest


def _base_llm1_structured_data() -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "agency_record_number": "12345",
        "patient": {
            "name": "Paciente",
            "age": 45,
            "sex": "F",
            "document_id": None,
        },
        "eda": {
            "indication_category": "dyspepsia",
            "exclusion_type": "none",
            "is_pediatric": False,
            "foreign_body_suspected": False,
            "requested_procedure": {
                "name": "EDA",
                "urgency": "eletivo",
                "subtype": "standard",
            },
            "labs": {
                "hb_g_dl": 10.5,
                "hct_percent": 31.0,
                "platelets_per_mm3": 180000,
                "tp_seconds": 12.0,
                "inr": 1.1,
                "rni": 1.1,
                "ttpa_seconds": 30.0,
                "urea_mg_dl": 28.0,
                "creatinine_mg_dl": 0.9,
                "source_text_hint": None,
            },
            "ecg": {
                "report_present": "yes",
                "abnormal_flag": "no",
                "source_text_hint": None,
            },
        },
        "preop_screening": {
            "exam_type": "eda",
            "has_cardiovascular_disease": "no",
            "has_active_respiratory_symptoms": "no",
            "has_prior_respiratory_disease": "no",
            "has_ecg_report": "yes",
            "has_chest_xray_report": "yes",
            "has_echocardiogram_report": "unknown",
            "hb_g_dl": 10.5,
            "platelets_per_mm3": 180000,
            "inr": 1.1,
            "evidence_spans": [
                {
                    "field_path": ("preop_screening.rulebook_signals.minimum_exam_evidence"),
                    "excerpt": "hb, plaquetas, inr, ttpa e funcao renal presentes",
                }
            ],
            "rulebook_signals": {
                "eda_subtype": "standard",
                "minimum_exam_evidence": {
                    "hb_or_hct_present": "yes",
                    "hb_numeric_present": "yes",
                    "platelets_numeric_present": "yes",
                    "tp_inr_rni_numeric_present": "yes",
                    "ttpa_present": "yes",
                    "urea_present": "yes",
                    "creatinine_present": "yes",
                    "coagulogram_normal_supports_ttpa": "no",
                    "renal_function_preserved_supports_urea_and_creatinine": "no",
                },
                "conditional_exam_requirements": {
                    "ecg_required": "yes",
                    "chest_xray_required": "unknown",
                    "echocardiogram_required": "unknown",
                    "ecg_report_finding_present": "yes",
                    "chest_xray_report_finding_present": "unknown",
                    "echocardiogram_report_finding_present": "unknown",
                },
                "clinical_flags": {
                    "hepatopathy_explicit": "no",
                    "cardiopathy_explicit": "no",
                    "known_cardiovascular_disease": "no",
                    "active_respiratory_symptoms": "no",
                    "prior_respiratory_disease": "no",
                    "multiple_comorbidities": "unknown",
                    "qt_prolonging_medications": "unknown",
                    "diabetes_mellitus": "unknown",
                    "explicit_obesity": "unknown",
                    "recent_chest_pain": "no",
                    "recent_dyspnea": "no",
                    "recent_palpitations": "no",
                    "recent_syncope": "no",
                    "unexplained_dyspnea": "unknown",
                    "heart_failure_signs": "unknown",
                    "new_or_unevaluated_murmur": "unknown",
                    "moderate_or_severe_valvulopathy_without_recent_echo": "unknown",
                    "worsening_cardiomyopathy": "unknown",
                    "pulmonary_hypertension": "unknown",
                    "prior_myocardial_infarction": "no",
                    "prior_coronary_bypass": "no",
                    "prior_coronary_angioplasty": "no",
                },
            },
        },
        "policy_precheck": {
            "excluded_from_eda_flow": False,
            "exclusion_reason": None,
            "labs_required": True,
            "labs_pass": "yes",
            "labs_failed_items": [],
            "ecg_required": True,
            "ecg_present": "yes",
            "pediatric_flag": False,
            "notes": None,
        },
        "summary": {
            "one_liner": "Resumo clinico",
            "bullet_points": ["a", "b", "c"],
        },
        "extraction_quality": {
            "confidence": "media",
            "missing_fields": [],
            "notes": None,
        },
    }


def _evaluate_preop_policy(*, structured_data: dict[str, object]) -> dict[str, object]:
    module = importlib.import_module("apps.pipeline.policy.eda_preop_policy")
    evaluate = getattr(module, "evaluate_eda_preop_policy")
    result = evaluate(structured_data=structured_data)
    assert isinstance(result, dict)
    return cast(dict[str, object], result)


def test_gastrostomy_uses_supported_eda_rulebook_and_is_not_excluded() -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    requested_procedure = cast(dict[str, object], eda["requested_procedure"])
    requested_procedure["subtype"] = "gastrostomy"
    requested_procedure["name"] = "EDA para gastrostomia"

    preop = cast(dict[str, object], payload["preop_screening"])
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    rulebook_signals["eda_subtype"] = "gastrostomy"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "accept"
    assert result["reason_code"] == "criteria_met"


def test_missing_creatinine_minimum_exam_drives_deny() -> None:
    payload = _base_llm1_structured_data()
    preop = cast(dict[str, object], payload["preop_screening"])
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    minimum_exam_evidence = cast(dict[str, object], rulebook_signals["minimum_exam_evidence"])
    minimum_exam_evidence["creatinine_present"] = "no"

    eda = cast(dict[str, object], payload["eda"])
    labs = cast(dict[str, object], eda["labs"])
    labs["creatinine_mg_dl"] = None

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == "missing_minimum_exam_creatinine"


def test_qualitative_ttpa_and_renal_equivalences_satisfy_minimum_exam_rulebook() -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    labs = cast(dict[str, object], eda["labs"])
    labs["ttpa_seconds"] = None
    labs["urea_mg_dl"] = None
    labs["creatinine_mg_dl"] = None

    preop = cast(dict[str, object], payload["preop_screening"])
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    minimum_exam_evidence = cast(dict[str, object], rulebook_signals["minimum_exam_evidence"])
    minimum_exam_evidence["ttpa_present"] = "yes"
    minimum_exam_evidence["coagulogram_normal_supports_ttpa"] = "yes"
    minimum_exam_evidence["urea_present"] = "yes"
    minimum_exam_evidence["creatinine_present"] = "yes"
    minimum_exam_evidence["renal_function_preserved_supports_urea_and_creatinine"] = "yes"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "accept"
    assert result["reason_code"] == "criteria_met"


def test_cardiopathy_threshold_uses_hb_less_than_8_rule() -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    labs = cast(dict[str, object], eda["labs"])
    labs["hb_g_dl"] = 7.9

    preop = cast(dict[str, object], payload["preop_screening"])
    preop["hb_g_dl"] = 7.9
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    clinical_flags = cast(dict[str, object], rulebook_signals["clinical_flags"])
    clinical_flags["cardiopathy_explicit"] = "yes"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == "hb_below_threshold"


def test_combined_hepatopathy_and_cardiopathy_uses_mixed_platelet_threshold() -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    labs = cast(dict[str, object], eda["labs"])
    labs["platelets_per_mm3"] = 49999

    preop = cast(dict[str, object], payload["preop_screening"])
    preop["platelets_per_mm3"] = 49999
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    clinical_flags = cast(dict[str, object], rulebook_signals["clinical_flags"])
    clinical_flags["hepatopathy_explicit"] = "yes"
    clinical_flags["cardiopathy_explicit"] = "yes"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == "platelets_below_threshold"


def test_age_above_40_requires_ecg_finding_not_only_exam_mention() -> None:
    payload = _base_llm1_structured_data()
    preop = cast(dict[str, object], payload["preop_screening"])
    preop["has_ecg_report"] = "yes"
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    conditional_exam_requirements = cast(
        dict[str, object],
        rulebook_signals["conditional_exam_requirements"],
    )
    conditional_exam_requirements["ecg_required"] = "unknown"
    conditional_exam_requirements["ecg_report_finding_present"] = "unknown"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == "missing_ecg_with_cardiovascular_disease"


def test_respiratory_risk_requires_chest_xray_finding_not_only_exam_mention() -> None:
    payload = _base_llm1_structured_data()
    preop = cast(dict[str, object], payload["preop_screening"])
    preop["has_chest_xray_report"] = "yes"
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    conditional_exam_requirements = cast(
        dict[str, object],
        rulebook_signals["conditional_exam_requirements"],
    )
    conditional_exam_requirements["chest_xray_required"] = "unknown"
    conditional_exam_requirements["chest_xray_report_finding_present"] = "unknown"
    clinical_flags = cast(dict[str, object], rulebook_signals["clinical_flags"])
    clinical_flags["active_respiratory_symptoms"] = "yes"
    preop["has_active_respiratory_symptoms"] = "yes"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == "missing_chest_xray_with_respiratory_risk"


def test_structural_heart_risk_requires_echocardiogram_finding() -> None:
    payload = _base_llm1_structured_data()
    preop = cast(dict[str, object], payload["preop_screening"])
    preop["has_echocardiogram_report"] = "yes"
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    conditional_exam_requirements = cast(
        dict[str, object],
        rulebook_signals["conditional_exam_requirements"],
    )
    conditional_exam_requirements["echocardiogram_required"] = "unknown"
    conditional_exam_requirements["echocardiogram_report_finding_present"] = "unknown"
    clinical_flags = cast(dict[str, object], rulebook_signals["clinical_flags"])
    clinical_flags["prior_myocardial_infarction"] = "yes"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == "missing_echocardiogram_with_structural_heart_risk"


def test_unknown_suspicion_does_not_force_ecg_gate_without_explicit_trigger() -> None:
    payload = _base_llm1_structured_data()
    patient = cast(dict[str, object], payload["patient"])
    patient["age"] = 39
    preop = cast(dict[str, object], payload["preop_screening"])
    preop["has_cardiovascular_disease"] = "unknown"
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    conditional_exam_requirements = cast(
        dict[str, object],
        rulebook_signals["conditional_exam_requirements"],
    )
    conditional_exam_requirements["ecg_required"] = "unknown"
    conditional_exam_requirements["ecg_report_finding_present"] = "unknown"
    clinical_flags = cast(dict[str, object], rulebook_signals["clinical_flags"])
    clinical_flags["known_cardiovascular_disease"] = "unknown"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "accept"
    assert result["reason_code"] == "criteria_met"


def test_foreign_body_bypasses_minimum_exam_and_threshold_denials() -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    eda["indication_category"] = "foreign_body"
    eda["foreign_body_suspected"] = True
    requested_procedure = cast(dict[str, object], eda["requested_procedure"])
    requested_procedure["subtype"] = "foreign_body"
    requested_procedure["name"] = "EDA para retirada de corpo estranho"
    labs = cast(dict[str, object], eda["labs"])
    labs["hb_g_dl"] = None
    labs["platelets_per_mm3"] = None
    labs["inr"] = None
    labs["rni"] = None
    labs["ttpa_seconds"] = None
    labs["urea_mg_dl"] = None
    labs["creatinine_mg_dl"] = None

    preop = cast(dict[str, object], payload["preop_screening"])
    preop["hb_g_dl"] = None
    preop["platelets_per_mm3"] = None
    preop["inr"] = None
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    rulebook_signals["eda_subtype"] = "foreign_body"
    minimum_exam_evidence = cast(dict[str, object], rulebook_signals["minimum_exam_evidence"])
    for key in tuple(minimum_exam_evidence):
        minimum_exam_evidence[key] = "unknown"
    conditional_exam_requirements = cast(
        dict[str, object],
        rulebook_signals["conditional_exam_requirements"],
    )
    conditional_exam_requirements["ecg_required"] = "yes"
    conditional_exam_requirements["chest_xray_required"] = "yes"
    conditional_exam_requirements["echocardiogram_required"] = "yes"
    conditional_exam_requirements["ecg_report_finding_present"] = "no"
    conditional_exam_requirements["chest_xray_report_finding_present"] = "no"
    conditional_exam_requirements["echocardiogram_report_finding_present"] = "no"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "accept"
    assert result["reason_code"] == "foreign_body_exception"


def test_pediatric_case_sets_flag_and_explicit_reason_text_signal() -> None:
    payload = _base_llm1_structured_data()
    patient = cast(dict[str, object], payload["patient"])
    patient["age"] = 15
    eda = cast(dict[str, object], payload["eda"])
    eda["is_pediatric"] = True
    policy_precheck = cast(dict[str, object], payload["policy_precheck"])
    policy_precheck["pediatric_flag"] = True

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["pediatric_flag"] is True
    reason_text = cast(str, result["reason_text"])
    assert "pedi" in reason_text.lower()


@pytest.mark.parametrize(
    ("field_name", "lab_key", "reason_code"),
    [
        (
            "platelets_numeric_present",
            "platelets_per_mm3",
            "missing_minimum_exam_platelets",
        ),
        (
            "tp_inr_rni_numeric_present",
            "rni",
            "missing_minimum_exam_tp_inr_rni",
        ),
        (
            "creatinine_present",
            "creatinine_mg_dl",
            "missing_minimum_exam_creatinine",
        ),
    ],
)
def test_missing_minimum_exam_fields_map_to_explicit_reason_codes(
    field_name: str,
    lab_key: str,
    reason_code: str,
) -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    labs = cast(dict[str, object], eda["labs"])
    labs[lab_key] = None
    if field_name == "tp_inr_rni_numeric_present":
        labs["inr"] = None

    preop = cast(dict[str, object], payload["preop_screening"])
    if field_name == "platelets_numeric_present":
        preop["platelets_per_mm3"] = None
    if field_name == "tp_inr_rni_numeric_present":
        preop["inr"] = None
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    minimum_exam_evidence = cast(dict[str, object], rulebook_signals["minimum_exam_evidence"])
    minimum_exam_evidence[field_name] = "no"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == reason_code


@pytest.mark.parametrize(
    ("profile", "lab_key", "lab_value", "reason_code"),
    [
        ("hepatopathy_hb", "hb_g_dl", 6.9, "hb_below_threshold"),
        ("hepatopathy_rni", "rni", 1.6, "inr_above_threshold"),
        ("general_hb", "hb_g_dl", 6.9, "hb_below_threshold"),
    ],
)
def test_threshold_profiles_cover_hepatopathy_and_general_rulebook_paths(
    profile: str,
    lab_key: str,
    lab_value: float,
    reason_code: str,
) -> None:
    payload = _base_llm1_structured_data()
    eda = cast(dict[str, object], payload["eda"])
    labs = cast(dict[str, object], eda["labs"])
    labs[lab_key] = lab_value
    if lab_key == "rni":
        labs["inr"] = lab_value

    preop = cast(dict[str, object], payload["preop_screening"])
    if lab_key == "hb_g_dl":
        preop["hb_g_dl"] = lab_value
    if lab_key == "rni":
        preop["inr"] = lab_value
    rulebook_signals = cast(dict[str, object], preop["rulebook_signals"])
    clinical_flags = cast(dict[str, object], rulebook_signals["clinical_flags"])
    if profile.startswith("hepatopathy"):
        clinical_flags["hepatopathy_explicit"] = "yes"

    result = _evaluate_preop_policy(structured_data=payload)

    assert result["decision"] == "deny"
    assert result["reason_code"] == reason_code
