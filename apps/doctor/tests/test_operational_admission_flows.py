"""Regression tests for operational admission flows chosen by the doctor."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import claim_case_lock

User = get_user_model()


@pytest.mark.django_db
class TestOperationalAdmissionFlows:
    """End-to-end checks for non-scheduled admission flows."""

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str):
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_case(self, *, status: str = CaseStatus.WAIT_DOCTOR, **attrs) -> Case:
        nir = User.objects.create_user(username=f"nir-{timezone.now().timestamp()}@ops.test", password="testpass123")
        nir.roles.add(self._role("nir"))
        defaults = {
            "created_by": nir,
            "status": status,
            "agency_record_number": "123456",
            "structured_data": {"patient": {"name": "Paciente Fluxo", "age": 8, "gender": "Feminino"}},
            "summary_text": "Resumo clínico de teste",
        }
        defaults.update(attrs)
        return Case.objects.create(**defaults)

    def _claim_doctor_lock(self, case: Case, doctor) -> str:
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        return str(result.token)

    def test_doctor_form_rejects_anesthesist_icu_final_support(self) -> None:
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            {
                "decision": "accept",
                "support_flag": "anesthesist_icu",
                "admission_flow": "scheduled",
            }
        )

        assert not form.is_valid()
        assert "support_flag" in form.errors

    def test_decision_page_hides_anesthesist_icu_and_shows_new_flows(self, client) -> None:
        case = self._make_case()
        self._login_as(client, "doctor", "doctor-page-ops@test.com")

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert '<option value="anesthesist_icu"' not in content
        assert "Vinda prévia para UTI" in content
        assert "Vinda para enfermaria (para retaguarda em UTI)" in content
        assert "Compartilhar com EM pediátrica" in content

    def test_accept_pre_icu_bypasses_scheduler_and_creates_operational_notice(self, client) -> None:
        case = self._make_case()
        doctor = self._login_as(client, "doctor", "doctor-submit-pre-icu@test.com")
        token = self._claim_doctor_lock(case, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "pre_icu",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_admission_flow == "pre_icu"
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        events = CaseEvent.objects.filter(case=case)
        assert events.filter(event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE").exists()
        assert events.filter(event_type="FINAL_REPLY_POSTED").exists()
        assert not events.filter(event_type="SCHEDULER_REQUEST_POSTED").exists()

    def test_scheduler_acknowledges_pre_icu_notice_and_sees_history_actor(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="pre_icu",
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=case.created_by,
            event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE",
            payload={"admission_flow": "pre_icu", "support_flag": "anesthesist"},
        )
        scheduler = self._login_as(client, "scheduler", "scheduler-pre-icu@test.com")

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Vinda prévia para UTI" in content
        assert "O NIR providenciará a reserva de UTI" in content
        assert "Confirmar ciência" in content

        ack = client.post(f"/scheduler/{case.case_id}/immediate-ack/", follow=True)
        assert ack.status_code == 200
        assert CaseEvent.objects.filter(
            case=case,
            event_type="SCHEDULER_OPERATIONAL_NOTICE_ACK",
            actor=scheduler,
        ).exists()

        history = client.get("/scheduler/?tab=processed")
        assert history.status_code == 200
        history_content = history.content.decode()
        assert "Ciências operacionais confirmadas hoje" in history_content
        assert "scheduler-pre-icu@test.com" in history_content
        assert "Vinda prévia para UTI" in history_content

    def test_nir_result_for_pediatric_em_has_specific_guidance(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_em",
        )
        self._login_as(client, "nir", "nir-pediatric-em@test.com")

        response = client.get(f"/cases/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Compartilhar com EM pediátrica" in content
        assert "Acionar o coordenador da EM Pediátrica" in content
        assert "Agendamento Confirmado" not in content

    def test_dashboard_admission_flow_counts_all_five_flows(self) -> None:
        from apps.dashboard.views import _compute_admission_flow

        for flow in ["scheduled", "immediate", "pre_icu", "ward_icu_backup", "pediatric_em"]:
            self._make_case(
                status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
                doctor_decision="accept",
                doctor_admission_flow=flow,
            )

        result = _compute_admission_flow(period="all")

        assert result["scheduled"] == 1
        assert result["immediate"] == 1
        assert result["pre_icu"] == 1
        assert result["ward_icu_backup"] == 1
        assert result["pediatric_em"] == 1
