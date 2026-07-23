"""Tests for accounts context processors."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.accounts.context_processors import app_display_name, queue_counts
from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


@pytest.mark.django_db
class TestQueueCounts:
    """Tests for the queue_counts context processor."""

    def test_unauthenticated_returns_empty(self) -> None:
        """Unauthenticated user gets an empty dict."""
        request = HttpRequest()
        request.user = type("AnonymousUser", (), {"is_authenticated": False})()
        result = queue_counts(request)
        assert result == {}

    def test_no_active_role_returns_empty(self, rf: RequestFactory) -> None:
        """Authenticated user with no active_role gets empty dict."""
        user = User.objects.create_user(username="norole@test.com", password="testpass")
        request = rf.get("/")
        request.user = user
        request.session = {}
        result = queue_counts(request)
        assert result == {}

    def test_doctor_returns_wait_doctor_count(self, rf: RequestFactory) -> None:
        """Doctor role returns count of cases in WAIT_DOCTOR."""
        user = User.objects.create_user(username="doctor@test.com", password="testpass")
        # Create some WAIT_DOCTOR cases
        for _ in range(3):
            Case.objects.create(created_by=user, status=CaseStatus.WAIT_DOCTOR)
        # Create a case in another status that should NOT be counted
        Case.objects.create(created_by=user, status=CaseStatus.WAIT_APPT)

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "doctor"}
        result = queue_counts(request)
        assert result == {"queue_count": 3}

    def test_scheduler_returns_wait_appt_count(self, rf: RequestFactory) -> None:
        """Scheduler role returns count of cases in WAIT_APPT."""
        user = User.objects.create_user(username="scheduler@test.com", password="testpass")
        for _ in range(5):
            Case.objects.create(created_by=user, status=CaseStatus.WAIT_APPT)
        # Should NOT count cases in other statuses
        Case.objects.create(created_by=user, status=CaseStatus.WAIT_DOCTOR)

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result == {"queue_count": 5}

    def test_scheduler_counts_unacknowledged_immediate_notice(self, rf: RequestFactory) -> None:
        """Scheduler badge includes immediate admission notices until acknowledged."""
        user = User.objects.create_user(username="scheduler-immediate@test.com", password="testpass")
        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_admission_flow="immediate",
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result == {"queue_count": 1}

    def test_scheduler_ignores_acknowledged_immediate_notice(self, rf: RequestFactory) -> None:
        """Scheduler badge drops immediate notice after operational acknowledgement."""
        user = User.objects.create_user(username="scheduler-immediate-ack@test.com", password="testpass")
        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_admission_flow="immediate",
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=user,
            event_type="SCHEDULER_IMMEDIATE_ACK",
            timestamp=timezone.now(),
        )

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result == {"queue_count": 0}

    def test_scheduler_counts_yesterday_notice(self, rf: RequestFactory) -> None:
        """Scheduler badge inclui notice de ontem sem ACK."""
        user = User.objects.create_user(username="scheduler-yesterday@test.com", password="testpass")
        yesterday = timezone.now() - timedelta(days=1, hours=12)
        case = Case.objects.create(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor_admission_flow="immediate",
        )
        event = CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=user,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
        )
        # Contorna auto_now_add=True no timestamp
        CaseEvent.objects.filter(pk=event.pk).update(timestamp=yesterday)

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result == {"queue_count": 1}

    def test_nir_returns_empty(self, rf: RequestFactory) -> None:
        """NIR role returns empty dict (no queue for this role)."""
        user = User.objects.create_user(username="nir@test.com", password="testpass")
        Case.objects.create(created_by=user, status=CaseStatus.WAIT_DOCTOR)

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "nir"}
        result = queue_counts(request)
        assert result == {}

    def test_manager_returns_empty(self, rf: RequestFactory) -> None:
        """Manager role returns empty dict (no queue for this role)."""
        user = User.objects.create_user(username="manager@test.com", password="testpass")

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "manager"}
        result = queue_counts(request)
        assert result == {}

    def test_admin_returns_empty(self, rf: RequestFactory) -> None:
        """Admin role returns empty dict (no queue for this role)."""
        user = User.objects.create_user(username="admin@test.com", password="testpass")

        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "admin"}
        result = queue_counts(request)
        assert result == {}


@pytest.mark.django_db
class TestQueueCountsTemplateBadge:
    """Tests that the queue_count badge renders correctly in templates."""

    def test_badge_not_shown_in_header_when_queue_count_positive(self, client) -> None:
        """Badge de queue_count NÃO é mais renderizado no header do perfil.

        Slice 001 removeu o badge grudado no nome/avatar. O context processor
        continua existindo (ainda usado por abas/outros contextos), mas o header
        do perfil não exibe mais o número.
        """
        from apps.accounts.models import Role

        user = User.objects.create_user(username="docbadge@test.com", password="testpass")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        # Create a WAIT_DOCTOR case so queue_count > 0
        Case.objects.create(created_by=user, status=CaseStatus.WAIT_DOCTOR)

        # Follow redirect: / → doctor:queue
        response = client.get("/", follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        # O badge do queue_count NÃO deve aparecer no perfil do header
        # Verificamos que o padrão específico do span removido não está presente
        assert 'class="badge bg-danger ms-1">1<' not in content

    def test_badge_hidden_when_queue_count_zero(self, client) -> None:
        """No badge rendered when there are no pending cases."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nobadge@test.com", password="testpass")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        # No WAIT_DOCTOR cases
        response = client.get("/", follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        # The string for badge class should NOT be present
        # (but could appear in other contexts, so check for the pattern)
        # If badge is present with class bg-danger and value 0, it would show "0"
        # The template only renders badge when queue_count > 0
        # So we check that there's no visible "0" badge count
        # Actually the safest: check badge styling is not present
        assert 'class="badge bg-danger ms-1">0<' not in content


class TestAppDisplayName:
    """Tests for the app_display_name context processor."""

    def test_returns_default_display_name_when_not_configured(self, rf: RequestFactory) -> None:
        """Retorna 'Regulação' como default determinístico do ambiente de teste."""
        request = rf.get("/")
        with override_settings(APP_DISPLAY_NAME="Regulação"):
            result = app_display_name(request)
        assert result == {"app_display_name": "Regulação"}

    def test_returns_configured_name(self, rf: RequestFactory) -> None:
        """Retorna o valor configurado em APP_DISPLAY_NAME."""
        request = rf.get("/")
        with override_settings(APP_DISPLAY_NAME="HGS"):
            result = app_display_name(request)
        assert result == {"app_display_name": "HGS"}

    def test_works_with_empty_string(self, rf: RequestFactory) -> None:
        """APP_DISPLAY_NAME vazio retorna string vazia."""
        request = rf.get("/")
        with override_settings(APP_DISPLAY_NAME=""):
            result = app_display_name(request)
        assert result == {"app_display_name": ""}

    def test_available_in_template_context(self, client) -> None:
        """Verifica que app_display_name está disponível no contexto do template."""
        # Testa com a página de login (não requer autenticação)
        with override_settings(APP_DISPLAY_NAME="Hospital Teste"):
            response = client.get("/login/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Hospital Teste" in content
        # Verifica que o nome customizado aparece no header e no h3
        assert '<span class="app-header__title">Hospital Teste</span>' in content
        assert "<title>Hospital Teste" in content

    def test_template_renders_default_when_not_configured(self, client) -> None:
        """Template renderiza 'Regulação' quando APP_DISPLAY_NAME não está configurado."""
        response = client.get("/login/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Regulação" in content
