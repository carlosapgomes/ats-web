"""Testes do Slice 004 — NIR confirma ciência da intercorrência respondida.

Estes testes verificam que:
- NIR vê resposta do agendador no detalhe do caso.
- Confirmação de recebimento encerra intercorrência e retorna a CLEANED.
- Evento de ciência é registrado.
- Fluxo normal de confirmação permanece coerente.
- Lock NIR é respeitado.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import (
    open_post_schedule_issue,
    respond_post_schedule_issue,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client, username: str = "nir@test.com"):
    """Cria usuário NIR, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    """Cria usuário doctor, faz login e retorna o cliente + user."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _build_cleaned_confirmed(case_factory, advance_to, user) -> Case:
    """Cria um Case CLEANED elegível para intercorrência."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.agency_record_number = "OCOR-ISSUE-001"
    case.appointment_at = "2027-01-15T10:00:00+00:00"
    case.appointment_location = "Hospital Central"
    case.appointment_instructions = "Jejum de 8h"
    case.structured_data = {
        "patient": {"name": "João Silva", "age": 45, "sex": "M"},
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
            "appointment_instructions",
            "structured_data",
        ]
    )
    return Case.objects.get(pk=case.pk)


def _create_responded_issue(
    case_factory,
    advance_to,
    user,
    scheduler_user=None,
    action: str = "cancel",
    response_message: str = "Agendamento cancelado conforme solicitação.",
) -> Case:
    """Cria um caso CLEANED elegível, abre e responde intercorrência."""
    case = _build_cleaned_confirmed(case_factory, advance_to, user)
    case = open_post_schedule_issue(
        case=case, user=user, reason="transport_unavailable", message="Transporte não disponível esta semana."
    )
    case = respond_post_schedule_issue(
        case=case,
        user=scheduler_user or user,
        action=action,
        response_message=response_message,
    )
    return Case.objects.get(pk=case.pk)


def _get_lock_token(client, case) -> str:
    """Abre detail para adquirir lock e extrai o token."""
    response = client.get(reverse("intake:case_detail", args=[case.case_id]))
    assert response.status_code == 200
    case_obj = Case.objects.get(pk=case.case_id)
    assert case_obj.lock_token is not None
    return str(case_obj.lock_token)


# ═══════════════════════════════════════════════════════════════════════════
# RED — detalhe com intercorrência respondida
# ═══════════════════════════════════════════════════════════════════════════


class TestDetailShowsRespondedIssue:
    """NIR vê resposta do agendador no detalhe do caso."""

    def test_detail_responded_shows_intercurrence_block(self, client, case_factory, advance_to) -> None:
        """Caso WAIT_R1_CLEANUP_THUMBS com issue responded mostra bloco de intercorrência."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência Pós-Aceitação" in content
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.post_schedule_issue_status == "responded"

    def test_detail_shows_nir_original_reason(self, client, case_factory, advance_to) -> None:
        """Bloco mostra motivo original do NIR e resposta do agendador."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Transporte não disponível" in content
        assert "Agendamento cancelado conforme solicitação" in content
        assert "Transporte indisponível" in content or "transport" in content.lower()

    def test_detail_reschedule_shows_new_date_location(self, client, case_factory, advance_to) -> None:
        """Para reschedule, mostra nova data/local."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        scheduler_user = user
        new_date = (datetime.now(ZoneInfo("UTC")) + timedelta(days=15)).isoformat()
        case = open_post_schedule_issue(
            case=case, user=user, reason="reschedule_request", message="Solicitamos nova data."
        )
        case = respond_post_schedule_issue(
            case=case,
            user=scheduler_user,
            action="reschedule",
            appointment_at=new_date,
            appointment_location="Hospital Novo Endereço",
            appointment_instructions="Chegar 30min antes",
            response_message="Reagendado a pedido da unidade.",
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reagendado" in content or "Hospital Novo Endereço" in content
        assert "Chegar 30min antes" in content

    def test_detail_cancel_shows_cancelled_status(self, client, case_factory, advance_to) -> None:
        """Para cancel, mostra que agendamento foi cancelado."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Cancelado" in content

    def test_detail_maintain_shows_preserved_appointment(self, client, case_factory, advance_to) -> None:
        """Para maintain, mostra que agendamento foi mantido."""
        client, user = _nir_client(client)
        case = _create_responded_issue(
            case_factory, advance_to, user, action="maintain", response_message="Agendamento mantido."
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Mantido" in content

    def test_detail_deny_shows_denied_request(self, client, case_factory, advance_to) -> None:
        """Para deny, mostra que solicitação foi negada."""
        client, user = _nir_client(client)
        case = _create_responded_issue(
            case_factory, advance_to, user, action="deny", response_message="Sem vagas disponíveis."
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Negada" in content or "Sem vagas disponíveis" in content


# ═══════════════════════════════════════════════════════════════════════════
# RED — confirmação de recebimento com intercorrência
# ═══════════════════════════════════════════════════════════════════════════


class TestConfirmReceiptWithRespondedIssue:
    """Confirmação de recebimento em issue respondida chama acknowledge."""

    def test_confirm_responded_acknowledges_and_cleans(self, client, case_factory, advance_to) -> None:
        """POST confirm_receipt em issue responded chama acknowledge e retorna CLEANED."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")
        token = _get_lock_token(client, case)

        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""

    def test_confirm_creates_acknowledged_event(self, client, case_factory, advance_to) -> None:
        """Evento POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED é criado."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")
        token = _get_lock_token(client, case)

        client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )

        event = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED",
        ).first()
        assert event is not None

    def test_confirm_clears_issue_fields(self, client, case_factory, advance_to) -> None:
        """Após confirmação, post_schedule_issue_status fica vazio."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")
        token = _get_lock_token(client, case)

        client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )

        case = Case.objects.get(pk=case.case_id)
        assert case.post_schedule_issue_status == ""
        assert case.post_schedule_issue_reason == ""
        assert case.post_schedule_issue_message == ""
        assert case.post_schedule_issue_response_action == ""
        assert case.post_schedule_issue_opened_by is None
        assert case.post_schedule_issue_responded_by is None


# ═══════════════════════════════════════════════════════════════════════════
# RED — lock permanece obrigatório
# ═══════════════════════════════════════════════════════════════════════════


class TestAcknowledgeRequiresLock:
    """POST sem lock NIR válido continua bloqueado."""

    def test_confirm_without_token_blocked(self, client, case_factory, advance_to) -> None:
        """POST sem lock_token não faz acknowledge."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        # Acquire lock first (as happens when viewing detail)
        _get_lock_token(client, case)

        # Post without token
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {},
        )
        assert response.status_code in (200, 302)

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.post_schedule_issue_status == "responded"

    def test_confirm_with_invalid_token_blocked(self, client, case_factory, advance_to) -> None:
        """POST com token inválido não faz acknowledge."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        _get_lock_token(client, case)

        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code in (200, 302)

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_confirm_by_other_user_blocked(self, client, case_factory, advance_to) -> None:
        """POST por outro NIR sem lock válido é bloqueado."""
        client_a, nir_a = _nir_client(client, "nir-a@test.com")
        case = _create_responded_issue(case_factory, advance_to, nir_a, action="cancel")
        token = _get_lock_token(client_a, case)

        client_b, nir_b = _nir_client(client, "nir-b@test.com")
        response = client_b.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code in (200, 302)

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS


# ═══════════════════════════════════════════════════════════════════════════
# RED — fluxo normal permanece coerente
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalConfirmStillWorks:
    """Confirmação normal de casos sem intercorrência continua funcionando."""

    def _create_receipt_case(self, case_factory, advance_to, user) -> Case:
        """Cria caso WAIT_R1_CLEANUP_THUMBS com doctor_denied (sem issue)."""
        case = case_factory(user)
        case = advance_to(case, CaseStatus.WAIT_R1_CLEANUP_THUMBS)
        return Case.objects.get(pk=case.pk)

    def test_normal_confirm_still_works(self, client, case_factory, advance_to) -> None:
        """Caso sem intercorrência continua confirmando normalmente."""
        client, user = _nir_client(client)
        case = self._create_receipt_case(case_factory, advance_to, user)
        token = _get_lock_token(client, case)

        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.CLEANED
        # Não deve ter post_schedule_issue fields
        assert case.post_schedule_issue_status == ""

    def test_normal_confirm_creates_cleanup_events(self, client, case_factory, advance_to) -> None:
        """Caso sem intercorrência cria CLEANUP_TRIGGERED e CLEANUP_COMPLETED."""
        client, user = _nir_client(client)
        case = self._create_receipt_case(case_factory, advance_to, user)
        token = _get_lock_token(client, case)

        client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )

        assert CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="CLEANUP_COMPLETED").exists()

    def test_responded_confirm_does_not_create_new_cleanup_events(self, client, case_factory, advance_to) -> None:
        """Caso com intercorrência NÃO cria NOVOS eventos de cleanup (usa acknowledge direto)."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        # Contar eventos de cleanup antes da confirmação
        cleanup_before = CaseEvent.objects.filter(
            case=case,
            event_type__in=["CLEANUP_TRIGGERED", "CLEANUP_COMPLETED"],
        ).count()

        token = _get_lock_token(client, case)
        client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )

        # Deve criar ACKNOWLEDGED (novo tipo pós-aceitação)
        assert CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").exists()

        # NÃO deve criar novos eventos de cleanup (contagem permanece igual)
        cleanup_after = CaseEvent.objects.filter(
            case=case,
            event_type__in=["CLEANUP_TRIGGERED", "CLEANUP_COMPLETED"],
        ).count()
        assert cleanup_after == cleanup_before


# ═══════════════════════════════════════════════════════════════════════════
# RED — bloqueio de nova intercorrência enquanto responded
# ═══════════════════════════════════════════════════════════════════════════


class TestBlockNewIssueWhileResponded:
    """Enquanto issue está responded, não permite abrir nova intercorrência."""

    def test_responded_blocks_new_issue_in_search(self, client, case_factory, advance_to) -> None:
        """Caso com issue responded aparece na busca mas sem botão abrir."""
        client, user = _nir_client(client)
        _create_responded_issue(case_factory, advance_to, user, action="cancel")

        # Busca pelo número da ocorrência
        response = client.get(
            reverse("intake:closed_cases_search"),
            {"q": "OCOR-ISSUE-001"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        # O caso aparece na busca (está WAIT_R1_CLEANUP_THUMBS com issue)
        assert "OCOR-ISSUE-001" in content or "Reg." in content or "João" in content
        # Mas o botão de abrir não aparece
        assert "Registrar intercorrência" not in content

    def test_responded_blocks_issue_form_page(self, client, case_factory, advance_to) -> None:
        """Acessar formulário de abertura para caso com issue responded mostra bloqueio."""
        client, user = _nir_client(client)
        case = _create_responded_issue(case_factory, advance_to, user, action="cancel")

        response = client.get(
            reverse("intake:post_schedule_issue_open", kwargs={"case_id": case.case_id}),
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência indisponível" in content or "ativa" in content.lower()
