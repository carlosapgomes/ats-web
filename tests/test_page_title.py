"""Tests for base.html page_title infrastructure (Slice 000).

Verifies:
1. Header subtitle is constant (no block)
2. <h1 class="page-title"> is absent by default
3. <h1 class="page-title"> renders when template defines {% block page_title %}
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template import engines
from django.template.loader import render_to_string
from django.test import RequestFactory


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


def _build_request(rf: RequestFactory):  # type: ignore[no-untyped-def]
    """Build a request with proper session (no middleware)."""
    request = rf.get("/")
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore()
    return request


def _render(
    rf: RequestFactory,
    page_title: str | None = None,
    authenticated: bool = True,
) -> str:
    class StubRoles:
        def count(self) -> int:
            return 1

    class StubUser:
        is_authenticated: bool = authenticated
        username: str = "jose.silva"

        def get_full_name(self) -> str:
            return "José Silva"

        @property
        def roles(self) -> StubRoles:
            return StubRoles()

    request = _build_request(rf)
    user = StubUser() if authenticated else AnonymousUser()
    request.user = user  # type: ignore[attr-defined,unused-ignore]

    ctx = {
        "user": user,
        "app_display_name": "ATS CHD",
        "active_role_display": "Médico",
        "notification_unread_count": 0,
    }

    # If page_title is provided, render a template that extends base and defines
    # {% block page_title %}.
    if page_title is not None:
        snippet = (
            '{% extends "base.html" %}'
            '{% block page_title %}<h1 class="page-title">' + page_title + "</h1>{% endblock %}"
        )
        django_engine = engines["django"]
        tmpl = django_engine.from_string(snippet)
        with patch(
            "apps.accounts.context_processors.get_unread_notification_count",
            return_value=0,
        ):
            return tmpl.render(ctx, request)

    with patch(
        "apps.accounts.context_processors.get_unread_notification_count",
        return_value=0,
    ):
        return render_to_string("base.html", ctx, request=request)


# ── Tests ──


def test_header_has_constant_tagline_no_subtitle_block(rf: RequestFactory) -> None:
    html = _render(rf)
    assert "Sistema de Regulação Hospitalar CHD" in html
    assert "{% block subtitle %}" not in html
    assert '<span class="app-header__subtitle">Sistema de Regulação Hospitalar CHD</span>' in html


def test_no_page_title_by_default(rf: RequestFactory) -> None:
    html = _render(rf)
    assert "page-title" not in html


def test_page_title_renders_h1_when_defined(rf: RequestFactory) -> None:
    html = _render(rf, page_title="Meus Casos")
    assert '<h1 class="page-title">Meus Casos</h1>' in html
