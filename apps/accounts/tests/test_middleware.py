"""Tests for ActiveRoleMiddleware and intranet helpers."""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.accounts.middleware import _is_intranet_ip

User = get_user_model()


@pytest.mark.django_db
class TestIntranetIpCheck:
    """Tests for _is_intranet_ip with single and multiple ranges."""

    @override_settings(INTRANET_IP_RANGE="127.0.0.0/8")
    def test_single_range_match(self) -> None:
        assert _is_intranet_ip("127.1.2.3") is True

    @override_settings(INTRANET_IP_RANGE="127.0.0.0/8")
    def test_single_range_no_match(self) -> None:
        assert _is_intranet_ip("10.0.0.1") is False

    @override_settings(INTRANET_IP_RANGE="127.0.0.0/8,192.168.15.0/24")
    def test_multiple_ranges_match_first(self) -> None:
        assert _is_intranet_ip("127.10.10.10") is True

    @override_settings(INTRANET_IP_RANGE="127.0.0.0/8,192.168.15.0/24")
    def test_multiple_ranges_match_second(self) -> None:
        assert _is_intranet_ip("192.168.15.77") is True

    @override_settings(INTRANET_IP_RANGE="127.0.0.0/8,192.168.15.0/24")
    def test_multiple_ranges_no_match(self) -> None:
        assert _is_intranet_ip("172.16.0.1") is False

    @override_settings(INTRANET_IP_RANGE="")
    def test_empty_range_returns_false(self) -> None:
        assert _is_intranet_ip("127.0.0.1") is False

    @override_settings(INTRANET_IP_RANGE="127.0.0.0/8")
    def test_invalid_ip_returns_false(self) -> None:
        assert _is_intranet_ip("not-an-ip") is False


@pytest.mark.django_db
class TestActiveRoleMiddleware:
    """Tests for the ActiveRoleMiddleware."""

    def test_middleware_redirects_to_switch_when_no_active_role(self, client) -> None:
        """User with multiple roles and no active_role is redirected to /switch-role/."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="multi@test.com", password="testpass123")
        role_nir = Role.objects.create(name="nir")
        role_doctor = Role.objects.create(name="doctor")
        user.roles.add(role_nir, role_doctor)
        client.force_login(user)

        response = client.get("/")

        assert response.status_code == 302
        assert response.url == reverse("switch_role")

    def test_middleware_auto_sets_single_role(self, client) -> None:
        """User with 1 role gets active_role set automatically."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="single@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        response = client.get("/")

        # Middleware auto-sets active_role; home_view then redirects
        assert response.status_code == 302
        assert client.session["active_role"] == "doctor"

    def test_middleware_skips_login_paths(self, client) -> None:
        """Middleware does not intercept /login/ path."""
        response = client.get(reverse("login"))

        # Should render login page (200), not redirect
        assert response.status_code == 200

    def test_middleware_allows_when_active_role_set(self, client) -> None:
        """User with active_role already set proceeds normally."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="active@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        # Manually set active_role in session
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/")

        # home_view now always redirects when active_role is set
        assert response.status_code == 302
