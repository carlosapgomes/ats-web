"""Testes verticais CHD para intercorrência operacional (Slice 003 Cobertura).

T3: card completo com delimitação estrutural, sentinela, CTA único
T4: badge versus _scheduler_queue_context com valores exatos
T5: histórico diário de ciências (ACK hoje/ontem)
     + asserts exatos preservados (F3, F4)
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


# ── Fixtures ────────────────────────────────────────────────────────────────


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


# ── Helpers ─────────────────────────────────────────────────────────────────


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


def _create_sentinel_case(nir_user):
    """Caso CLEANED operacional com structured_data completo (T3 sentinela)."""
    from apps.cases.services import open_post_acceptance_issue

    case = Case.objects.create(
        created_by=nir_user,
        status=CaseStatus.CLEANED,
        doctor_decision="accept",
        doctor_admission_flow="pre_icu",
        agency_record_number="REG-SENTINELA-003",
        structured_data={
            "patient": {"name": "Paciente Sentinela"},
            "origin_context": {
                "hospital": "Hospital Origem Sentinela",
                "unit": "Unidade Sentinela",
            },
        },
    )
    case = Case.objects.get(pk=case.pk)
    return open_post_acceptance_issue(
        case=case,
        user=nir_user,
        reason="accepted_elsewhere",
        message="Transferido para Hospital Destino",
        context="operational_notice",
    )


def _extract_card_html(content, case_id):
    """Extrai HTML do card delimitado entre data attr e comentário final (T3)."""
    import re

    pattern = rf'data-operational-issue-card="{case_id}"(.*?)<!-- end-operational-issue-card:{case_id} -->'
    match = re.search(pattern, content, re.DOTALL)
    assert match is not None, f"Card delimitado nao encontrado para {case_id}"
    return match.group(0)


def _queue_context(scheduler_user):
    """Helper: executa _scheduler_queue_context e queue_counts (T4)."""
    from apps.scheduler.views import _scheduler_queue_context

    rf = RequestFactory()
    request = rf.get("/")
    request.user = scheduler_user
    request.session = {"active_role": "scheduler"}

    qc = queue_counts(request)
    ctx = _scheduler_queue_context(user=scheduler_user)
    return qc, ctx


# ── T3: Card CHD com delimitação estrutural ─────────────────────────────────


class TestChdOperationalIssueCard:
    """T3: Card completo, estruturalmente delimitado, CTA único."""

    def test_card_has_data_attribute(self, scheduler_client, nir_user):
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert f'data-operational-issue-card="{case.case_id}"' in content

    def test_card_has_end_delimiter(self, scheduler_client, nir_user):
        """T3: template inclui comentario delimitador final."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert f"<!-- end-operational-issue-card:{case.case_id} -->" in content

    def test_card_sentinel_full_content(self, scheduler_client, nir_user):
        """T3: card sentinela com todos os dados visíveis estruturalmente."""
        case = _create_sentinel_case(nir_user)
        case = Case.objects.get(pk=case.pk)

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        card_html = _extract_card_html(content, str(case.case_id))

        # Dados sentinela obrigatórios — asserts exatos sem fallback
        assert "Paciente Sentinela" in card_html
        assert "REG-SENTINELA-003" in card_html
        assert "Hospital Origem Sentinela" in card_html
        assert "Unidade Sentinela" in card_html
        # Label do fluxo pre_icu
        assert "Vinda prévia para UTI" in card_html
        # Motivo traduzido
        assert "unidade mais próxima" in card_html
        # Mensagem
        assert "Transferido para Hospital Destino" in card_html
        # Ator (username exato)
        assert nir_user.username in card_html
        # Horário formatado (dd/mm/YYYY HH:MM)
        import re

        assert re.search(r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}", card_html) is not None

    def test_card_has_exactly_one_confirmar_ciencia_cta(self, scheduler_client, nir_user):
        """T3: Dentro do card, 'Confirmar ciência' aparece exatamente 1 vez."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        card_html = _extract_card_html(content, str(case.case_id))

        assert card_html.count("Confirmar ciência") == 1

    def test_card_no_scheduling_actions(self, scheduler_client, nir_user):
        """T3: Card operacional NÃO contém verbos/inputs de agenda."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        card_html = _extract_card_html(content, str(case.case_id))

        forbidden = [
            "Agendar",
            "Cancelar agendamento",
            "Reagendar",
            "Manter agendamento",
            "Negar solicitação",
            "appointment_at",
            "appointment_location",
        ]
        for term in forbidden:
            assert term not in card_html, f"'{term}' nao deveria aparecer no card operacional"

    def test_no_card_when_no_issue(self, scheduler_client, nir_user):
        """T3: Sem issue operacional, nenhum data-operational-issue-card aparece."""
        # Apenas cria caso sem issue
        Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
        )
        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert "data-operational-issue-card" not in content
        assert "apenas para ciência" not in content.lower()


# ── Copia F3 existente (endpoint) ───────────────────────────────────────────


class TestChdOperationalAckEndpoint:
    """Endpoint de ACK operacional via HTTP com todos os 6 campos."""

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


# ── T4: Badge versus _scheduler_queue_context ───────────────────────────────


class TestBadgeVsQueueContext:
    """T4: Comparação badge/fila com _scheduler_queue_context e HTML."""

    def test_single_issue_all_counts_exact(self, scheduler_client, scheduler_user, nir_user):
        """T4: Apenas 1 issue operacional → badge=1, operational_issue_count=1,
        immediate_notice_count=0, pending_count=0, total_notice_count=1,
        HTML contém exatamente 1 card."""
        _create_case_with_operational_issue(nir_user, flow="immediate")
        qc, ctx = _queue_context(scheduler_user)

        assert qc["queue_count"] == 1
        assert ctx["operational_issue_count"] == 1
        assert ctx["immediate_notice_count"] == 0
        assert ctx["pending_count"] == 0
        assert ctx["total_notice_count"] == 1

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert content.count("data-operational-issue-card") == 1

    def test_notice_plus_issue_deduplication_exact(self, scheduler_client, scheduler_user, nir_user):
        """T4: notice inicial ADMISSION_FLOW_OPERATIONAL_NOTICE + issue ativa →
        notice count=0, issue count=1, badge=1, total=1, 1 card."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        CaseEvent.objects.create(
            case=case,
            actor=nir_user,
            actor_type="human",
            event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        qc, ctx = _queue_context(scheduler_user)

        assert qc["queue_count"] == 1
        assert ctx["immediate_notice_count"] == 0
        assert ctx["operational_issue_count"] == 1
        assert ctx["total_notice_count"] == 1

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert content.count("data-operational-issue-card") == 1

    def test_after_ack_all_zero(self, scheduler_client, scheduler_user, nir_user):
        """T4: Após ACK → notice=0, issue=0, badge=0, total=0, zero cards."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        qc, ctx = _queue_context(scheduler_user)

        assert qc["queue_count"] == 0
        assert ctx["immediate_notice_count"] == 0
        assert ctx["operational_issue_count"] == 0
        assert ctx["total_notice_count"] == 0

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert "data-operational-issue-card" not in content

    def test_wait_appt_plus_issue_combo(self, scheduler_client, scheduler_user, nir_user):
        """T4: WAIT_APPT + issue operacional →
        pending=1, issue=1, total=2, queue_count=2."""
        _create_case_with_operational_issue(nir_user, flow="immediate")
        Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_APPT)
        qc, ctx = _queue_context(scheduler_user)

        assert qc["queue_count"] == 2
        assert ctx["pending_count"] == 1
        assert ctx["operational_issue_count"] == 1
        assert ctx["total_notice_count"] == 2


# ── T5: Histórico diário de ciências ────────────────────────────────────────


class TestDailyAcknowledgmentHistory:
    """T5: acknowledged_notice_count com ACK hoje/ontem + novo ciclo.

    H1: durabilidade da issue aberta ontem.
    """

    def test_ack_today_shows_in_history(self, scheduler_client, scheduler_user, nir_user):
        """T5.1: ACK operacional hoje → acknowledged_notice_count == 1."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        _qc, ctx = _queue_context(scheduler_user)

        assert ctx["acknowledged_notice_count"] == 1
        assert any(str(c["case_id"]) == str(case.case_id) for c in ctx["acknowledged_notice_cases"])

    def test_ack_yesterday_not_in_today_history(self, scheduler_client, scheduler_user, nir_user):
        """T5.2: ACK movido para ontem → acknowledged_notice_count == 0."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        # Move timestamp do ACK para ontem
        yesterday = timezone.now() - timedelta(days=1, hours=12)
        CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").update(timestamp=yesterday)

        _qc, ctx = _queue_context(scheduler_user)

        assert ctx["acknowledged_notice_count"] == 0

    def test_historical_ack_does_not_block_new_cycle(self, scheduler_client, scheduler_user, nir_user):
        """T5.3: ACK histórico de ciclo anterior não impede novo ciclo ativo."""
        from apps.cases.services import open_post_acceptance_issue

        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        # ACK
        scheduler_client.post(
            reverse("scheduler:operational_issue_ack", args=[case.case_id]),
            follow=True,
        )
        # Move ACK para ontem
        yesterday = timezone.now() - timedelta(days=1, hours=12)
        CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").update(timestamp=yesterday)

        # Novo ciclo
        case = Case.objects.get(pk=case.pk)
        case = open_post_acceptance_issue(
            case=case,
            user=nir_user,
            reason="origin_cancelled",
            message="Nova intercorrência",
            context="operational_notice",
        )

        _qc, ctx = _queue_context(scheduler_user)

        # Histórico do dia não contém ACK antigo
        assert ctx["acknowledged_notice_count"] == 0
        # Mas nova issue ativa aparece
        assert ctx["operational_issue_count"] == 1
        assert ctx["total_notice_count"] == 1
        assert any(str(c["case_id"]) == str(case.case_id) for c in ctx["operational_issue_cases"])

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert "data-operational-issue-card" in content

    # ── H1: Durabilidade da issue aberta ontem ──────────────────────────

    def test_issue_opened_yesterday_still_in_queue(self, scheduler_client, scheduler_user, nir_user):
        """H1: Issue aberta há 36h ainda aparece na fila — sem filtro de data."""
        case = _create_case_with_operational_issue(nir_user, flow="immediate")
        # Move abertura para 36 horas atrás
        thirty_six_hours_ago = timezone.now() - timedelta(hours=36)
        Case.objects.filter(pk=case.pk).update(post_schedule_issue_opened_at=thirty_six_hours_ago)

        qc, ctx = _queue_context(scheduler_user)

        assert qc["queue_count"] == 1
        assert ctx["operational_issue_count"] == 1
        assert ctx["immediate_notice_count"] == 0
        assert ctx["pending_count"] == 0
        assert ctx["total_notice_count"] == 1

        response = scheduler_client.get(reverse("scheduler:queue"))
        content = response.content.decode()
        assert content.count("data-operational-issue-card") == 1
