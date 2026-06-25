"""Tests for scheduler queue view."""

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Role
from apps.cases.models import Case, CaseCommunicationMessage, CaseEvent, CaseStatus

User = get_user_model()


@pytest.mark.django_db
class TestSchedulerQueueView:
    """Tests for the scheduler queue view (GET /scheduler/)."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> None:
        """Create user with given role, login, and set active_role in session."""
        user = User.objects.create_user(username=f"{role_name}@sched.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    # ── Authentication tests ──────────────────────────────────────────

    def test_queue_requires_login(self, client) -> None:
        """GET /scheduler/ without auth redirects to login."""
        response = client.get("/scheduler/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_queue_accessible_for_scheduler(self, client) -> None:
        """GET /scheduler/ returns 200 for user with active_role='scheduler'."""
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200

    def test_queue_has_htmx_polling_container(self, client) -> None:
        """Full scheduler page polls the partial endpoint with HTMX."""
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'hx-get="/scheduler/partials/queue/?tab=pending"' in content
        assert 'hx-trigger="every 20s"' in content

    def test_queue_partial_renders_without_layout(self, client) -> None:
        """HTMX partial returns scheduler queue content without full layout."""
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/partials/queue/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<!DOCTYPE html>" not in content
        assert "Atualizado automaticamente" in content

    # ── Content tests ─────────────────────────────────────────────────

    def test_queue_shows_doctor_observation_badge_only_for_filled_pending_cases(self, client) -> None:
        """WAIT_APPT cards show medical observation badge only when filled."""
        nir_user = User.objects.create_user(username="nir_obs_pending@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            agency_record_number="OBS-001",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            doctor_observation="Preparar sala com suporte X",
            structured_data={"patient": {"name": "Paciente Com Obs", "age": 61, "gender": "Feminino"}},
        )
        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            agency_record_number="OBS-002",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            doctor_observation="   ",
            structured_data={"patient": {"name": "Paciente Sem Obs", "age": 62, "gender": "Masculino"}},
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente Com Obs" in content
        assert "Paciente Sem Obs" in content
        assert content.count("Orientação médica") == 1

    def test_queue_shows_pending_cases(self, client) -> None:
        """Pending (WAIT_APPT) cases appear in the queue."""
        nir_user = User.objects.create_user(username="nir_pend@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            agency_record_number="2026-0428-001",
            summary_text="Catarata bilateral — cirurgia eletiva",
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="scheduled",
            structured_data={
                "patient": {
                    "name": "Maria Silva dos Santos",
                    "age": 75,
                    "gender": "Feminino",
                },
            },
        )
        case.save()

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Silva dos Santos" in content
        assert "2026-0428-001" in content

    def test_queue_shows_doctor_decision_in_cards(self, client) -> None:
        """Cards display doctor decision, support flag, and admission flow."""
        nir_user = User.objects.create_user(username="nir_dd@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_support_flag="anesthesist_icu",
            doctor_admission_flow="immediate",
            structured_data={
                "patient": {"name": "João Teste", "age": 50, "gender": "Masculino"},
            },
        )
        case.save()

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "ACEITAR" in content
        assert "Anestesista + UTI" in content

    def test_queue_shows_immediate_admission_doctor_observation_in_card(self, client) -> None:
        """Immediate admission cards show badge and full observation in the queue."""
        nir_user = User.objects.create_user(username="nir_immediate_obs@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        observation = "Avisar equipe de plantão e reservar suporte anestésico."

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="IMM-OBS",
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="immediate",
            doctor_observation=observation,
            structured_data={"patient": {"name": "Imediata Com Obs", "age": 70, "gender": "Masculino"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Imediata Com Obs" in content
        assert "Orientação médica" in content
        assert observation in content

    def test_queue_shows_immediate_admission_operational_notice(self, client) -> None:
        """Immediate admission appears as operational notice, not scheduling gate."""
        nir_user = User.objects.create_user(username="nir_immediate_notice@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="IMM-001",
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Vinda Imediata", "age": 70, "gender": "Masculino"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Vinda imediata autorizada" in content
        assert "Não abrir agendamento" in content
        assert "Confirmar ciência" in content
        assert "Vinda Imediata" in content
        assert "IMM-001" in content
        assert f'href="/scheduler/{case.case_id}/"' not in content

    def test_immediate_admission_ack_removes_notice_from_queue(self, client) -> None:
        """Scheduler can acknowledge immediate notice and remove it from queue."""
        nir_user = User.objects.create_user(username="nir_immediate_ack@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="IMM-ACK",
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Ack Imediata", "age": 70, "gender": "Masculino"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        self._login_as(client, "scheduler")
        response = client.post(f"/scheduler/{case.case_id}/immediate-ack/", follow=True)
        assert response.status_code == 200

        assert CaseEvent.objects.filter(case=case, event_type="SCHEDULER_IMMEDIATE_ACK").exists()
        content = response.content.decode()
        assert "Ack Imediata" not in content
        assert "IMM-ACK" not in content

    def test_queue_hides_acknowledged_immediate_admission_notice(self, client) -> None:
        """Acknowledged immediate notices do not remain stuck in scheduler queue."""
        nir_user = User.objects.create_user(username="nir_immediate_hidden@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="IMM-HIDDEN",
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Hidden Imediata", "age": 70, "gender": "Masculino"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="SCHEDULER_IMMEDIATE_ACK",
            timestamp=timezone.now(),
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Hidden Imediata" not in content
        assert "IMM-HIDDEN" not in content

    def test_queue_shows_waiting_time(self, client) -> None:
        """Case cards display waiting time since created_at."""
        nir_user = User.objects.create_user(username="nir_wt@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            structured_data={
                "patient": {"name": "Teste Tempo", "age": 40, "gender": "Feminino"},
            },
        )
        case.created_at = timezone.now() - timedelta(minutes=30)
        case.save()

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "30" in content

    # ── Role guard tests ────────────────────────────────────────────

    def test_queue_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot access /scheduler/."""
        self._login_as(client, "nir")
        response = client.get("/scheduler/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_queue_blocks_doctor(self, client) -> None:
        """Doctor with active_role='doctor' cannot access /scheduler/."""
        self._login_as(client, "doctor")
        response = client.get("/scheduler/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_queue_blocks_manager(self, client) -> None:
        """Manager with active_role='manager' cannot access /scheduler/."""
        self._login_as(client, "manager")
        response = client.get("/scheduler/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_queue_partial_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot access HTMX partial."""
        self._login_as(client, "nir")
        response = client.get("/scheduler/partials/queue/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_immediate_ack_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot POST immediate ack."""
        nir_user = User.objects.create_user(username="nir_ackblock@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Ack Block", "age": 50, "gender": "M"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        self._login_as(client, "nir")
        response = client.post(f"/scheduler/{case.case_id}/immediate-ack/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_exclude_non_wait_appt(self, client) -> None:
        """Cases with status != WAIT_APPT do not appear in pending list."""
        nir_user = User.objects.create_user(username="nir_excl@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # WAIT_APPT → should appear
        pending = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            structured_data={"patient": {"name": "Pendente Scheduler", "age": 30, "gender": "Masculino"}},
        )
        pending.save()

        # WAIT_DOCTOR → should NOT appear
        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Falso Positivo", "age": 40, "gender": "Feminino"}},
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Pendente Scheduler" in content
        assert "Falso Positivo" not in content


@pytest.mark.django_db
class TestSchedulerConfirmView:
    """Tests for the scheduler confirm view (GET /scheduler/<uuid>/)."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> None:
        user = User.objects.create_user(username=f"{role_name}@confirm.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(username="nir_case@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Maria Silva dos Santos",
                    "age": 75,
                    "gender": "Feminino",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    # ── Authentication ────────────────────────────────────────────────

    def test_confirm_requires_login(self, client) -> None:
        """GET /scheduler/<uuid>/ without auth redirects to login."""
        case = self._create_waited_case()
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_confirm_accessible_for_scheduler(self, client) -> None:
        """GET /scheduler/<uuid>/ returns 200 for scheduler with WAIT_APPT case."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200

    # ── Role guard tests ────────────────────────────────────────────

    def test_confirm_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot access confirm."""
        self._login_as(client, "nir")
        case = self._create_waited_case()
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_confirm_blocks_doctor(self, client) -> None:
        """Doctor with active_role='doctor' cannot access confirm."""
        self._login_as(client, "doctor")
        case = self._create_waited_case()
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_confirm_blocks_manager(self, client) -> None:
        """Manager with active_role='manager' cannot access confirm."""
        self._login_as(client, "manager")
        case = self._create_waited_case()
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 302
        assert response.url == "/"

    # ── Guard ─────────────────────────────────────────────────────────

    def test_confirm_404_for_non_wait_appt(self, client) -> None:
        """GET /scheduler/<uuid>/ returns 404 for case not in WAIT_APPT."""
        self._login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir_g@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Teste", "age": 30, "gender": "M"}},
        )
        case.save()
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 404

    def test_confirm_404_for_unknown_case(self, client) -> None:
        """GET /scheduler/<uuid>/ returns 404 for non-existent case."""
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404

    # ── Content ───────────────────────────────────────────────────────

    def test_confirm_shows_case_info(self, client) -> None:
        """Confirm page shows patient name, record, and doctor decision."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case(agency_record_number="2026-0507-001")
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Silva dos Santos" in content
        assert "2026-0507-001" in content
        assert "ACEITAR" in content

    def test_confirm_shows_doctor_observation_when_filled(self, client) -> None:
        """Confirm page shows full medical observation when filled."""
        self._login_as(client, "scheduler")
        observation = "Preparar sala com suporte X e manter anestesista disponível."
        case = self._create_waited_case(doctor_observation=observation)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Orientações médicas" in content
        assert observation in content

    def test_confirm_hides_doctor_observation_when_empty_or_spaces(self, client) -> None:
        """Confirm page does not render empty orientation UI."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case(doctor_observation="   ")

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Orientações médicas" not in content

    def test_confirm_shows_doctor_display(self, client) -> None:
        """Confirm page shows doctor name and CRM."""
        self._login_as(client, "scheduler")
        doctor = User.objects.create_user(
            username="doc.confirm@test.com",
            password="pass123",
            first_name="Laura",
            last_name="Mendes",
        )
        doctor.professional_council = "CRM"
        doctor.professional_council_number = "99999"
        doctor.save()
        case = self._create_waited_case(
            agency_record_number="2026-0507-DOC",
            doctor=doctor,
        )
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Laura Mendes" in content
        assert "CRM 99999" in content


@pytest.mark.django_db
class TestSchedulerQueueDoctorDisplay:
    """Tests for doctor display in scheduler queue cards."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> None:
        user = User.objects.create_user(username=f"{role_name}@docdisp.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    def _create_nir(self):
        nir = User.objects.create_user(username="nir_docdisp@test.com", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        return nir

    def _create_doctor(self, first_name: str, last_name: str, council: str = "", number: str = ""):
        doc = User.objects.create_user(
            username=f"{first_name.lower()}.{last_name.lower()}",
            password="pass123",
            first_name=first_name,
            last_name=last_name,
        )
        if council and number:
            doc.professional_council = council
            doc.professional_council_number = number
            doc.save()
        return doc

    def test_pending_case_shows_doctor_display(self, client) -> None:
        """WAIT_APPT card shows doctor name and CRM."""
        nir = self._create_nir()
        doctor = self._create_doctor("Rafael", "Oliveira", "CRM", "77777")
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor,
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Paciente Teste", "age": 50, "gender": "M"}},
        )
        case.save()

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Rafael Oliveira" in content
        assert "CRM 77777" in content

    def test_immediate_notice_shows_doctor_display(self, client) -> None:
        """Immediate admission notice shows doctor name and CRM."""
        nir = self._create_nir()
        doctor = self._create_doctor("Juliana", "Lima", "CRM", "88888")
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor=doctor,
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Paciente Imediata", "age": 60, "gender": "F"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Juliana Lima" in content
        assert "CRM 88888" in content

    def test_pending_case_shows_doctor_without_crm(self, client) -> None:
        """WAIT_APPT card shows at least doctor name when no CRM."""
        nir = self._create_nir()
        doctor = self._create_doctor("Fernando", "Almeida")
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor,
            doctor_decision="accept",
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Paciente Nocrm", "age": 45, "gender": "M"}},
        )
        case.save()

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Fernando Almeida" in content


@pytest.mark.django_db
class TestSchedulerDecisionForm:
    """Tests for SchedulerDecisionForm validation."""

    def _valid_confirm_data(self, **overrides) -> dict[str, str]:
        data: dict[str, str] = {
            "decision": "confirm",
            "appointment_date": "2026-05-15",
            "appointment_time": "14:30",
            "notes": "Trazer exames.",
            "reason": "",
        }
        data.update(overrides)
        return data

    def _valid_deny_data(self, **overrides) -> dict[str, str]:
        data: dict[str, str] = {
            "decision": "deny",
            "appointment_date": "",
            "appointment_time": "",
            "notes": "",
            "reason": "Indisponibilidade de vaga na data solicitada.",
        }
        data.update(overrides)
        return data

    def test_confirm_valid(self) -> None:
        """Confirm with date and time is valid."""
        from apps.scheduler.forms import SchedulerDecisionForm

        form = SchedulerDecisionForm(data=self._valid_confirm_data())
        assert form.is_valid()
        assert form.cleaned_data["decision"] == "confirm"

    def test_deny_valid(self) -> None:
        """Deny with reason is valid."""
        from apps.scheduler.forms import SchedulerDecisionForm

        form = SchedulerDecisionForm(data=self._valid_deny_data())
        assert form.is_valid()
        assert form.cleaned_data["decision"] == "deny"

    def test_confirm_missing_date_invalid(self) -> None:
        """Confirm without date is invalid."""
        from apps.scheduler.forms import SchedulerDecisionForm

        form = SchedulerDecisionForm(data=self._valid_confirm_data(appointment_date=""))
        assert not form.is_valid()
        assert "appointment_date" in form.errors

    def test_confirm_missing_time_invalid(self) -> None:
        """Confirm without time is invalid."""
        from apps.scheduler.forms import SchedulerDecisionForm

        form = SchedulerDecisionForm(data=self._valid_confirm_data(appointment_time=""))
        assert not form.is_valid()
        assert "appointment_time" in form.errors

    def test_deny_missing_reason_invalid(self) -> None:
        """Deny without reason is invalid."""
        from apps.scheduler.forms import SchedulerDecisionForm

        form = SchedulerDecisionForm(data=self._valid_deny_data(reason=""))
        assert not form.is_valid()
        assert "reason" in form.errors


@pytest.mark.django_db
class TestSchedulerSubmitView:
    """Tests for the scheduler submit view (POST /scheduler/<uuid>/submit/)."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> None:
        user = User.objects.create_user(username=f"{role_name}@submit.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(username="nir_sub@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Maria Silva dos Santos",
                    "age": 75,
                    "gender": "Feminino",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    def _claim_lock(self, case_id, scheduler) -> str:
        """Acquire a scheduler_confirm lock for the given case and user."""
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=scheduler,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True
        return str(result.token)

    # ── Confirm submit ────────────────────────────────────────────────

    def test_submit_confirm_updates_case(self, client) -> None:
        """POST confirm transiciona para APPT_CONFIRMED → WAIT_R1_CLEANUP_THUMBS e persiste campos."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@submit.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-05-15",
                "appointment_time": "14:30",
                "notes": "Trazer exames.",
                "reason": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"
        assert updated_case.appointment_at is not None
        local_at = timezone.localtime(updated_case.appointment_at)
        assert local_at.date() == date(2026, 5, 15)
        assert local_at.hour == 14
        assert local_at.minute == 30
        assert updated_case.appointment_instructions == "Trazer exames."
        assert updated_case.scheduler == scheduler_user
        assert updated_case.appointment_decided_at is not None

    def test_submit_confirm_creates_case_events(self, client) -> None:
        """POST confirm registra CaseEvent APPT_CONFIRMED + FINAL_REPLY_POSTED."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@submit.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-05-15",
                "appointment_time": "14:30",
                "notes": "",
                "reason": "",
                "lock_token": token,
            },
        )

        assert CaseEvent.objects.filter(case=case, event_type="APPT_CONFIRMED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

    # ── Deny submit ───────────────────────────────────────────────────

    def test_submit_deny_updates_case(self, client) -> None:
        """POST deny transiciona para APPT_DENIED → WAIT_R1_CLEANUP_THUMBS e persiste motivo."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@submit.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "Indisponibilidade de vaga.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "denied"
        assert updated_case.appointment_reason == "Indisponibilidade de vaga."
        assert updated_case.scheduler == scheduler_user
        assert updated_case.appointment_decided_at is not None

    def test_submit_deny_creates_case_events(self, client) -> None:
        """POST deny registra CaseEvent APPT_DENIED + FINAL_REPLY_POSTED."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@submit.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "Conflito de agenda.",
                "lock_token": token,
            },
        )

        assert CaseEvent.objects.filter(case=case, event_type="APPT_DENIED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

    # ── Role guard tests ────────────────────────────────────────────

    def test_submit_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot POST submit."""
        self._login_as(client, "nir")
        case = self._create_waited_case()
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"decision": "confirm", "appointment_date": "2026-05-15", "appointment_time": "14:30"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_submit_blocks_doctor(self, client) -> None:
        """Doctor with active_role='doctor' cannot POST submit."""
        self._login_as(client, "doctor")
        case = self._create_waited_case()
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"decision": "confirm", "appointment_date": "2026-05-15", "appointment_time": "14:30"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_submit_blocks_manager(self, client) -> None:
        """Manager with active_role='manager' cannot POST submit."""
        self._login_as(client, "manager")
        case = self._create_waited_case()
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"decision": "confirm", "appointment_date": "2026-05-15", "appointment_time": "14:30"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    # ── Guards ────────────────────────────────────────────────────────

    def test_submit_invalid_form_rerenders(self, client) -> None:
        """POST with invalid data re-renders template with errors."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "",
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Informe a data do agendamento" in content

    def test_submit_404_for_non_wait_appt(self, client) -> None:
        """POST for case not in WAIT_APPT returns 404."""
        self._login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir_sg@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            structured_data={"patient": {"name": "Teste", "age": 30, "gender": "M"}},
        )
        case.save()

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"decision": "confirm", "appointment_date": "2026-05-15", "appointment_time": "14:30"},
        )
        assert response.status_code == 404

    def test_submit_get_returns_404(self, client) -> None:
        """GET to submit URL returns 404."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        response = client.get(f"/scheduler/{case.case_id}/submit/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestSchedulerConfirmLock:
    """Tests for scheduler_confirm lock acquisition and template."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@lock.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(username="nir_lock@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Maria Lock",
                    "age": 75,
                    "gender": "Feminino",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    def test_confirm_acquires_lock_on_get(self, client) -> None:
        """GET scheduler_confirm acquires a WORK_LOCK_CLAIMED with context scheduler_confirm."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200

        # Lock should be acquired
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is not None
        assert case.lock_context == "scheduler_confirm"
        assert case.lock_role == "scheduler"
        assert case.lock_token is not None
        assert case.locked_until is not None
        assert case.locked_at is not None

        # Verify event
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_CLAIMED").exists()

    def test_confirm_template_contains_lock_token_and_js_config(self, client) -> None:
        """Template contains hidden lock_token and work-lock-config for JS heartbeat."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Hidden lock_token input
        assert 'name="lock_token"' in content
        assert 'type="hidden"' in content

        # Work lock JS config
        assert "data-work-lock-config" in content
        assert "data-renew-url" in content
        assert "data-release-url" in content
        assert "data-lock-token" in content

        # work_lock.js script loaded
        assert "work_lock.js" in content

        # Warning element exists
        assert "work-lock-warning" in content

    def test_second_scheduler_blocked_from_locked_case(self, client) -> None:
        """Second scheduler cannot open confirm page for case locked by another scheduler."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        # First scheduler acquires lock
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200

        # Second scheduler tries to open
        scheduler_b = User.objects.create_user(username="scheduler_b@lock.test", password="testpass123")
        scheduler_b.roles.add(self._create_role("scheduler"))
        client.force_login(scheduler_b)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        response = client.get(f"/scheduler/{case.case_id}/")
        # Should redirect to queue with a warning
        assert response.status_code == 302
        assert response.url == "/scheduler/"

    def test_submit_with_valid_token_succeeds(self, client) -> None:
        """POST submit with valid lock_token confirms and follows FSM."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        # First acquire lock via GET
        client.get(f"/scheduler/{case.case_id}/")
        case = Case.objects.get(pk=case.case_id)
        token = str(case.lock_token)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-15",
                "appointment_time": "14:30",
                "notes": "Confirmado",
                "reason": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        # Verify FSM transition
        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"

    def test_submit_without_token_does_not_submit(self, client) -> None:
        """POST submit without lock_token does not alter case status."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-15",
                "appointment_time": "14:30",
                "notes": "",
                "reason": "",
            },
        )
        assert response.status_code == 200  # Re-renders with error
        content = response.content.decode()
        assert "reserva" in content.lower() or "Token" in content

        # Case should still be WAIT_APPT
        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_APPT

    def test_submit_with_invalid_token_returns_error(self, client) -> None:
        """POST submit with invalid lock_token does not alter case."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-15",
                "appointment_time": "14:30",
                "notes": "",
                "reason": "",
                "lock_token": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "reserva" in content.lower()

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_APPT

    def test_expired_lock_can_be_assumed_by_another_scheduler(self, client) -> None:
        """Expired lock can be taken over by another scheduler."""
        scheduler_a = self._login_as(client, "scheduler")
        case = self._create_waited_case()

        # Acquire lock with lease_seconds=0 (expired immediately via manual override not possible through view)
        # We'll use the service directly
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case.case_id,
            user=scheduler_a,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
            lease_seconds=0,
        )
        assert result.acquired is True

        # Force expiration
        from datetime import timedelta

        from django.utils import timezone

        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        # Second scheduler claims expired lock
        scheduler_b = User.objects.create_user(username="scheduler_exp@lock.test", password="testpass123")
        scheduler_b.first_name = "Sched"
        scheduler_b.last_name = "B"
        scheduler_b.roles.add(self._create_role("scheduler"))
        client.force_login(scheduler_b)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200

        # Must have WORK_LOCK_EXPIRED event
        expired_event = CaseEvent.objects.filter(
            case=case,
            event_type="WORK_LOCK_EXPIRED",
        ).last()
        assert expired_event is not None
        assert expired_event.payload.get("expired_locked_by_id") is not None
        assert expired_event.payload.get("context") == "scheduler_confirm"


@pytest.mark.django_db
class TestSchedulerLockEndpoints:
    """Tests for scheduler lock renew/release endpoints."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@locksvc.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(username="nir_locksvc@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Lock Svc",
                    "age": 50,
                    "gender": "M",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    def test_renew_requires_scheduler_role(self, client) -> None:
        """Renew endpoint redirects non-scheduler roles."""
        case = self._create_waited_case()
        self._login_as(client, "nir")
        response = client.post(f"/scheduler/{case.case_id}/lock/renew/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_release_requires_scheduler_role(self, client) -> None:
        """Release endpoint redirects non-scheduler roles."""
        case = self._create_waited_case()
        self._login_as(client, "nir")
        response = client.post(f"/scheduler/{case.case_id}/lock/release/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_renew_rejects_get(self, client) -> None:
        """Renew endpoint returns 404 for GET."""
        case = self._create_waited_case()
        self._login_as(client, "scheduler")
        response = client.get(f"/scheduler/{case.case_id}/lock/renew/")
        assert response.status_code == 404

    def test_release_rejects_get(self, client) -> None:
        """Release endpoint returns 404 for GET."""
        case = self._create_waited_case()
        self._login_as(client, "scheduler")
        response = client.get(f"/scheduler/{case.case_id}/lock/release/")
        assert response.status_code == 404

    def test_renew_with_valid_token_returns_success(self, client) -> None:
        """POST renew with valid token returns JSON success."""
        user = self._login_as(client, "scheduler")
        case = self._create_waited_case()

        # Acquire lock first
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True

        response = client.post(
            f"/scheduler/{case.case_id}/lock/renew/",
            data={"lock_token": str(result.token)},
        )
        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data.get("success") is True
        assert "locked_until" in data

    def test_renew_with_invalid_token_returns_error(self, client) -> None:
        """POST renew with invalid token returns error."""
        user = self._login_as(client, "scheduler")
        case = self._create_waited_case()

        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True

        import uuid

        response = client.post(
            f"/scheduler/{case.case_id}/lock/renew/",
            data={"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data.get("success") is False
        assert "error" in data

    def test_release_with_valid_token_clears_lock(self, client) -> None:
        """POST release with valid token clears lock fields."""
        user = self._login_as(client, "scheduler")
        case = self._create_waited_case()

        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True

        response = client.post(
            f"/scheduler/{case.case_id}/lock/release/",
            data={"lock_token": str(result.token)},
        )
        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data.get("success") is True

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is None
        assert case.lock_token is None

    def test_release_with_invalid_token_does_not_clear(self, client) -> None:
        """POST release with invalid token does not clear lock."""
        user = self._login_as(client, "scheduler")
        case = self._create_waited_case()

        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True

        import uuid

        response = client.post(
            f"/scheduler/{case.case_id}/lock/release/",
            data={"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data.get("success") is False

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == user


@pytest.mark.django_db
class TestSchedulerQueueLockDisplay:
    """Tests for lock display in scheduler queue."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@qldisp.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(username="nir_qldisp@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Queue Lock",
                    "age": 45,
                    "gender": "M",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    def test_queue_shows_locked_by_other_scheduler(self, client) -> None:
        """WAIT_APPT case locked by another scheduler shows lock info."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()

        # Lock the case to another user directly
        other = User.objects.create_user(username="other_sched@qldisp.test", password="testpass123")
        other.first_name = "Outro"
        other.last_name = "Agendador"
        other.roles.add(self._create_role("scheduler"))
        other.save()

        import uuid
        from datetime import timedelta

        from django.utils import timezone

        Case.objects.filter(case_id=case.case_id).update(
            locked_by=other,
            locked_at=timezone.now(),
            locked_until=timezone.now() + timedelta(minutes=5),
            lock_token=uuid.uuid4(),
            lock_context="scheduler_confirm",
            lock_role="scheduler",
        )

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        assert "Outro Agendador" in content or other.display_name in content
        assert "Agendar" not in content or "disabled" in content

    def test_queue_shows_continue_for_own_lock(self, client) -> None:
        """WAIT_APPT case locked by current user shows continue button."""
        user = self._login_as(client, "scheduler")
        case = self._create_waited_case()

        # Lock the case to current user
        import uuid
        from datetime import timedelta

        from django.utils import timezone

        Case.objects.filter(case_id=case.case_id).update(
            locked_by=user,
            locked_at=timezone.now(),
            locked_until=timezone.now() + timedelta(minutes=5),
            lock_token=uuid.uuid4(),
            lock_context="scheduler_confirm",
            lock_role="scheduler",
        )

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        # Should show a way to continue, not a disabled button
        assert "disabled" not in content or "Reservado" not in content
        # The case should still be visible
        assert "Queue Lock" in content or "Agendar" in content


@pytest.mark.django_db
class TestImmediateAckIdempotent:
    """Tests for immediate_ack idempotency under concurrency."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@immack.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def test_immediate_ack_requires_scheduler_role(self, client) -> None:
        """POST immediate_ack blocks non-scheduler roles."""
        nir_user = User.objects.create_user(username="nir_immack@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Imm Ack", "age": 50, "gender": "M"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        self._login_as(client, "nir")
        response = client.post(f"/scheduler/{case.case_id}/immediate-ack/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_immediate_ack_does_not_duplicate_event(self, client) -> None:
        """Repeated POST immediate_ack does not create multiple SCHEDULER_IMMEDIATE_ACK events."""
        self._login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir_dup@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Dup Imm", "age": 50, "gender": "M"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        # Call twice
        client.post(f"/scheduler/{case.case_id}/immediate-ack/")
        client.post(f"/scheduler/{case.case_id}/immediate-ack/")

        events = CaseEvent.objects.filter(case=case, event_type="SCHEDULER_IMMEDIATE_ACK")
        assert events.count() == 1

    def test_immediate_ack_removes_notice_from_queue(self, client) -> None:
        """After ack, case no longer appears in immediate notice section."""
        self._login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir_imm_remove@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Remove Imm", "age": 50, "gender": "M"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        # Before ack: notice should appear
        response = client.get("/scheduler/")
        assert "Remove Imm" in response.content.decode()

        # After ack: notice should disappear
        client.post(f"/scheduler/{case.case_id}/immediate-ack/")
        response = client.get("/scheduler/")
        assert "Remove Imm" not in response.content.decode()


@pytest.mark.django_db
class TestSchedulerExpiredLockInQueue:
    """Tests for expired locks appearing available in scheduler queue."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@expired.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def test_expired_lock_shows_available_in_scheduler_queue(self, client) -> None:
        """Case with expired lock shows as available in scheduler queue."""
        from apps.cases.services import claim_case_lock

        nir_user = User.objects.create_user(username="nir_exp_sched@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="scheduled",
            structured_data={
                "patient": {
                    "name": "Sched Expired Lock",
                    "age": 55,
                    "gender": "Masculino",
                },
            },
        )
        case.save()

        sched_a = User.objects.create_user(username="sched_expired@test.com", password="testpass123")
        sched_a.roles.add(self._create_role("scheduler"))
        sched_a.first_name = "Sched. Antigo"
        sched_a.save()

        # Claim lock and force expiration
        claim_case_lock(
            case_id=case.case_id,
            user=sched_a,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
            lease_seconds=0,
        )
        from datetime import timedelta

        from django.utils import timezone

        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        # Login as another scheduler — queue calls expire_stale_locks
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        # Case should appear and NOT be locked by the previous owner
        assert "Sched Expired Lock" in content
        assert "Sched. Antigo" not in content
        case_from_db = Case.objects.get(pk=case.case_id)
        assert case_from_db.locked_by is None


# ── Lock release on submit tests ──────────────────────────────────────────


@pytest.mark.django_db
class TestSchedulerLockReleaseOnSubmit:
    """RED tests: lock is released after successful submit, preserved on errors."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@schlocksub.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(username="nir_schlocksub@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Sched Lock Release",
                    "age": 50,
                    "gender": "M",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    def _claim_lock(self, case_id, scheduler_user) -> str:
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=scheduler_user,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True
        return str(result.token)

    def test_submit_confirm_releases_lock_after_success(self, client) -> None:
        """POST confirm → lock cleared, WORK_LOCK_RELEASED created."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@schlocksub.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-10",
                "appointment_time": "10:00",
                "notes": "",
                "reason": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.locked_by is None
        assert case.lock_token is None
        assert case.lock_context == ""
        assert case.lock_role == ""
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_deny_releases_lock_after_success(self, client) -> None:
        """POST deny → lock cleared, WORK_LOCK_RELEASED created."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@schlocksub.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "Vaga indisponível",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.locked_by is None
        assert case.lock_token is None
        assert case.lock_context == ""
        assert case.lock_role == ""
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_invalid_form_preserves_lock(self, client) -> None:
        """POST invalid form → lock preserved, status unchanged."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@schlocksub.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        # confirm without date/time
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_APPT  # unchanged
        assert case.locked_by == scheduler_user
        assert not CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_without_token_preserves_lock_and_status(self, client) -> None:
        """POST without lock_token → status unchanged, lock preserved."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@schlocksub.test")
        self._claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-10",
                "appointment_time": "10:00",
                "notes": "",
                "reason": "",
                # no lock_token
            },
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_APPT  # unchanged
        assert case.locked_by == scheduler_user
        assert not CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_with_invalid_token_preserves_lock_and_status(self, client) -> None:
        """POST with invalid lock_token → status unchanged, lock preserved."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@schlocksub.test")
        self._claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-10",
                "appointment_time": "10:00",
                "notes": "",
                "reason": "",
                "lock_token": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_APPT  # unchanged
        assert case.locked_by == scheduler_user
        assert not CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_handoff_scheduler_to_nir_immediate(self, client) -> None:
        """Handoff imediato: scheduler confirma → NIR abre detalhe sem esperar."""
        # Scheduler submits confirm
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@schlocksub.test")
        token = self._claim_lock(case.case_id, scheduler_user)

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-10",
                "appointment_time": "10:00",
                "notes": "",
                "reason": "",
                "lock_token": token,
            },
        )

        # Now login as NIR
        nir_user = User.objects.create_user(username="nir_sched_handoff@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        client.force_login(nir_user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.locked_by is None  # scheduler released lock

        # NIR opens detail immediately
        from django.urls import reverse

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200

        # NIR acquired their own lock
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == nir_user
        assert case.lock_context == "nir_receipt"


@pytest.mark.django_db
class TestSchedulerProcessedTodayTab:
    """Tests for the Processados Hoje tab in scheduler queue."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> Any:
        user = User.objects.create_user(username=f"{role_name}@proctab.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case(self, scheduler_user: Any = None, **overrides: Any) -> Case:
        nir_user = User.objects.create_user(username="nir_proctab@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        defaults: dict[str, Any] = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "scheduler": scheduler_user or nir_user,
            "appointment_status": "confirmed",
            "appointment_decided_at": timezone.now(),
            "structured_data": {
                "patient": {
                    "name": "Paciente Processado",
                    "age": 45,
                    "gender": "Masculino",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    # ── Navigation tests ────────────────────────────────────────────────

    def test_queue_nav_has_functional_processed_tab_and_no_history(self, client) -> None:
        """GET /scheduler/ contains Processados Hoje link, no Histórico nor Confirmados Hoje."""
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "?tab=processed" in content
        assert "Processados Hoje" in content
        assert "Histórico" not in content
        assert "Confirmados Hoje" not in content

    # ── Query tests ────────────────────────────────────────────────────

    def test_processed_today_tab_uses_appointment_decided_at_not_status(self, client) -> None:
        """Processados Hoje uses appointment_decided_at, not FSM status."""
        scheduler_user = self._login_as(client, "scheduler")
        self._create_case(
            scheduler_user=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            status=CaseStatus.CLEANED,
            agency_record_number="DECIDED-001",
        )
        response = client.get("/scheduler/?tab=processed")
        assert response.status_code == 200
        content = response.content.decode()
        assert "DECIDED-001" in content or "Paciente Processado" in content

    def test_processed_today_tab_includes_denied_cases(self, client) -> None:
        """Denied cases appear in Processados Hoje."""
        scheduler_user = self._login_as(client, "scheduler")
        self._create_case(
            scheduler_user=scheduler_user,
            appointment_status="denied",
            appointment_decided_at=timezone.now(),
            appointment_reason="Vaga indisponível",
            agency_record_number="DENIED-001",
        )
        response = client.get("/scheduler/?tab=processed")
        assert response.status_code == 200
        content = response.content.decode()
        assert "DENIED-001" in content

    def test_processed_today_tab_excludes_other_scheduler_cases(self, client) -> None:
        """Cases processed by another scheduler do not appear."""
        self._login_as(client, "scheduler")
        other_scheduler = User.objects.create_user(username="other_sched_proc@test.com", password="testpass123")
        other_scheduler.roles.add(self._create_role("scheduler"))
        self._create_case(
            scheduler_user=other_scheduler,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="OTHER-SCHED",
        )
        response = client.get("/scheduler/?tab=processed")
        assert response.status_code == 200
        content = response.content.decode()
        assert "OTHER-SCHED" not in content

    def test_pending_tab_does_not_render_processed_list(self, client) -> None:
        """GET /scheduler/?tab=pending does not show processed list."""
        scheduler_user = self._login_as(client, "scheduler")
        self._create_case(
            scheduler_user=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="PEND-NO-SHOW",
        )
        response = client.get("/scheduler/?tab=pending")
        assert response.status_code == 200
        content = response.content.decode()
        assert "PEND-NO-SHOW" not in content

    def test_processed_tab_has_detail_link(self, client) -> None:
        """Processados Hoje item contains link to processed_detail."""
        scheduler_user = self._login_as(client, "scheduler")
        case = self._create_case(
            scheduler_user=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="DETAIL-LINK",
        )
        response = client.get("/scheduler/?tab=processed")
        assert response.status_code == 200
        content = response.content.decode()
        assert f"processed/{case.case_id}/" in content
        assert "Ver detalhes" in content

    # ── Detail view tests ──────────────────────────────────────────────

    def test_scheduler_processed_detail_renders_read_only_case_detail(self, client) -> None:
        """Scheduler can view read-only detail of own processed case."""
        scheduler_user = self._login_as(client, "scheduler")
        case = self._create_case(
            scheduler_user=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="DETAIL-001",
        )
        response = client.get(f"/scheduler/processed/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "DETAIL-001" in content or case.agency_record_number in content
        assert "Voltar aos processados hoje" in content
        assert "btn-hospital-outline" in content or "btn-outline-secondary" in content

    def test_scheduler_processed_detail_404_for_other_scheduler_case(self, client) -> None:
        """Scheduler A gets 404 for case processed by scheduler B."""
        self._login_as(client, "scheduler")
        other_scheduler = User.objects.create_user(username="other_sched_detail@test.com", password="testpass123")
        other_scheduler.roles.add(self._create_role("scheduler"))
        case = self._create_case(
            scheduler_user=other_scheduler,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="OTHER-DETAIL",
        )
        response = client.get(f"/scheduler/processed/{case.case_id}/")
        assert response.status_code == 404

    def test_scheduler_processed_pdf_404_for_other_scheduler_case(self, client) -> None:
        """Scheduler A gets 404 for PDF of case processed by scheduler B."""
        self._login_as(client, "scheduler")
        other_scheduler = User.objects.create_user(username="other_sched_pdf@test.com", password="testpass123")
        other_scheduler.roles.add(self._create_role("scheduler"))
        case = self._create_case(
            scheduler_user=other_scheduler,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="OTHER-PDF",
        )
        response = client.get(f"/scheduler/processed/{case.case_id}/pdf/")
        assert response.status_code == 404

    def test_queue_partial_preserves_processed_tab(self, client) -> None:
        """HTMX partial for tab=processed returns processed content, not pending."""
        scheduler_user = self._login_as(client, "scheduler")
        self._create_case(
            scheduler_user=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            agency_record_number="PARTIAL-PROC",
        )
        response = client.get("/scheduler/partials/queue/?tab=processed")
        assert response.status_code == 200
        content = response.content.decode()
        assert "PARTIAL-PROC" in content
        assert "Atualizado automaticamente" in content


@pytest.mark.django_db
class TestSchedulerQueueRegulationDays:
    """Tests for regulation_days_on_screen ordering and display in scheduler queue."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> None:
        user = User.objects.create_user(username=f"{role_name}@regdays.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    # ── Ordering tests ──────────────────────────────────────────────────

    def test_queue_orders_wait_appt_by_regulation_days_desc(self, client) -> None:
        """WAIT_APPT ordena por regulation_days_on_screen DESC, NULL por último."""
        nir_user = User.objects.create_user(username="nir_regorder@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        now = timezone.now()

        case_a = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=2,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Case A (2 days)", "age": 40, "gender": "M"}},
        )
        Case.objects.filter(case_id=case_a.case_id).update(created_at=now - timedelta(hours=3))

        case_b = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=10,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Case B (10 days)", "age": 50, "gender": "F"}},
        )
        Case.objects.filter(case_id=case_b.case_id).update(created_at=now - timedelta(hours=2))

        case_c = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=None,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Case C (null)", "age": 30, "gender": "M"}},
        )
        Case.objects.filter(case_id=case_c.case_id).update(created_at=now - timedelta(hours=1))

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        # B (10) deve aparecer antes de A (2), e A antes de C (null)
        pos_b = content.index("Case B (10 days)")
        pos_a = content.index("Case A (2 days)")
        pos_c = content.index("Case C (null)")
        assert pos_b < pos_a, f"B (10) should be before A (2): B={pos_b}, A={pos_a}"
        assert pos_a < pos_c, f"A (2) should be before C (null): A={pos_a}, C={pos_c}"

    # ── Display tests ───────────────────────────────────────────────────

    def test_queue_shows_regulation_days_badge_when_available(self, client) -> None:
        """Card WAIT_APPT exibe badge 'Dias em tela: N' quando disponível."""
        nir_user = User.objects.create_user(username="nir_regbadge@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=10,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Badge Test", "age": 45, "gender": "M"}},
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dias em tela: 10" in content

    def test_queue_hides_regulation_days_badge_when_null(self, client) -> None:
        """Card WAIT_APPT NÃO exibe badge 'Dias em tela' quando campo é None."""
        nir_user = User.objects.create_user(username="nir_noreg@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=None,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "No Badge", "age": 35, "gender": "F"}},
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dias em tela:" not in content

    # ── Tiebreaker test ─────────────────────────────────────────────────

    def test_queue_uses_created_at_as_tiebreaker(self, client) -> None:
        """Empate em regulation_days_on_screen usa created_at mais antigo primeiro."""
        nir_user = User.objects.create_user(username="nir_tiesched@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        now = timezone.now()

        old_case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=5,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "Old (created first)", "age": 40, "gender": "M"}},
        )
        Case.objects.filter(case_id=old_case.case_id).update(created_at=now - timedelta(hours=5))

        new_case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=5,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "New (created later)", "age": 50, "gender": "F"}},
        )
        Case.objects.filter(case_id=new_case.case_id).update(created_at=now - timedelta(hours=1))

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        pos_old = content.index("Old (created first)")
        pos_new = content.index("New (created later)")
        assert pos_old < pos_new, "Older case should appear before newer when tie"

    # ── Immediate notice above WAIT_APPT test ───────────────────────────

    def test_queue_nav_uses_action_and_neutral_count_badges(self, client) -> None:
        """Pendentes uses action badge, Processados Hoje uses neutral badge."""
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        # Pendentes should have data-count and the action/danger class
        assert "nav-count-badge--danger" in content, "Pendentes must use danger/action badge class"
        # Processados Hoje should have data-count and the neutral class
        assert "nav-count-badge--neutral" in content, "Processados Hoje must use neutral badge class"
        # Processados Hoje link must NOT use .notif-badge
        assert "notif-badge" not in content.split("Processados Hoje")[0][-300:], (
            "Processados Hoje must not use .notif-badge"
        )

    def test_processed_today_nav_badge_uses_processed_today_count(self, client) -> None:
        """Processados Hoje badge uses processed_today_count from context."""
        self._login_as(client, "scheduler")
        scheduler_user = User.objects.get(username="scheduler@regdays.test")

        # Create a case processed today by this scheduler
        nir_user = User.objects.create_user(username="nir_proc_count@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="PROC-COUNT-001",
            doctor_decision="accept",
            doctor_support_flag="anesthesist",
            doctor_admission_flow="scheduled",
            scheduler=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            structured_data={
                "patient": {
                    "name": "Proc Count",
                    "age": 50,
                    "gender": "M",
                },
            },
        )
        case.save()

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        # The Processados Hoje link should have data-count="1"
        # Find the link containing Processados Hoje
        processed_idx = content.find("Processados Hoje")
        assert processed_idx > -1, "Processados Hoje not found"
        # Look backwards for the <a tag opening
        a_start = content.rfind("<a", 0, processed_idx)
        assert a_start > -1, "Processados Hoje <a> tag not found"
        a_tag = content[a_start : processed_idx + 50]
        assert 'data-count="1"' in a_tag, "Processados Hoje link must have data-count=1, got: " + a_tag[:200]

    def test_immediate_notice_remains_above_wait_appt(self, client) -> None:
        """Vinda imediata continua aparecendo acima de WAIT_APPT com alto Dias em tela."""
        nir_user = User.objects.create_user(username="nir_immabv@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Immediate notice case
        imm_case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            doctor_support_flag="anesthesist",
            structured_data={"patient": {"name": "Vinda Imediata Topo", "age": 60, "gender": "F"}},
        )
        CaseEvent.objects.create(
            case=imm_case,
            actor_type="human",
            actor=nir_user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        # WAIT_APPT case with very high regulation_days_on_screen
        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            regulation_days_on_screen=999,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "WAIT_APPT Alto Score", "age": 50, "gender": "M"}},
        )

        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()

        # Vinda imediata autorizada deve aparecer antes do WAIT_APPT
        assert "Vinda imediata autorizada" in content
        pos_immediate = content.index("Vinda imediata autorizada")
        pos_wait_appt = content.index("WAIT_APPT Alto Score")
        assert pos_immediate < pos_wait_appt, "Immediate notice should appear before WAIT_APPT cases"


@pytest.mark.django_db
class TestSchedulerContextDetail:
    """Tests for scheduler context detail view (read-only)."""

    def setup_method(self, method: Any = None) -> None:
        self._last_user = None

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str = "sched_ctx") -> None:
        """Create user with given role, login, and set active_role in session."""
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        self._last_user = user

    def _get_last_user(self) -> Any:
        """Return the last created user from _login_as."""
        return self._last_user

    def _create_notification(self, user, case):
        """Create a UserNotification for the user/case pair."""
        from apps.accounts.models import UserNotification

        msg = CaseCommunicationMessage.objects.create(
            case=case,
            author=user,
            author_role="nir",
            body="Teste de menção @scheduler",
        )
        notif = UserNotification.objects.create(
            recipient=user,
            case=case,
            communication_message=msg,
            triggered_by=user,
            notification_type="case_communication_mention",
            title="Você foi mencionado",
            body_preview="Teste de menção @scheduler",
        )
        return notif

    # ── Authentication tests ──────────────────────────────────────────────

    def test_scheduler_context_detail_requires_login(self, client) -> None:
        """GET /scheduler/context/<uuid>/ without auth redirects to login."""
        from apps.cases.models import Case

        case = Case.objects.create(created_by=User.objects.create_user(username="ctx_owner"))
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_scheduler_context_detail_requires_scheduler_role(self, client) -> None:
        """Usuário sem papel ativo scheduler não acessa."""
        nir_user = User.objects.create_user(username="nir_ctx_no_role")
        nir_user.roles.add(self._create_role("nir"))
        client.force_login(nir_user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        case = Case.objects.create(created_by=nir_user)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 302

    # ── Authorization tests ────────────────────────────────────────────────

    def test_scheduler_context_detail_requires_notification_for_user(self, client) -> None:
        """Scheduler sem notificação para o caso não acessa."""
        self._login_as(client, "scheduler", username="sched_no_notif")
        nir_user = User.objects.create_user(username="ctx_nir_no_notif")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 404

    def test_scheduler_context_detail_allows_recipient_notification(self, client) -> None:
        """Scheduler com UserNotification para o caso acessa."""
        self._login_as(client, "scheduler", username="sched_allowed")
        nir_user = User.objects.create_user(username="ctx_nir_allowed")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            structured_data={"patient": {"name": "Paciente Teste", "age": 45, "gender": "M"}},
        )
        self._create_notification(self._get_last_user(), case)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200

    def test_scheduler_context_detail_does_not_allow_other_scheduler_notification(self, client) -> None:
        """Notificação de outro scheduler não autoriza o usuário atual."""
        self._login_as(client, "scheduler", username="sched_other_notif")
        other_scheduler = User.objects.create_user(username="sched_other_user")
        other_scheduler.roles.add(self._create_role("scheduler"))

        nir_user = User.objects.create_user(username="ctx_nir_other")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user)
        # Notification for other_scheduler, not for user
        self._create_notification(other_scheduler, case)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 404

    # ── Content tests ─────────────────────────────────────────────────────

    def test_scheduler_context_detail_renders_readonly_case_context(self, client) -> None:
        """Mostra paciente/ocorrência/status/thread."""
        self._login_as(client, "scheduler", username="sched_content")
        nir_user = User.objects.create_user(username="ctx_nir_content")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            agency_record_number="REC-001",
            structured_data={
                "patient": {"name": "Maria Souza", "age": 35, "gender": "F"},
                "eda": {"indication_category": "Cirurgia Geral"},
            },
        )
        self._create_notification(self._get_last_user(), case)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Souza" in content
        assert "REC-001" in content
        assert "Cirurgia Geral" in content
        # Should show status label
        assert any(label in content for label in ["Novo", "New", case.status])

    def test_scheduler_context_detail_hides_workflow_actions(self, client) -> None:
        """Não contém botões de confirmar/negar agendamento, lock token ou submit estruturado."""
        self._login_as(client, "scheduler", username="sched_noactions")
        nir_user = User.objects.create_user(username="ctx_nir_noactions")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": "João", "age": 50, "gender": "M"}},
        )
        self._create_notification(self._get_last_user(), case)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Must NOT contain workflow action indicators
        assert "Confirmar Agendamento" not in content
        assert "Negar Agendamento" not in content
        assert "lock_token" not in content
        assert "lock-renew" not in content
        assert "scheduler:submit" not in content
        assert "work-lock-config" not in content
        assert "SchedulerDecisionForm" not in content

    # ── Communication tests ─────────────────────────────────────────────────

    def test_scheduler_context_detail_allows_communication_reply_when_not_cleaned(self, client) -> None:
        """Formulário de comunicação aparece quando caso não CLEANED."""
        self._login_as(client, "scheduler", username="sched_comm_allowed")
        nir_user = User.objects.create_user(username="ctx_nir_comm_allowed")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            structured_data={"patient": {"name": "Comm Test", "age": 30, "gender": "M"}},
        )
        self._create_notification(self._get_last_user(), case)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Communication form should be present
        assert "Comunicação operacional" in content, "Communication section should be present"
        assert "Enviar mensagem" in content, "Submit button should be present"

    def test_scheduler_context_detail_post_reply_creates_message(self, client) -> None:
        """POST via endpoint existente como scheduler cria CaseCommunicationMessage."""
        self._login_as(client, "scheduler", username="sched_comm_post")
        nir_user = User.objects.create_user(username="ctx_nir_comm_post")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Post Test", "age": 40, "gender": "M"}},
        )
        self._create_notification(self._get_last_user(), case)

        # POST to the existing communication endpoint (under /cases/ prefix)
        response = client.post(
            f"/cases/{case.case_id}/communication/",
            {"body": "Resposta do scheduler sobre o caso", "next": f"/scheduler/context/{case.case_id}/"},
        )
        assert response.status_code == 302
        # Message should exist
        assert CaseCommunicationMessage.objects.filter(
            case=case,
            author=self._get_last_user(),
            body="Resposta do scheduler sobre o caso",
        ).exists()

    def test_scheduler_context_detail_cleaned_is_readonly_for_communication(self, client) -> None:
        """Se caso CLEANED, não renderiza form de post."""
        self._login_as(client, "scheduler", username="sched_comm_cleaned")
        nir_user = User.objects.create_user(username="ctx_nir_comm_cleaned")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Cleaned Test", "age": 60, "gender": "M"}},
        )
        self._create_notification(self._get_last_user(), case)
        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Should show that communication is not possible
        assert "Comunicação operacional" in content, "Communication section should be present"
        assert "Não é possível enviar mensagens" in content, "Should show read-only communication message"

    # ── Notification read marking hardening ───────────────────────────────

    def test_scheduler_context_detail_direct_access_does_not_mark_notification_read(self, client) -> None:
        """Acesso direto ao context detail não marca notificação como lida."""
        from apps.accounts.models import UserNotification

        self._login_as(client, "scheduler", username="sched_read_harden")
        nir_user = User.objects.create_user(username="nir_read_harden")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            structured_data={"patient": {"name": "Read Harden", "age": 40, "gender": "M"}},
        )
        self._create_notification(self._get_last_user(), case)

        notif = UserNotification.objects.get(
            recipient=self._get_last_user(),
            case=case,
        )
        assert notif.read_at is None, "Notification should start unread"

        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200

        notif.refresh_from_db()
        assert notif.read_at is None, "Direct context detail access must NOT mark the notification as read"

    def test_scheduler_context_detail_does_not_mark_notification_read_with_multiple_unread(self, client) -> None:
        """Acesso direto com múltiplas notificações não lidas não marca nenhuma."""
        from apps.accounts.models import UserNotification
        from apps.cases.models import CaseCommunicationMessage

        self._login_as(client, "scheduler", username="sched_multi_harden")
        nir_user = User.objects.create_user(username="nir_multi_harden")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            structured_data={"patient": {"name": "Multi Harden", "age": 50, "gender": "M"}},
        )

        # Create two different messages that trigger notifications
        msg1 = CaseCommunicationMessage.objects.create(
            case=case, author=nir_user, author_role="nir", body="Primeira menção @scheduler"
        )
        msg2 = CaseCommunicationMessage.objects.create(
            case=case, author=nir_user, author_role="nir", body="Segunda menção @scheduler"
        )
        notif1 = UserNotification.objects.create(
            recipient=self._get_last_user(),
            case=case,
            communication_message=msg1,
            triggered_by=nir_user,
            notification_type="case_communication_mention",
            title="Menção 1",
            body_preview="Primeira menção",
        )
        notif2 = UserNotification.objects.create(
            recipient=self._get_last_user(),
            case=case,
            communication_message=msg2,
            triggered_by=nir_user,
            notification_type="case_communication_mention",
            title="Menção 2",
            body_preview="Segunda menção",
        )
        assert notif1.read_at is None
        assert notif2.read_at is None

        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200

        notif1.refresh_from_db()
        notif2.refresh_from_db()
        assert notif1.read_at is None, "First notification must remain unread"
        assert notif2.read_at is None, "Second notification must remain unread"


@pytest.mark.django_db
class TestSchedulerHistoricalSearch:
    """Tests for scheduler historical search view."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str = "sched_hist") -> None:
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    def _make_historical_case(self, user, agency_record_number="HIST-001", patient_name="Maria Historica"):
        """Cria caso histórico elegível: accept + scheduled + confirmed + CLEANED."""

        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number=agency_record_number,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            structured_data={
                "patient": {"name": patient_name, "age": 60, "gender": "F"},
            },
        )
        return case

    # ── Authentication ─────────────────────────────────────────────────

    def test_scheduler_historical_search_requires_scheduler_role(self, client):
        """Usuário sem papel scheduler não acessa."""
        nir_user = User.objects.create_user(username="nir_nosched")
        nir_user.roles.add(self._create_role("nir"))
        client.force_login(nir_user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get("/scheduler/historical/")
        assert response.status_code == 302

    # ── Search tests ───────────────────────────────────────────────────

    def test_scheduler_historical_search_by_agency_record_number(self, client):
        """Encontra caso histórico por ocorrência."""
        self._login_as(client, "scheduler", username="sched_search1")
        nir_user = User.objects.create_user(username="nir_search1")
        nir_user.roles.add(self._create_role("nir"))
        self._make_historical_case(nir_user, agency_record_number="HIST-SEARCH-001")

        response = client.get("/scheduler/historical/?q=HIST-SEARCH-001")
        assert response.status_code == 200
        content = response.content.decode()
        assert "HIST-SEARCH-001" in content

    def test_scheduler_historical_search_by_patient_name(self, client):
        """Encontra caso histórico por nome do paciente."""
        self._login_as(client, "scheduler", username="sched_search2")
        nir_user = User.objects.create_user(username="nir_search2")
        nir_user.roles.add(self._create_role("nir"))
        self._make_historical_case(nir_user, patient_name="Paciente Especial")

        response = client.get("/scheduler/historical/?q=Paciente Especial")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente Especial" in content

    def test_scheduler_historical_search_excludes_non_scheduled_acceptance(self, client):
        """Exclui vinda imediata, negado médico ou sem agendamento processado."""
        self._login_as(client, "scheduler", username="sched_search3")
        nir_user = User.objects.create_user(username="nir_search3")
        nir_user.roles.add(self._create_role("nir"))

        # In scope
        self._make_historical_case(nir_user, agency_record_number="IN-SCOPE", patient_name="In Scope")

        # Out of scope: immediate admission
        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": "Immediate Out"}},
        )

        # Out of scope: doctor denied
        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            doctor_decision="deny",
            structured_data={"patient": {"name": "Denied Out"}},
        )

        response = client.get("/scheduler/historical/?q=Scope")
        assert response.status_code == 200
        content = response.content.decode()
        assert "IN-SCOPE" in content
        assert "Immediate Out" not in content
        assert "Denied Out" not in content

    def test_scheduler_historical_search_not_limited_to_today_or_current_scheduler(self, client):
        """Caso antigo e/ou processado por outro scheduler aparece."""
        self._login_as(client, "scheduler", username="sched_search4")
        other_scheduler = User.objects.create_user(username="sched_other_hist")
        other_scheduler.roles.add(self._create_role("scheduler"))
        nir_user = User.objects.create_user(username="nir_search4")
        nir_user.roles.add(self._create_role("nir"))

        _ = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            agency_record_number="OLD-HIST-999",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            scheduler=other_scheduler,
            structured_data={"patient": {"name": "Old Patient", "age": 80, "gender": "M"}},
        )

        response = client.get("/scheduler/historical/?q=OLD-HIST-999")
        assert response.status_code == 200
        content = response.content.decode()
        assert "OLD-HIST-999" in content

    def test_scheduler_historical_cards_have_details_link(self, client):
        """Cards apontam para detalhe read-only."""
        self._login_as(client, "scheduler", username="sched_search5")
        nir_user = User.objects.create_user(username="nir_search5")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        response = client.get("/scheduler/historical/?q=HIST-001")
        assert response.status_code == 200
        content = response.content.decode()
        detail_url = f"/scheduler/context/{case.case_id}/"
        assert detail_url in content


@pytest.mark.django_db
class TestSchedulerHistoricalContextDetail:
    """Tests for scheduler context_detail for historical cases."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str = "sched_hist_detail") -> None:
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    def _make_historical_case(self, user, **kwargs):
        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            structured_data={"patient": {"name": "Hist Patient", "age": 55, "gender": "M"}},
            **kwargs,
        )
        return case

    def test_scheduler_context_detail_allows_historical_case_without_notification(self, client):
        """Caso histórico em escopo abre sem notificação prévia."""
        self._login_as(client, "scheduler", username="sched_hist_allowed")
        nir_user = User.objects.create_user(username="nir_hist_allowed")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200

    def test_scheduler_context_detail_blocks_non_historical_case_without_notification(self, client):
        """Caso fora do escopo e sem notificação não abre."""
        self._login_as(client, "scheduler", username="sched_hist_block")
        nir_user = User.objects.create_user(username="nir_hist_block")
        nir_user.roles.add(self._create_role("nir"))

        # Non-historical case (doctor denied, no scheduling)
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            doctor_decision="deny",
            structured_data={"patient": {"name": "Denied", "age": 50, "gender": "F"}},
        )

        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 404

    def test_scheduler_historical_detail_hides_workflow_actions(self, client):
        """Sem lock, sem formulário de agendamento/intercorrência."""
        self._login_as(client, "scheduler", username="sched_hist_noaction")
        nir_user = User.objects.create_user(username="nir_hist_noaction")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Must NOT contain workflow action indicators
        assert "Confirmar Agendamento" not in content
        assert "Negar Agendamento" not in content
        assert "lock_token" not in content
        assert "scheduler:submit" not in content
        assert "SchedulerDecisionForm" not in content


@pytest.mark.django_db
class TestSchedulerHistoricalMessageNir:
    """Tests for scheduler historical message to NIR endpoint."""

    def _create_role(self, name: str):
        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str = "sched_msg") -> None:
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        self._last_user = user

    def _get_last_user(self):
        return self._last_user

    def _make_historical_case(self, user, **kwargs):
        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            structured_data={"patient": {"name": "Msg Patient", "age": 55, "gender": "M"}},
            **kwargs,
        )
        return case

    def test_scheduler_historical_message_requires_post(self, client):
        """GET não executa ação."""
        self._login_as(client, "scheduler", username="sched_msg_get")
        nir_user = User.objects.create_user(username="nir_msg_get")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        response = client.get(f"/scheduler/historical/{case.case_id}/message-nir/")
        # Should redirect or return method-not-allowed; we expect redirect
        assert response.status_code in (302, 405)

    def test_scheduler_historical_message_requires_historical_scope(self, client):
        """Não posta em caso fora do escopo."""
        self._login_as(client, "scheduler", username="sched_msg_scope")
        nir_user = User.objects.create_user(username="nir_msg_scope")
        nir_user.roles.add(self._create_role("nir"))

        # Non-historical: doctor denied
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            doctor_decision="deny",
            structured_data={"patient": {"name": "No Scope"}},
        )

        response = client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "Mensagem de teste"},
        )
        assert response.status_code in (302, 404)

    def test_scheduler_historical_message_requires_body(self, client):
        """Body vazio não cria mensagem."""
        self._login_as(client, "scheduler", username="sched_msg_empty")
        nir_user = User.objects.create_user(username="nir_msg_empty")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "   "},
        )
        # Test message was NOT created
        assert CaseCommunicationMessage.objects.filter(case=case).count() == 0

    def test_scheduler_historical_message_creates_case_communication_message(self, client):
        """Mensagem é criada na thread do caso."""
        self._login_as(client, "scheduler", username="sched_msg_create")
        nir_user = User.objects.create_user(username="nir_msg_create")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        response = client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "Precisamos de ajuda com este caso."},
        )
        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=case).count() == 1

    def test_scheduler_historical_message_adds_nir_mention_when_missing(self, client):
        """Body salvo contém @nir ou notificação NIR é criada mesmo sem o usuário digitar."""
        from apps.accounts.models import UserNotification

        self._login_as(client, "scheduler", username="sched_msg_nir")
        nir_user = User.objects.create_user(username="nir_msg_nir")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        # NIR user must be active for notification to be created
        # (nir_user already is active by default)

        response = client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "Precisamos de ajuda com este caso."},
        )
        assert response.status_code == 302

        # The notification should exist for nir_user since @nir should be added
        msg = CaseCommunicationMessage.objects.get(case=case)
        assert "@nir" in msg.body, "@nir should be in the saved body"

        # A UserNotification should exist (for nir_user via @nir role)
        notifs = UserNotification.objects.filter(case=case, recipient__roles__name="nir")
        assert notifs.count() >= 1

    def test_scheduler_historical_message_preserves_additional_mentions(self, client):
        """Menções adicionais permanecem no corpo salvo."""
        self._login_as(client, "scheduler", username="sched_msg_mentions")
        nir_user = User.objects.create_user(username="nir_msg_mentions")
        nir_user.roles.add(self._create_role("nir"))

        doctor_user = User.objects.create_user(username="doutor.plantao")
        doctor_user.roles.add(self._create_role("doctor"))

        case = self._make_historical_case(nir_user)

        response = client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "@doutor.plantao e @medico favor verificar."},
        )
        assert response.status_code == 302

        msg = CaseCommunicationMessage.objects.get(case=case)
        # The body should still contain @doutor.plantao and @medico
        # Additionally, @nir should have been prepended
        assert "@doutor.plantao" in msg.body, "Username mention should be preserved"
        assert "@medico" in msg.body, "Role mention @medico should be preserved"
        assert "@nir" in msg.body, "@nir should also be present"

    def test_scheduler_historical_message_creates_nir_notification(self, client):
        """NIR ativo recebe UserNotification."""
        from apps.accounts.models import UserNotification

        self._login_as(client, "scheduler", username="sched_msg_notif")
        nir_user = User.objects.create_user(username="nir_msg_notif")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)

        client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "Teste de notificação."},
        )

        msg = CaseCommunicationMessage.objects.get(case=case)
        notifs = UserNotification.objects.filter(case=case, communication_message=msg)
        assert len(notifs) >= 1
        # The NIR user should be among the recipients
        assert any(n.recipient == nir_user for n in notifs)

    def test_scheduler_historical_message_notifies_additional_mentioned_recipient(self, client):
        """Médico/usuário adicional mencionado recebe UserNotification."""
        from apps.accounts.models import UserNotification

        self._login_as(client, "scheduler", username="sched_msg_add")
        nir_user = User.objects.create_user(username="nir_msg_add")
        nir_user.roles.add(self._create_role("nir"))

        doctor_user = User.objects.create_user(username="dr_msg_add")
        doctor_user.roles.add(self._create_role("doctor"))

        case = self._make_historical_case(nir_user)

        client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "@nir e @doctor por favor verifiquem."},
        )

        doctor_notifs = UserNotification.objects.filter(case=case, recipient=doctor_user)
        assert len(doctor_notifs) >= 1, "Doctor should receive a notification"

    def test_scheduler_historical_message_does_not_change_case_status(self, client):
        """Caso CLEANED permanece CLEANED após mensagem."""
        self._login_as(client, "scheduler", username="sched_msg_status")
        nir_user = User.objects.create_user(username="nir_msg_status")
        nir_user.roles.add(self._create_role("nir"))
        case = self._make_historical_case(nir_user)
        before_status = case.status

        client.post(
            f"/scheduler/historical/{case.case_id}/message-nir/",
            {"body": "Mensagem sem mudar status."},
        )

        # Use get() instead of refresh_from_db() to avoid FSM direct-set error
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == before_status
        assert reloaded.status == CaseStatus.CLEANED


@pytest.mark.django_db
class TestPostCaseCommunicationAllowCleaned:
    """Tests for allow_cleaned opt-in in post_case_communication_message."""

    def test_post_case_communication_cleaned_still_blocked_by_default(self, db, case_factory, advance_to):
        """Chamada padrão em CLEANED continua levantando CaseCommunicationError."""
        from django.contrib.auth import get_user_model

        from apps.cases.services import CaseCommunicationError, post_case_communication_message

        u_model = get_user_model()
        user = u_model.objects.create_user(username="test_cleaned_block")
        case = case_factory(user)
        case = advance_to(case, CaseStatus.CLEANED)

        with pytest.raises(CaseCommunicationError, match="encerrado|CLEANED|finalizado"):
            post_case_communication_message(
                case=case,
                author=user,
                author_role="scheduler",
                body="Teste sem opt-in.",
            )

    def test_post_case_communication_cleaned_allowed_only_with_explicit_opt_in(self, db, case_factory, advance_to):
        """Chamada com allow_cleaned=True funciona."""
        from django.contrib.auth import get_user_model

        from apps.cases.services import post_case_communication_message

        u_model = get_user_model()
        user = u_model.objects.create_user(username="test_cleaned_optin")
        case = case_factory(user)
        case = advance_to(case, CaseStatus.CLEANED)

        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="scheduler",
            body="Teste com opt-in explícito.",
            allow_cleaned=True,
        )
        assert msg is not None
        assert msg.body == "Teste com opt-in explícito."
