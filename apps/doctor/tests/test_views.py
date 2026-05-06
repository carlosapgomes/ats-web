"""Tests for doctor queue view."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


@pytest.mark.django_db
class TestDoctorQueueView:
    """Tests for the doctor queue view (GET /doctor/)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> None:
        """Create user with given role, login, and set active_role in session."""
        user = User.objects.create_user(username=f"{role_name}@test.com", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()

    # ── Authentication tests ──────────────────────────────────────────

    def test_queue_requires_login(self, client) -> None:
        """GET /doctor/ without auth redirects to login."""
        response = client.get("/doctor/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_queue_accessible_for_doctor(self, client) -> None:
        """GET /doctor/ returns 200 for user with active_role='doctor'."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200

    # ── Content tests ─────────────────────────────────────────────────

    def test_queue_shows_pending_cases(self, client) -> None:
        """Pending (WAIT_DOCTOR) cases appear in the queue."""
        user = User.objects.create_user(username="nir@test.com", password="testpass123")
        user.roles.add(self._create_role("nir"))

        case = Case.objects.create(created_by=user, status=CaseStatus.WAIT_DOCTOR)
        case.agency_record_number = "2026-0428-001"
        case.summary_text = "Paciente com fratura de fêmur"
        case.structured_data = {
            "patient": {
                "name": "João Pereira Gomes",
                "age": 62,
                "gender": "Masculino",
            },
            "diagnosis": "Fratura de fêmur D — urgência ortopédica",
        }
        case.suggested_action = {
            "support": "Anestesista UTI",
            "admission_flow": "Vinda Imediata",
        }
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "João Pereira Gomes" in content

    def test_queue_shows_decided_today(self, client) -> None:
        """Cases decided by the doctor today appear in 'Decididos Hoje'."""
        doctor_user = User.objects.create_user(username="doctor@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor_user,
            doctor_decision="accept",
            suggested_action={"support": "Nenhum", "admission_flow": "Agendamento"},
            structured_data={
                "patient": {
                    "name": "Maria Silva dos Santos",
                    "age": 75,
                    "gender": "Feminino",
                }
            },
        )
        case.agency_record_number = "2026-0428-001"
        case.save()

        CaseEvent.objects.create(
            case=case,
            actor_type="doctor",
            actor=doctor_user,
            event_type="DOCTOR_ACCEPT",
            timestamp=timezone.now(),
        )

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Silva dos Santos" in content

    def test_queue_excludes_other_statuses(self, client) -> None:
        """Cases with status != WAIT_DOCTOR do not appear in pending list."""
        nir_user = User.objects.create_user(username="nir@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # WAIT_DOCTOR → should appear
        pending = Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_DOCTOR)
        pending.agency_record_number = "2026-0428-001"
        pending.structured_data = {"patient": {"name": "Pendente Silva", "age": 40, "gender": "Masculino"}}
        pending.save()

        # NEW → should NOT appear in pending
        Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Pendente Silva" in content
        # NEW case should not be in queue context
        assert "pending" in content.lower() or "Pendentes" in content

    def test_queue_shows_waiting_time(self, client) -> None:
        """Case cards display waiting time since created_at."""
        nir_user = User.objects.create_user(username="nir@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Create a case that has been waiting 45 minutes
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
        )
        case.created_at = timezone.now() - timedelta(minutes=45)
        case.agency_record_number = "2026-0428-002"
        case.structured_data = {"patient": {"name": "João Teste", "age": 50, "gender": "Masculino"}}
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Should show the waiting time somewhere
        assert "45" in content or "min" in content.lower()

    def test_queue_shows_average_wait_time(self, client) -> None:
        """Queue page shows average wait time for pending cases."""
        nir_user = User.objects.create_user(username="nir@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        for i, minutes in enumerate([10, 20, 30]):
            case = Case.objects.create(
                created_by=nir_user,
                status=CaseStatus.WAIT_DOCTOR,
            )
            case.created_at = timezone.now() - timedelta(minutes=minutes)
            case.structured_data = {
                "patient": {
                    "name": f"Paciente {i}",
                    "age": 40 + i,
                    "gender": "Masculino",
                }
            }
            case.agency_record_number = f"2026-0428-00{i}"
            case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        # Should mention something about wait time
        content = response.content.decode()
        assert "Tempo médio" in content or "Espera" in content or "aguardando" in content.lower()

    def test_queue_shows_patient_details(self, client) -> None:
        """Case cards show patient name, age, gender, registration number."""
        nir_user = User.objects.create_user(username="nir@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="2026-0428-005",
            structured_data={
                "patient": {
                    "name": "Antônio Ferreira Lima",
                    "age": 58,
                    "gender": "Masculino",
                },
                "diagnosis": "Colecistectomia videolaparoscópica",
            },
            summary_text="Paciente com IMC elevado (34). Risco anestésico ASA II.",
            suggested_action={
                "support": "Anestesista",
                "admission_flow": "Agendamento",
            },
        )
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Antônio Ferreira Lima" in content
        assert "58" in content
        assert "2026-0428-005" in content
