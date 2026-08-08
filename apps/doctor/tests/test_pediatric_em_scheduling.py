"""TDD — Slice 001: decisão pediátrica → agendamento CHD → resultado NIR.

Cobertura:
- R1: DoctorDecisionForm aceita ``pediatric_appt`` e rejeita ``pediatric_em``
  como nova decisão (legado fica apenas para leitura/compatibilidade histórica);
- R2: aceite médico ``pediatric_appt`` transiciona até ``WAIT_APPT`` com
  ``CASE_READY_FOR_SCHEDULER``/``SCHEDULER_REQUEST_POSTED`` e sem notice
  operacional nem ``FINAL_REPLY_POSTED`` na etapa médica;
- R3: fila CHD contém o caso e mostra label inequívoco de entrada pela
  EM Pediátrica;
- R4: confirmação do CHD persiste data/hora e o resultado NIR (ativo e
  histórico CLEANED) exibe data + entrada pela EM Pediátrica + orientação;
  em ``WAIT_APPT`` não há resultado final nem botão de confirmação;
- R5: negativa do CHD preserva motivo no resultado NIR;
- R7: ``pediatric_em`` histórico permanece fluxo operacional sem agendamento.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import claim_case_lock
from tests.shared_case_fixtures import attach_approved_procedures

User = get_user_model()


@pytest.mark.django_db
class TestPediatricEmScheduling:
    """End-to-end checks for the new pediatric scheduled admission flow."""

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
        nir = User.objects.create_user(
            username=f"nir-{timezone.now().timestamp()}@ops.test",
            password="testpass123",
        )
        nir.roles.add(self._role("nir"))
        defaults = {
            "created_by": nir,
            "status": status,
            "agency_record_number": "123456",
            "structured_data": {"patient": {"name": "Paciente Pediátrico", "age": 8, "gender": "Feminino"}},
            "summary_text": "Resumo clínico de teste",
        }
        defaults.update(attrs)
        case = Case.objects.create(**defaults)
        # Projeção aprovada explícita (Slice 009-B): casos CHD-operáveis
        # (doctor_decision="accept") exigem row aprovada para aparecer no
        # universo do agendador. Casos médicos (WAIT_DOCTOR) não a recebem.
        if defaults.get("doctor_decision") == "accept":
            attach_approved_procedures(case, approved=("eda",))
        return case

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

    def _claim_scheduler_lock(self, case: Case, scheduler) -> str:
        result = claim_case_lock(
            case_id=case.case_id,
            user=scheduler,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True
        return str(result.token)

    # ── R1: choice/forms ────────────────────────────────────────────

    def test_form_accepts_pediatric_appt_and_rejects_legacy_pediatric_em(self) -> None:
        from apps.doctor.forms import DoctorDecisionForm

        new_form = DoctorDecisionForm(
            {
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "pediatric_appt",
            }
        )
        assert new_form.is_valid(), new_form.errors
        assert new_form.cleaned_data["admission_flow"] == "pediatric_appt"

        legacy_form = DoctorDecisionForm(
            {
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "pediatric_em",
            }
        )
        assert not legacy_form.is_valid()
        assert "admission_flow" in legacy_form.errors

    def test_decision_page_offers_pediatric_appt_not_pediatric_em(self, client) -> None:
        case = self._make_case()
        self._login_as(client, "doctor", "doctor-page-pediatric@test.com")

        response = client.get(f"/doctor/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="pediatric_appt"' in content
        assert "Compartilhar com EM pediátrica — com agendamento" in content
        assert 'value="pediatric_em"' not in content

    # ── R2: médico aceita → WAIT_APPT ──────────────────────────────

    def test_accept_pediatric_appt_opens_scheduling_gate(self, client) -> None:
        case = self._make_case()
        doctor = self._login_as(client, "doctor", "doctor-submit-pediatric@test.com")
        token = self._claim_doctor_lock(case, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "pediatric_appt",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_admission_flow == "pediatric_appt"
        assert case.status == CaseStatus.WAIT_APPT
        events = CaseEvent.objects.filter(case=case)
        assert events.filter(event_type="DOCTOR_ACCEPT").exists()
        assert events.filter(event_type="CASE_READY_FOR_SCHEDULER").exists()
        assert events.filter(event_type="SCHEDULER_REQUEST_POSTED").exists()
        assert not events.filter(event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE").exists()
        assert not events.filter(event_type="FINAL_REPLY_POSTED").exists()

    # ── R3: fila CHD ───────────────────────────────────────────────

    def test_scheduler_queue_shows_pediatric_appt_case_with_explicit_label(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_appt",
        )
        self._login_as(client, "scheduler", "scheduler-queue-pediatric@test.com")

        response = client.get("/scheduler/")

        assert response.status_code == 200
        content = response.content.decode()
        assert str(case.case_id) in content
        assert "Entrada pela Emergência Pediátrica" in content

    # ── R3/R4: CHD confirma → NIR ativo ────────────────────────────

    def test_scheduler_confirm_pediatric_appt_persists_date_and_nir_result(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_appt",
        )
        scheduler = self._login_as(client, "scheduler", "scheduler-confirm-pediatric@test.com")
        token = self._claim_scheduler_lock(case, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "confirm",
                "appointment_date": "2026-06-15",
                "appointment_time": "14:30",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.appointment_status == "confirmed"
        assert case.appointment_at is not None
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        events = CaseEvent.objects.filter(case=case)
        assert events.filter(event_type="APPT_CONFIRMED").exists()
        assert events.filter(event_type="FINAL_REPLY_POSTED").exists()

        # NIR ativo vê data/hora + via de entrada explícita
        self._login_as(client, "nir", "nir-active-pediatric@test.com")
        detail = client.get(f"/cases/{case.case_id}/")
        assert detail.status_code == 200
        content = detail.content.decode()
        assert "Agendamento Confirmado" in content
        assert "15/06/2026 14:30" in content
        assert "Entrada pela Emergência Pediátrica" in content
        assert "comunicará a Emergência Pediátrica" in content

    # ── R4: sem resultado pronto em WAIT_APPT ──────────────────────

    def test_wait_appt_has_no_final_result_nor_receipt_button(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_appt",
        )
        self._login_as(client, "nir", "nir-wait-appt-pediatric@test.com")

        response = client.get(f"/cases/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" not in content
        assert "Confirmar Recebimento" not in content

    # ── R4: detalhe histórico CLEANED ──────────────────────────────

    def test_closed_detail_preserves_date_and_pediatric_entry(self, client) -> None:
        appt_at = timezone.make_aware(datetime.datetime(2026, 6, 15, 14, 30))
        case = self._make_case(
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_appt",
            appointment_status="confirmed",
            appointment_at=appt_at,
        )
        self._login_as(client, "nir", "nir-closed-pediatric@test.com")

        response = client.get(f"/cases/closed-cases/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content
        assert "15/06/2026 14:30" in content
        assert "Entrada pela Emergência Pediátrica" in content
        assert "comunicará a Emergência Pediátrica" in content

    # ── R5: CHD nega → NIR vê motivo ───────────────────────────────

    def test_scheduler_deny_pediatric_appt_returns_reason_to_nir(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_appt",
        )
        scheduler = self._login_as(client, "scheduler", "scheduler-deny-pediatric@test.com")
        token = self._claim_scheduler_lock(case, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Sala indisponível no período solicitado.",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.appointment_status == "denied"
        assert case.appointment_reason == "Sala indisponível no período solicitado."
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        events = CaseEvent.objects.filter(case=case)
        assert events.filter(event_type="APPT_DENIED").exists()
        assert events.filter(event_type="FINAL_REPLY_POSTED").exists()

        self._login_as(client, "nir", "nir-deny-pediatric@test.com")
        detail = client.get(f"/cases/{case.case_id}/")
        assert detail.status_code == 200
        content = detail.content.decode()
        assert "Agendamento Negado" in content
        assert "Sala indisponível no período solicitado." in content

    # ── R7: legado pediatric_em continua operacional ───────────────

    def test_legacy_pediatric_em_remains_operational_notice(self, client) -> None:
        case = self._make_case(
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="pediatric_em",
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=case.created_by,
            event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE",
            payload={"admission_flow": "pediatric_em", "support_flag": "none"},
        )
        self._login_as(client, "scheduler", "scheduler-legacy-pediatric@test.com")

        queue = client.get("/scheduler/")
        assert queue.status_code == 200
        content = queue.content.decode()
        assert "Compartilhar com EM pediátrica" in content
        assert "Confirmar ciência" in content

        ack = client.post(f"/scheduler/{case.case_id}/immediate-ack/", follow=True)
        assert ack.status_code == 200
        assert CaseEvent.objects.filter(
            case=case,
            event_type="SCHEDULER_OPERATIONAL_NOTICE_ACK",
        ).exists()

        # O caso não é movido para WAIT_APPT
        # (refresh_from_db conflita com o campo status protegido do django-fsm)
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        self._login_as(client, "nir", "nir-legacy-pediatric@test.com")
        detail = client.get(f"/cases/{case.case_id}/")
        assert detail.status_code == 200
        detail_content = detail.content.decode()
        assert "Acionar o coordenador da EM Pediátrica" in detail_content
        assert "Agendamento Confirmado" not in detail_content
