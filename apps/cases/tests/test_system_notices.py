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
