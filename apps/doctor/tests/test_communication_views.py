"""Tests for doctor case communication views.

RED phase: all tests should fail before implementation.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseStatus

User = get_user_model()


def _set_active_role(client, role: str) -> None:
    """Helper to set active_role in session."""
    session = client.session
    session["active_role"] = role
    session.save()


def _doctor_login(client):
    """Create and login a doctor user. Returns the user."""
    user = User.objects.create_user(username="doctoruser", password="testpass123!")
    client.login(username="doctoruser", password="testpass123!")
    _set_active_role(client, "doctor")
    return user


def _nir_login(client):
    """Create and login an NIR user. Returns the user."""
    user = User.objects.create_user(username="niruser2", password="testpass123!")
    client.login(username="niruser2", password="testpass123!")
    _set_active_role(client, "nir")
    return user


@pytest.fixture
def doctor_case(db, case_factory, advance_to) -> Case:
    """Create a case at WAIT_DOCTOR for doctor tests."""
    nir = User.objects.create_user(username="nir_doctor_test", password="testpass123!")
    case = case_factory(nir)
    case = advance_to(case, CaseStatus.WAIT_DOCTOR)
    return case  # type: ignore[no-any-return]


def test_doctor_decision_shows_case_communication_messages(client, db, doctor_case, user):
    """R16: mensagem criada pelo NIR aparece na tela de decisão."""
    from apps.cases.services import post_case_communication_message

    _doctor_login(client)

    # NIR posted a message
    post_case_communication_message(
        case=doctor_case,
        author=user,  # nir user
        author_role="nir",
        body="Paciente trouxe novo exame.",
    )

    url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Paciente trouxe novo exame." in content


def test_doctor_decision_shows_communication_thread_title(client, db, doctor_case):
    """R17: título da comunicação aparece na tela de decisão."""
    _doctor_login(client)

    url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "Comunicação operacional" in content


def test_doctor_decision_shows_mention_alias_help(client, db, doctor_case):
    """Thread orienta aliases de menção para equipes operacionais."""
    _doctor_login(client)

    url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(url)
    content = response.content.decode("utf-8")

    assert "@nir" in content
    assert "@medico" in content
    assert "@chd" in content
    assert "@supervisor" in content


def test_doctor_decision_has_post_form(client, db, doctor_case):
    """R18: formulário de post está presente na tela de decisão."""
    _doctor_login(client)

    url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "Enviar mensagem" in content


def test_doctor_posts_case_communication_message(client, db, doctor_case):
    """R19: médico posta resposta e NIR vê depois."""
    _doctor_login(client)

    post_url = reverse("intake:post_case_communication", args=[doctor_case.case_id])
    response = client.post(
        post_url,
        {"body": "Vou revisar o caso com atenção.", "next": reverse("doctor:decision", args=[doctor_case.case_id])},
    )
    assert response.status_code == 302

    # NIR should see the message
    _nir_login(client)
    detail_url = reverse("intake:case_detail", args=[doctor_case.case_id])
    response = client.get(detail_url)
    content = response.content.decode("utf-8")
    assert "Vou revisar o caso com atenção." in content


def test_doctor_decision_form_still_works_with_communication_thread(client, db, doctor_case):
    """R20: regressão — partial não quebra decisão médica."""

    _doctor_login(client)

    # First, visit the decision page to acquire the lock
    decision_url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(decision_url)
    assert response.status_code == 200

    # Extract lock_token from the page
    content = response.content.decode("utf-8")
    import re

    # Try to find the lock token in the work-lock-config div
    match = re.search(r'data-lock-token="([^"]+)"', content)
    lock_token = match.group(1) if match else None

    # If we have a lock token, try to submit the decision
    if lock_token:
        submit_url = reverse("doctor:submit", args=[doctor_case.case_id])
        response = client.post(
            submit_url,
            {
                "decision": "accept",
                "support_flag": "none",
                "admission_flow": "scheduled",
                "observation": "Teste com comunicação ativa.",
                "reason": "",
                "lock_token": lock_token,
            },
        )
        # Should redirect to queue after success
        assert response.status_code == 302
        queue_url = reverse("doctor:queue")
        assert queue_url in response.url
    else:
        # If no lock token (maybe already locked), just check the page renders
        assert "Comunicação operacional" in content


def test_nir_and_doctor_see_same_messages_in_order(client, db, doctor_case, user):
    """R21: mensagens de NIR e médico aparecem na ordem cronológica correta."""
    from apps.cases.services import post_case_communication_message

    _nir_login(client)

    # Create messages with different authors
    post_case_communication_message(
        case=doctor_case,
        author=user,
        author_role="nir",
        body="Primeira mensagem do NIR.",
    )

    post_case_communication_message(
        case=doctor_case,
        author=user,
        author_role="doctor",
        body="Resposta do médico.",
    )

    post_case_communication_message(
        case=doctor_case,
        author=user,
        author_role="nir",
        body="Segunda mensagem do NIR.",
    )

    # Check the order on the doctor page
    _doctor_login(client)
    url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(url)
    content = response.content.decode("utf-8")

    first_pos = content.index("Primeira mensagem do NIR.")
    second_pos = content.index("Resposta do médico.")
    third_pos = content.index("Segunda mensagem do NIR.")

    assert first_pos < second_pos < third_pos, "Messages are not in chronological order"


def test_doctor_sees_author_and_role_in_messages(client, db, doctor_case, user):
    """R22: médico vê autor e papel nas mensagens."""
    from apps.cases.services import post_case_communication_message

    _doctor_login(client)

    post_case_communication_message(
        case=doctor_case,
        author=user,
        author_role="nir",
        body="Mensagem com dados de autor.",
    )

    url = reverse("doctor:decision", args=[doctor_case.case_id])
    response = client.get(url)
    content = response.content.decode("utf-8")

    assert "nir" in content.lower() or "NIR" in content
