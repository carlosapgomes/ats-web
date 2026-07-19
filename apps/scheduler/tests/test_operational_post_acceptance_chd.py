"""Testes verticais CHD para intercorrência operacional (Slice 003 F3-F4).

Asserts exatos: card escopado, CTA único, contagens de badge/fila, 6 campos.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.context_processors import queue_counts
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
    """F3: Card CHD escopado com data attribute e CTA único."""

    def test_card_has_data_attribute(self, scheduler_client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert f'data-operational-issue-card="{case.case_id}"' in content

    def test_card_shows_sentinel_data(self, scheduler_client, nir_user):
        """F3: Card exibe dados sentinela exatos."""
        case = _create_case_with_operational_issue(
            nir_user,
            flow="pre_icu",
            reason="accepted_elsewhere",
            message="Transferido para Hospital X",
        )
        case = Case.objects.get(pk=case.pk)

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert "Intercorrência pós-aceitação" in content
        assert "unidade mais próxima" in content.lower()
        assert "Transferido para Hospital X" in content
        assert nir_user.get_full_name() or nir_user.username in content

    def test_card_has_only_confirmar_ciencia_cta(self, scheduler_client, nir_user):
        """F3: Dentro do card escopado, apenas 'Confirmar ciência'."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()

        # Isola o HTML do card operacional
        marker = f'data-operational-issue-card="{case.case_id}"'
        assert marker in content
        card_start = content.index(marker)
        # Pega ~2500 caracteres a partir do início do card
        card_html = content[card_start : card_start + 2500]

        # CTA único presente
        assert "Confirmar ciência" in card_html

        # Ações de agenda AUSENTES dentro do card
        assert "Agendar" not in card_html
        assert "Cancelar agendamento" not in card_html
        assert "Reagendar" not in card_html
        assert "Manter agendamento" not in card_html
        assert "Negar solicitação" not in card_html
        assert "appointment_at" not in card_html
        assert "appointment_location" not in card_html


class TestChdOperationalAckEndpoint:
    """F3: Endpoint de ACK operacional via HTTP com todos os 6 campos."""

    def test_post_creates_ack_and_redirects(self, scheduler_client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        assert response.status_code == 200
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == ""

    def test_get_returns_404(self, scheduler_client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:operational_issue_ack", args=[case.case_id]))
        assert response.status_code == 404

    def test_repeated_post_does_not_duplicate(self, scheduler_client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        ack_count = CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").count()
        assert ack_count == 1

    def test_non_scheduler_blocked(self, client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        client.login(username="nir_chd_test", password="testpass")
        session = client.session
        session["active_role"] = "nir"
        session.save()
        client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        case = Case.objects.get(pk=case.pk)
        assert case.post_schedule_issue_status == "opened"

    def test_anonymous_redirected_to_login(self, client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = client.post(reverse("scheduler:operational_issue_ack", args=[case.case_id]))
        assert response.status_code == 302

    def test_csrf_enforced(self, scheduler_user, nir_user):
        from django.test import Client

        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username="sched_chd_test", password="testpass")
        session = csrf_client.session
        session["active_role"] = "scheduler"
        session.save()
        response = csrf_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            data={},
        )
        assert response.status_code == 403

    def test_all_six_appointment_fields_unchanged_after_ack_http(self, scheduler_client, nir_user):
        """F3: Todos os 6 campos appointment_* imutáveis após ACK via HTTP."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
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

        snap_before = {
            "appointment_status": case.appointment_status,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
            "appointment_reason": case.appointment_reason,
            "appointment_decided_at": case.appointment_decided_at,
        }

        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )

        case = Case.objects.get(pk=case.pk)
        snap_after = {
            "appointment_status": case.appointment_status,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
            "appointment_reason": case.appointment_reason,
            "appointment_decided_at": case.appointment_decided_at,
        }
        assert snap_after == snap_before, f"Campos mudaram: before={snap_before}, after={snap_after}"
        assert case.status == CaseStatus.CLEANED


class TestQueueBadgeExact:
    """F4: Badge=fila com contagens exatas."""

    def test_issue_only_counts_one(self, scheduler_client, scheduler_user, nir_user):
        """F4: Apenas uma issue operacional → queue_count == 1."""
        _create_case_with_operational_issue(nir_user, flow="immediate")
        rf = RequestFactory()
        request = rf.get("/")
        request.user = scheduler_user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] == 1

    def test_notice_plus_issue_counts_exactly_one(self, scheduler_client, scheduler_user, nir_user):
        """F4: notice inicial real + issue ativa → count == 1 (deduplicação)."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        # Adiciona notice inicial real além da issue
        CaseEvent.objects.create(
            case=case,
            actor=nir_user,
            actor_type="human",
            event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        rf = RequestFactory()
        request = rf.get("/")
        request.user = scheduler_user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] == 1, f"Esperado 1, obtido {result}"

    def test_after_ack_counts_zero(self, scheduler_client, scheduler_user, nir_user):
        """F4: Após ACK → queue_count == 0."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        rf = RequestFactory()
        request = rf.get("/")
        request.user = scheduler_user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] == 0, f"Esperado 0, obtido {result}"

    def test_wait_appt_plus_issue_counts_exactly_two(self, scheduler_client, scheduler_user, nir_user):
        """F4: WAIT_APPT + issue operacional → total == 2."""
        _create_case_with_operational_issue(nir_user, flow="immediate")
        Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_APPT)
        rf = RequestFactory()
        request = rf.get("/")
        request.user = scheduler_user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] == 2, f"Esperado 2, obtido {result}"

    def test_issue_yesterday_still_visible_today(self, scheduler_client, scheduler_user, nir_user):
        """F4: Issue aberta ontem → count == 1 hoje."""
        case = _create_case_with_operational_issue(nir_user, flow="pre_icu")
        yesterday = timezone.now() - timedelta(days=1, hours=12)
        Case.objects.filter(pk=case.pk).update(post_schedule_issue_opened_at=yesterday)
        rf = RequestFactory()
        request = rf.get("/")
        request.user = scheduler_user
        request.session = {"active_role": "scheduler"}
        result = queue_counts(request)
        assert result["queue_count"] == 1, f"Esperado 1, obtido {result}"
