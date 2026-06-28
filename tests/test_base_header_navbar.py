"""Tests for base.html header refactored to Bootstrap navbar (Slice 002).

Verifies the header uses navbar-expand-lg with hybrid collapse:
- Always visible: brand (logo + name) + notification bell + avatar
- Collapsible: full name + role, manual, switch role, logout
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
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


def _render(rf: RequestFactory, authenticated: bool = True, multi_role: bool = True) -> str:
    class StubRoles:
        def count(self) -> int:
            return 2 if multi_role else 1

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
    request.user = user  # type: ignore[assignment,unused-ignore]

    ctx = {
        "user": user,
        "app_display_name": "ATS CHD",
        "active_role_display": "Médico",
        "notification_unread_count": 0,
    }

    with patch(
        "apps.accounts.context_processors.get_unread_notification_count",
        return_value=0,
    ):
        return render_to_string("base.html", ctx, request=request)


# ── RED tests ──


def test_header_uses_navbar(rf: RequestFactory) -> None:
    html = _render(rf)
    assert 'class="app-header navbar navbar-expand-lg' in html


def test_navbar_brand_has_icon_and_name(rf: RequestFactory) -> None:
    html = _render(rf)
    assert "navbar-brand" in html
    assert "icons/icon-192.png" in html
    assert "ATS CHD" in html


def test_navbar_toggler_targets_session_menu(rf: RequestFactory) -> None:
    html = _render(rf)
    assert 'data-bs-target="#sessionMenu"' in html
    assert 'aria-controls="sessionMenu"' in html
    assert 'id="sessionMenu"' in html


def test_notification_badge_preserved(rf: RequestFactory) -> None:
    html = _render(rf)
    assert 'id="notification-badge"' in html
    assert "notification-badge" in html
    assert "data-notifications-badge" in html


def test_logout_form_present(rf: RequestFactory) -> None:
    html = _render(rf)
    assert 'action="/logout/"' in html


def test_switch_role_only_when_multi_role(rf: RequestFactory) -> None:
    assert "/switch-role/" in _render(rf, multi_role=True)
    assert "/switch-role/" not in _render(rf, multi_role=False)


def test_unauthenticated_has_no_session_block(rf: RequestFactory) -> None:
    html = _render(rf, authenticated=False)
    assert "navbar-toggler" not in html
    assert 'action="/logout/"' not in html


def test_navbar_toggler_icon_present(rf: RequestFactory) -> None:
    html = _render(rf)
    assert "navbar-toggler-icon" in html


def test_avatar_link_present(rf: RequestFactory) -> None:
    html = _render(rf)
    assert 'href="' in html  # avatar links to profile
    # Look for the avatar circle with initials
    assert "JOS" in html or "JO" in html or "J." in html  # initials from "José Silva"


# ── Slice 002b: DOM order + subnav full-width ──


def test_toggler_precedes_collapse_in_dom(rf: RequestFactory) -> None:
    """O toggler deve aparecer ANTES do collapse no DOM (padrão Bootstrap canônico).

    Garante que, ao expandir o menu no mobile, o bloco sempre-visível
    (sino/avatar/toggler) permanece no topo em vez de cair abaixo do menu.
    """
    html = _render(rf)
    i_toggler = html.index('class="navbar-toggler')
    i_collapse = html.index('class="collapse navbar-collapse')
    assert i_toggler < i_collapse, "navbar-toggler deve preceder o collapse navbar-collapse no DOM"


def test_order_lg_utilities_present(rf: RequestFactory) -> None:
    """order-lg-* devem estar presentes para reposicionar blocos no desktop."""
    html = _render(rf)
    assert "order-lg-2" in html, "Falta order-lg-2 no collapse"
    assert "order-lg-3" in html, "Falta order-lg-3 no bloco sempre-visível"


def test_app_nav_full_width_css() -> None:
    """A subnav (app-nav) deve ocupar largura total dentro do navbar (linha própria)."""
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "static" / "css" / "app.css").read_text()
    assert ".app-header .app-nav" in css, "Falta regra .app-header .app-nav em app.css"
    # localiza o bloco da regra e verifica flex-basis: 100%
    idx = css.index(".app-header .app-nav")
    block = css[idx : idx + 120]
    assert "flex-basis: 100%" in block, ".app-header .app-nav deve ter flex-basis: 100% para ocupar linha própria"


# ── Slice 003: ajustes complementares mobile (toque 44px + flex-wrap) ──


def test_touch_targets_css_present() -> None:
    """No mobile (<lg), botões do header devem ter área de toque >= 44px (WCAG 2.5.5)."""
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "static" / "css" / "app.css").read_text()
    # localiza um bloco mobile que afete notification-icon-btn/avatar-circle/navbar-toggler
    needle = ".app-header .notification-icon-btn"
    idx = css.index(needle)
    # procura no máximo 400 chars adiante (deve estar dentro de uma media query)
    block = css[idx : idx + 400]
    assert "min-width: 44px" in block, "Falta min-width: 44px nos botões do header no mobile"
    assert "min-height: 44px" in block, "Falta min-height: 44px nos botões do header no mobile"
    assert "avatar-circle" in block, "avatar-circle deve estar junto dos alvos de toque"
    assert "navbar-toggler" in block, "navbar-toggler deve estar junto dos alvos de toque"


def test_flex_wrap_defensive_css_present() -> None:
    """Em telas muito estreitas (<360px), o bloco sempre-visível deve flex-wrap."""
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "static" / "css" / "app.css").read_text()
    assert "max-width: 359.98px" in css, "Falta media query max-width: 359.98px para flex-wrap defensivo"
    assert "flex-wrap: wrap" in css, "Falta flex-wrap: wrap no bloco sempre-visível para telas muito estreitas"
