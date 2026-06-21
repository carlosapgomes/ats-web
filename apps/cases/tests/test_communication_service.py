"""Tests for the CaseCommunicationMessage service layer.

RED phase: all tests should fail before implementation.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import CaseStatus

User = get_user_model()


def test_post_case_communication_message_creates_message(db, case_factory, user):
    """R1: cria mensagem com case, author, author_role, body normalizado."""
    from apps.cases.services import (
        CASE_COMMUNICATION_MAX_LENGTH,
        post_case_communication_message,
    )

    case = case_factory(user)
    body = "  Precisamos de mais informações sobre este caso.  "
    msg = post_case_communication_message(
        case=case,
        author=user,
        author_role="nir",
        body=body,
    )

    assert msg.message_id is not None
    assert isinstance(msg.message_id, uuid.UUID)
    assert msg.case == case
    assert msg.author == user
    assert msg.author_role == "nir"
    # body must be normalized (strip)
    assert msg.body == "Precisamos de mais informações sobre este caso."
    assert len(msg.body) <= CASE_COMMUNICATION_MAX_LENGTH


def test_post_case_communication_message_rejects_blank_body(db, case_factory, user):
    """R2: body vazio/apenas espaços rejeitado."""
    from apps.cases.services import (
        CaseCommunicationError,
        post_case_communication_message,
    )

    case = case_factory(user)

    with pytest.raises(CaseCommunicationError, match="não pode estar vazia"):
        post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="   ",
        )


def test_post_case_communication_message_rejects_too_long_body(db, case_factory, user):
    """R3: acima do limite rejeitado."""
    from apps.cases.services import (
        CASE_COMMUNICATION_MAX_LENGTH,
        CaseCommunicationError,
        post_case_communication_message,
    )

    case = case_factory(user)
    long_body = "x" * (CASE_COMMUNICATION_MAX_LENGTH + 1)

    with pytest.raises(CaseCommunicationError, match="excede o limite"):
        post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body=long_body,
        )


def test_post_case_communication_message_rejects_disallowed_role(db, case_factory, user):
    """R4: papel não permitido rejeitado."""
    from apps.cases.services import (
        CaseCommunicationError,
        post_case_communication_message,
    )

    case = case_factory(user)

    with pytest.raises(CaseCommunicationError, match="Papel.*não permitido"):
        post_case_communication_message(
            case=case,
            author=user,
            author_role="patient",
            body="Mensagem teste.",
        )


def test_post_case_communication_message_rejects_cleaned_case(db, case_factory, advance_to, user):
    """R5: caso CLEANED rejeitado no MVP."""
    from apps.cases.services import (
        CaseCommunicationError,
        post_case_communication_message,
    )

    case = case_factory(user)
    case = advance_to(case, CaseStatus.CLEANED)

    with pytest.raises(CaseCommunicationError, match="encerrado|CLEANED|finalizado"):
        post_case_communication_message(
            case=case,
            author=user,
            author_role="nir",
            body="Mensagem em caso encerrado.",
        )


def test_post_case_communication_message_records_case_event(db, case_factory, user):
    """R6: evento CASE_COMMUNICATION_MESSAGE_POSTED criado com preview e id."""
    from apps.cases.models import CaseEvent
    from apps.cases.services import (
        post_case_communication_message,
    )

    case = case_factory(user)
    body = "Este é um teste de mensagem com corpo suficiente para testar preview."
    msg = post_case_communication_message(
        case=case,
        author=user,
        author_role="doctor",
        body=body,
    )

    events = list(CaseEvent.objects.filter(case=case))
    matching = [e for e in events if e.event_type == "CASE_COMMUNICATION_MESSAGE_POSTED"]
    assert len(matching) == 1, f"Expected 1 event, got {len(matching)}"
    event = matching[0]
    payload = event.payload or {}
    assert payload.get("message_id") == str(msg.message_id)
    assert payload.get("author_role") == "doctor"
    assert payload.get("body_preview") == body[:120]

    # O corpo completo NÃO deve estar duplicado no payload do evento
    assert payload.get("body") is None


def test_post_case_communication_message_creates_message_with_body_at_limit(db, case_factory, user):
    """R7: body exatamente no limite é aceito."""
    from apps.cases.services import (
        CASE_COMMUNICATION_MAX_LENGTH,
        post_case_communication_message,
    )

    case = case_factory(user)
    body = "x" * CASE_COMMUNICATION_MAX_LENGTH
    msg = post_case_communication_message(
        case=case,
        author=user,
        author_role="nir",
        body=body,
    )
    assert len(msg.body) == CASE_COMMUNICATION_MAX_LENGTH


def test_post_case_communication_message_allows_allowed_roles(db, case_factory, user):
    """R8: todos os papéis permitidos podem postar."""
    from apps.cases.services import (
        ALLOWED_COMMUNICATION_ROLES,
        post_case_communication_message,
    )

    case = case_factory(user)
    for role in sorted(ALLOWED_COMMUNICATION_ROLES):
        msg = post_case_communication_message(
            case=case,
            author=user,
            author_role=role,
            body=f"Mensagem do papel {role}.",
        )
        assert msg.author_role == role
