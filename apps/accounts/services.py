"""Services for transactional email flows (Slice 003).

Centralized helpers for sending account-related transactional emails
as defined by ADR-0002.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

PUBLIC_ROLE_NAMES = {"doctor", "manager", "admin"}
"""Role names that grant access from public URL (outside intranet)."""

INTRANET_ONLY_ROLE_NAMES = {"nir", "scheduler"}
"""Role names that only access from inside intranet."""

# Reusable token generator (same as Django's PasswordResetView)
token_generator = PasswordResetTokenGenerator()


def get_account_action_base_url(user: User) -> str:
    """Select the correct base URL for account action emails based on user roles.

    If the user has ANY public role (doctor, manager, admin), return the
    public base URL. Otherwise (only nir/scheduler or no roles), return the
    internal intranet base URL.

    Args:
        user: The user to evaluate roles for.

    Returns:
        The base URL (without trailing slash) for building action links.
    """
    user_roles = set(user.roles.values_list("name", flat=True))

    if user_roles & PUBLIC_ROLE_NAMES:
        return settings.PUBLIC_APP_BASE_URL.rstrip("/")

    # Edge case: user without roles → use public URL for operational safety
    return settings.INTERNAL_APP_BASE_URL.rstrip("/")


def send_user_invitation_email(user: User) -> None:
    """Send an invitation email to a newly created user.

    The email contains a link to set/confirm their password using Django's
    native password reset token mechanism. The base URL is selected based
    on the user's roles.

    Args:
        user: The newly created user (must already be persisted with roles).

    Raises:
        Exception: Re-raises any email sending exception after logging.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    base_url = get_account_action_base_url(user)

    reset_path = f"/reset/{uid}/{token}/"
    action_url = f"{base_url}{reset_path}"

    subject = render_to_string(
        "accounts/email/user_invitation_subject.txt",
        {"app_display_name": settings.APP_DISPLAY_NAME},
    ).strip()

    body = render_to_string(
        "accounts/email/user_invitation_email.html",
        {
            "user": user,
            "action_url": action_url,
            "app_display_name": settings.APP_DISPLAY_NAME,
            "password_reset_timeout": settings.PASSWORD_RESET_TIMEOUT // 3600,
            "uid": uid,
            "token": token,
        },
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f"Acesse {action_url} para definir sua senha no {settings.APP_DISPLAY_NAME}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(body, "text/html")
        msg.send(fail_silently=False)
    except Exception:
        logger.exception(f"Falha ao enviar email de convite para {user.email}")
        raise
