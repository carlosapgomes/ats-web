"""Testes do Slice 003 — Agendador resolve intercorrência pós-agendamento."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _login_as(client, role_name: str):
    """Create user with given role, login, and set active_role in session."""
    user = User.objects.create_user(username=f"{role_name}@psi-sched.test", password="testpass123")
    user.roles.add(_create_role(role_name))
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _create_waited_case(user, **overrides) -> Case:
    """Create a Case in WAIT_APPT suitable for scheduler."""
    nir_user = User.objects.create_user(username="nir@psi-sched.test", password="testpass123")
    nir_user.roles.add(_create_role("nir"))
    defaults = {
        "created_by": nir_user,
        "status": CaseStatus.WAIT_APPT,
        "doctor_decision": "accept",
        "doctor_admission_flow": "scheduled",
        "appointment_status": "",
        "structured_data": {
            "patient": {
                "name": "Paciente Teste",
                "age": 55,
                "gender": "Masculino",
            },
        },
    }
    defaults.update(overrides)
    case = Case.objects.create(**defaults)
    case.save()
    return Case.objects.get(pk=case.pk)


def _create_case_with_opened_issue(case_factory, advance_to, user) -> Case:
    """Cria um Case em WAIT_APPT com intercorrência aberta."""
    from apps.cases.services import open_post_schedule_issue

    nir_user = User.objects.create_user(username="nir@test-issue.test", password="testpass123")
    nir_user.roles.add(_create_role("nir"))

    case = advance_to(case_factory(nir_user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.agency_record_number = "OCOR-PSI-001"
    case.appointment_at = timezone.now() + timedelta(days=7)
    case.appointment_location = "Hospital Central"
    case.structured_data = {
        "patient": {"name": "Maria Intercorrência", "age": 50, "sex": "F"},
        "eda": {"indication_category": "HDA"},
    }
    case.save(
        update_fields=[
            "doctor_decision",
            "doctor_admission_flow",
            "appointment_status",
            "agency_record_number",
            "appointment_at",
            "appointment_location",
            "structured_data",
        ]
    )
    case = Case.objects.get(pk=case.pk)
    case = open_post_schedule_issue(
        case=case,
        user=nir_user,
        reason="reschedule_request",
        message="Unidade solicita reagendamento para próxima semana.",
    )
    return Case.objects.get(pk=case.pk)


def _create_case_with_opened_issue_reason(case_factory, advance_to, reason: str, message: str = "") -> tuple[Case, Any]:  # noqa: ANN401  # User from get_user_model()
    """Cria Case em WAIT_APPT com intercorrência de motivo específico.

    Retorna (case, nir_user) para reuso nos testes.
    """
    from apps.cases.services import open_post_schedule_issue

    nir_user = User.objects.create_user(username=f"nir-{reason}@test-issue.test", password="testpass123")
    nir_user.roles.add(_create_role("nir"))

    case = advance_to(case_factory(nir_user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.agency_record_number = f"OCOR-{reason[:8].upper()}"
    case.appointment_at = timezone.now() + timedelta(days=7)
    case.appointment_location = "Hospital Central"
    case.structured_data = {
        "patient": {"name": f"Paciente {reason}", "age": 45, "sex": "F"},
        "eda": {"indication_category": "HDA"},
    }
    case.save(
        update_fields=[
            "doctor_decision",
            "doctor_admission_flow",
            "appointment_status",
            "agency_record_number",
            "appointment_at",
            "appointment_location",
            "structured_data",
        ]
    )
    case = Case.objects.get(pk=case.pk)
    case = open_post_schedule_issue(
        case=case,
        user=nir_user,
        reason=reason,
        message=message,
    )
    return Case.objects.get(pk=case.pk), nir_user


def _claim_lock(case_id, scheduler_user) -> str:
    """Acquire a scheduler_confirm lock and return token."""
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


# ══════════════════════════════════════════════════════════════════════════
# TESTS DA FILA — intercorrência aparece na fila do agendador
# ══════════════════════════════════════════════════════════════════════════


class TestQueuePostScheduleIssue:
    """RED 1-3: Intercorrência aparece na fila do agendador com destaque."""

    def test_issue_appears_in_scheduler_queue(self, client, case_factory, advance_to) -> None:
        """Caso WAIT_APPT com post_schedule_issue_status='opened' aparece na fila."""
        _login_as(client, "scheduler")
        _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Intercorrência" in content
        assert "OCOR-PSI-001" in content

    def test_issue_card_shows_badge(self, client, case_factory, advance_to) -> None:
        """Card mostra badge 'Intercorrência pós-aceitação'."""
        _login_as(client, "scheduler")
        _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência pós-aceitação" in content or "Intercorrência" in content

    def test_issue_card_shows_nir_reason(self, client, case_factory, advance_to) -> None:
        """Card mostra o motivo e mensagem do NIR."""
        _login_as(client, "scheduler")
        _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "reschedule_request" in content or "reagendamento" in content.lower()
        assert "Unidade solicita" in content

    def test_issue_card_shows_portuguese_reason_label_death(self, client, case_factory, advance_to) -> None:
        """Card com motivo 'death' mostra 'Paciente faleceu' em português."""
        _login_as(client, "scheduler")
        _create_case_with_opened_issue_reason(case_factory, advance_to, "death")

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente faleceu" in content

    def test_issue_card_does_not_show_raw_code_death(self, client, case_factory, advance_to) -> None:
        """Card NÃO mostra o código cru 'death' como motivo visível."""
        _login_as(client, "scheduler")
        _create_case_with_opened_issue_reason(case_factory, advance_to, "death")

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        # O código 'death' não deve aparecer como texto de motivo visível;
        # pode aparecer em atributos técnicos (name, value, data-*), mas não
        # como texto de display do motivo.
        motivo_death = content.count("Motivo (death)")
        assert motivo_death == 0, f"Encontrado 'Motivo (death)' {motivo_death} vez(es) no HTML"

    def test_issue_card_shows_reschedule_request_label_and_message(self, client, case_factory, advance_to) -> None:
        """Card com 'reschedule_request' mostra label em português e mensagem do NIR."""
        _login_as(client, "scheduler")
        _create_case_with_opened_issue_reason(
            case_factory,
            advance_to,
            "reschedule_request",
            message="Paciente precisa de nova data por conflito de horário.",
        )

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Solicitação de reagendamento pela unidade de origem" in content
        assert "Paciente precisa de nova data" in content

    def test_normal_case_without_issue_has_no_badge(self, client, case_factory, advance_to) -> None:
        """Caso WAIT_APPT normal (sem intercorrência) não mostra badge."""
        _login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir@noissue.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = advance_to(case_factory(nir_user), CaseStatus.WAIT_APPT)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.agency_record_number = "NORMAL-001"
        case.structured_data = {"patient": {"name": "Sem Issue", "age": 40, "sex": "M"}}
        case.save(
            update_fields=[
                "doctor_decision",
                "doctor_admission_flow",
                "agency_record_number",
                "structured_data",
            ]
        )

        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência" not in content


# ══════════════════════════════════════════════════════════════════════════
# TESTS DA TELA DE CONFIRMAÇÃO — agendador vê mensagem do NIR
# ══════════════════════════════════════════════════════════════════════════


class TestConfirmPostScheduleIssue:
    """RED 3-4: GET da tela mostra mensagem do NIR e lock é adquirido."""

    def test_get_shows_nir_message(self, client, case_factory, advance_to) -> None:
        """GET da tela do agendador mostra mensagem do NIR para caso com issue."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Unidade solicita" in content
        assert "reschedule_request" in content or "reagendamento" in content.lower()

    def test_lock_is_acquired_on_get(self, client, case_factory, advance_to) -> None:
        """Lock scheduler_confirm é adquirido na GET como no fluxo normal."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is not None
        assert case.lock_context == "scheduler_confirm"
        assert case.lock_role == "scheduler"
        assert case.lock_token is not None
        assert CaseEvent.objects.filter(case=case, event_type="WORK_LOCK_CLAIMED").exists()

    def test_get_shows_intercurrence_form(self, client, case_factory, advance_to) -> None:
        """GET renderiza formulário de intercorrência (com ações) ao invés do normal."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Must show the 4 action buttons/fields
        assert "cancel" in content.lower() or "Cancelar" in content
        assert "reschedule" in content.lower() or "Reagendar" in content
        assert "maintain" in content.lower() or "Manter" in content
        assert "deny" in content.lower() or "Negar" in content

    def test_normal_case_shows_normal_form(self, client, case_factory, advance_to) -> None:
        """Caso WAIT_APPT sem intercorrência continua mostrando formulário normal."""
        _login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir@normform.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = advance_to(case_factory(nir_user), CaseStatus.WAIT_APPT)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.structured_data = {"patient": {"name": "Normal Form", "age": 30, "sex": "M"}}
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "structured_data"])

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Must show the normal confirm/deny form
        assert "Confirmar Agendamento" in content or "Status do Agendamento" in content
        # Should show the confirm/deny radio buttons (not intercurrence-specific actions)
        assert 'value="confirm"' in content
        assert 'value="deny"' in content
        # Should NOT show intercurrence-specific action buttons
        assert 'value="reschedule"' not in content
        assert 'value="maintain"' not in content

    def test_confirm_shows_portuguese_reason_label_death(self, client, case_factory, advance_to) -> None:
        """Tela de confirmação com motivo 'death' mostra 'Paciente faleceu'."""
        _login_as(client, "scheduler")
        case, _ = _create_case_with_opened_issue_reason(case_factory, advance_to, "death")

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente faleceu" in content

    def test_confirm_does_not_show_raw_code_death(self, client, case_factory, advance_to) -> None:
        """Tela de confirmação NÃO mostra 'Motivo: death' como texto visível."""
        _login_as(client, "scheduler")
        case, _ = _create_case_with_opened_issue_reason(case_factory, advance_to, "death")

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # A seção de motivo deve conter a label em português, não o código cru
        assert "Paciente faleceu" in content
        # O texto 'Motivo: death' NÃO deve aparecer (antes mostrava o código cru)
        assert "Motivo: death" not in content

    def test_confirm_shows_reschedule_request_label_and_message(self, client, case_factory, advance_to) -> None:
        """Tela de confirmação com 'reschedule_request' mostra label em português e mensagem."""
        _login_as(client, "scheduler")
        case, _ = _create_case_with_opened_issue_reason(
            case_factory,
            advance_to,
            "reschedule_request",
            message="Reagendar para próxima semana.",
        )

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Solicitação de reagendamento pela unidade de origem" in content
        assert "Reagendar para próxima semana." in content


# ══════════════════════════════════════════════════════════════════════════
# TESTS DE SUBMIT — ações do agendador
# ══════════════════════════════════════════════════════════════════════════


class TestSubmitPostScheduleIssue:
    """RED 1-8: Ações do agendador na intercorrência."""

    def test_cancel_action_works(self, client, case_factory, advance_to) -> None:
        """POST cancel marca appointment_status='cancelled' e vai para WAIT_R1_CLEANUP_THUMBS."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        token = _claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "cancel",
                "psi_response_message": "Paciente faleceu. Agendamento cancelado.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "cancelled"
        assert updated_case.post_schedule_issue_status == "responded"
        assert updated_case.post_schedule_issue_response_action == "cancel"

    def test_reschedule_action_works(self, client, case_factory, advance_to) -> None:
        """POST reschedule com data/local/instruções válidas atualiza agendamento."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        token = _claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "reschedule",
                "psi_response_message": "Reagendado conforme solicitação.",
                "psi_appointment_date": "2026-07-15",
                "psi_appointment_time": "10:30",
                "psi_appointment_location": "Hospital Central - Sala 3",
                "psi_appointment_instructions": "Trazer exames anteriores.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"
        assert updated_case.post_schedule_issue_status == "responded"
        assert updated_case.post_schedule_issue_response_action == "reschedule"
        # Check appointment fields were updated
        assert updated_case.appointment_at is not None
        assert "Hospital Central - Sala 3" in (updated_case.appointment_location or "")
        assert "Trazer exames" in (updated_case.appointment_instructions or "")

    def test_maintain_action_works(self, client, case_factory, advance_to) -> None:
        """POST maintain preserva agendamento confirmado e vai para WAIT_R1_CLEANUP_THUMBS."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        # Record original appointment
        original_location = case.appointment_location
        original_at = case.appointment_at
        token = _claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "maintain",
                "psi_response_message": "Agendamento mantido conforme solicitado.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"
        assert updated_case.post_schedule_issue_response_action == "maintain"
        # Preserved original data
        assert updated_case.appointment_location == original_location
        assert updated_case.appointment_at == original_at

    def test_deny_action_works(self, client, case_factory, advance_to) -> None:
        """POST deny com motivo preserva agendamento e vai para WAIT_R1_CLEANUP_THUMBS."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        original_location = case.appointment_location
        token = _claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "deny",
                "psi_response_message": "Sem vagas disponíveis para reagendamento neste mês.",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"
        assert updated_case.post_schedule_issue_response_action == "deny"
        # Preserved original data
        assert updated_case.appointment_location == original_location

    def test_deny_without_message_shows_error(self, client, case_factory, advance_to) -> None:
        """POST deny sem motivo exibe erro e não altera o caso."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        token = _claim_lock(case.case_id, scheduler_user)
        original_status = Case.objects.get(pk=case.case_id).status

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "deny",
                "psi_response_message": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 200  # re-renders with error
        content = response.content.decode()
        assert "obrigatória" in content.lower() or "obrigatório" in content.lower()

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == original_status  # not changed

    def test_reschedule_without_date_shows_error(self, client, case_factory, advance_to) -> None:
        """POST reschedule sem nova data exibe erro."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        token = _claim_lock(case.case_id, scheduler_user)
        original_status = Case.objects.get(pk=case.case_id).status

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "reschedule",
                "psi_response_message": "Solicitação aceita.",
                "psi_appointment_date": "",
                "psi_appointment_time": "",
                "psi_appointment_location": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "data" in content.lower() or "horário" in content.lower()

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == original_status

    def test_submit_without_valid_lock_blocked(self, client, case_factory, advance_to) -> None:
        """Submit sem lock válido é bloqueado como no fluxo normal."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        original_status = Case.objects.get(pk=case.case_id).status

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "cancel",
                "psi_response_message": "Cancelado.",
                "lock_token": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "reserva" in content.lower() or "Token" in content

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == original_status

    def test_submit_with_invalid_lock_token_blocked(self, client, case_factory, advance_to) -> None:
        """Submit com token inválido não altera case."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        original_status = Case.objects.get(pk=case.case_id).status

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "cancel",
                "psi_response_message": "Cancelado.",
                "lock_token": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "reserva" in content.lower() or "inválido" in content.lower()

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == original_status

    def test_normal_flow_preserved(self, client, case_factory, advance_to) -> None:
        """Fluxo normal de WAIT_APPT sem intercorrência continua confirmando/negando."""
        scheduler_user = _login_as(client, "scheduler")
        nir_user = User.objects.create_user(username="nir@normflow.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = advance_to(case_factory(nir_user), CaseStatus.WAIT_APPT)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.structured_data = {"patient": {"name": "Normal Flow", "age": 30, "sex": "M"}}
        case.save(update_fields=["doctor_decision", "doctor_admission_flow", "structured_data"])

        token = _claim_lock(case.case_id, scheduler_user)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-15",
                "appointment_time": "14:30",
                "notes": "Normal confirmation.",
                "reason": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"


# ══════════════════════════════════════════════════════════════════════════
# TESTS DE EVENTOS — auditoria
# ══════════════════════════════════════════════════════════════════════════


class TestPostScheduleIssueEvents:
    """Evento POST_ACCEPTANCE_ISSUE_RESPONDED registrado (Slice 002)."""

    def test_respond_creates_event(self, client, case_factory, advance_to) -> None:
        """Ação do agendador registra POST_ACCEPTANCE_ISSUE_RESPONDED com payload."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        token = _claim_lock(case.case_id, scheduler_user)

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "cancel",
                "psi_response_message": "Cancelado por óbito.",
                "lock_token": token,
            },
        )

        event = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_RESPONDED",
        ).first()
        assert event is not None
        assert event.payload.get("action") == "cancel"
        assert event.payload.get("response_message") == "Cancelado por óbito."

    def test_reschedule_creates_event(self, client, case_factory, advance_to) -> None:
        """Reschedule registra evento POST_ACCEPTANCE_ISSUE_RESPONDED."""
        scheduler_user = _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        token = _claim_lock(case.case_id, scheduler_user)

        client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "psi_action": "reschedule",
                "psi_response_message": "Reagendado.",
                "psi_appointment_date": "2026-07-20",
                "psi_appointment_time": "09:00",
                "psi_appointment_location": "Sala 2",
                "lock_token": token,
            },
        )

        event = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_RESPONDED",
        ).first()
        assert event is not None
        assert event.payload.get("action") == "reschedule"


# ══════════════════════════════════════════════════════════════════════════
# TESTS DE ROLE GUARD
# ══════════════════════════════════════════════════════════════════════════


class TestPostScheduleIssueRoleGuard:
    """Submit de intercorrência respeita role_guard 'scheduler'."""

    def test_submit_blocks_nir(self, client, case_factory, advance_to) -> None:
        """NIR não pode POST submit de intercorrência."""
        _login_as(client, "nir")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"psi_action": "cancel", "psi_response_message": "X"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_submit_blocks_doctor(self, client, case_factory, advance_to) -> None:
        """Doctor não pode POST submit de intercorrência."""
        _login_as(client, "doctor")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"psi_action": "cancel", "psi_response_message": "X"},
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_confirm_blocks_nir(self, client, case_factory, advance_to) -> None:
        """NIR não pode acessar confirm de intercorrência."""
        _login_as(client, "nir")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 302
        assert response.url == "/"


class TestPostScheduleIssueFormDuplicateFields:
    """RED: formulário lida com múltiplos psi_response_message (browser envia 3 valores)."""

    def test_clean_picks_first_non_empty_from_multiple_values(self) -> None:
        """Quando browser envia 3 psi_response_message (um por seção),
        o clean() deve usar o primeiro valor não-vazio, não o último (Django default)."""
        from django.http import QueryDict

        from apps.scheduler.forms import PostScheduleIssueForm

        # Simula o que o browser envia: cancel/deny preenchido, reschedule vazio, maintain vazio
        qd = QueryDict(mutable=True)
        qd.setlist("psi_action", ["cancel"])
        qd.setlist("psi_response_message", ["Paciente faleceu.", "", ""])

        form = PostScheduleIssueForm(qd)
        assert form.is_valid(), f"Form should be valid but got errors: {form.errors}"
        assert form.cleaned_data["psi_response_message"] == "Paciente faleceu.", (
            f"Expected 'Paciente faleceu.' but got '{form.cleaned_data['psi_response_message']}'"
        )

    def test_clean_uses_first_non_empty_when_first_is_empty(self) -> None:
        """Se 1º valor é vazio (ex: usuário preencheu reschedule section),
        o clean() deve usar o primeiro valor não-vazio encontrado."""
        from django.http import QueryDict

        from apps.scheduler.forms import PostScheduleIssueForm

        # Simula usuário que selecionou reschedule e preencheu o campo lá
        qd = QueryDict(mutable=True)
        qd.setlist("psi_action", ["reschedule"])
        qd.setlist("psi_response_message", ["", "Reagendado conforme solicitado.", ""])
        qd.setlist("psi_appointment_date", ["2026-07-15"])
        qd.setlist("psi_appointment_time", ["10:30"])

        form = PostScheduleIssueForm(qd)
        assert form.is_valid(), f"Form should be valid but got errors: {form.errors}"
        assert form.cleaned_data["psi_response_message"] == "Reagendado conforme solicitado."

    def test_clean_fails_when_all_messages_empty_and_action_requires_message(self) -> None:
        """Se todos os valores de psi_response_message são vazios e a ação exige
        mensagem (cancel/deny), o formulário deve ser inválido."""
        from django.http import QueryDict

        from apps.scheduler.forms import PostScheduleIssueForm

        qd = QueryDict(mutable=True)
        qd.setlist("psi_action", ["deny"])
        qd.setlist("psi_response_message", ["", "", ""])

        form = PostScheduleIssueForm(qd)
        assert not form.is_valid()
        assert "psi_response_message" in form.errors
        assert "obrigatória" in str(form.errors["psi_response_message"]).lower()

    def test_clean_passes_when_all_empty_but_action_optional(self) -> None:
        """Para ação 'maintain', mensagem é opcional. Todos vazios deve ser válido."""
        from django.http import QueryDict

        from apps.scheduler.forms import PostScheduleIssueForm

        qd = QueryDict(mutable=True)
        qd.setlist("psi_action", ["maintain"])
        qd.setlist("psi_response_message", ["", "", ""])

        form = PostScheduleIssueForm(qd)
        assert form.is_valid(), f"Form should be valid but got errors: {form.errors}"


class TestPostScheduleIssueExternalJS:
    """RED: template carrega JS externo e não contém inline."""

    def test_template_loads_external_js(self, client, case_factory, advance_to) -> None:
        """GET da tela de intercorrência inclui script externo."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Verifica que o JS externo de toggle é carregado
        assert (
            'src="/static/js/post_schedule_issue_form.js"' in content
            or 'src="{% static &quot;js/post_schedule_issue_form.js&quot;' in content
            or "js/post_schedule_issue_form.js" in content
        )

    def test_template_does_not_contain_inline_js(self, client, case_factory, advance_to) -> None:
        """HTML renderizado não contém o bloco JS inline antigo."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Verifica que o código inline específico NÃO está presente
        assert "const actionRadios = document.querySelectorAll" not in content
        assert "toggleSections" not in content

    def test_template_still_loads_work_lock_js(self, client, case_factory, advance_to) -> None:
        """A tela continua carregando work_lock.js."""
        _login_as(client, "scheduler")
        case = _create_case_with_opened_issue(case_factory, advance_to, None)

        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "work_lock.js" in content

    def test_js_file_contains_submit_handler_to_disable_hidden_fields(self) -> None:
        """O JS externo contém o handler de submit que desabilita textareas ocultos
        para evitar que múltiplos valores de psi_response_message sejam enviados."""
        from pathlib import Path

        js_path = Path("static/js/post_schedule_issue_form.js")
        content = js_path.read_text()

        # Verifica o handler de submit
        assert "addEventListener('submit'" in content
        # Verifica que desabilita textareas ocultos
        assert "textarea.disabled = true" in content
        # Verifica que busca a seção pai para checar visibilidade
        assert "closest('.psi-section')" in content
        # Verifica que checa display:none
        assert "style.display === 'none'" in content
