"""Tests for ActiveRoleMiddleware."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


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

        # Should NOT redirect; active_role is auto-set
        assert response.status_code != 302
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

        # Should not redirect
        assert response.status_code != 302
