"""Slice 003 — Presenter e decisão médica para colonoscopia.

Proves the doctor report identifies Colonoscopia (canonical procedure without
"EDA") and that the existing doctor form/lock/FSM flow accepts and denies
colonoscopy cases without any per-exam branch.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.cases.models import Case, CaseStatus
from apps.doctor.presenters import DoctorReportPresenter

# ── Presenter fixture helpers ───────────────────────────────────────────────


def _colonoscopy_structured() -> dict[str, Any]:
    return {
        "patient": {"name": "Maria", "age": 50, "sex": "F"},
        "eda": {
            "requested_procedure": {"name": "Colonoscopia", "subtype": "standard"},
            "indication_category": "other",
            "is_pediatric": False,
            "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
            "ecg": {"report_present": "unknown", "abnormal_flag": "unknown"},
        },
        "preop_screening": {
            "exam_type": "colonoscopy",
            "medications_described": [
                {
                    "name": "rivaroxabana",
                    "medication_class": "anticoagulant",
                    "use_status": "current",
                    "source_text_hint": "em uso de rivaroxabana",
                }
            ],
        },
        "policy_precheck": {
            "labs_required": True,
            "labs_pass": "yes",
            "ecg_required": False,
            "ecg_present": "unknown",
            "labs_failed_items": [],
            "excluded_from_eda_flow": False,
        },
    }


def _make_presenter(*, exam_type: str = "colonoscopy") -> DoctorReportPresenter:
    return DoctorReportPresenter(
        structured_data=_colonoscopy_structured(),
        summary_text="Colonoscopia eletiva indicada para rastreamento.",
        suggested_action={"suggestion": "accept", "support_recommendation": "none"},
        source_text="Solicito colonoscopia.",
        priority_signals=[],
        exam_type=exam_type,
    )


# ── RED 14: presenter identifica Colonoscopia ───────────────────────────────


class TestColonoscopyPresenter:
    def test_canonical_procedure_is_colonoscopia(self) -> None:
        report = _make_presenter().build_report()
        assert report["context"]["procedure"] == "procedimento solicitado: Colonoscopia"

    def test_procedure_never_says_eda(self) -> None:
        text = _make_presenter().build_text_report()
        assert "procedimento solicitado: Colonoscopia" in text
        assert "procedimento EDA" not in text
        assert "EDA" not in text.splitlines()[1]  # first context line is the procedure

    def test_seven_blocks_remain(self) -> None:
        report = _make_presenter().build_report()
        assert set(report["blocks"].keys()) == {
            "resumo_clinico",
            "achados_criticos",
            "pendencias_criticas",
            "decisao_sugerida",
            "suporte_recomendado",
            "asa_estimado",
            "motivo_objetivo",
        }

    def test_medication_alert_still_rendered(self) -> None:
        report = _make_presenter().build_report()
        critical = "\n".join(report["blocks"]["achados_criticos"])
        assert "Medicamento relevante: rivaroxabana" in critical
        assert "confirmar manejo peri-procedimento" in critical

    def test_eda_presenter_unchanged(self) -> None:
        report = _make_presenter(exam_type="eda").build_report()
        assert report["context"]["procedure"] == "procedimento solicitado: EDA"


# ── RED 15: doctor accept/deny usa fluxo atual ──────────────────────────────


@pytest.mark.django_db
class TestColonoscopyDoctorDecision:
    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(username=f"{role_name}@colon.test", password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _case_at_wait_doctor(self, user) -> Case:
        case = Case.objects.create(
            created_by=user,
            agency_record_number="54321",
            extracted_text="Solicito colonoscopia.",
            exam_type="colonoscopy",
            structured_data=_colonoscopy_structured(),
            summary_text="Colonoscopia eletiva.",
            suggested_action={"suggestion": "accept", "support_recommendation": "none"},
        )
        # Slice 009-A (R4): row detectada explícita autoriza o badge do card
        # médico em modo estrito (sem fallback da ponte ``Case.exam_type``).
        from apps.cases.models import CaseProcedure

        CaseProcedure.objects.create(
            case=case,
            procedure_type="colonoscopy",
            declared_by_nir=True,
            detection_status="detected",
        )
        case.start_processing(user=user)
        case.save()
        case.start_extraction(user=user)
        case.save()
        case.extraction_complete(success=True, user=user)
        case.save()
        case.llm1_complete(success=True, user=user)
        case.save()
        case.llm2_complete(success=True, user=user)
        case.save()
        case.ready_for_doctor()
        case.save()
        return Case.objects.get(case_id=case.case_id)

    def _claim_lock(self, case_id, doctor) -> str:
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        return str(result.token)

    def test_doctor_deny_uses_existing_flow(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(nir)

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={"decision": "deny", "reason": "Exames insuficientes para colonoscopia.", "lock_token": token},
        )
        assert response.status_code == 302

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.doctor_decision == "deny"
        assert case.doctor_reason == "Exames insuficientes para colonoscopia."

    def test_doctor_accept_scheduled_reaches_wait_appt(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(nir)

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "observation": "Agendar colonoscopia.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(case_id=case.case_id)
        assert case.status == CaseStatus.WAIT_APPT
        assert case.doctor_decision == "accept"
        assert case.doctor_admission_flow == "scheduled"

    def test_doctor_decision_page_shows_colonoscopy(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._case_at_wait_doctor(nir)

        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Colonoscopia" in content

    def test_queue_card_identifies_colonoscopy(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._case_at_wait_doctor(nir)

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Badge explícito de tipo no card (não apenas o diagnóstico).
        assert 'class="badge exam-type-badge bg-secondary ms-1">Colonoscopia' in content
