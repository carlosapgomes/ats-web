"""Tests for doctor queue view."""

import uuid
from datetime import timedelta
from pathlib import Path

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

    def test_queue_has_htmx_polling_container(self, client) -> None:
        """Full queue page polls the partial endpoint with HTMX."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert (
            'hx-get="/doctor/partials/queue/?tab=pending"' in content
            or 'hx-get="/doctor/partials/queue/?tab="' in content
        )
        assert 'hx-trigger="every 20s"' in content

    def test_queue_partial_renders_without_layout(self, client) -> None:
        """HTMX partial returns queue content without full base layout."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/partials/queue/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<!DOCTYPE html>" not in content
        assert "Atualizado automaticamente" in content

    # ── Role guard tests ─────────────────────────────────────────────

    def test_queue_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot access /doctor/."""
        self._login_as(client, "nir")
        response = client.get("/doctor/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_queue_blocks_scheduler(self, client) -> None:
        """Scheduler with active_role='scheduler' cannot access /doctor/."""
        self._login_as(client, "scheduler")
        response = client.get("/doctor/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_queue_blocks_manager(self, client) -> None:
        """Manager with active_role='manager' cannot access /doctor/."""
        self._login_as(client, "manager")
        response = client.get("/doctor/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_queue_allows_manager_with_active_doctor(self, client) -> None:
        """Manager who selects active_role='doctor' can access /doctor/."""
        user = User.objects.create_user(username="manager-doctor@test.com", password="testpass123")
        user.roles.add(self._create_role("manager"))
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
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
        """Cases decided by the doctor today appear in 'Decididos Hoje' tab."""
        doctor_user = User.objects.create_user(username="doctor@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
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

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/?tab=decided")
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

    def test_queue_excludes_scope_gated_cases(self, client) -> None:
        """Scope-gated cases (WAIT_R1_CLEANUP_THUMBS) do not appear in doctor queue."""
        nir_user = User.objects.create_user(username="nir_scopegate@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Create a scope-gated case that ended in WAIT_R1_CLEANUP_THUMBS
        gated = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={
                "decision": "manual_review_required",
                "reason_code": "non_eda_request",
                "reason_text": "Fora de escopo.",
            },
        )
        gated.structured_data = {"patient": {"name": "Gated Case", "age": 40, "gender": "Masculino"}}
        gated.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Scope-gated case should NOT appear
        assert "Gated Case" not in content

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

    # ── Decided Today tab tests ────────────────────────────────────────

    def test_queue_nav_has_functional_decided_tab_and_no_history(self, client) -> None:
        """R1: Nav has functional Decididos Hoje link and no Histórico."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Must have a functional link to ?tab=decided
        assert "?tab=decided" in content or "tab=decided" in content
        # Must NOT contain Histórico
        assert "Histórico" not in content

    def test_decided_today_tab_uses_doctor_decided_at_not_status(self, client) -> None:
        """R2: Decided today query uses doctor_decided_at, not status.

        A case decided today by the doctor that has moved to WAIT_APPT
        (not DOCTOR_ACCEPTED/DOCTOR_DENIED) must appear in ?tab=decided.
        """
        doctor_user = User.objects.create_user(username="doc_decided_at@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_decided_at@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Create a case that was decided today but has advanced to WAIT_APPT
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Advance Case", "age": 50, "gender": "M"}},
            suggested_action={"support_recommendation": "none", "suggestion": "accept"},
        )
        case.agency_record_number = "2026-0606-ADV"
        case.save()

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Advance Case" in content

    def test_decided_today_tab_excludes_other_doctor_cases(self, client) -> None:
        """R2: Cases decided by another doctor do not appear."""
        doctor_a = User.objects.create_user(username="doc_a_exclude@test.com", password="testpass123")
        doctor_a.roles.add(self._create_role("doctor"))

        doctor_b = User.objects.create_user(username="doc_b_exclude@test.com", password="testpass123")
        doctor_b.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_exclude@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Case decided by doctor_a (should NOT appear for doctor_b)
        case_a = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_a,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Doc A Case", "age": 40, "gender": "M"}},
        )
        case_a.save()

        # Case decided by doctor_b (should appear for doctor_b)
        case_b = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_b,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Doc B Case", "age": 45, "gender": "F"}},
        )
        case_b.save()

        # Login as doctor_b
        client.force_login(doctor_b)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Doc B Case" in content
        assert "Doc A Case" not in content

    def test_pending_tab_does_not_render_decided_list(self, client) -> None:
        """R3: GET /doctor/?tab=pending does not render decided list."""
        doctor_user = User.objects.create_user(username="doc_pending@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_pending@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Create a decided case for the doctor
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Decided Case", "age": 50, "gender": "M"}},
        )
        case.save()

        # Also create a pending case
        pending = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Pending Case", "age": 30, "gender": "F"}},
        )
        pending.save()

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/?tab=pending")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Pending Case" in content
        assert "Decided Case" not in content

    def test_decided_tab_has_detail_link(self, client) -> None:
        """R4-R5: Each decided item has a link to doctor:decided_detail."""
        doctor_user = User.objects.create_user(username="doc_detail_link@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_detail_link@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Detail Link", "age": 40, "gender": "M"}},
        )
        case.save()

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        # Must contain a link to the decided detail page
        assert f"/doctor/decided/{case.case_id}/" in content

    def test_doctor_decided_detail_renders_read_only_case_detail(self, client) -> None:
        """R5: GET /doctor/decided/<case_id>/ renders read-only case detail."""
        doctor_user = User.objects.create_user(username="doc_detail@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_detail@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Detail Case", "age": 60, "gender": "F"}},
            agency_record_number="2026-0606-DTL",
        )
        case.save()

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(f"/doctor/decided/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Should show case data
        assert "Detail Case" in content
        assert "2026-0606-DTL" in content
        # Should have back label
        assert "Voltar aos decididos hoje" in content
        # Should NOT show confirm receipt button
        assert "Confirmar Recebimento" not in content

    def test_doctor_decided_detail_404_for_other_doctor_case(self, client) -> None:
        """R5: Doctor cannot access details of another doctor's case."""
        doctor_a = User.objects.create_user(username="doc_a_detail404@test.com", password="testpass123")
        doctor_a.roles.add(self._create_role("doctor"))

        doctor_b = User.objects.create_user(username="doc_b_detail404@test.com", password="testpass123")
        doctor_b.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_detail404@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_a,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Doc A Only", "age": 50, "gender": "M"}},
        )
        case.save()

        # Login as doctor_b
        client.force_login(doctor_b)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(f"/doctor/decided/{case.case_id}/")
        assert response.status_code == 404

    # ── Regulation days on screen ordering tests ────────────────────────

    def test_queue_orders_by_regulation_days_on_screen_desc(self, client) -> None:
        """WAIT_DOCTOR cases ordered by regulation_days_on_screen DESC."""
        nir_user = User.objects.create_user(username="nir_order@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        now = timezone.now()

        case_a = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=2,
            structured_data={"patient": {"name": "Case A (2 days)", "age": 40, "gender": "M"}},
        )
        Case.objects.filter(case_id=case_a.case_id).update(created_at=now - timedelta(hours=3))

        case_b = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=10,
            structured_data={"patient": {"name": "Case B (10 days)", "age": 50, "gender": "F"}},
        )
        Case.objects.filter(case_id=case_b.case_id).update(created_at=now - timedelta(hours=2))

        case_c = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=None,
            structured_data={"patient": {"name": "Case C (null)", "age": 30, "gender": "M"}},
        )
        Case.objects.filter(case_id=case_c.case_id).update(created_at=now - timedelta(hours=1))

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()

        # B (10) deve aparecer antes de A (2), e A antes de C (null)
        pos_b = content.index("Case B (10 days)")
        pos_a = content.index("Case A (2 days)")
        pos_c = content.index("Case C (null)")
        assert pos_b < pos_a, f"B (10) should be before A (2): B={pos_b}, A={pos_a}"
        assert pos_a < pos_c, f"A (2) should be before C (null): A={pos_a}, C={pos_c}"

    def test_queue_shows_regulation_days_badge_when_available(self, client) -> None:
        """Card exibe "Dias em tela: N" quando o campo está preenchido."""
        nir_user = User.objects.create_user(username="nir_badge@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=10,
            structured_data={"patient": {"name": "Badge Test", "age": 45, "gender": "M"}},
        )
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dias em tela: 10" in content

    def test_queue_hides_regulation_days_badge_when_null(self, client) -> None:
        """Card NÃO exibe badge "Dias em tela" quando o campo é None."""
        nir_user = User.objects.create_user(username="nir_nobadge@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=None,
            structured_data={"patient": {"name": "No Badge", "age": 35, "gender": "F"}},
        )
        case.save()

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dias em tela:" not in content

    def test_queue_uses_created_at_as_tiebreaker(self, client) -> None:
        """Empate em regulation_days_on_screen usa created_at mais antigo primeiro."""
        nir_user = User.objects.create_user(username="nir_tie@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        now = timezone.now()

        old_case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=5,
            structured_data={"patient": {"name": "Old (created first)", "age": 40, "gender": "M"}},
        )
        Case.objects.filter(case_id=old_case.case_id).update(created_at=now - timedelta(hours=5))

        new_case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            regulation_days_on_screen=5,
            structured_data={"patient": {"name": "New (created later)", "age": 50, "gender": "F"}},
        )
        Case.objects.filter(case_id=new_case.case_id).update(created_at=now - timedelta(hours=1))

        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()

        pos_old = content.index("Old (created first)")
        pos_new = content.index("New (created later)")
        assert pos_old < pos_new, "Older case should appear before newer when tie"

    def test_queue_nav_uses_action_and_neutral_count_badges(self, client) -> None:
        """R1: Pendentes uses action badge, Decididos Hoje uses neutral badge."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()

        # Pendentes should have data-count and the action/danger class
        assert "nav-count-badge--danger" in content, "Pendentes must use danger/action badge class"
        # Decididos Hoje should have data-count and the neutral class
        assert "nav-count-badge--neutral" in content, "Decididos Hoje must use neutral badge class"
        # Decididos Hoje must NOT use .notif-badge
        # Check the Decididos Hoje link area (rough check before the closing </a>)
        content_lower = content.lower()
        decided_pos = content_lower.find("decididos hoje")
        assert decided_pos > -1, "Decididos Hoje text not found"
        # Look backwards from 'Decididos Hoje' to find the <a tag and check for notif-badge
        a_tag_start = content.rfind("<a", 0, decided_pos)
        if a_tag_start > -1:
            a_tag_section = content[a_tag_start : decided_pos + 50]
            assert "notif-badge" not in a_tag_section, "Decididos Hoje must not use .notif-badge"

    def test_queue_page_title_pending_tab(self, client) -> None:
        """?tab=pending shows 'Casos aguardando decisão' as page title."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/?tab=pending")
        assert response.status_code == 200
        content = response.content.decode()
        assert '<h1 class="page-title">Casos aguardando decisão</h1>' in content

    def test_queue_page_title_default_tab(self, client) -> None:
        """Default tab (no ?tab) shows the pending page title."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert '<h1 class="page-title">Casos aguardando decisão</h1>' in content

    def test_queue_page_title_decided_tab(self, client) -> None:
        """?tab=decided shows 'Casos decididos hoje' as page title."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        assert '<h1 class="page-title">Casos decididos hoje</h1>' in content
        assert "Casos aguardando decisão</h1>" not in content

    def test_queue_browser_title_reflects_active_tab(self, client) -> None:
        """<title> tag reflects the active tab for both pending and decided."""
        self._login_as(client, "doctor")

        pending = client.get("/doctor/?tab=pending").content.decode()
        assert "<title>Casos aguardando decisão — Médico" in pending

        decided = client.get("/doctor/?tab=decided").content.decode()
        assert "<title>Casos decididos hoje — Médico" in decided

    def test_queue_partial_preserves_decided_tab(self, client) -> None:
        """R3: HTMX partial for ?tab=decided returns only decided content."""
        doctor_user = User.objects.create_user(username="doc_partial@test.com", password="testpass123")
        doctor_user.roles.add(self._create_role("doctor"))

        nir_user = User.objects.create_user(username="nir_partial@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        # Create a decided case
        decided = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": "Partial Decided", "age": 40, "gender": "M"}},
        )
        decided.save()

        # Create a pending case (should NOT appear in decided tab)
        pending = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Partial Pending", "age": 30, "gender": "F"}},
        )
        pending.save()

        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/doctor/partials/queue/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Partial Decided" in content
        assert "Partial Pending" not in content


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
        CaseStatus.WAIT_APPT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
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

    def test_decision_requires_doctor_role(self, client) -> None:
        """NIR with active_role='nir' cannot GET /doctor/<case_id>/."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "João", "age": 50, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "nir")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 302
        assert response.url == "/"

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

    def test_decision_form_uses_acceptance_orientation_label(self, client) -> None:
        """R1: Form label shows 'Orientações para agendamento/execução', not 'Observação Médica'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Label Test", "age": 40, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Orientações para agendamento/execução" in content
        assert "Observação Médica" not in content

    def test_decision_page_guides_missing_documents_to_operational_communication(self, client) -> None:
        """R3: Page guides user to use Comunicação operacional for missing docs."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Microcopy Test", "age": 45, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Comunicação operacional" in content
        assert "NIR" in content
        assert "volte sem decidir" in content or "Voltar sem decidir" in content

    def test_decision_page_cancel_link_says_back_without_deciding(self, client) -> None:
        """R4: Return link says 'Voltar sem decidir', not 'Cancelar'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Cancel Test", "age": 35, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Voltar sem decidir" in content
        import re

        actions_match = re.search(r'<div class="d-flex gap-2">.*?</div>\s*</form>', content, re.DOTALL)
        if actions_match:
            actions_html = actions_match.group(0)
            assert "Voltar sem decidir" in actions_html
            assert "Cancelar" not in actions_html

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

    def test_decision_shows_patient_sex_from_schema(self, client) -> None:
        """Patient sex from LLM1 schema (patient.sex) is displayed."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.agency_record_number = "2026-0506-SEX"
        case.structured_data = {
            "patient": {"name": "Maria Sex", "age": 35, "sex": "F"},
        }
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "F" in content

    def test_decision_shows_patient_gender_fallback(self, client) -> None:
        """When sex is absent but gender is present, gender is used as fallback."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.agency_record_number = "2026-0506-GEN"
        case.structured_data = {
            "patient": {"name": "João Gender", "age": 40, "gender": "Masculino"},
        }
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Masculino" in content

    def test_decision_shows_all_seven_report_blocks(self, client) -> None:
        """Decision page renders all 7 report block titles."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.summary_text = "Paciente com HDA. Hb 8.5."
        case.structured_data = {
            "patient": {"name": "João Blocos", "age": 45, "gender": "Masculino"},
            "eda": {
                "labs": {
                    "hb_g_dl": 8.5,
                    "platelets_per_mm3": 120000,
                    "inr": 1.1,
                },
                "ecg": {
                    "report_present": True,
                    "abnormal_flag": False,
                },
            },
        }
        case.suggested_action = {
            "suggestion": "accept",
            "support_recommendation": "anesthesist",
            "asa": {"display_text": "ASA II"},
        }
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # All 7 block titles must appear
        assert "Resumo Clínico" in content
        assert "Achados Críticos" in content
        assert "Pendências Críticas" in content
        assert "Decisão Sugerida" in content
        assert "Suporte Recomendado" in content
        assert "ASA Estimado" in content
        assert "Motivo Objetivo" in content

        # Context must appear
        assert "procedimento solicitado" in content.lower()

    # ── Slice 001: Decision feedback and pending modal ────────────────────────

    def test_decision_page_has_confirmar_decisao_button(self, client) -> None:
        """Button text is 'Confirmar decisão', not 'Enviar Decisão'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Btn Test", "age": 40, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Confirmar decisão" in content
        assert "Enviar Decisão" not in content

    def test_decision_page_does_not_show_case_id_label(self, client) -> None:
        """The visible 'ID do Caso' label is removed from the form."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "UUID Test", "age": 30, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "ID do Caso" not in content

    def test_decision_page_has_decision_option_classes(self, client) -> None:
        """Template uses scoped decision-option--accept and decision-option--deny classes."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Class Test", "age": 35, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "decision-option--accept" in content
        assert "decision-option--deny" in content

    # ── Slice 002: Reading order and decision anchor ────────────────────────

    def test_decision_page_has_form_after_report(self, client) -> None:
        """'Relatório Automático da Regulação' appears before 'Formulário de Decisão'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.summary_text = "Hérnia inguinal bilateral"
        case.structured_data = {"patient": {"name": "Order Test", "age": 40, "gender": "Masculino"}}
        case.suggested_action = {"suggestion": "accept", "support_recommendation": "anesthesist"}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        report_pos = content.index("Relatório Automático da Regulação")
        form_pos = content.index("Formulário de Decisão")
        assert report_pos < form_pos, (
            f"'Relatório Automático da Regulação' at {report_pos} should come before "
            f"'Formulário de Decisão' at {form_pos}"
        )

    def test_decision_page_has_form_after_communication(self, client) -> None:
        """'Comunicação operacional' appears before 'Formulário de Decisão'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Comm Order", "age": 35, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        comm_pos = content.index("Comunicação operacional")
        form_pos = content.index("Formulário de Decisão")
        assert comm_pos < form_pos, (
            f"'Comunicação operacional' at {comm_pos} should come before 'Formulário de Decisão' at {form_pos}"
        )

    def test_decision_page_has_decision_form_anchor(self, client) -> None:
        """The decision form card has id='doctor-decision-form'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Anchor Test", "age": 30, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="doctor-decision-form"' in content, "Missing id='doctor-decision-form' on form card"

    def test_decision_page_has_shortcut_link(self, client) -> None:
        """Page has a shortcut link pointing to #doctor-decision-form."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Shortcut Test", "age": 45, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'href="#doctor-decision-form"' in content, "Missing shortcut link to #doctor-decision-form"

    def test_decision_page_has_ir_para_decisao_text(self, client) -> None:
        """Page contains 'Ir para decisão' text in the shortcut."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Shortcut Text", "age": 28, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Ir para decisão" in content, "Missing 'Ir para decisão' text"

    def test_decision_page_preserves_decision_form_id(self, client) -> None:
        """The form still has id='decision-form' after the move."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Preserve Form", "age": 33, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="decision-form"' in content, "Missing id='decision-form'"

    def test_decision_page_preserves_work_lock_config(self, client) -> None:
        """The work-lock-config div still exists after the move."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Lock Config", "age": 40, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="work-lock-config"' in content, "Missing id='work-lock-config'"

    def test_decision_page_preserves_confirm_modal(self, client) -> None:
        """The confirm-modal still exists after the move."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Modal Preserve", "age": 50, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="confirm-modal"' in content, "Missing id='confirm-modal'"

    # ── Slice 003: Compact help texts and card selection ─────────────────────

    def test_decision_page_has_faltam_informacoes_text(self, client) -> None:
        """Texto 'Faltam informações?' existe na página."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Info Help", "age": 40, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Faltam informações?" in content, "Texto 'Faltam informações?' deve estar presente"

    def test_decision_page_has_detalhes_link_and_collapse(self, client) -> None:
        """Link 'Detalhes' e collapse id missing-info-help existem."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Detalhes Link", "age": 35, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Detalhes" in content, "Link 'Detalhes' deve estar presente"
        assert 'id="missing-info-help"' in content, "Collapse id missing-info-help deve existir"

    def test_faltam_informacoes_appears_after_voltar_sem_decidir(self, client) -> None:
        """'Faltam informações?' aparece depois de 'Voltar sem decidir' no HTML."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Position Test", "age": 30, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        voltar_pos = content.index("Voltar sem decidir")
        faltam_pos = content.index("Faltam informações?")
        assert voltar_pos < faltam_pos, (
            f"'Voltar sem decidir' at {voltar_pos} deve vir antes de 'Faltam informações?' at {faltam_pos}"
        )

    def test_decision_page_has_complemento_text_in_collapse(self, client) -> None:
        """'Não use negativa apenas para solicitar complemento' está presente (collapse)."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Complemento", "age": 28, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Não use negativa apenas para solicitar complemento" in content

    def test_decision_page_no_old_precisa_mais_info_alert(self, client) -> None:
        """O antigo alerta fixo 'Precisa de mais informações?' não existe como alert-info."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Old Alert", "age": 32, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # The old title "Precisa de mais informações?" should not appear
        assert "Precisa de mais informações?" not in content, (
            "Antigo alerta 'Precisa de mais informações?' não deve mais existir"
        )

    def test_decision_radio_has_visually_hidden_class(self, client) -> None:
        """Radios de decisão têm classe visually-hidden."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Visually Hidden", "age": 45, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Radio inputs with name="decision" should have visually-hidden class
        import re

        radio_matches = re.findall(r'<input[^>]*type="radio"[^>]*name="decision"[^>]*>', content)
        assert len(radio_matches) >= 2, "Devem existir pelo menos 2 radio inputs com name='decision'"
        for radio in radio_matches:
            assert "visually-hidden" in radio or "visually-hidden" in radio.lower(), (
                f"Radio deve ter classe visually-hidden: {radio[:100]}"
            )

    def test_decision_radio_present_with_type_radio_and_name_decision(self, client) -> None:
        """Radios continuam presentes com type='radio' e name='decision'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Radio Present", "age": 38, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        import re

        radio_matches = re.findall(r'<input[^>]*type="radio"[^>]*name="decision"[^>]*>', content)
        assert len(radio_matches) >= 2, "Devem existir pelo menos 2 radio inputs type='radio' name='decision'"

    def test_decision_cards_have_selecionado_indicator(self, client) -> None:
        """Cards Aceitar/Negar têm indicador 'Selecionado' no markup."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Selecionado", "age": 42, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Selecionado" in content, "Indicador 'Selecionado' deve estar presente no markup"

    def test_decision_page_has_btn_stack_mobile_below_buttons(self, client) -> None:
        """Verifica que a orientação compacta está abaixo do btn-stack-mobile."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Stack Order", "age": 33, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        btn_stack_pos = content.rfind("btn-stack-mobile")
        faltam_pos = content.find("Faltam informações?")
        assert btn_stack_pos >= 0, "btn-stack-mobile deve estar presente"
        assert faltam_pos >= 0, "'Faltam informações?' deve estar presente"
        assert btn_stack_pos < faltam_pos, "Orientações 'Faltam informações?' devem aparecer depois do btn-stack-mobile"

    # ── Slice 004: Compact acceptance orientation help text ───────────────────

    def test_decision_page_has_compact_observation_help_text(self, client) -> None:
        """Texto compacto do campo de orientações está presente."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Obs Help", "age": 40, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Opcional · Máx. 500 caracteres." in content, (
            "Texto compacto 'Opcional · Máx. 500 caracteres.' deve estar presente"
        )
        assert "Para pedir documentos, use Comunicação operacional" in content, (
            "Frase sobre documentos na Comunicação operacional deve estar presente"
        )

    def test_decision_page_has_observation_detalhes_and_collapse(self, client) -> None:
        """Link 'Detalhes' e collapse id doctor-observation-help existem."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Detalhes Obs", "age": 35, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Detalhes" in content, "Link 'Detalhes' deve estar presente"
        assert 'id="doctor-observation-help"' in content, "Collapse id doctor-observation-help deve existir"

    def test_decision_page_has_observation_detail_examples(self, client) -> None:
        """Exemplos detalhados do campo de orientações estão presentes (colapsáveis)."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Examples", "age": 30, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "suporte, preparo, prioridade ou cuidados" in content, (
            "Exemplos detalhados devem estar presentes (colapsáveis)"
        )

    def test_decision_page_no_long_observation_help_text(self, client) -> None:
        """O texto longo antigo não aparece como form-text permanente único."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Long Help", "age": 28, "gender": "Masculino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # A string antiga completa não deve aparecer como texto contínuo não-colapsável
        old_text = (
            "Use para orientações que devem acompanhar o aceite, como suporte, preparo, "
            "prioridade ou cuidados no agendamento/execução. Para pedir documentos ou avisar "
            "outra equipe, use a comunicação operacional."
        )
        # Find the form-text div and check it doesn't contain the old long text
        import re

        form_text_matches = re.findall(r'<div class="form-text">(.*?)</div>', content, re.DOTALL)
        found_long_in_form_text = any(old_text in ft for ft in form_text_matches)
        assert not found_long_in_form_text, "O texto longo antigo não deve estar em um form-text permanente"

    def test_decision_page_has_observation_label(self, client) -> None:
        """Label 'Orientações para agendamento/execução' continua presente."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Label Check", "age": 32, "gender": "Feminino"}}
        case.save()
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Orientações para agendamento/execução" in content, (
            "Label 'Orientações para agendamento/execução' deve continuar presente"
        )


# ── Prior case card tests ───────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecisionPriorCaseCard:
    """Tests for prior case context card in doctor decision view."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@prior.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_prior_denied_case(self, user, arn: str, reason: str, days_ago: int = 1) -> Case:
        """Create a prior DOCTOR_DENIED case with the same agency_record_number."""
        from datetime import timedelta

        case = Case.objects.create(
            created_by=user,
            agency_record_number=arn,
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason=reason,
            doctor_decided_at=timezone.now() - timedelta(days=days_ago),
        )
        Case.objects.filter(case_id=case.case_id).update(created_at=timezone.now() - timedelta(days=days_ago))
        return case

    def test_prior_case_card_shows_when_recent_denial(self, client) -> None:
        """Card 'Caso Anterior' aparece quando há negação recente."""
        nir_user = User.objects.create_user(username="nir_prior1@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        current = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ARN-001",
            structured_data={"patient": {"name": "João Prior", "age": 50, "gender": "Masculino"}},
        )
        current.save()

        # Create prior case with same ARN
        doctor_user = User.objects.create_user(
            username="doc_prior1@test.com",
            password="testpass123",
            first_name="Dr. Carlos",
        )
        doctor_user.professional_council = "CRM"
        doctor_user.professional_council_number = "99999"
        doctor_user.save()
        prior = self._make_prior_denied_case(nir_user, "ARN-001", "Contorno clínico elevado")
        prior.doctor = doctor_user
        prior.save()

        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{current.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Caso Anterior" in content
        assert "Regulação Negada" in content
        assert "Contorno clínico elevado" in content
        assert "Dr. Carlos — CRM 99999" in content

    def test_prior_case_card_hidden_when_no_prior(self, client) -> None:
        """Card não aparece quando não há caso anterior."""
        nir_user = User.objects.create_user(username="nir_prior2@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        current = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ARN-002",
            structured_data={"patient": {"name": "Maria SemPrior", "age": 40, "gender": "Feminino"}},
        )
        current.save()

        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{current.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Caso Anterior" not in content

    def test_prior_case_card_shows_multiple_denials_badge(self, client) -> None:
        """Card mostra badge de contagem quando múltiplas negações."""
        nir_user = User.objects.create_user(username="nir_prior3@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))

        current = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ARN-003",
            structured_data={"patient": {"name": "Multi Prior", "age": 60, "gender": "Masculino"}},
        )
        current.save()

        # Create 2 prior denied cases
        self._make_prior_denied_case(nir_user, "ARN-003", "Primeira negação", days_ago=2)
        self._make_prior_denied_case(nir_user, "ARN-003", "Segunda negação", days_ago=1)

        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{current.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Caso Anterior" in content
        assert "2 negações" in content or "negações em 7 dias" in content


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

    # ── Observation field tests ──────────────────────────────────────────

    def test_accept_with_empty_observation_is_valid(self) -> None:
        """Accept decision with empty observation is valid."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
                "observation": "",
            }
        )
        assert form.is_valid()

    def test_accept_with_500_char_observation_is_valid(self) -> None:
        """Accept decision with observation of exactly 500 chars is valid."""
        from apps.doctor.forms import DoctorDecisionForm

        text_500 = "x" * 500
        form = DoctorDecisionForm(
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
                "observation": text_500,
            }
        )
        assert form.is_valid()

    def test_accept_with_501_char_observation_is_invalid(self) -> None:
        """Accept decision with observation of 501 chars is invalid."""
        from apps.doctor.forms import DoctorDecisionForm

        text_501 = "x" * 501
        form = DoctorDecisionForm(
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
                "observation": text_501,
            }
        )
        assert not form.is_valid()
        assert "observation" in form.errors

    def test_deny_with_observation_is_valid(self) -> None:
        """Deny decision with observation filled is valid."""
        from apps.doctor.forms import DoctorDecisionForm

        form = DoctorDecisionForm(
            data={
                "decision": "deny",
                "reason": "Contorno clínico não indicado",
                "observation": "Paciente pode ser reavaliado em 30 dias.",
            }
        )
        assert form.is_valid()


# ── Lock renew/release endpoint tests ────────────────────────────────────


@pytest.mark.django_db
class TestDoctorLockEndpoints:
    """Tests for POST /doctor/<case_id>/lock/renew/ and /lock/release/."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@lockep.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_in_status(self, status: str) -> Case:
        nir_user = User.objects.create_user(
            username=f"nir_lockep_{(status or 'new').lower()}@test.com", password="testpass123"
        )
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        if status != CaseStatus.NEW:
            case = _advance_case_to(case, status)
        return case

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

    def test_renew_with_valid_token_returns_json_success(self, client):
        """POST renew with valid token returns JSON success."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Renew OK", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/lock/renew/",
            data={"lock_token": token},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        import json

        data = json.loads(response.content)
        assert data.get("success") is True
        assert "locked_until" in data

    def test_renew_with_invalid_token_returns_error(self, client):
        """POST renew with invalid token returns error and does not alter lock."""
        from apps.cases.services import claim_case_lock

        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Renew Bad", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        # First claim to establish lock
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        original_locked_until = Case.objects.get(pk=case.case_id).locked_until

        response = client.post(
            f"/doctor/{case.case_id}/lock/renew/",
            data={"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        import json

        data = json.loads(response.content)
        assert data.get("success") is False
        assert "error" in data or "detail" in data

        # locked_until unchanged
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_until == original_locked_until

    def test_release_with_valid_token_clears_lock(self, client):
        """POST release with valid token clears lock fields."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Release OK", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/lock/release/",
            data={"lock_token": token},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        import json

        data = json.loads(response.content)
        assert data.get("success") is True

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is None
        assert case.lock_token is None

    def test_release_with_invalid_token_does_not_clear(self, client):
        """POST release with invalid token does not clear lock."""
        from apps.cases.services import claim_case_lock

        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Release Fail", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        # Claim lock
        claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        response = client.post(
            f"/doctor/{case.case_id}/lock/release/",
            data={"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        import json

        data = json.loads(response.content)
        assert data.get("success") is False

        # Lock still intact
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == doctor

    def test_lock_endpoints_require_doctor_role(self, client):
        """Lock endpoints return redirect for non-doctor roles."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Role Check", "age": 40, "gender": "M"}}
        case.save()

        self._login_as(client, "nir")

        response = client.post(f"/doctor/{case.case_id}/lock/renew/")
        assert response.status_code == 302
        assert response.url == "/"

        response = client.post(f"/doctor/{case.case_id}/lock/release/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_lock_endpoints_reject_get(self, client):
        """Lock endpoints return 404 for GET requests."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "GET Check", "age": 40, "gender": "M"}}
        case.save()

        self._login_as(client, "doctor")

        response = client.get(f"/doctor/{case.case_id}/lock/renew/")
        assert response.status_code == 404

        response = client.get(f"/doctor/{case.case_id}/lock/release/")
        assert response.status_code == 404


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

    def test_submit_blocks_nir(self, client) -> None:
        """NIR with active_role='nir' cannot POST /doctor/<case_id>/submit/."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Blocked", "age": 40, "gender": "Masculino"}}
        case.save()

        self._login_as(client, "nir")

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
            },
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_submit_accept_persists_fields_and_transitions(self, client) -> None:
        """POST accept → fields persisted, FSM: WAIT_DOCTOR → DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Test Accept", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
                "lock_token": token,
            },
        )
        assert response.status_code == 302  # redirect after success

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.doctor_support_flag == "anesthesist"
        assert case.doctor_admission_flow == "scheduled"
        assert case.doctor == doctor
        assert case.doctor_decided_at is not None
        assert case.status == CaseStatus.WAIT_APPT

    def test_submit_accept_immediate_bypasses_scheduler_and_posts_final_reply(self, client) -> None:
        """POST accept/immediate → no scheduling gate; final result returns to NIR."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Immediate", "age": 70, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "immediate",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.doctor_admission_flow == "immediate"
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

        events = CaseEvent.objects.filter(case=case)
        assert events.filter(event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE").exists()
        assert events.filter(event_type="FINAL_REPLY_POSTED").exists()
        assert not events.filter(event_type="SCHEDULER_REQUEST_POSTED").exists()

    def test_submit_accept_creates_scheduler_event(self, client) -> None:
        """POST accept creates SCHEDULER_REQUEST_POSTED event (auto-transition)."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Sched Event", "age": 35, "gender": "Feminino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": token,
            },
        )

        events = CaseEvent.objects.filter(case=case, event_type="SCHEDULER_REQUEST_POSTED")
        assert events.exists()

    def test_submit_deny_persists_fields_and_transitions(self, client) -> None:
        """POST deny → fields persisted, FSM: WAIT_DOCTOR → DOCTOR_DENIED → WAIT_R1_CLEANUP_THUMBS."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Test Deny", "age": 50, "gender": "Feminino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Contorno clínico não indicado",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "deny"
        assert case.doctor_reason == "Contorno clínico não indicado"
        assert case.doctor == doctor
        assert case.doctor_decided_at is not None
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_submit_deny_creates_final_reply_event(self, client) -> None:
        """POST deny cria evento FINAL_REPLY_POSTED (auto-transição)."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Final Reply", "age": 45, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Sem indicação cirúrgica",
                "lock_token": token,
            },
        )

        events = CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED")
        assert events.exists()

    def test_submit_creates_case_event_accept(self, client) -> None:
        """POST accept creates a DOCTOR_ACCEPT CaseEvent."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Event Accept", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "immediate",
                "lock_token": token,
            },
        )

        events = CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_")
        assert events.filter(event_type="DOCTOR_ACCEPT").exists()

    def test_submit_creates_case_event_deny(self, client) -> None:
        """POST deny creates a DOCTOR_DENY and FINAL_REPLY_POSTED CaseEvent."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Event Deny", "age": 50, "gender": "Feminino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Motivo de teste",
                "lock_token": token,
            },
        )

        events = CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_")
        assert events.filter(event_type="DOCTOR_DENY").exists()
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

    # ── Slice 001: Decision feedback and pending modal ────────────────────────

    def test_decision_js_contains_pending_modal_references(self) -> None:
        """decision.js must reference pending modal elements and strings."""
        js = Path("static/js/decision.js").read_text()
        assert "Decisão incompleta" in js
        assert "btn-leave-without-decision" in js
        assert "btn-back-to-form" in js
        assert "form.requestSubmit()" in js
        assert "collectMissingItems" in js
        assert "showPendingModal" in js
        assert "showFinalConfirmModal" in js

    def test_decision_js_uses_normal_submit_path_after_modal_confirmation(self) -> None:
        """Modal confirmation must not use bare form.submit() as the primary path.

        The manual dev flow showed POST /doctor/<id>/submit/ reaching
        @login_required as anonymous immediately after modal confirmation.
        Keep the JS on requestSubmit(), with a confirmation guard, so the final
        POST follows the browser's normal form submission path.
        """
        js = Path("static/js/decision.js").read_text()
        assert "finalSubmitConfirmed" in js
        assert "form.requestSubmit()" in js
        assert "if (finalSubmitConfirmed) return;" in js

    def test_service_worker_does_not_intercept_post_requests(self) -> None:
        """Service worker must not wrap Django form POST requests.

        Role switching and decision/receipt forms rely on normal browser
        cookie/session/CSRF behavior. The service worker may cache GET assets,
        but non-GET requests must go straight to Django.
        """
        sw = Path("static/js/sw.js").read_text()
        assert 'event.request.method !== "GET"' in sw
        assert "ats-cache-v5" in sw

    def test_service_worker_bypasses_pdf_and_attachment_navigations(self) -> None:
        """SW must not intercept target="_blank" navigations to PDF/attachment routes.

        Chromium's native PDF viewer does not render when a navigation response
        is delivered via respondWith, leaving the new tab blank. File-viewing
        routes must bypass the SW so the browser fetches them natively.
        """
        sw = Path("static/js/sw.js").read_text()
        assert 'endsWith("/pdf/")' in sw
        assert 'includes("/attachments/")' in sw

    # ── Observation submit tests ──────────────────────────────────────────

    def test_submit_accept_with_observation_persists(self, client) -> None:
        """POST accept with observation persists case.doctor_observation (orientation)."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Obs Accept", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "scheduled",
                "observation": "Priorizar por anemia. Agendar com anestesia.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_observation == "Priorizar por anemia. Agendar com anestesia."

    def test_submit_deny_with_observation_ignores_orientation(self, client) -> None:
        """POST deny with observation does NOT persist orientation; doctor_observation stays empty."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Deny Obs Ignore", "age": 50, "gender": "Feminino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Sem indicação cirúrgica",
                "observation": "Encaminhar para avaliação clínica.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_reason == "Sem indicação cirúrgica"
        assert case.doctor_observation == "", (
            f"Expected doctor_observation to be empty on deny, got: {case.doctor_observation!r}"
        )

    def test_submit_accept_strips_orientation_whitespace(self, client) -> None:
        """POST accept strips whitespace from observation before persisting."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Strip Test", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "observation": "  Espaços ao redor  ",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_observation == "Espaços ao redor"

    def test_submit_without_observation_persists_empty_string(self, client) -> None:
        """POST without observation persists empty string and doesn't break flow."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "No Obs", "age": 35, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_observation == ""
        assert case.status == CaseStatus.WAIT_APPT

    def test_submit_with_observation_over_500_chars_shows_error(self, client) -> None:
        """POST with observation over 500 chars re-renders form with error."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Long Obs", "age": 45, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        text_501 = "x" * 501
        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "observation": text_501,
                "lock_token": token,
            },
        )
        assert response.status_code == 200  # re-renders form
        content = response.content.decode()
        assert "error" in content.lower() or "caractere" in content.lower()

        # Case status should NOT have changed
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_observation == ""

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


# ── Lock behavior tests ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecisionLockBehavior:
    """Tests for lock acquisition and validation in doctor decision/submit."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

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

    def _create_case_in_status(self, status: str) -> Case:
        nir_user = User.objects.create_user(
            username=f"nir_lock_{(status or 'new').lower()}@test.com", password="testpass123"
        )
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        if status != CaseStatus.NEW:
            case = _advance_case_to(case, status)
        return case

    def test_decision_get_acquires_lock_and_includes_token(self, client) -> None:
        """GET /doctor/<case_id>/ acquires lock and includes hidden lock_token."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Lock Test", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200

        content = response.content.decode()
        assert 'name="lock_token"' in content
        assert 'type="hidden"' in content

        # Lock should be persisted
        case_from_db = Case.objects.get(pk=case.case_id)
        assert case_from_db.locked_by == doctor
        assert case_from_db.lock_context == "doctor_decision"
        assert case_from_db.lock_role == "doctor"

    def test_second_doctor_redirected_when_case_locked(self, client) -> None:
        """Second doctor GET /doctor/<case_id>/ is redirected when case is locked by another."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Locked Case", "age": 50, "gender": "Masculino"}}
        case.save()

        # First doctor acquires lock
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200

        # Second doctor tries to access - use a different client

        from django.test import Client

        client_b = Client()
        doc_b = User.objects.create_user(username="doctor_b_locked@test.com", password="testpass123")
        doc_b.roles.add(self._create_role("doctor"))
        doc_b.first_name = "Dr. Segundo"
        doc_b.save()
        client_b.force_login(doc_b)
        session = client_b.session
        session["active_role"] = "doctor"
        session.save()

        response_b = client_b.get(f"/doctor/{case.case_id}/")
        assert response_b.status_code == 302  # redirect to queue

    def test_submit_with_valid_lock_succeeds(self, client) -> None:
        """POST submit with valid lock_token executes and redirects."""
        from apps.cases.services import claim_case_lock

        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Valid Lock", "age": 40, "gender": "Masculino"}}
        case.save()

        doctor = self._login_as(client, "doctor")

        # Pre-acquire lock
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": str(result.token),
            },
        )
        assert response.status_code == 302

        case_from_db = Case.objects.get(pk=case.case_id)
        assert case_from_db.doctor_decision == "accept"
        assert case_from_db.status == CaseStatus.WAIT_APPT

    def test_submit_without_token_shows_error(self, client) -> None:
        """POST submit without lock_token shows error and does not change status."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "No Token", "age": 40, "gender": "Masculino"}}
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
        assert response.status_code == 200  # re-renders form
        content = response.content.decode()
        assert "lock" in content.lower() or "token" in content.lower() or "reserva" in content.lower()

        case_from_db = Case.objects.get(pk=case.case_id)
        assert case_from_db.status == CaseStatus.WAIT_DOCTOR  # unchanged

    def test_submit_with_invalid_token_shows_error(self, client) -> None:
        """POST submit with wrong lock_token shows error and does not change status."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Bad Token", "age": 40, "gender": "Masculino"}}
        case.save()

        self._login_as(client, "doctor")

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 200  # re-renders form
        content = response.content.decode()
        assert "lock" in content.lower() or "token" in content.lower() or "reserva" in content.lower()

        case_from_db = Case.objects.get(pk=case.case_id)
        assert case_from_db.status == CaseStatus.WAIT_DOCTOR  # unchanged

    def test_queue_shows_case_reserved_by_other(self, client) -> None:
        """Queue shows when a case is reserved by another doctor."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Reserved Case", "age": 45, "gender": "Feminino"}}
        case.save()

        from apps.cases.services import claim_case_lock

        doc_a = User.objects.create_user(username="doc_queue_lock@test.com", password="testpass123")
        doc_a.roles.add(self._create_role("doctor"))
        doc_a.first_name = "Dra. A"
        doc_a.save()

        result = claim_case_lock(
            case_id=case.case_id,
            user=doc_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        # Login as a different doctor to see the queue
        doc_b = self._login_as(client, "doctor")
        doc_b.first_name = "Dr. B"
        doc_b.save()

        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reserved Case" in content
        assert "Dra. A" in content
        assert "reservado" in content.lower() or "bloqueado" in content.lower() or "desabilitado" in content.lower()

    def test_expired_lock_shows_available_in_queue(self, client) -> None:
        """Case with expired lock shows as available (not blocked) in doctor queue."""
        from apps.cases.services import claim_case_lock

        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Expired Lock", "age": 50, "gender": "Masculino"}}
        case.save()

        doc_a = User.objects.create_user(username="doc_expired@test.com", password="testpass123")
        doc_a.roles.add(self._create_role("doctor"))
        doc_a.first_name = "Dr. Antigo"
        doc_a.save()

        # Claim lock and force expiration
        claim_case_lock(
            case_id=case.case_id,
            user=doc_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=0,
        )
        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        # Login as a different doctor — queue view calls expire_stale_locks
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()

        # The lock has expired and been cleared by expire_stale_locks
        # Case should show up and NOT be marked as reserved
        assert "Expired Lock" in content
        # Should NOT show locked indicators
        assert "Dr. Antigo" not in content
        case_from_db = Case.objects.get(pk=case.case_id)
        assert case_from_db.locked_by is None

    def test_queue_renders_locked_case_with_locked_by_name(self, client) -> None:
        """Queue renders a locked case with the locked_by display name."""
        from apps.cases.services import claim_case_lock

        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Locked Display", "age": 45, "gender": "Feminino"}}
        case.save()

        doc_a = User.objects.create_user(username="doc_display@test.com", password="testpass123")
        doc_a.roles.add(self._create_role("doctor"))
        doc_a.first_name = "Dra. Display"
        doc_a.save()

        # Acquire lock
        claim_case_lock(
            case_id=case.case_id,
            user=doc_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        # Login as a different doctor to see the lock display
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Locked Display" in content
        assert "Dra. Display" in content


# ── Lock release on submit tests ──────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorLockReleaseOnSubmit:
    """RED tests: lock is released after successful submit, preserved on errors."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@locksub.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_in_status(self, status: str) -> Case:
        nir_user = User.objects.create_user(
            username=f"nir_locksub_{(status or 'new').lower()}@test.com", password="testpass123"
        )
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        if status != CaseStatus.NEW:
            case = _advance_case_to(case, status)
        return case

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

    def test_submit_accept_scheduled_releases_lock_after_success(self, client) -> None:
        """POST accept/scheduled → lock fields cleared, WORK_LOCK_RELEASED created."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Lock Release", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_APPT
        assert case.locked_by is None
        assert case.lock_token is None
        assert case.locked_until is None
        assert case.lock_context == ""
        assert case.lock_role == ""

        # Verify WORK_LOCK_RELEASED event
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_deny_releases_lock_after_success(self, client) -> None:
        """POST deny → lock fields cleared, WORK_LOCK_RELEASED created."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Lock Deny", "age": 50, "gender": "F"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "reason": "Contorno clínico não indicado",
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

        # Verify WORK_LOCK_RELEASED event
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_accept_immediate_releases_lock_after_success(self, client) -> None:
        """POST accept/immediate → lock fields cleared, WORK_LOCK_RELEASED created."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Lock Immediate", "age": 70, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "anesthesist",
                "admission_flow": "immediate",
                "lock_token": token,
            },
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.locked_by is None
        assert case.lock_token is None
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_invalid_form_preserves_lock(self, client) -> None:
        """POST invalid → lock preserved, status unchanged."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Lock Preserve", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        # Submit accept without required support_flag
        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "",
                "admission_flow": "scheduled",
                "lock_token": token,
            },
        )
        assert response.status_code == 200  # re-renders form

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_DOCTOR  # unchanged
        assert case.locked_by == doctor
        assert case.lock_token is not None
        # No WORK_LOCK_RELEASED should exist for failed submit
        assert not CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_without_token_preserves_lock_and_status(self, client) -> None:
        """POST without lock_token → status unchanged, lock preserved."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "No Token", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        # Submit without lock_token (but with valid form data)
        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                # no lock_token
            },
        )
        assert response.status_code == 200  # re-renders with error

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_DOCTOR  # unchanged
        # Lock should still be held by the doctor (assert_case_lock wasn't called for token=None path)
        assert case.locked_by == doctor
        assert not CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_submit_with_invalid_token_preserves_lock_and_status(self, client) -> None:
        """POST with invalid lock_token → status unchanged, lock preserved."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Bad Token", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        self._claim_lock(case.case_id, doctor)

        # Submit with wrong token
        wrong_token = str(uuid.uuid4())
        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": wrong_token,
            },
        )
        assert response.status_code == 200  # re-renders with error

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_DOCTOR  # unchanged
        assert case.locked_by == doctor
        assert not CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_RELEASED").exists()

    def test_handoff_doctor_to_scheduler_immediate(self, client) -> None:
        """Handoff imediato: médico aceita scheduled → scheduler abre confirm sem esperar."""
        # Doctor submits accept/scheduled
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Handoff D2S", "age": 40, "gender": "M"}}
        case.save()

        doctor = self._login_as(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        client.post(
            f"/doctor/{case.case_id}/submit/",
            data={
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "lock_token": token,
            },
        )

        # Now login as scheduler
        from apps.accounts.models import Role

        scheduler_user = User.objects.create_user(username="scheduler_handoff@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="scheduler")
        scheduler_user.roles.add(role)
        client.force_login(scheduler_user)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        # Scheduler should be able to open confirm page immediately
        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_APPT
        assert case.locked_by is None  # lock was released by doctor submit

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200  # can access immediately

        # Scheduler acquired their own lock
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == scheduler_user
        assert case.lock_context == "scheduler_confirm"
