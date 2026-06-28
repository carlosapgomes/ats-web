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


# ── Migração por módulo (Slices 1-4) ──

from pathlib import Path  # noqa: E402


def _has_page_title_block(template_rel: str) -> bool:
    content = Path(template_rel).read_text()
    return '{% block page_title %}<h1 class="page-title">' in content


def _has_subtitle_block(template_rel: str) -> bool:
    return "{% block subtitle %}" in Path(template_rel).read_text()


ACCOUNTS_TEMPLATES = [
    "templates/accounts/manual.html",
    "templates/accounts/notifications.html",
]


@pytest.mark.parametrize("template_rel", ACCOUNTS_TEMPLATES)
def test_accounts_template_uses_page_title_block(template_rel: str) -> None:
    assert _has_page_title_block(template_rel), (
        f"{template_rel} deve usar {{% block page_title %}} com <h1 class='page-title'>"
    )
    assert not _has_subtitle_block(template_rel), f"{template_rel} ainda contém {{% block subtitle %}}"


INTAKE_TEMPLATES = [
    "templates/intake/corrected_resubmission.html",
    "templates/intake/my_cases.html",
    "templates/intake/closed_cases_search.html",
    "templates/intake/case_detail.html",
    "templates/intake/closed_case_detail.html",
    "templates/intake/post_schedule_issue_form.html",
    "templates/intake/intake_home.html",
]


@pytest.mark.parametrize("template_rel", INTAKE_TEMPLATES)
def test_intake_template_uses_page_title_block(template_rel: str) -> None:
    assert _has_page_title_block(template_rel)
    assert not _has_subtitle_block(template_rel)


SCHEDULER_TEMPLATES = [
    "templates/scheduler/confirm.html",
    "templates/scheduler/confirm_post_schedule_issue.html",
    "templates/scheduler/historical_search.html",
    "templates/scheduler/context_detail.html",
    "templates/scheduler/queue.html",
]


@pytest.mark.parametrize("template_rel", SCHEDULER_TEMPLATES)
def test_scheduler_template_uses_page_title_block(template_rel: str) -> None:
    assert _has_page_title_block(template_rel)
    assert not _has_subtitle_block(template_rel)


REMAINING_TEMPLATES = [
    "templates/doctor/decision.html",
    "templates/doctor/queue.html",
    "templates/dashboard/index.html",
    "templates/dashboard/summaries.html",
    "templates/admin_ui/prompt_detail.html",
    "templates/admin_ui/prompt_create.html",
    "templates/admin_ui/user_form.html",
    "templates/admin_ui/prompt_list.html",
    "templates/admin_ui/user_list.html",
]


@pytest.mark.parametrize("template_rel", REMAINING_TEMPLATES)
def test_remaining_template_uses_page_title_block(template_rel: str) -> None:
    assert _has_page_title_block(template_rel)
    assert not _has_subtitle_block(template_rel)


def test_scheduler_confirm_preserves_case_variables() -> None:
    content = Path("templates/scheduler/confirm.html").read_text()
    assert "{{ case.agency_record_number|default:case.case_id|truncatechars:16 }}" in content
    assert "{{ patient_name }}" in content


def test_doctor_decision_preserves_case_variables() -> None:
    content = Path("templates/doctor/decision.html").read_text()
    assert "{{ case.agency_record_number|default:case.case_id|truncatechars:16 }}" in content
    assert "{{ patient_name }}" in content


def test_no_subtitle_block_remains_anywhere() -> None:
    """Após todos os slices, nenhum template deve conter {% block subtitle %}."""
    import os

    for root, _dirs, files in os.walk("templates"):
        for f in files:
            if f.endswith(".html"):
                path = os.path.join(root, f)
                assert "{% block subtitle %}" not in Path(path).read_text(), (
                    f"{path} ainda contém {{% block subtitle %}}"
                )
