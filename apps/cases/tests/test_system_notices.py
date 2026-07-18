"""Tests for system communication notices from CaseEvent (Slice 001).

RED phase: all tests should fail before implementation.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.cases.models import CaseEvent

User = get_user_model()


# ── Model Tests ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_case_communication_message_supports_system_message_without_author(case_factory):
    """Cria mensagem sistêmica com author=None."""
    from apps.cases.models import CaseCommunicationMessage

    case = case_factory(User.objects.create_user(username="creator"))
    msg = CaseCommunicationMessage.objects.create(
        case=case,
        author=None,
        author_role="",
        body="Mensagem do sistema.",
        message_type="system",
        system_event_type="CASE_ATTACHMENT_SUPPRESSED",
    )
    assert msg.message_id is not None
    assert msg.author is None
    assert msg.author_role == ""
    assert msg.message_type == "system"
    assert msg.system_event_type == "CASE_ATTACHMENT_SUPPRESSED"


@pytest.mark.django_db
def test_manual_communication_message_still_requires_author_via_service(case_factory, user):
    """Serviço manual continua validando author/role."""
    from apps.cases.models import CaseCommunicationMessage
    from apps.cases.services import (
        post_case_communication_message,
    )

    case = case_factory(user)

    # Criar diretamente sem author no model deve falhar para message_type="user"
    msg = CaseCommunicationMessage(
        case=case,
        author=None,
        author_role="nir",
        body="Mensagem sem autor.",
        message_type="user",
    )
    with pytest.raises(ValidationError, match="exigem author"):
        msg.full_clean()

    # Mensagem manual normal ainda funciona
    msg = post_case_communication_message(
        case=case,
        author=user,
        author_role="nir",
        body="Mensagem manual normal.",
    )
    assert msg.message_type == "user"
    assert msg.author == user
    assert msg.source_event is None
    assert msg.system_event_type == ""


# ── System Service Tests ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_supported_attachment_suppressed_event_creates_system_notice(case_factory):
    """CASE_ATTACHMENT_SUPPRESSED gera CaseCommunicationMessage sistêmica."""
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPRESSED",
        actor=creator,
        actor_type="human",
        payload={
            "original_filename": "exame-antigo.pdf",
            "reason": "Enviado no caso errado",
        },
    )

    msg = create_system_communication_notice_for_event(event)
    assert msg is not None
    assert msg.message_type == "system"
    assert msg.author is None
    assert msg.source_event == event
    assert msg.system_event_type == "CASE_ATTACHMENT_SUPPRESSED"
    assert "exame-antigo.pdf" in msg.body
    assert "Enviado no caso errado" in msg.body


@pytest.mark.django_db
def test_supported_supplemental_attachment_event_creates_system_notice(case_factory):
    """CASE_ATTACHMENT_SUPPLEMENT_ADDED gera CaseCommunicationMessage sistêmica."""
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPLEMENT_ADDED",
        actor=creator,
        actor_type="human",
        payload={
            "original_filename": "laudo-cardio.pdf",
            "note": "Complemento recebido da origem",
        },
    )

    msg = create_system_communication_notice_for_event(event)
    assert msg is not None
    assert msg.message_type == "system"
    assert msg.source_event == event
    assert "laudo-cardio.pdf" in msg.body
    assert "Complemento recebido da origem" in msg.body


@pytest.mark.django_db
def test_correction_created_event_creates_system_notice(case_factory):
    """CASE_CORRECTION_CREATED gera CaseCommunicationMessage sistêmica."""
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_CORRECTION_CREATED",
        actor=creator,
        actor_type="human",
        payload={
            "original_case_id": str(uuid.uuid4()),
            "correction_reason": "PDF incompleto",
        },
    )

    msg = create_system_communication_notice_for_event(event)
    assert msg is not None
    assert msg.message_type == "system"
    assert msg.source_event == event
    assert "PDF incompleto" in msg.body


@pytest.mark.django_db
def test_marked_superseded_event_creates_system_notice(case_factory):
    """CASE_MARKED_SUPERSEDED gera CaseCommunicationMessage sistêmica."""
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_MARKED_SUPERSEDED",
        actor=creator,
        actor_type="human",
        payload={
            "corrected_case_id": str(uuid.uuid4()),
            "correction_reason": "Anexo incorreto no envio anterior",
        },
    )

    msg = create_system_communication_notice_for_event(event)
    assert msg is not None
    assert msg.message_type == "system"
    assert msg.source_event == event
    assert "Anexo incorreto" in msg.body


@pytest.mark.django_db
def test_unsupported_event_does_not_create_system_notice(case_factory):
    """Evento não suportado não gera mensagem sistêmica."""
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="LLM1_OK",
        actor=creator,
        actor_type="system",
    )

    msg = create_system_communication_notice_for_event(event)
    assert msg is None


@pytest.mark.django_db
def test_case_communication_posted_event_does_not_create_system_notice(case_factory):
    """CASE_COMMUNICATION_MESSAGE_POSTED não gera loop/ruído."""
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_COMMUNICATION_MESSAGE_POSTED",
        actor=creator,
        actor_type="human",
    )

    msg = create_system_communication_notice_for_event(event)
    assert msg is None


@pytest.mark.django_db
def test_system_notice_is_idempotent_per_case_event(case_factory):
    """Chamar serviço duas vezes para mesmo evento não duplica."""
    from apps.cases.models import CaseCommunicationMessage
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPRESSED",
        actor=creator,
        actor_type="human",
        payload={"original_filename": "exame.pdf", "reason": "teste"},
    )

    msg1 = create_system_communication_notice_for_event(event)
    msg2 = create_system_communication_notice_for_event(event)

    assert msg1 is not None
    assert msg2 is not None
    assert msg1.pk == msg2.pk  # mesma mensagem

    count = CaseCommunicationMessage.objects.filter(source_event=event).count()
    assert count == 1


@pytest.mark.django_db
def test_system_notice_does_not_create_user_notification(case_factory):
    """Mensagem sistêmica não cria UserNotification."""
    from apps.cases.models import CaseCommunicationMessage
    from apps.cases.services import create_system_communication_notice_for_event

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPRESSED",
        actor=creator,
        actor_type="human",
        payload={"original_filename": "exame.pdf", "reason": "teste"},
    )

    create_system_communication_notice_for_event(event)

    # Verificar que mensagem foi criada
    msg_count = CaseCommunicationMessage.objects.filter(case=case).count()
    assert msg_count == 1

    # Verificar que nenhuma UserNotification foi criada
    from apps.accounts.models import UserNotification

    notif_count = UserNotification.objects.filter(case=case).count()
    assert notif_count == 0


# ── Signal Tests ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_signal_creates_system_notice_on_supported_event(case_factory):
    """Signal post_save de CaseEvent cria mensagem sistêmica."""
    from apps.cases.models import CaseCommunicationMessage

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    # Criar CaseEvent via ORM — signal post_save deve disparar
    event = CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPRESSED",
        actor=creator,
        actor_type="human",
        payload={"original_filename": "exame.pdf", "reason": "teste"},
    )

    msg = CaseCommunicationMessage.objects.filter(source_event=event).first()
    assert msg is not None
    assert msg.message_type == "system"


@pytest.mark.django_db
def test_signal_ignores_unsupported_event(case_factory):
    """Signal ignora evento não suportado."""
    from apps.cases.models import CaseCommunicationMessage

    creator = User.objects.create_user(username="creator")
    case = case_factory(creator)

    event = CaseEvent.objects.create(
        case=case,
        event_type="LLM1_OK",
        actor=creator,
        actor_type="system",
    )

    msg = CaseCommunicationMessage.objects.filter(source_event=event).first()
    assert msg is None


# ── UI Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_communication_thread_renders_system_notice_as_system(client, case_factory):
    """Thread renderiza mensagem sistêmica como 'Sistema'."""
    from django.urls import reverse

    from apps.accounts.models import Role
    from apps.cases.models import CaseEvent

    # Criar usuário NIR
    nir_role, _ = Role.objects.get_or_create(name="nir")
    nir_user = User.objects.create_user(username="niruser", password="testpass")
    nir_user.roles.add(nir_role)

    case = case_factory(nir_user)

    # Criar evento — signal cria mensagem sistêmica
    CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPRESSED",
        actor=nir_user,
        actor_type="human",
        payload={"original_filename": "exame.pdf", "reason": "teste"},
    )

    # Autenticar e configurar active_role
    client.force_login(nir_user)
    session = client.session
    session["active_role"] = "nir"
    session.save()

    response = client.get(reverse("intake:case_detail", kwargs={"case_id": case.case_id}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Sistema" in content


@pytest.mark.django_db
def test_communication_thread_still_renders_manual_message_author(client, case_factory):
    """Regressão: mensagem manual ainda mostra autor."""
    from django.urls import reverse

    from apps.accounts.models import Role
    from apps.cases.services import post_case_communication_message

    nir_role, _ = Role.objects.get_or_create(name="nir")
    nir_user = User.objects.create_user(username="niruser", password="testpass")
    nir_user.roles.add(nir_role)

    case = case_factory(nir_user)
    post_case_communication_message(
        case=case,
        author=nir_user,
        author_role="nir",
        body="Mensagem manual de teste.",
    )

    client.force_login(nir_user)
    session = client.session
    session["active_role"] = "nir"
    session.save()

    response = client.get(reverse("intake:case_detail", kwargs={"case_id": case.case_id}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "niruser" in content


@pytest.mark.django_db
def test_manual_message_with_mention_still_creates_notification(case_factory, user):
    """Regressão: mensagem manual com @menção ainda cria UserNotification."""
    from apps.accounts.models import User, UserNotification
    from apps.cases.services import post_case_communication_message

    # Criar um segundo usuário para ser mencionado
    doctor_user = User.objects.create_user(username="doutor", is_active=True)
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name="doctor")
    doctor_user.roles.add(role)

    case = case_factory(user)
    post_case_communication_message(
        case=case,
        author=user,
        author_role="nir",
        body="Por favor, @doctor verifique este caso.",
    )

    notif_count = UserNotification.objects.filter(case=case).count()
    assert notif_count > 0


# ── Operational Workflow Integration Tests ─────────────────────────────────
# Slice 002: system notices from post-schedule issue and administrative closure


@pytest.fixture
def _cleaned_and_eligible(case_factory, advance_to, user):
    """Cria um caso CLEANED elegível para post-schedule issue."""
    from apps.cases.models import Case, CaseStatus

    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.appointment_at = "2026-07-15 10:00:00+00:00"
    case.appointment_location = "Hospital Central"
    case.save(
        update_fields=[
            "doctor_decision",
            "doctor_admission_flow",
            "appointment_status",
            "appointment_at",
            "appointment_location",
        ]
    )
    return Case.objects.get(pk=case.pk)


@pytest.fixture
def _nir_user(db):
    """Cria um usuário com papel nir."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="niruser", password="testpass")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


@pytest.mark.django_db
class TestPostScheduleIssueSystemNotices:
    """Testes de mensagens sistêmicas para eventos de intercorrência pós-agendamento."""

    def test_post_schedule_issue_opened_creates_system_notice(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """POST_ACCEPTANCE_ISSUE_OPENED gera mensagem sistêmica na thread."""
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import open_post_schedule_issue

        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="transport_unavailable",
            message="Paciente sem transporte",
        )

        msgs = CaseCommunicationMessage.objects.filter(case=case, message_type="system")
        assert msgs.count() >= 1
        msg = msgs.order_by("-created_at").first()
        assert msg is not None
        assert msg.system_event_type == "POST_ACCEPTANCE_ISSUE_OPENED"
        assert msg.author is None
        assert "transporte" in msg.body.lower() or "Transporte" in msg.body

    def test_post_schedule_issue_opened_notice_uses_reason_label_and_message(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """Mensagem sistêmica contém label do motivo e mensagem do NIR."""
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import open_post_schedule_issue

        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="reschedule_request",
            message="Precisamos reagendar para próxima semana",
        )

        msgs = CaseCommunicationMessage.objects.filter(case=case, system_event_type="POST_ACCEPTANCE_ISSUE_OPENED")
        assert msgs.count() >= 1
        msg = msgs.order_by("-created_at").first()
        assert msg is not None
        assert "Solicitação de reagendamento" in msg.body or "reagendamento" in msg.body.lower()
        assert "Precisamos reagendar" in msg.body

    def test_post_schedule_issue_responded_creates_system_notice(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """POST_ACCEPTANCE_ISSUE_RESPONDED gera mensagem sistêmica."""
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import open_post_schedule_issue, respond_post_schedule_issue

        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="death",
        )

        case = respond_post_schedule_issue(
            case=case, user=user, action="cancel", response_message="Agendamento cancelado"
        )

        msgs = CaseCommunicationMessage.objects.filter(case=case, system_event_type="POST_ACCEPTANCE_ISSUE_RESPONDED")
        assert msgs.count() >= 1
        msg = msgs.order_by("-created_at").first()
        assert msg is not None
        assert "Cancelado" in msg.body or "cancelado" in msg.body.lower()

    @pytest.mark.parametrize(
        "action, expected_label, appointment_at",
        [
            ("cancel", "Cancelado", None),
            ("reschedule", "Reagendado", "2026-08-01T14:00:00Z"),
            ("maintain", "Mantido", None),
            ("deny", "Solicitação negada", None),
        ],
    )
    def test_post_schedule_issue_responded_notice_includes_action_details(
        self,
        user,
        case_factory,
        advance_to,
        _cleaned_and_eligible,
        _nir_user,
        action,
        expected_label,
        appointment_at,
    ):
        """Cada ação do scheduler gera label amigável correta na mensagem sistêmica."""
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import open_post_schedule_issue, respond_post_schedule_issue

        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="death",
        )

        case2 = respond_post_schedule_issue(
            case=case,
            user=user,
            action=action,
            appointment_at=appointment_at,
            appointment_location="Hospital Central - Sala 3" if appointment_at else "",
        )

        msg = (
            CaseCommunicationMessage.objects.filter(case=case2, system_event_type="POST_ACCEPTANCE_ISSUE_RESPONDED")
            .order_by("-created_at")
            .first()
        )
        assert msg is not None
        assert expected_label in msg.body

    def test_post_acceptance_issue_acknowledged_creates_system_notice(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED gera mensagem sistêmica (C6).

        Diferente do ACK legado (POST_SCHEDULE_ISSUE_ACKNOWLEDGED) que tem
        payload vazio, o novo ACK possui cycle_id, context e admission_flow
        e merece projeção na thread.
        """
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import (
            acknowledge_post_schedule_issue,
            open_post_schedule_issue,
            respond_post_schedule_issue,
        )

        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="death",
        )
        case = respond_post_schedule_issue(case=case, user=user, action="cancel")
        case = acknowledge_post_schedule_issue(case=case, user=_nir_user)

        ack_msgs = CaseCommunicationMessage.objects.filter(
            case=case, system_event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED"
        )
        assert ack_msgs.count() == 1, "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED deve gerar mensagem sistêmica"
        msg = ack_msgs.first()
        assert msg is not None
        assert msg.message_type == "system"
        assert "ciência" in msg.body.lower() or "Ciência" in msg.body


@pytest.mark.django_db
class TestAdministrativeClosureSystemNotices:
    """Testes de mensagens sistêmicas para encerramento administrativo."""

    def test_administrative_closure_creates_system_notice(self, user, case_factory, advance_to):
        """CASE_ADMINISTRATIVELY_CLOSED gera mensagem sistêmica."""
        from apps.cases.models import Case, CaseCommunicationMessage, CaseStatus
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug no processamento",
            active_role="manager",
        )

        # Buscar instância fresca
        case = Case.objects.get(pk=case.pk)

        msgs = CaseCommunicationMessage.objects.filter(case=case, system_event_type="CASE_ADMINISTRATIVELY_CLOSED")
        assert msgs.count() >= 1
        msg = msgs.order_by("-created_at").first()
        assert msg is not None
        assert "encerrado" in msg.body.lower()

    def test_administrative_closure_notice_includes_reason(self, user, case_factory, advance_to):
        """Mensagem sistêmica de encerramento inclui motivo e status anterior."""
        from apps.cases.models import Case, CaseCommunicationMessage, CaseStatus
        from apps.cases.services import administratively_close_case

        case = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case,
            user=user,
            reason_code="stuck_lock",
            reason_text="Lock expirado do médico",
            active_role="manager",
        )

        case = Case.objects.get(pk=case.pk)

        msg = (
            CaseCommunicationMessage.objects.filter(case=case, system_event_type="CASE_ADMINISTRATIVELY_CLOSED")
            .order_by("-created_at")
            .first()
        )
        assert msg is not None
        assert "Lock expirado" in msg.body or "lock" in msg.body.lower()
        assert "WAIT_DOCTOR" in msg.body or "Wait Doctor" in msg.body or "Wait" in msg.body


@pytest.mark.django_db
class TestOperationalSystemNoticeHardening:
    """Testes de hardening: sistêmicas não geram notificação/badge."""

    def test_operational_system_notices_do_not_create_user_notifications(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """Eventos operacionais não criam UserNotification."""
        from apps.accounts.models import UserNotification
        from apps.cases.models import CaseStatus
        from apps.cases.services import (
            administratively_close_case,
            open_post_schedule_issue,
        )

        notif_before = UserNotification.objects.count()

        # Criar evento de intercorrência
        open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="death",
        )

        # Criar evento de encerramento administrativo
        case2 = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case2,
            user=user,
            reason_code="system_bug",
            reason_text="Bug",
            active_role="manager",
        )

        notif_after = UserNotification.objects.count()
        assert notif_after == notif_before

    def test_operational_system_notices_do_not_change_unread_badge_count(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """Badge de notificações não muda por mensagens sistêmicas."""
        from apps.accounts.models import get_unread_notification_count
        from apps.cases.models import CaseStatus
        from apps.cases.services import (
            administratively_close_case,
            open_post_schedule_issue,
        )

        badge_before = get_unread_notification_count(_nir_user)

        open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="death",
        )

        case2 = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        administratively_close_case(
            case=case2,
            user=user,
            reason_code="system_bug",
            reason_text="Bug",
            active_role="manager",
        )

        badge_after = get_unread_notification_count(_nir_user)
        assert badge_after == badge_before

    def test_system_notice_with_at_symbol_does_not_trigger_mention_notifications(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """Mensagem sistêmica com @ não aciona menções."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import open_post_schedule_issue

        # Motivo/mensagem com @
        open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="other",
            message="Favor @nir verificar agenda. @doctor comunicou mudança.",
        )

        notif_count = UserNotification.objects.filter(case=_cleaned_and_eligible).count()
        assert notif_count == 0

    def test_system_notice_source_event_idempotency_for_operational_events(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """Chamar criação duas vezes para mesmo evento não duplica."""
        from apps.cases.models import CaseCommunicationMessage, CaseEvent

        # Abrir intercorrência
        from apps.cases.services import create_system_communication_notice_for_event, open_post_schedule_issue

        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="death",
        )

        event = CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_OPENED").first()
        assert event is not None

        msg1 = create_system_communication_notice_for_event(event)
        msg2 = create_system_communication_notice_for_event(event)

        assert msg1 is not None
        assert msg2 is not None
        assert msg1.pk == msg2.pk

        count = CaseCommunicationMessage.objects.filter(source_event=event).count()
        assert count == 1

    def test_manual_mentions_still_create_notifications_after_system_notice_changes(
        self, user, case_factory, advance_to
    ):
        """Regressão: mensagem manual com @menção ainda cria notificação."""
        from apps.accounts.models import User, UserNotification
        from apps.cases.models import CaseStatus
        from apps.cases.services import post_case_communication_message

        doctor_user = User.objects.create_user(username="doutor", is_active=True)
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="doctor")
        doctor_user.roles.add(role)

        case = advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="Por favor, @doctor verifique este caso.",
        )

        notif_count = UserNotification.objects.filter(case=case).count()
        assert notif_count > 0

    def test_workflow_structured_fields_are_unchanged_by_system_notice(
        self, user, case_factory, advance_to, _cleaned_and_eligible, _nir_user
    ):
        """Campos estruturados de intercorrência/encerramento continuam corretos."""
        from apps.cases.models import CaseStatus
        from apps.cases.services import (
            administratively_close_case,
            open_post_schedule_issue,
        )

        # Abrir intercorrência
        case = open_post_schedule_issue(
            case=_cleaned_and_eligible,
            user=_nir_user,
            reason="transport_unavailable",
            message="Sem transporte",
        )
        assert case.post_schedule_issue_status == "opened"
        assert case.post_schedule_issue_reason == "transport_unavailable"
        assert case.post_schedule_issue_message == "Sem transporte"
        assert case.post_schedule_issue_opened_by == _nir_user
        assert case.status == CaseStatus.WAIT_APPT

        # Encerrar administrativamente
        case2 = advance_to(case_factory(user), CaseStatus.WAIT_DOCTOR)
        case2 = administratively_close_case(
            case=case2,
            user=user,
            reason_code="system_bug",
            reason_text="Bug crítico no processamento",
            active_role="admin",
        )
        assert case2.status == CaseStatus.CLEANED
        assert case2.locked_by is None
        assert CaseEvent.objects.filter(case=case2, event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()


@pytest.mark.django_db
class TestLegacyPostScheduleEventCompatibility:
    """Testes de compatibilidade com eventos legados POST_SCHEDULE_ISSUE_*.

    Eventos legados são criados manualmente (simulando registros históricos
    já existentes no banco). Wrappers legados não são usados — eles agora
    delegam aos serviços pós-aceitação e emitem eventos novos.
    """

    def _make_legacy_event(self, case, user, event_type, payload):
        """Cria CaseEvent legado manualmente."""
        from apps.cases.models import CaseEvent

        return CaseEvent.objects.create(
            case=case,
            event_type=event_type,
            payload=payload,
            actor=user,
        )

    def _cleaned_case(self, user, case_factory, advance_to):
        """Cria caso CLEANED para teste de evento legado."""
        from apps.cases.models import CaseStatus

        return advance_to(case_factory(user), CaseStatus.CLEANED)

    # ── OPENED ───────────────────────────────────────────────────────

    def test_legacy_opened_creates_system_notice(self, user, case_factory, advance_to):
        """POST_SCHEDULE_ISSUE_OPENED legado gera mensagem sistêmica."""
        from apps.cases.services import create_system_communication_notice_for_event

        case = self._cleaned_case(user, case_factory, advance_to)
        event = self._make_legacy_event(
            case,
            user,
            "POST_SCHEDULE_ISSUE_OPENED",
            {"reason": "death", "message": "Óbito constatado", "admission_flow": "scheduled"},
        )

        msg = create_system_communication_notice_for_event(event)
        assert msg is not None
        assert msg.message_type == "system"
        assert msg.system_event_type == "POST_SCHEDULE_ISSUE_OPENED"
        assert "Óbito" in msg.body or "Intercorrência" in msg.body

    def test_legacy_opened_idempotent(self, user, case_factory, advance_to):
        """System notice de POST_SCHEDULE_ISSUE_OPENED é idempotente."""
        from apps.cases.services import create_system_communication_notice_for_event

        case = self._cleaned_case(user, case_factory, advance_to)
        event = self._make_legacy_event(
            case,
            user,
            "POST_SCHEDULE_ISSUE_OPENED",
            {"reason": "death", "message": "Óbito", "admission_flow": "scheduled"},
        )

        msg1 = create_system_communication_notice_for_event(event)
        msg2 = create_system_communication_notice_for_event(event)
        assert msg1 is not None
        assert msg2 is not None
        assert msg1.pk == msg2.pk, "System notice deve ser idempotente por source_event"

    def test_legacy_opened_no_user_notification(self, user, case_factory, advance_to):
        """System notice legado não cria UserNotification."""
        from apps.accounts.models import UserNotification
        from apps.cases.services import create_system_communication_notice_for_event

        case = self._cleaned_case(user, case_factory, advance_to)
        event = self._make_legacy_event(
            case,
            user,
            "POST_SCHEDULE_ISSUE_OPENED",
            {"reason": "death", "message": "Óbito", "admission_flow": "scheduled"},
        )

        before = UserNotification.objects.count()
        create_system_communication_notice_for_event(event)
        after = UserNotification.objects.count()
        assert after == before, "System notice legado não deve criar UserNotification"

    # ── RESPONDED ────────────────────────────────────────────────────

    def test_legacy_responded_creates_system_notice(self, user, case_factory, advance_to):
        """POST_SCHEDULE_ISSUE_RESPONDED legado gera mensagem sistêmica."""
        from apps.cases.services import create_system_communication_notice_for_event

        case = self._cleaned_case(user, case_factory, advance_to)
        event = self._make_legacy_event(
            case,
            user,
            "POST_SCHEDULE_ISSUE_RESPONDED",
            {
                "action": "cancel",
                "response_message": "Agendamento cancelado",
                "admission_flow": "scheduled",
            },
        )

        msg = create_system_communication_notice_for_event(event)
        assert msg is not None
        assert msg.message_type == "system"
        assert msg.system_event_type == "POST_SCHEDULE_ISSUE_RESPONDED"
        assert "cancelado" in msg.body.lower() or "Cancelado" in msg.body

    def test_legacy_responded_shows_action_translated(self, user, case_factory, advance_to):
        """Ação da resposta legada é traduzida no corpo da mensagem."""
        from apps.cases.services import create_system_communication_notice_for_event

        case = self._cleaned_case(user, case_factory, advance_to)
        event = self._make_legacy_event(
            case,
            user,
            "POST_SCHEDULE_ISSUE_RESPONDED",
            {
                "action": "reschedule",
                "response_message": "Nova data definida",
                "admission_flow": "scheduled",
            },
        )

        msg = create_system_communication_notice_for_event(event)
        assert msg is not None
        # Deve conter termo legível de reagendamento ou ação
        assert "Reagendado" in msg.body or "reagendamento" in msg.body.lower() or "Nova data" in msg.body

    # ── ACKNOWLEDGED (legado — omitido da thread) ───────────────────

    def test_legacy_acknowledged_does_not_create_system_notice(self, user, case_factory, advance_to):
        """POST_SCHEDULE_ISSUE_ACKNOWLEDGED legado NÃO gera system notice.

        Decisão histórica preservada: payload vazio, sem projeção na thread.
        """
        from apps.cases.models import CaseCommunicationMessage
        from apps.cases.services import create_system_communication_notice_for_event

        case = self._cleaned_case(user, case_factory, advance_to)
        event = self._make_legacy_event(
            case,
            user,
            "POST_SCHEDULE_ISSUE_ACKNOWLEDGED",
            {},  # payload vazio legado
        )

        msg = create_system_communication_notice_for_event(event)
        assert msg is None, "POST_SCHEDULE_ISSUE_ACKNOWLEDGED legado não deve projetar mensagem sistêmica"

        ack_count = CaseCommunicationMessage.objects.filter(
            case=case, system_event_type="POST_SCHEDULE_ISSUE_ACKNOWLEDGED"
        ).count()
        assert ack_count == 0

    def test_legacy_acknowledged_has_label_and_dot(self):
        """POST_SCHEDULE_ISSUE_ACKNOWLEDGED legado tem label e dot CSS."""
        from apps.intake.views import EVENT_DOT_CSS, EVENT_LABELS

        label = EVENT_LABELS.get("POST_SCHEDULE_ISSUE_ACKNOWLEDGED")
        assert label is not None, "POST_SCHEDULE_ISSUE_ACKNOWLEDGED deve ter label na timeline"
        assert "ciência" in label.lower() or "Ciência" in label

        dot = EVENT_DOT_CSS.get("POST_SCHEDULE_ISSUE_ACKNOWLEDGED")
        assert dot is not None, "POST_SCHEDULE_ISSUE_ACKNOWLEDGED deve ter dot CSS"
