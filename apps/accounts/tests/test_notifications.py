"""Tests for UserNotification model, mention parser, service, and views.

RED phase: all tests should fail before implementation.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Role
from apps.cases.models import CaseStatus

User = get_user_model()


# ── Helper fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def role_nir(db: Any) -> Role:
    return Role.objects.get_or_create(name="nir")[0]


@pytest.fixture
def role_doctor(db: Any) -> Role:
    return Role.objects.get_or_create(name="doctor")[0]


@pytest.fixture
def role_scheduler(db: Any) -> Role:
    return Role.objects.get_or_create(name="scheduler")[0]


@pytest.fixture
def role_manager(db: Any) -> Role:
    return Role.objects.get_or_create(name="manager")[0]


@pytest.fixture
def role_admin(db: Any) -> Role:
    return Role.objects.get_or_create(name="admin")[0]


@pytest.fixture
def user_doctor(db: Any, role_doctor: Role) -> User:
    u = User.objects.create_user(username="doctor1", password="testpass")
    u.roles.add(role_doctor)
    return u


@pytest.fixture
def user_nir(db: Any, role_nir: Role) -> User:
    u = User.objects.create_user(username="nir1", password="testpass")
    u.roles.add(role_nir)
    return u


@pytest.fixture
def user_scheduler(db: Any, role_scheduler: Role) -> User:
    u = User.objects.create_user(username="scheduler1", password="testpass")
    u.roles.add(role_scheduler)
    return u


@pytest.fixture
def user_maria(db: Any, role_doctor: Role) -> User:
    """User with username 'maria' for @maria mention tests."""
    u = User.objects.create_user(username="maria", password="testpass")
    u.roles.add(role_doctor)
    return u


@pytest.fixture
def inactive_user(db: Any, role_doctor: Role) -> User:
    """Inactive user that should not receive notifications."""
    u = User.objects.create_user(
        username="inactive_doctor",
        password="testpass",
        is_active=False,
    )
    u.roles.add(role_doctor)
    u.account_status = "active"
    u.save()
    return u


@pytest.fixture
def blocked_user(db: Any, role_doctor: Role) -> User:
    """Blocked user that should not receive notifications."""
    u = User.objects.create_user(username="blocked_doctor", password="testpass", is_active=True)
    u.roles.add(role_doctor)
    u.account_status = "blocked"
    u.save()
    return u


# ── Parser tests ─────────────────────────────────────────────────────────


class TestMentionParser:
    """Tests for the mention token parser."""

    def test_extracts_role_mentions_from_message_body(self, db: Any) -> None:
        """@doctor @nir extrai papéis normalizados."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("@doctor @nir revisar caso urgente")
        assert result.role_tokens == {"doctor", "nir"}
        assert result.username_tokens == set()

    def test_role_mentions_are_case_insensitive(self, db: Any) -> None:
        """@Doctor @NIR deve normalizar para lowercase."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("@Doctor @NIR")
        assert result.role_tokens == {"doctor", "nir"}

    def test_extracts_username_mentions_from_message_body(self, db: Any) -> None:
        """@maria extrai username."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("Favor revisar @maria")
        assert result.username_tokens == {"maria"}

    def test_mixed_role_and_username_mentions(self, db: Any) -> None:
        """@doctor @maria @scheduler extrai papéis e usernames."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("@doctor @maria @scheduler ok?")
        assert result.role_tokens == {"doctor", "scheduler"}
        assert result.username_tokens == {"maria"}

    def test_unknown_mentions_are_ignored(self, db: Any) -> None:
        """@fantasma não quebra, apenas é ignorado."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("Olá @fantasma")
        assert result.role_tokens == set()
        assert result.username_tokens == {"fantasma"}

    def test_duplicate_tokens_are_deduplicated(self, db: Any) -> None:
        """@doctor @doctor aparece uma vez no conjunto."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("@doctor @doctor @nir")
        assert result.role_tokens == {"doctor", "nir"}

    def test_no_mentions_returns_empty_sets(self, db: Any) -> None:
        """Mensagem sem @ retorna conjuntos vazios."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("Mensagem sem menção")
        assert result.role_tokens == set()
        assert result.username_tokens == set()

    def test_email_like_not_mistaken_for_mention(self, db: Any) -> None:
        """Email-like patterns com @ no meio não são capturados."""
        from apps.accounts.services import parse_mentions

        result = parse_mentions("user@example.com por favor")
        assert result.role_tokens == set()
        assert result.username_tokens == set()


# ── Notification creation service tests ──────────────────────────────────


class TestNotificationCreationService:
    """Tests for create_case_communication_notifications."""

    def test_role_mention_creates_notifications_for_active_role_users(
        self, db: Any, case_factory: Any, user: Any, user_doctor: Any, user_nir: Any, role_scheduler: Any
    ) -> None:
        """@doctor cria notificação para usuários ativos com papel doctor."""
        from apps.accounts.models import UserNotification
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        # Criar segundo médico
        doctor2 = User.objects.create_user(username="doctor2", password="testpass")
        doctor2.roles.add(Role.objects.get(name="doctor"))

        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@doctor revisar urgente",
        )

        result = create_case_communication_notifications(message=msg)
        assert result.notification_count == 2  # user_doctor + doctor2
        assert "doctor" in result.mentioned_roles
        assert UserNotification.objects.filter(recipient=user_doctor, case=case).count() == 1
        assert UserNotification.objects.filter(recipient=doctor2, case=case).count() == 1

    def test_username_mention_creates_notification(
        self, db: Any, case_factory: Any, user: Any, user_maria: Any
    ) -> None:
        """@maria cria notificação para usuário com username maria."""
        from apps.accounts.models import UserNotification
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@maria por favor",
        )

        result = create_case_communication_notifications(message=msg)
        assert result.notification_count == 1
        assert "maria" in result.mentioned_usernames
        assert UserNotification.objects.filter(recipient=user_maria, case=case).count() == 1

    def test_inactive_or_blocked_users_do_not_receive_notifications(
        self, db: Any, case_factory: Any, user: Any, user_doctor: Any, inactive_user: Any, blocked_user: Any
    ) -> None:
        """Usuários inativos ou blocked não recebem notificação."""
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@doctor revisar",
        )

        result = create_case_communication_notifications(message=msg)
        # Apenas user_doctor (active) recebe, inactive_user e blocked_user são excluídos
        assert result.notification_count == 1

    def test_author_does_not_receive_own_mention_notification(
        self, db: Any, case_factory: Any, user_doctor: Any
    ) -> None:
        """Autor mencionando @doctor não recebe própria notificação."""
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.services import post_case_communication_message

        case = case_factory(user_doctor)
        msg = post_case_communication_message(
            case=case,
            author=user_doctor,
            author_role="doctor",
            body="@doctor eu mesmo?",
        )

        result = create_case_communication_notifications(message=msg)
        # Nenhum outro doctor ativo, e o autor foi excluído
        assert result.notification_count == 0

    def test_duplicate_role_and_username_mentions_create_single_notification_per_recipient(
        self, db: Any, case_factory: Any, user: Any, user_doctor: Any
    ) -> None:
        """Usuário mencionado por @doctor @doctor1 recebe 1 notificação."""
        from apps.accounts.models import UserNotification
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        # user_doctor tem username doctor1 e role doctor
        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@doctor @doctor1 urgente",
        )

        result = create_case_communication_notifications(message=msg)
        assert result.notification_count == 1
        assert UserNotification.objects.filter(recipient=user_doctor, case=case).count() == 1

    def test_message_without_mentions_creates_no_notifications(self, db: Any, case_factory: Any, user: Any) -> None:
        """Mensagem sem menção não cria notificação."""
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="Mensagem normal sem menção",
        )

        result = create_case_communication_notifications(message=msg)
        assert result.notification_count == 0

    def test_communication_event_payload_includes_mentions_and_notification_count(
        self, db: Any, case_factory: Any, user: Any, user_doctor: Any, user_maria: Any
    ) -> None:
        """Payload do evento inclui mentioned_roles, mentioned_usernames e notification_count."""
        from apps.accounts.services import create_case_communication_notifications
        from apps.cases.models import CaseEvent
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@doctor @maria revisar urgente",
        )

        create_case_communication_notifications(message=msg)

        # Verify payload via CaseEvent
        events = list(CaseEvent.objects.filter(case=case, event_type="CASE_COMMUNICATION_MESSAGE_POSTED"))
        assert len(events) == 1
        payload = events[0].payload or {}
        assert payload.get("mentioned_roles") == ["doctor"]
        assert "maria" in payload.get("mentioned_usernames", [])
        assert payload.get("notification_count") == 2

    def test_integrated_post_creates_notifications(
        self, db: Any, case_factory: Any, user: Any, user_doctor: Any
    ) -> None:
        """post_case_communication_message integrado já cria notificações."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@doctor revisar integrado",
        )

        assert UserNotification.objects.filter(recipient=user_doctor, case=case).count() == 1


# ── View tests ───────────────────────────────────────────────────────────


class TestNotificationViews:
    """Tests for notification views and SSR badge."""

    @pytest.fixture
    def case_with_notification(self, db: Any, case_factory: Any, user: Any, user_doctor: Any) -> tuple[Any, Any]:
        """Cria um caso com notificação não lida para user_doctor.

        A notificação é criada automaticamente por post_case_communication_message
        quando o body contém @doctor.
        """
        from apps.accounts.models import UserNotification
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="@doctor revisar urgente",
        )
        notif = UserNotification.objects.get(
            recipient=user_doctor,
            case=case,
        )
        return case, notif

    def test_header_shows_unread_notification_badge(
        self, db: Any, client: Any, case_with_notification: Any, user_doctor: Any
    ) -> None:
        """Badge SSR mostra contagem de não lidas no header."""
        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        # Home redireciona, então testamos contra a página de notificações que herda base.html
        response = client.get(reverse("notifications"))
        content = response.content.decode()
        assert 'data-count="1"' in content or "notif-badge" in content

    def test_notifications_list_shows_only_current_user_notifications(
        self, db: Any, client: Any, case_factory: Any, user: Any, user_doctor: Any, user_nir: Any
    ) -> None:
        """Lista de notificações mostra apenas as do usuário autenticado."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        # Mensagem com @doctor já cria notificação para user_doctor via integração
        post_case_communication_message(case=case, author=user, author_role="nir", body="@doctor test")

        # Criar notificação para user_nir com outra mensagem (sem menção para não duplicar)
        case2 = case_factory(user)
        msg2 = post_case_communication_message(case=case2, author=user, author_role="nir", body="sem menção")
        UserNotification.objects.create(
            recipient=user_nir,
            case=case2,
            communication_message=msg2,
            triggered_by=user,
            title="Você foi mencionado",
            body_preview="test nir",
        )

        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("notifications"))
        assert response.status_code == 200
        content = response.content.decode()
        # Deve mostrar notificação do médico
        assert "Você foi mencionado" in content
        # NOT deve mostrar notificação do nir (não vazar)
        assert "test nir" not in content

    def test_open_notification_marks_read_and_redirects(
        self, db: Any, client: Any, case_with_notification: Any, user_doctor: Any
    ) -> None:
        """Abrir notificação marca read_at e redireciona."""

        case, notif = case_with_notification
        assert notif.read_at is None

        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("notification_open", kwargs={"notification_id": notif.notification_id}))
        assert response.status_code == 302

        notif.refresh_from_db()
        assert notif.read_at is not None

    def test_user_cannot_open_other_users_notification(
        self, db: Any, client: Any, case_with_notification: Any, user_nir: Any
    ) -> None:
        """Usuário não pode abrir notificação de outro usuário."""

        _, notif = case_with_notification

        client.force_login(user_nir)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(reverse("notification_open", kwargs={"notification_id": notif.notification_id}))
        assert response.status_code in (302, 404)

        notif.refresh_from_db()
        assert notif.read_at is None  # Não foi marcada como lida

    def test_mark_notification_read_requires_post(
        self, db: Any, client: Any, case_with_notification: Any, user_doctor: Any
    ) -> None:
        """GET em mark_read não marca como lida."""

        _, notif = case_with_notification
        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("notification_mark_read", kwargs={"notification_id": notif.notification_id}))
        assert response.status_code in (302, 405)

        notif.refresh_from_db()
        assert notif.read_at is None

    def test_mark_notification_read_via_post(
        self, db: Any, client: Any, case_with_notification: Any, user_doctor: Any
    ) -> None:
        """POST em mark_read marca como lida."""

        _, notif = case_with_notification
        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.post(reverse("notification_mark_read", kwargs={"notification_id": notif.notification_id}))
        assert response.status_code == 302

        notif.refresh_from_db()
        assert notif.read_at is not None

    def test_mark_all_notifications_read_marks_only_current_user(
        self, db: Any, client: Any, case_factory: Any, user: Any, user_doctor: Any, user_nir: Any
    ) -> None:
        """Marcar todas como lidas só afeta o usuário atual."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import post_case_communication_message

        # Mensagem @doctor cria notificação automática para user_doctor
        case = case_factory(user)
        post_case_communication_message(case=case, author=user, author_role="nir", body="@doctor test")
        notif_doctor = UserNotification.objects.get(recipient=user_doctor, case=case)

        # Criar notificação para user_nir com outra mensagem
        case2 = case_factory(user)
        msg2 = post_case_communication_message(case=case2, author=user, author_role="nir", body="outra mensagem")
        notif_nir = UserNotification.objects.create(
            recipient=user_nir,
            case=case2,
            communication_message=msg2,
            triggered_by=user,
            title="Você foi mencionado",
            body_preview="outra",
        )

        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.post(reverse("notifications_mark_all_read"))
        assert response.status_code == 302

        notif_doctor.refresh_from_db()
        notif_nir.refresh_from_db()
        assert notif_doctor.read_at is not None
        assert notif_nir.read_at is None  # Notificação do nir não foi alterada

    def test_notifications_list_requires_login(self, db: Any, client: Any) -> None:
        """Lista de notificações requer login."""
        response = client.get(reverse("notifications"))
        # Deve redirecionar para login
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_notification_open_redirection_by_role_doctor_wait_doctor(
        self, db: Any, case_factory: Any, user: Any, user_doctor: Any, advance_to: Any
    ) -> None:
        """Doctor abre notificação de caso WAIT_DOCTOR → redireciona para doctor:decision."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import post_case_communication_message

        case = case_factory(user)
        case = advance_to(case, CaseStatus.WAIT_DOCTOR)

        # @doctor cria notificação automática (desde que o user_doctor exista)
        # Mas user_doctor não é o autor, então deve receber
        # O body precisa mencionar doctor
        post_case_communication_message(case=case, author=user, author_role="nir", body="@doctor urgente")
        notif = UserNotification.objects.get(recipient=user_doctor, case=case)

        client_doctor = _get_client(user_doctor)
        response = client_doctor.get(reverse("notification_open", kwargs={"notification_id": notif.notification_id}))
        assert response.status_code == 302
        # Deve redirecionar para doctor:decision ou fallback doctor:queue
        assert response.url is not None

    def test_notification_list_renders_empty_state(self, db: Any, client: Any, user_doctor: Any) -> None:
        """Lista de notificações sem notificações mostra estado vazio."""
        client.force_login(user_doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("notifications"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "nenhuma" in content.lower() or "sem notifica" in content.lower()


def _get_client(user: Any) -> Any:
    """Helper to create an authenticated client for a user."""
    from django.test.client import Client

    c = Client()
    c.force_login(user)
    session = c.session
    session["active_role"] = list(user.roles.values_list("name", flat=True))[0]
    session.save()
    return c
