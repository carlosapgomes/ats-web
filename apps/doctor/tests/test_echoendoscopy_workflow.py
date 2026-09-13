"""Slice 002 (R6) — relatório médico para casos 3.0 especializados.

Cobre:

- o relatório identifica Ecoendoscopia como procedimento (sem cair em modo
  singular legado "EDA");
- a decisão por componente lista o procedimento correto;
- casos 3.0 exibem o aviso de que anexos não participaram da sugestão
  automática (D9), a partir do relatório principal;
- casos 1.1 legados permanecem sem o aviso (limite é do contrato 3.0).
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.cases.models import Case
from apps.cases.procedures import set_declared_procedures
from apps.doctor.reporting import prepare_doctor_case_report

pytestmark = pytest.mark.django_db


def _imaging(context: str) -> dict[str, Any]:
    return {
        "modality": "ct",
        "anatomical_site": "abdomen",
        "report_finding_present": "yes",
        "source_document": "main_report",
        "evidence_context_excerpt": context,
        "finding_excerpt": context,
        "exam_datetime_iso": None,
    }


def _v3_structured_data(*, procedure_type: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": "3.0",
        "language": "pt-BR",
        "agency_record_number": "12345",
        "patient": {"name": "Paciente", "age": 35, "sex": "M", "document_id": None},
        "common_preop": {
            "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0, "source_text_hint": None},
            "ecg": {"report_present": "unknown", "abnormal_flag": "unknown", "source_text_hint": None},
            "asa": {"bucket": "I-II", "source_text_hint": None},
            "cardiovascular_risk": {"level": "low", "source_text_hint": None},
            "rulebook_signals": {
                "eda_subtype": "standard",
                "minimum_exam_evidence": {
                    "hb_numeric_present": "yes",
                    "platelets_numeric_present": "yes",
                    "tp_inr_rni_numeric_present": "yes",
                    "ttpa_present": "yes",
                    "urea_present": "yes",
                    "creatinine_present": "yes",
                },
                "conditional_exam_requirements": {},
                "clinical_flags": {},
            },
            "comorbidities_described": [],
            "medications_described": [],
            "abdominal_imaging": [_imaging("Conclusao: TC de abdome demonstrou lesao")],
            "evidence_spans": [],
        },
        "requested_procedures": [
            {
                "procedure_type": procedure_type,
                "name": "Ecoendoscopia",
                "urgency": "eletivo",
                "evidence_spans": [{"field_path": "p.0", "excerpt": "Solicito ecoendoscopia"}],
            }
        ],
        "policy_precheck": {
            "excluded_from_eda_flow": "no",
            "exclusion_reason": None,
            "labs_required": "yes",
            "labs_pass": "yes",
            "labs_failed_items": [],
            "ecg_required": "no",
            "ecg_present": "unknown",
            "pediatric_flag": False,
            "notes": None,
        },
        "summary": {"one_liner": summary, "bullet_points": ["a", "b", "c"]},
        "extraction_quality": {"confidence": "alta", "missing_fields": [], "notes": None},
        "transfusion": {"had_transfusion": "no"},
    }


def _v3_case(user, *, procedure_type: str) -> Case:
    case = Case.objects.create(
        created_by=user,
        agency_record_number="12345",
        extracted_text="Solicito ecoendoscopia.\nConclusao: TC de abdome demonstrou lesao.",
        structured_data=_v3_structured_data(procedure_type=procedure_type, summary="Ecoendoscopia indicada."),
        suggested_action={
            "schema_version": "3.0",
            "procedure_recommendations": [
                {
                    "procedure_type": procedure_type,
                    "suggestion": "deny",
                    "support_recommendation": "none",
                    "preop_decision": {"decision": "deny", "reason_code": "abdominal_imaging_finding_absent"},
                }
            ],
            "global_support_recommendation": "none",
        },
    )
    set_declared_procedures(case=case, procedure_types=[procedure_type], actor=user)
    return Case.objects.get(case_id=case.case_id)


class TestSpecializedDoctorReport:
    def test_report_identifies_echoendoscopy(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-echo")
        case = _v3_case(user, procedure_type="echoendoscopy")

        report = prepare_doctor_case_report(case).presenter.build_report()

        assert "Ecoendoscopia" in report["context"]["procedure"]
        assert "EDA" not in report["context"]["procedure"]

    def test_decision_block_lists_echoendoscopy(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-echo-2")
        case = _v3_case(user, procedure_type="echoendoscopy")

        blocks = prepare_doctor_case_report(case).presenter.build_report()["blocks"]

        decision_lines = " ".join(blocks["decisao_sugerida"])
        assert "Ecoendoscopia" in decision_lines

    def test_v3_report_warns_that_attachments_are_outside_automation(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-echo-3")
        case = _v3_case(user, procedure_type="echoendoscopy")

        report = prepare_doctor_case_report(case).presenter.build_report()

        notices = " ".join(report["notices"])
        assert "anexo" in notices.lower()
        assert "autom" in notices.lower()

    def test_legacy_case_has_no_attachment_notice(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="doc-legacy")
        case = Case.objects.create(
            created_by=user,
            agency_record_number="12345",
            extracted_text="Solicito EDA.",
            structured_data={
                "schema_version": "1.1",
                "eda": {"requested_procedure": {"subtype": "standard"}},
                "preop_screening": {"evidence_spans": []},
            },
            suggested_action={"suggestion": "accept"},
        )
        set_declared_procedures(case=case, procedure_types=["eda"], actor=user)
        case = Case.objects.get(case_id=case.case_id)

        report = prepare_doctor_case_report(case).presenter.build_report()

        assert report["notices"] == []
