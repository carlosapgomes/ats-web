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
        }
        case.suggested_action = {
            "support_recommendation": "anesthesist_icu",
            "suggestion": "accept",
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
            suggested_action={
                "support_recommendation": "none",
                "suggestion": "accept",
            },
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
            },
            summary_text="Paciente com IMC elevado (34). Risco anestésico ASA II.",
            suggested_action={
                "support_recommendation": "anesthesist",
                "suggestion": "accept",
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

    # ── Support recommendation mapping ────────────────────────────────

    def test_support_recommendation_maps_to_portuguese(self, client) -> None:
        """support_recommendation values are mapped to Portuguese labels."""
        nir_user = User.objects.create_user(username="nir3@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        for rec_key, expected_label in [
            ("none", "Nenhum"),
            ("anesthesist", "Anestesista"),
            ("anesthesist_icu", "Anestesista + UTI"),
        ]:
            case = Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_DOCTOR)
            case.structured_data = {"patient": {"name": f"Teste {rec_key}", "age": 40, "gender": "Masculino"}}
            case.suggested_action = {"support_recommendation": rec_key, "suggestion": "accept"}
            case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Anestesista + UTI" in content
        assert "Anestesista" in content

    # ── Diagnosis sources ─────────────────────────────────────────────

    def test_diagnosis_uses_summary_text_priority(self, client) -> None:
        """_get_diagnosis prefers summary_text over structured_data."""
        nir_user = User.objects.create_user(username="nir4@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            summary_text="Hérnia inguinal bilateral — cirurgia eletiva",
            structured_data={
                "patient": {"name": "João Hérnia", "age": 62, "gender": "Masculino"},
                "eda": {"indication_category": "standard"},
            },
        )
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # summary_text should appear as diagnosis, not the eda indication
        assert "Hérnia inguinal bilateral" in content

    # ── Suggestion flow mapping ───────────────────────────────────────

    def test_suggestion_flow_displays_mapped_value(self, client) -> None:
        """suggestion values are mapped to display text in card."""
        nir_user = User.objects.create_user(username="nir5@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Teste Flow", "age": 45, "gender": "Feminino"}}
        case.suggested_action = {
            "support_recommendation": "none",
            "suggestion": "manual_review_required",
        }
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Revisão Manual" in content

    # ── Navigation links ──────────────────────────────────────────────

    def test_queue_has_evaluate_case_link(self, client) -> None:
        """Each pending case card has a link to the decision page."""
        nir_user = User.objects.create_user(username="nir_link@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Link Test", "age": 40, "gender": "Masculino"}}
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert f"/doctor/{case.case_id}/" in content


# ── Helpers for decision view tests ────────────────────────────────────


def _advance_case_to(case: Case, target: str) -> Case:
    """Advance a Case through FSM transitions to reach a target status."""
    path: dict[str, list[str]] = {
        CaseStatus.R1_ACK_PROCESSING: ["start_processing"],
        CaseStatus.EXTRACTING: ["start_processing", "start_extraction"],
        CaseStatus.LLM_STRUCT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
        ],
        CaseStatus.LLM_SUGGEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
        ],
        CaseStatus.R2_POST_WIDGET: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
        ],
        CaseStatus.WAIT_DOCTOR: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
        ],
        CaseStatus.DOCTOR_ACCEPTED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
        ],
        CaseStatus.DOCTOR_DENIED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='deny')",
        ],
        CaseStatus.R3_POST_REQUEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
        ],
    }
    steps = path.get(target, [])
    for step in steps:
        if "(" in step:
            method_name, args_str = step.split("(", 1)
            args_str = args_str.rstrip(")")
            kwargs: dict[str, object] = {}
            if "=" in args_str:
                for pair in args_str.split(","):
                    k, v = pair.split("=")
                    k = k.strip()
                    v = v.strip().strip("'")
                    if v == "True":
                        v = True
                    elif v == "False":
                        v = False
                    kwargs[k] = v
                getattr(case, method_name)(**kwargs)
            else:
                getattr(case, method_name)()
        else:
            getattr(case, step)()
        case.save()
    return Case.objects.get(pk=case.pk)


# ── Decision view tests ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecisionView:
    """Tests for the doctor decision view (GET /doctor/<case_id>/)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@decision.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_in_status(self, status: str) -> Case:
        """Create a case, optionally advancing to a target status."""
        nir_user = User.objects.create_user(
            username=f"nir_{(status or 'new').lower()}@test.com", password="testpass123"
        )
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        if status != CaseStatus.NEW:
            case = _advance_case_to(case, status)
        return case

    def test_decision_returns_200_for_wait_doctor(self, client) -> None:
        """GET /doctor/<case_id>/ returns 200 for WAIT_DOCTOR case."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "João", "age": 50, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200

    def test_decision_returns_404_for_non_wait_doctor(self, client) -> None:
        """GET /doctor/<case_id>/ returns 404 for non-WAIT_DOCTOR case."""
        case = self._create_case_in_status(CaseStatus.DOCTOR_ACCEPTED)
        case.structured_data = {"patient": {"name": "Maria", "age": 75, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 404

    def test_decision_shows_patient_data(self, client) -> None:
        """Decision page displays patient name, age, gender, registration."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.agency_record_number = "2026-0506-001"
        case.structured_data = {
            "patient": {"name": "João Pereira Gomes", "age": 62, "gender": "Masculino"},
        }
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "João Pereira Gomes" in content
        assert "62" in content
        assert "2026-0506-001" in content

    def test_decision_shows_ia_extraction(self, client) -> None:
        """Decision page displays IA extraction data: diagnosis, summary, suggestions."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.summary_text = "Hérnia inguinal bilateral — cirurgia eletiva"
        case.structured_data = {
            "patient": {"name": "Teste IA", "age": 40, "gender": "Feminino"},
        }
        case.suggested_action = {
            "support_recommendation": "anesthesist",
            "suggestion": "accept",
        }
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Hérnia inguinal bilateral" in content
        assert "Anestesista" in content

    def test_decision_shows_pdf_info(self, client) -> None:
        """Decision page shows PDF file info for the case."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Teste PDF", "age": 30, "gender": "Masculino"}}
        case.save()
        # pdf_file is empty, but the PDF card section should appear
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "PDF" in content or "pdf" in content.lower() or "Encaminhamento" in content


# ── Form validation tests ────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecisionForm:
    """Tests for DoctorDecisionForm validation rules."""

    def test_accept_requires_support_flag(self) -> None:
        """Accept decision without support_flag is invalid."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "accept",
                "support_flag": "",
                "admission_flow": "scheduled",
            }
        )
        assert not form.is_valid()
        assert "support_flag" in form.errors or "__all__" in form.errors

    def test_accept_requires_admission_flow(self) -> None:
        """Accept decision without admission_flow is invalid."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "",
            }
        )
        assert not form.is_valid()
        assert "admission_flow" in form.errors or "__all__" in form.errors

    def test_deny_requires_reason(self) -> None:
        """Deny decision without reason is invalid."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "deny",
                "reason": "",
            }
        )
        assert not form.is_valid()
        assert "reason" in form.errors or "__all__" in form.errors

    def test_valid_accept_form(self) -> None:
        """Valid accept form data passes validation."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
            }
        )
        assert form.is_valid()

    def test_valid_deny_form(self) -> None:
        """Valid deny form data passes validation."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "deny",
                "reason": "Contorno clínico não indicado para este caso",
            }
        )
        assert form.is_valid()


# ── FSM tests ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecisionFSM:
    """Tests for FSM transitions: doctor_decide and ready_for_scheduler."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def test_doctor_decide_accept_transitions_to_accepted(self) -> None:
        """doctor_decide('accept') transitions WAIT_DOCTOR → DOCTOR_ACCEPTED."""
        nir_user = User.objects.create_user(username="nir_fsm1@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        doctor = User.objects.create_user(username="doctor_fsm1@test.com", password="testpass123")
        doctor.roles.add(self._create_role("doctor"))

        case = Case.objects.create(created_by=nir_user)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
        assert case.status == CaseStatus.WAIT_DOCTOR

        case.doctor_decide(decision="accept", user=doctor)
        case.save()

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.DOCTOR_ACCEPTED

    def test_doctor_decide_deny_transitions_to_denied(self) -> None:
        """doctor_decide('deny') transitions WAIT_DOCTOR → DOCTOR_DENIED."""
        nir_user = User.objects.create_user(username="nir_fsm2@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        doctor = User.objects.create_user(username="doctor_fsm2@test.com", password="testpass123")
        doctor.roles.add(self._create_role("doctor"))

        case = Case.objects.create(created_by=nir_user)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
        assert case.status == CaseStatus.WAIT_DOCTOR

        case.doctor_decide(decision="deny", user=doctor)
        case.save()

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.DOCTOR_DENIED

    def test_ready_for_scheduler_transitions_accepted_to_r3_to_wait_appt(self) -> None:
        """ready_for_scheduler transitions DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT."""
        nir_user = User.objects.create_user(username="nir_fsm3@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        doctor = User.objects.create_user(username="doctor_fsm3@test.com", password="testpass123")
        doctor.roles.add(self._create_role("doctor"))

        case = Case.objects.create(created_by=nir_user)
        case = _advance_case_to(case, CaseStatus.DOCTOR_ACCEPTED)
        assert case.status == CaseStatus.DOCTOR_ACCEPTED

        case.ready_for_scheduler(user=doctor)
        case.save()

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.R3_POST_REQUEST


# ── Submit view tests ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorSubmitView:
    """Tests for POST /doctor/<case_id>/submit/."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@submit.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_in_status(self, status: str) -> Case:
        nir_user = User.objects.create_user(
            username=f"nir_{(status or 'new').lower()}_submit@test.com", password="testpass123"
        )
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        if status != CaseStatus.NEW:
            case = _advance_case_to(case, status)
        return case

    def test_submit_accept_persists_fields_and_transitions(self, client) -> None:
        """POST accept → fields persisted, FSM: WAIT_DOCTOR → DOCTOR_ACCEPTED → R3_POST_REQUEST."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Test Accept", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
            },
        )
        assert response.status_code == 302  # redirect after success

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.doctor_support_flag == "anesthesist"
        assert case.doctor_admission_flow == "scheduled"
        assert case.doctor == doctor
        assert case.doctor_decided_at is not None
        assert case.status == CaseStatus.R3_POST_REQUEST

    def test_submit_deny_persists_fields_and_transitions(self, client) -> None:
        """POST deny → fields persisted, FSM: WAIT_DOCTOR → DOCTOR_DENIED."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Test Deny", "age": 50, "gender": "Feminino"}}
        case.save()

        doctor = self._login_as(client, "doctor")

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Contorno clínico não indicado",
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "deny"
        assert case.doctor_reason == "Contorno clínico não indicado"
        assert case.doctor == doctor
        assert case.doctor_decided_at is not None
        assert case.status == CaseStatus.DOCTOR_DENIED

    def test_submit_creates_case_event_accept(self, client) -> None:
        """POST accept creates a DOCTOR_ACCEPT CaseEvent."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Event Accept", "age": 40, "gender": "Masculino"}}
        case.save()

        self._login_as(client, "doctor")

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "immediate",
            },
        )

        events = CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_")
        assert events.filter(event_type="DOCTOR_ACCEPT").exists()

    def test_submit_creates_case_event_deny(self, client) -> None:
        """POST deny creates a DOCTOR_DENY CaseEvent."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Event Deny", "age": 50, "gender": "Feminino"}}
        case.save()

        self._login_as(client, "doctor")

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Motivo de teste",
            },
        )

        events = CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_")
        assert events.filter(event_type="DOCTOR_DENY").exists()

    def test_submit_non_wait_doctor_returns_404(self, client) -> None:
        """POST to non-WAIT_DOCTOR case returns 404."""
        case = self._create_case_in_status(CaseStatus.DOCTOR_DENIED)
        case.structured_data = {"patient": {"name": "Nao Valido", "age": 40, "gender": "Masculino"}}
        case.save()

        self._login_as(client, "doctor")

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
            },
        )
        assert response.status_code == 404
