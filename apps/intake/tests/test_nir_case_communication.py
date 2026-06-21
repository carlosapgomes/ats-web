"""Tests for NIR case communication views.

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


def _nir_login(client):
    """Create and login an NIR user. Returns the user."""
    user = User.objects.create_user(username="niruser", password="testpass123!")
    client.login(username="niruser", password="testpass123!")
    _set_active_role(client, "nir")
    return user


@pytest.fixture
def nir_case(db, case_factory) -> Case:
    """Create a simple case at WAIT_DOCTOR for NIR tests."""
    nir = User.objects.create_user(username="nir_cases", password="testpass123!")
    case = case_factory(nir)
    return case  # type: ignore[no-any-return]


def test_nir_case_detail_shows_communication_thread(client, db, nir_case):
    """R9: GET detalhe do caso mostra título e área de comunicação."""
    _nir_login(client)
    url = reverse("intake:case_detail", args=[nir_case.case_id])
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Comunicação operacional" in content


def test_nir_case_detail_shows_existing_communication_messages(client, db, nir_case, user):
    """R10: mensagens existentes aparecem no detalhe."""
    from apps.cases.services import post_case_communication_message

    _nir_login(client)

    # Create a message before visiting the page
    post_case_communication_message(
        case=nir_case,
        author=user,
        author_role="doctor",
        body="Preciso de mais exames complementares.",
    )

    url = reverse("intake:case_detail", args=[nir_case.case_id])
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Preciso de mais exames complementares." in content


def test_nir_posts_case_communication_message(client, db, nir_case):
    """R11: POST válido cria mensagem e redireciona."""
    _nir_login(client)
    url = reverse("intake:post_case_communication", args=[nir_case.case_id])

    response = client.post(
        url,
        {
            "body": "Mensagem do NIR sobre este caso.",
        },
        follow=False,
    )

    assert response.status_code == 302
    # Verificar redirecionamento
    expected_redirect = reverse("intake:case_detail", args=[nir_case.case_id])
    assert expected_redirect in response.url or nir_case.case_id in response.url


def test_nir_posts_and_sees_message(client, db, nir_case):
    """R11b: NIR posta e vê a mensagem após redirect."""
    _nir_login(client)
    post_url = reverse("intake:post_case_communication", args=[nir_case.case_id])

    client.post(
        post_url,
        {"body": "Mensagem de teste do NIR."},
    )

    detail_url = reverse("intake:case_detail", args=[nir_case.case_id])
    response = client.get(detail_url)
    content = response.content.decode("utf-8")
    assert "Mensagem de teste do NIR." in content


def test_nir_posts_empty_message_fails(client, db, nir_case):
    """R12: POST com body vazio mostra warning."""
    _nir_login(client)
    url = reverse("intake:post_case_communication", args=[nir_case.case_id])

    response = client.post(url, {"body": "   "}, follow=True)

    messages_list = list(response.context.get("messages", []))
    warning_texts = [str(m) for m in messages_list if m.level_tag == "warning"]
    assert any(
        "vazia" in text.lower() or "espaços" in text.lower() or "inválida" in text.lower() for text in warning_texts
    )


def test_post_case_communication_uses_safe_next_redirect(client, db, nir_case):
    """R13: next=https://evil.example não redireciona externamente."""
    _nir_login(client)
    url = reverse("intake:post_case_communication", args=[nir_case.case_id])

    response = client.post(
        url,
        {"body": "Mensagem segura.", "next": "https://evil.example.com"},
    )

    assert response.status_code == 302
    # Deve redirecionar para o detalhe do caso, não para evil.example.com
    assert "evil.example.com" not in response.url


def test_nir_case_detail_has_post_form(client, db, nir_case):
    """R14: formulário de post está presente no detalhe."""
    _nir_login(client)
    url = reverse("intake:case_detail", args=[nir_case.case_id])
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "Enviar mensagem" in content
    assert "textarea" in content.lower() or 'name="body"' in content


def test_nir_cannot_post_on_cleaned_case(client, db, nir_case, advance_to):
    """R15: NIR não pode postar em caso CLEANED via view."""
    _nir_login(client)
    nir_case = advance_to(nir_case, CaseStatus.CLEANED)
    url = reverse("intake:post_case_communication", args=[nir_case.case_id])

    response = client.post(url, {"body": "Mensagem em caso encerrado."})
    # Should either redirect (with warning) or return some non-success
    assert response.status_code == 302
    # And no message should have been created
    from apps.cases.models import CaseCommunicationMessage

    assert CaseCommunicationMessage.objects.filter(case=nir_case).count() == 0
