"""Testes do Slice 006 — NIR: lease para confirmação de recebimento.

NIR adquire lock ao abrir detalhe de caso WAIT_R1_CLEANUP_THUMBS com
context 'nir_receipt'. Confirmação de recebimento exige lock válido.
Lista NIR mostra reserva ativa. Heartbeat/release endpoints protegidos.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import claim_case_lock

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client, username: str = "nir-a@test.com") -> tuple:  # type: ignore[type-arg]
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


def _advance_to_wait_r1_cleanup_thumbs(case: Case) -> Case:
    """Avança um caso via FSM até WAIT_R1_CLEANUP_THUMBS via doctor_deny."""
    case.start_processing()
    case.save()
    case.start_extraction()
    case.save()
    case.extraction_complete(success=True)
    case.save()
    case.llm1_complete(success=True)
    case.save()
    case.llm2_complete(success=True)
    case.save()
    case.ready_for_doctor()
    case.save()
    case.doctor_decide(decision="deny", user=case.created_by)
    case.save()
    case.final_reply_posted(user=case.created_by)
    case.save()
    return Case.objects.get(pk=case.pk)


def _advance_through_cleanup(case: Case) -> Case:
    """Avança um caso WAIT_R1_CLEANUP_THUMBS até CLEANED."""
    case.cleanup_triggered(user=case.created_by)
    case.save()
    case.cleanup_completed(user=case.created_by)
    case.save()
    return Case.objects.get(pk=case.pk)


def _create_wait_receipt_case(created_by) -> Case:
    """Cria e avança um caso até WAIT_R1_CLEANUP_THUMBS."""
    case = Case.objects.create(created_by=created_by)
    return _advance_to_wait_r1_cleanup_thumbs(case)


# ═══════════════════════════════════════════════════════════════════════════
# RED — detalhe/claim
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirReceiptDetailClaim:
    """NIR adquire lock ao abrir detalhe de caso WAIT_R1_CLEANUP_THUMBS."""

    def test_case_detail_creates_lock_for_wait_receipt(self, client) -> None:
        """Abrir detalhe de WAIT_R1_CLEANUP_THUMBS cria lock nir_receipt."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200

        # Verify lock was created
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == user
        assert case.lock_context == "nir_receipt"

    def test_template_contains_hidden_lock_token(self, client) -> None:
        """Template contém hidden lock_token no formulário de confirmação."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Must include work-lock-config with token
        assert "data-lock-token" in content
        assert "data-renew-url" in content
        assert "data-release-url" in content
        # Must inject work_lock.js
        assert "work_lock.js" in content

    def test_template_contains_work_lock_config(self, client) -> None:
        """Template contém configuração do work_lock.js."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Verify data attributes for work_lock config
        assert "data-renew-url" in content
        assert "data-release-url" in content

    def test_second_nir_gets_blocked_from_active_locked_case(self, client) -> None:
        """Segundo NIR abrindo detalhe de caso reservado não recebe formulário ativo."""
        client_a, nir_a = _nir_client(client, "nir-a@test.com")
        case = _create_wait_receipt_case(created_by=nir_a)

        # NIR A opens the detail (acquires lock)
        client_a.get(reverse("intake:case_detail", args=[case.case_id]))

        # NIR B opens the same case
        client_b, nir_b = _nir_client(client, "nir-b@test.com")
        response_b = client_b.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response_b.status_code == 200

        content_b = response_b.content.decode()

        # NIR B should NOT see an active confirm button (locked by other)
        assert "btn-confirm" not in content_b or "disabled" in content_b or "Confirmar Recebimento" not in content_b

    def test_expired_lock_can_be_assumed_by_another_nir(self, client) -> None:
        """Lock expirado pode ser assumido por outro NIR e gera WORK_LOCK_EXPIRED."""
        client_a, nir_a = _nir_client(client, "nir-alpha@test.com")
        nir_a.first_name = "Alpha"
        nir_a.save()

        case = _create_wait_receipt_case(created_by=nir_a)

        # NIR A opens detail (acquires lock)
        claim_case_lock(
            case_id=case.case_id,
            user=nir_a,
            expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            context="nir_receipt",
            role="nir",
            lease_seconds=0,
        )

        # Force expiration
        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        # NIR B opens the case and assumes the expired lock
        client_b, nir_b = _nir_client(client, "nir-beta@test.com")
        nir_b.first_name = "Beta"
        nir_b.save()

        response_b = client_b.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response_b.status_code == 200

        # Verify WORK_LOCK_EXPIRED was created with Alpha's info
        expired_events = CaseEvent.objects.filter(
            case=case,
            event_type="WORK_LOCK_EXPIRED",
        )
        assert expired_events.exists()
        latest_expired = expired_events.latest("timestamp")
        payload = latest_expired.payload
        assert "Alpha" in payload.get("expired_locked_by_display", "")

        # Verify Beta now holds the lock
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == nir_b


# ═══════════════════════════════════════════════════════════════════════════
# RED — confirmação
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirConfirmReceiptWithLock:
    """Confirmação de recebimento exige lock válido."""

    def _get_lock_token(self, client, case) -> str:
        """Helper: open detail to claim lock and extract token."""
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        case = Case.objects.get(pk=case.case_id)
        assert case.lock_token is not None
        return str(case.lock_token)

    def test_confirm_with_valid_token_executes_cleanup(self, client) -> None:
        """POST confirm_receipt com token válido executa cleanup e conclui caso."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        token = self._get_lock_token(client, case)

        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code == 302  # redirects to my_cases

        # Case should now be CLEANED
        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.CLEANED

    def test_confirm_without_token_does_not_change_status(self, client) -> None:
        """POST sem token não altera status do caso."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        self._get_lock_token(client, case)

        # Submit without lock_token
        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {},  # no lock_token
        )
        # Should redirect to case_detail with error (not change status)
        assert response.status_code in (200, 302)

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_confirm_with_invalid_token_does_not_change_status(self, client) -> None:
        """POST com token inválido não altera status."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        self._get_lock_token(client, case)

        response = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code in (200, 302)

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_confirm_by_other_nir_without_lock_fails(self, client) -> None:
        """POST por outro NIR sem lock válido não altera status."""
        client_a, nir_a = _nir_client(client, "nir-a@test.com")
        case = _create_wait_receipt_case(created_by=nir_a)
        self._get_lock_token(client_a, case)

        # NIR B tries to confirm without having the lock
        client_b, nir_b = _nir_client(client, "nir-b@test.com")
        response_b = client_b.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": str(uuid.uuid4())},
        )
        assert response_b.status_code in (200, 302)

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_repeated_post_after_cleaned_does_not_break(self, client) -> None:
        """Repetição de POST após CLEANED não reexecuta transições nem quebra."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        token = self._get_lock_token(client, case)

        # First confirm — succeeds
        client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.CLEANED

        # Second confirm — should not error
        response2 = client.post(
            reverse("intake:confirm_receipt", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response2.status_code in (200, 302)
        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.CLEANED


# ═══════════════════════════════════════════════════════════════════════════
# RED — heartbeat endpoints
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirHeartbeatEndpoints:
    """Renew/release NIR endpoints."""

    def _claim_lock(self, client, case) -> str:
        """Abre detail e retorna o lock_token."""
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        case_obj = Case.objects.get(pk=case.case_id)
        assert case_obj.lock_token is not None
        return str(case_obj.lock_token)

    def test_renew_requires_nir_role(self, client) -> None:
        """Renew exige papel ativo nir."""
        from apps.accounts.models import Role

        # Create a doctor user (not NIR)
        user = User.objects.create_user(username="doc@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        case = _create_wait_receipt_case(created_by=user)
        response = client.post(
            reverse("intake:nir_lock_renew", args=[case.case_id]),
            {"lock_token": str(uuid.uuid4())},
        )
        # Should be blocked by role_required
        assert response.status_code in (302, 403)

    def test_renew_with_valid_token_extends_lock(self, client) -> None:
        """Renew com token válido estende lock."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        token = self._claim_lock(client, case)

        original_locked_until = Case.objects.get(pk=case.case_id).locked_until
        assert original_locked_until is not None

        response = client.post(
            reverse("intake:nir_lock_renew", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        new_locked_until = Case.objects.get(pk=case.case_id).locked_until
        assert new_locked_until is not None
        assert new_locked_until > original_locked_until

    def test_release_with_valid_token_clears_lock(self, client) -> None:
        """Release com token válido limpa lock."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        token = self._claim_lock(client, case)

        response = client.post(
            reverse("intake:nir_lock_release", args=[case.case_id]),
            {"lock_token": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is None

    def test_release_with_invalid_token_does_not_clear_lock(self, client) -> None:
        """Token inválido não limpa lock."""
        client, user = _nir_client(client)
        case = _create_wait_receipt_case(created_by=user)
        self._claim_lock(client, case)

        response = client.post(
            reverse("intake:nir_lock_release", args=[case.case_id]),
            {"lock_token": str(uuid.uuid4())},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is not None


# ═══════════════════════════════════════════════════════════════════════════
# RED — lista
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNirListLockIndicators:
    """Lista NIR mostra quando resultado pendente está reservado."""

    def test_pending_result_locked_by_other_shows_who(self, client) -> None:
        """Resultado pendente reservado por outro NIR mostra quem reservou."""
        client_a, nir_a = _nir_client(client, "nir-lock-a@test.com")
        nir_a.first_name = "LockA"
        nir_a.save()

        case = _create_wait_receipt_case(created_by=nir_a)

        # NIR A opens detail (lock acquired)
        client_a.get(reverse("intake:case_detail", args=[case.case_id]))

        # NIR B views my_cases
        client_b, nir_b = _nir_client(client, "nir-lock-b@test.com")
        response_b = client_b.get(reverse("intake:my_cases"))
        assert response_b.status_code == 200
        content_b = response_b.content.decode()

        # Should show that it's locked by someone
        assert "LockA" in content_b or "Reservado" in content_b

    def test_pending_result_locked_by_current_user_allows_continue(self, client) -> None:
        """Resultado pendente reservado pelo próprio NIR permite continuar."""
        client_a, nir_a = _nir_client(client, "nir-lock-c@test.com")
        nir_a.first_name = "LockC"
        nir_a.save()

        case = _create_wait_receipt_case(created_by=nir_a)

        # NIR A opens detail (lock acquired)
        client_a.get(reverse("intake:case_detail", args=[case.case_id]))

        # NIR A views my_cases
        response = client_a.get(reverse("intake:my_cases"))
        assert response.status_code == 200
        content = response.content.decode()

        # Should show that it's locked by current user
        assert "LockC" in content or "você" in content or "Voce" in content
