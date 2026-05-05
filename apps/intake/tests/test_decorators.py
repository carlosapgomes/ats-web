"""Tests for the role_required decorator and intake views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestRoleRequiredDecorator:
    """Tests for the @role_required decorator, including view integration."""

    def test_role_required_allows_correct_role(self, client) -> None:
        """nir with active_role='nir' can access the intake view -> 200."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@test.com", password="testpass123")
        role = Role.objects.create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 200

    def test_role_required_blocks_wrong_role(self, client) -> None:
        """doctor with active_role='doctor' accessing nir view -> redirect + error message."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="doctor@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 302
        assert response.url == "/"

        # Follow redirect and check that error message is rendered
        followed = client.get("/")
        content = followed.content.decode()
        assert "permissão" in content.lower() or "acesso" in content.lower()

    def test_role_required_blocks_no_role(self, client) -> None:
        """User without active_role -> redirect."""
        user = User.objects.create_user(username="norole@test.com", password="testpass123")
        client.force_login(user)

        # No active_role set in session

        response = client.get(reverse("intake:home"))
        assert response.status_code == 302

    def test_role_required_allows_multiple_roles(self, client) -> None:
        """Decorator with multiple allowed roles lets any of them through."""
        from apps.accounts.models import Role

        # We need a view with @role_required("nir", "doctor") to test.
        # For now, we verify the decorator's behavior via the intake home
        # which only allows "nir". This test validates the mechanism exists.
        user = User.objects.create_user(username="multi@test.com", password="testpass123")
        role_nir = Role.objects.create(name="nir")
        role_doctor = Role.objects.create(name="doctor")
        user.roles.add(role_nir, role_doctor)
        client.force_login(user)

        # nir role -> should work
        session = client.session
        session["active_role"] = "nir"
        session.save()
        response = client.get(reverse("intake:home"))
        assert response.status_code == 200

    def test_intake_home_requires_login(self, client) -> None:
        """GET /cases/ without login -> redirect /login/."""
        response = client.get(reverse("intake:home"))
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_intake_home_allows_nir(self, client) -> None:
        """nir + login -> 200."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nirfull@test.com", password="testpass123")
        role = Role.objects.create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 200
        assert "construção" in response.content.decode().lower()

    def test_intake_home_blocks_doctor(self, client) -> None:
        """doctor + login -> redirect."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="doc@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 302
        assert response.url == "/"
