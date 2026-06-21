"""Services for transactional email flows (Slice 003) and mention/notification services (Slice 001).

Centralized helpers for sending account-related transactional emails
as defined by ADR-0002, and for parsing mention tokens in case communication
messages and creating in-app notifications.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.cases.models import CaseCommunicationMessage


# ── Mention Parser ────────────────────────────────────────────────────────


MENTION_TOKEN_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_\.\-]{2,50})")
"""Regex para capturar tokens de menção no corpo da mensagem.

Não captura @ que já faz parte de outro token (ex: email).
"""

COMMUNICATION_MENTION_ROLES: set[str] = {"nir", "doctor", "scheduler", "manager", "admin"}
"""Papéis reconhecidos como tokens de menção."""


@dataclass(frozen=True)
class MentionParseResult:
    """Resultado do parser de menções."""

    role_tokens: set[str] = field(default_factory=set)
    username_tokens: set[str] = field(default_factory=set)


def parse_mentions(body: str) -> MentionParseResult:
    """Extrai tokens de menção de um corpo de mensagem.

    Tokens de papel (case-insensitive) são normalizados para lowercase.
    Tokens de username: qualquer @token que não seja papel reconhecido.
    Tokens repetidos são deduplicados.

    Args:
        body: O texto da mensagem.

    Returns:
        MentionParseResult com conjuntos de role_tokens e username_tokens.
    """
    matches = MENTION_TOKEN_RE.findall(body)
    if not matches:
        return MentionParseResult()

    role_tokens: set[str] = set()
    username_tokens: set[str] = set()

    for token in matches:
        normalized = token.lower()
        if normalized in COMMUNICATION_MENTION_ROLES:
            role_tokens.add(normalized)
        else:
            username_tokens.add(token)

    return MentionParseResult(role_tokens=role_tokens, username_tokens=username_tokens)


# ── Notification Creation ─────────────────────────────────────────────────


@dataclass(frozen=True)
class NotificationCreationResult:
    """Resultado da criação de notificações para uma mensagem."""

    mentioned_roles: tuple[str, ...] = ()
    mentioned_usernames: tuple[str, ...] = ()
    notification_count: int = 0


def create_case_communication_notifications(*, message: CaseCommunicationMessage) -> NotificationCreationResult:
    """Cria notificações para destinatários mencionados em uma mensagem.

    Regras:
    1. Papéis reconhecidos resolvem usuários ativos com aquele papel.
    2. Usernames resolvem usuários ativos com username correspondente.
    3. Destinatários duplicados (papel + username) recebem 1 notificação.
    4. Autor da mensagem não recebe notificação.
    5. Usuários inativos (is_active=False ou account_status!="active") não recebem.
    6. No máximo uma notificação por destinatário por mensagem (unique constraint).
    7. Mensagem sem menção retorna notification_count=0.

    Args:
        message: A CaseCommunicationMessage recém-criada.

    Returns:
        NotificationCreationResult com resumo das menções e contagem.
    """
    from apps.accounts.models import Role, User, UserNotification

    parsed = parse_mentions(message.body)
    if not parsed.role_tokens and not parsed.username_tokens:
        return NotificationCreationResult()

    # Resolver destinatários por papel
    role_recipient_ids: set[int] = set()
    if parsed.role_tokens:
        role_qs = Role.objects.filter(name__in=parsed.role_tokens)
        role_users = User.objects.filter(
            roles__in=role_qs,
            is_active=True,
            account_status="active",
        ).values_list("id", flat=True)
        role_recipient_ids = set(role_users)

    # Resolver destinatários por username (case-insensitive, conforme D5)
    username_recipient_ids: set[int] = set()
    if parsed.username_tokens:
        username_q = Q()
        for token in parsed.username_tokens:
            username_q |= Q(username__iexact=token)
        username_users = User.objects.filter(
            username_q,
            is_active=True,
            account_status="active",
        ).values_list("id", flat=True)
        username_recipient_ids = set(username_users)

    # Combinar e excluir autor
    all_recipient_ids = (role_recipient_ids | username_recipient_ids) - {message.author_id}

    if not all_recipient_ids:
        return NotificationCreationResult(
            mentioned_roles=tuple(sorted(parsed.role_tokens)),
            mentioned_usernames=tuple(sorted(parsed.username_tokens)),
            notification_count=0,
        )

    # Criar notificações
    now = timezone.now()
    notifications = [
        UserNotification(
            recipient_id=rid,
            case=message.case,
            communication_message=message,
            triggered_by=message.author,
            notification_type="case_communication_mention",
            title="Você foi mencionado em um caso",
            body_preview=message.body[:240],
            created_at=now,
        )
        for rid in sorted(all_recipient_ids)
    ]

    created_count = 0
    if notifications:
        # bulk_create(ignore_conflicts=True) não informa quantas linhas foram efetivamente
        # inseridas (devolve um objeto por item do input). Consultamos o total antes/depois
        # para obter a contagem real de inserções nesta chamada, respeitando o unique
        # constraint que descarta duplicatas silenciosamente.
        existing_before = UserNotification.objects.filter(
            recipient_id__in=all_recipient_ids,
            communication_message=message,
        ).count()
        UserNotification.objects.bulk_create(notifications, ignore_conflicts=True)
        existing_after = UserNotification.objects.filter(
            recipient_id__in=all_recipient_ids,
            communication_message=message,
        ).count()
        created_count = existing_after - existing_before

    return NotificationCreationResult(
        mentioned_roles=tuple(sorted(parsed.role_tokens)),
        mentioned_usernames=tuple(sorted(parsed.username_tokens)),
        notification_count=created_count,
    )


# ── Redirecionamento seguro ao abrir notificação ─────────────────────────


def resolve_notification_redirect_url(*, case: Any, user: Any, active_role: str) -> str:
    """Define a URL de redirecionamento seguro ao abrir uma notificação.

    Baseado no papel ativo e status do caso.

    Args:
        case: O Case vinculado à notificação.
        user: O usuário destinatário.
        active_role: O papel ativo do usuário no momento.

    Returns:
        URL de redirecionamento obtida via ``reverse()`` (sem paths hardcoded).
    """
    from django.urls import reverse

    from apps.cases.models import CaseStatus

    status = case.status

    if active_role == "nir":
        if status != CaseStatus.CLEANED:
            return reverse("intake:case_detail", kwargs={"case_id": case.pk})
        return reverse("intake:home")

    if active_role == "doctor":
        if status == CaseStatus.WAIT_DOCTOR:
            return reverse("doctor:decision", kwargs={"case_id": case.pk})
        # Caso já decidido pelo próprio médico destinatário → detalhe read-only.
        if case.doctor_id is not None and case.doctor_id == user.pk and case.doctor_decision in ("accept", "deny"):
            return reverse("doctor:decided_detail", kwargs={"case_id": case.pk})
        return reverse("doctor:queue")

    if active_role == "scheduler":
        if status == CaseStatus.WAIT_APPT:
            return reverse("scheduler:confirm", kwargs={"case_id": case.pk})
        return reverse("scheduler:queue")

    # manager / admin / fallback
    return reverse("dashboard:index")


# ── Email services (original) ────────────────────────────────────────────


PUBLIC_ROLE_NAMES = {"doctor", "manager", "admin"}
"""Role names that grant access from public URL (outside intranet)."""

INTRANET_ONLY_ROLE_NAMES = {"nir", "scheduler"}
"""Role names that only access from inside intranet."""

# Reusable token generator (same as Django's PasswordResetView)
token_generator = PasswordResetTokenGenerator()


def get_account_action_base_url(user: User) -> str:
    """Select the correct base URL for account action emails based on user roles.

    Rules:
        - Any public role (doctor/manager/admin, including multi-role) -> public URL.
        - Only intranet-only roles (nir/scheduler) -> internal URL.
        - No roles assigned -> public URL (operational safety default).

    Args:
        user: The user to evaluate roles for.

    Returns:
        The base URL (without trailing slash) for building action links.
    """
    user_roles = set(user.roles.values_list("name", flat=True))

    if user_roles & PUBLIC_ROLE_NAMES:
        return settings.PUBLIC_APP_BASE_URL.rstrip("/")
    if user_roles & INTRANET_ONLY_ROLE_NAMES:
        return settings.INTERNAL_APP_BASE_URL.rstrip("/")
    # Edge case: user without roles -> public URL for operational safety.
    return settings.PUBLIC_APP_BASE_URL.rstrip("/")


def send_user_invitation_email(user: User) -> None:
    """Send an invitation email to a newly created user.

    The email contains a link to set/confirm their password using Django's
    native password reset token mechanism. The base URL is selected based
    on the user's roles.

    Args:
        user: The newly created user (must already be persisted with roles).

    Raises:
        Exception: Any exception raised by the email backend during send.
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

    msg = EmailMultiAlternatives(
        subject=subject,
        body=f"Acesse {action_url} para definir sua senha no {settings.APP_DISPLAY_NAME}.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(body, "text/html")
    msg.send(fail_silently=False)
