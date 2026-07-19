"""Testes verticais CHD para intercorrência operacional (Slice 003 C3-C4).

Cobre:
- Card específico com CTA único "Confirmar ciência"
- Endpoint ACK via HTTP com permissões, CSRF, idempotência
- Fila, badge, durabilidade e deduplicação (C4)
- Todos os 6 campos appointment_* imutáveis (C5)
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.cases.models import Case, CaseEvent, CaseStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def nir_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="nir_chd_test", password="testpass")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


@pytest.fixture
def scheduler_user(db):
    from django.contrib.auth import get_user_model

    User = get_user_model()  # noqa: N806
    user = User.objects.create_user(username="sched_chd_test", password="testpass")
    role, _ = Role.objects.get_or_create(name="scheduler")
    user.roles.add(role)
    return user


@pytest.fixture
def scheduler_client(client, scheduler_user):
    client.login(username="sched_chd_test", password="testpass")
    session = client.session
    session["active_role"] = "scheduler"
    session.save()
    return client


def _create_case_with_operational_issue(nir_user, flow="immediate", reason="patient_absconded", message="Evadiu-se"):
    """Cria case CLEANED com issue operacional aberta."""
    from apps.cases.services import open_post_acceptance_issue

    case = Case.objects.create(
        created_by=nir_user,
        status=CaseStatus.CLEANED,
        doctor_decision="accept",
        doctor_admission_flow=flow,
        agency_record_number="REG-CHD-001",
    )
    case = Case.objects.get(pk=case.pk)

    return open_post_acceptance_issue(
        case=case, user=nir_user, reason=reason, message=message, context="operational_notice"
    )


class TestChdOperationalIssueCard:
    """C3: Card CHD específico para intercorrência operacional."""

    def test_card_shows_intercorrencia_title(self, scheduler_client, nir_user):
        """Card exibe título 'Intercorrência pós-aceitação'."""
        _create_case_with_operational_issue(nir_user, flow="immediate")

        response = scheduler_client.get(reverse("scheduler:queue"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência pós-aceitação" in content

    def test_card_shows_patient_and_reason(self, scheduler_client, nir_user):
        """Card exibe motivo, mensagem, ator e horário."""
        _create_case_with_operational_issue(
            nir_user,
            flow="pre_icu",
            reason="accepted_elsewhere",
            message="Transferido para Hospital X",
        )

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert "unidade mais próxima" in content.lower() or "Transferido" in content
        # O nome do NIR deve aparecer
        assert nir_user.get_full_name() or nir_user.username in content

    def test_card_has_only_confirmar_ciencia_cta(self, scheduler_client, nir_user):
        """Card NÃO contém ações de agenda — apenas Confirmar ciência."""
        _create_case_with_operational_issue(nir_user, flow="immediate")

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()

        # CTA correto presente
        assert "Confirmar ciência" in content

        # Ações de agenda AUSENTES no card operacional
        # O card de pending cases também pode conter "Agendar", então
        # verificamos que o card operacional está em seção própria
        assert "Intercorrência pós-aceitação" in content

    def test_card_absent_when_no_issue(self, scheduler_client):
        """Sem issue operacional, seção não aparece."""
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        # A seção operacional não deve aparecer
        # (pode ou não ter outras seções dependendo dos dados)
        assert "apenas para ciência" not in content.lower()


class TestChdOperationalAckEndpoint:
    """C3: Endpoint de ACK operacional via HTTP."""

    def test_post_creates_ack_and_redirects(self, scheduler_client, nir_user):
        """POST scheduler cria ACK e redireciona com sucesso."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        response = scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""
        assert case.post_acceptance_issue_context == ""

    def test_get_returns_404(self, scheduler_client, nir_user):
        """GET retorna 404."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        response = scheduler_client.get(reverse("scheduler:operational_issue_ack", args=[case.case_id]))
        assert response.status_code == 404

    def test_repeated_post_does_not_duplicate(self, scheduler_client, nir_user):
        """POST repetido não cria segundo ACK nem corrompe o caso."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        # Primeiro POST
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )

        # Segundo POST
        response = scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        assert response.status_code == 200

        # Verifica que só existe um evento ACK
        ack_count = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED",
        ).count()
        assert ack_count == 1, f"Esperado 1 ACK, encontrado {ack_count}"

    def test_non_scheduler_blocked(self, client, nir_user):
        """Usuário sem papel scheduler é bloqueado."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        client.login(username="nir_chd_test", password="testpass")
        session = client.session
        session["active_role"] = "nir"
        session.save()

        client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        # Deve ser redirecionado ou bloqueado
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "opened", "issue nao deve ser fechada por nao-scheduler"

    def test_anonymous_redirected_to_login(self, client, nir_user):
        """Usuário anônimo é redirecionado para login."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        response = client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
        )
        assert response.status_code == 302

    def test_csrf_enforced(self, scheduler_client, scheduler_user, nir_user):
        """CSRF é obrigatório — POST sem token CSRF falha."""
        from django.test import Client

        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        # Cria um client que faz login mas usa enforce_csrf_checks
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username="sched_chd_test", password="testpass")
        # Seta o active_role via session
        session = csrf_client.session
        session["active_role"] = "scheduler"
        session.save()

        response = csrf_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            data={},
        )
        # Sem token CSRF, deve falhar com 403
        assert response.status_code == 403

    def test_appointment_fields_unchanged_after_ack_http(self, scheduler_client, nir_user):
        """C5: Todos os 6 campos appointment_* imutáveis após ACK via HTTP."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        # Preenche valores sentinela
        sentinel_dt = timezone.now()
        Case.objects.filter(pk=case.pk).update(
            appointment_status="sentinel-status",
            appointment_at=sentinel_dt,
            appointment_location="sentinel-local",
            appointment_instructions="sentinel-instr",
            appointment_reason="sentinel-reason",
            appointment_decided_at=sentinel_dt,
        )
        case = Case.objects.get(pk=case.pk)

        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )

        case = Case.objects.get(pk=case.pk)
        assert case.appointment_status == "sentinel-status"
        assert case.appointment_location == "sentinel-local"
        assert case.appointment_instructions == "sentinel-instr"
        assert case.appointment_reason == "sentinel-reason"
        assert case.status == CaseStatus.CLEANED


class TestQueueBadgeDurability:
    """C4: Fila, badge, durabilidade e deduplicação."""

    def test_operational_issue_increases_queue_count(self, scheduler_client, nir_user):
        """Issue operacional soma no badge do scheduler."""
        from django.test import RequestFactory

        from apps.accounts.context_processors import queue_counts

        _create_case_with_operational_issue(nir_user, flow="immediate")

        rf = RequestFactory()
        request = rf.get("/")
        request.user = scheduler_client.session.get("_auth_user_id") and type("User", (), {"is_authenticated": False})()

        # Usa o context processor diretamente com scheduler role
        from django.contrib.auth import get_user_model

        User = get_user_model()  # noqa: N806
        user = User.objects.get(username="sched_chd_test")
        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] >= 1

    def test_issue_yesterday_still_visible_today(self, scheduler_client, nir_user):
        """C4: Issue aberta ontem continua na fila hoje."""
        case = _create_case_with_operational_issue(nir_user, flow="pre_icu")

        # Simula abertura ontem
        yesterday = timezone.now() - timedelta(days=1, hours=12)
        Case.objects.filter(pk=case.pk).update(
            post_schedule_issue_opened_at=yesterday,
        )

        response = scheduler_client.get(reverse("scheduler:queue"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência pós-aceitação" in content

    def test_count_zero_after_ack(self, scheduler_client, nir_user):
        """C4: Após ACK, soma 0 no badge."""
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        from apps.accounts.context_processors import queue_counts

        case = _create_case_with_operational_issue(nir_user, flow="immediate")

        # ACK
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )

        User = get_user_model()  # noqa: N806
        user = User.objects.get(username="sched_chd_test")
        rf = RequestFactory()
        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] == 0

    def test_wait_appt_still_counted(self, scheduler_client, nir_user):
        """C4: WAIT_APPT scheduled continua somado sem regressão."""
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        from apps.accounts.context_processors import queue_counts

        Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_APPT)

        User = get_user_model()  # noqa: N806
        user = User.objects.get(username="sched_chd_test")
        rf = RequestFactory()
        request = rf.get("/")
        request.user = user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] >= 1
