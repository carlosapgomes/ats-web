"""Tests for email services and URL selection (Slice 003).

TDD: These tests must fail before implementation and pass after.
"""

from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail

from apps.accounts.models import Role

User = get_user_model()


def _get_full_message_text(email: Any) -> str:
    """Extrai todo o texto do email (plain text + HTML alternatives)."""
    full_text: str = email.body
    for alt_content, alt_type in getattr(email, "alternatives", []):
        if alt_type == "text/html":
            full_text += "\n" + alt_content
    return full_text


@pytest.mark.django_db
class TestGetAccountActionBaseUrl:
    """R2: Helper centralizado de URL — seleção por papéis."""

    def test_get_account_action_base_url_uses_internal_for_nir_only(self, client) -> None:
        """Usuário apenas nir → URL interna."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="nir-only", password="pass123!")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        url = get_account_action_base_url(user)
        assert url == settings.INTERNAL_APP_BASE_URL

    def test_get_account_action_base_url_uses_internal_for_scheduler_only(self, client) -> None:
        """Usuário apenas scheduler → URL interna."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="sched-only", password="pass123!")
        role, _ = Role.objects.get_or_create(name="scheduler")
        user.roles.add(role)
        url = get_account_action_base_url(user)
        assert url == settings.INTERNAL_APP_BASE_URL

    def test_get_account_action_base_url_uses_public_for_doctor(self, client) -> None:
        """Usuário doctor → URL pública."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="doc-only", password="pass123!")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        url = get_account_action_base_url(user)
        assert url == settings.PUBLIC_APP_BASE_URL

    def test_get_account_action_base_url_uses_public_for_manager(self, client) -> None:
        """Usuário manager → URL pública."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="mgr-only", password="pass123!")
        role, _ = Role.objects.get_or_create(name="manager")
        user.roles.add(role)
        url = get_account_action_base_url(user)
        assert url == settings.PUBLIC_APP_BASE_URL

    def test_get_account_action_base_url_uses_public_for_admin(self, client) -> None:
        """Usuário admin → URL pública."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="admin-only", password="pass123!")
        role, _ = Role.objects.get_or_create(name="admin")
        user.roles.add(role)
        url = get_account_action_base_url(user)
        assert url == settings.PUBLIC_APP_BASE_URL

    def test_get_account_action_base_url_uses_public_for_nir_plus_manager(self, client) -> None:
        """Usuário multi-role nir + manager → URL pública (manager é público)."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="nir-mgr", password="pass123!")
        for role_name in ("nir", "manager"):
            role, _ = Role.objects.get_or_create(name=role_name)
            user.roles.add(role)
        url = get_account_action_base_url(user)
        assert url == settings.PUBLIC_APP_BASE_URL


@pytest.mark.django_db
class TestSendUserInvitationEmail:
    """R3: Serviço de email de cadastro."""

    def test_send_user_invitation_email_uses_expected_base_url_and_token(self, client) -> None:
        """Email contém link com base correta e uid/token."""
        from apps.accounts.services import send_user_invitation_email

        user = User.objects.create_user(
            username="invitedoc",
            email="invitedoc@test.com",
            password="TempPass123!",
        )
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)

        send_user_invitation_email(user)

        # Email foi enviado
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert "invitedoc@test.com" in email.to

        # Texto completo (plain + HTML) contém URL pública (doctor)
        full_text = _get_full_message_text(email)
        assert settings.PUBLIC_APP_BASE_URL in full_text

        # Texto contém path de reset
        assert "/reset/" in full_text

        # Assunto deve mencionar cadastro/convite
        subject = email.subject.lower()
        assert "cadastro" in subject or "convite" in subject or "conta" in subject or "acesso" in subject

    def test_send_user_invitation_email_internal_for_nir(self, client) -> None:
        """Usuário nir recebe link com URL interna."""
        from apps.accounts.services import send_user_invitation_email

        user = User.objects.create_user(
            username="nir-invite",
            email="nir-invite@test.com",
            password="TempPass123!",
        )
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)

        send_user_invitation_email(user)

        assert len(mail.outbox) == 1
        full_text = _get_full_message_text(mail.outbox[0])
        assert settings.INTERNAL_APP_BASE_URL in full_text
        assert "/reset/" in full_text

    def test_send_user_invitation_email_does_not_include_temporary_password(self, client) -> None:
        """Email não contém a senha temporária."""
        from apps.accounts.services import send_user_invitation_email

        user = User.objects.create_user(
            username="nopassemail",
            email="nopassemail@test.com",
            password="SuperSecret123!",
        )
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)

        send_user_invitation_email(user)

        full_text = _get_full_message_text(mail.outbox[0])
        assert "SuperSecret123!" not in full_text
        assert "TempPass123!" not in full_text
        assert "senha temporária" not in full_text.lower() or "senha provisória" not in full_text.lower()


@pytest.mark.django_db
class TestSendUserInvitationEdgeCases:
    """Edge cases do serviço de email."""

    def test_get_account_action_base_url_no_roles_uses_public(self, client) -> None:
        """Usuário sem papéis → URL pública (fallback)."""
        from apps.accounts.services import get_account_action_base_url

        user = User.objects.create_user(username="noroles", password="pass123!")
        url = get_account_action_base_url(user)
        assert url == settings.PUBLIC_APP_BASE_URL
