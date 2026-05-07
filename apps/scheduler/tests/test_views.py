"""Tests for scheduler queue view."""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


@pytest.mark.django_db
class TestSchedulerQueueView:
    """Tests for the scheduler queue view (GET /scheduler/)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

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

    # ── Content tests ─────────────────────────────────────────────────

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

    def test_queue_excludes_non_wait_appt(self, client) -> None:
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
        from apps.accounts.models import Role

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
        from apps.accounts.models import Role

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

    # ── Confirm submit ────────────────────────────────────────────────

    def test_submit_confirm_updates_case(self, client) -> None:
        """POST confirm transiciona para APPT_CONFIRMED → WAIT_R1_CLEANUP_THUMBS e persiste campos."""
        self._login_as(client, "scheduler")
        case = self._create_waited_case()
        scheduler_user = User.objects.get(username="scheduler@submit.test")

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-05-15",
                "appointment_time": "14:30",
                "notes": "Trazer exames.",
                "reason": "",
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

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-05-15",
                "appointment_time": "14:30",
                "notes": "",
                "reason": "",
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

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "Indisponibilidade de vaga.",
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

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "notes": "",
                "reason": "Conflito de agenda.",
            },
        )

        assert CaseEvent.objects.filter(case=case, event_type="APPT_DENIED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

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
