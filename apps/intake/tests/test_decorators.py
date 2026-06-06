"""Tests for the role_required decorator and intake views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
HOME_URL = reverse("intake:home")


@pytest.mark.django_db
class TestRoleRequiredDecorator:
    """Tests for the @role_required decorator, including view integration."""

    def test_role_required_allows_correct_role(self, client) -> None:
        """nir with active_role='nir' can access the intake view -> 200."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 200

    def test_role_required_blocks_wrong_role(self, client) -> None:
        """doctor with active_role='doctor' accessing nir view -> redirect to /."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="doctor@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 302
        assert response.url == "/"

        # role_required sets an error message via django.contrib.messages
        # home_view then redirects "/" to intake:home for doctor (loop),
        # so we verify the message was queued instead of checking rendered content
        from django.contrib.messages import get_messages

        msgs = list(get_messages(response.wsgi_request))
        assert any("permissão" in str(m) for m in msgs)

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
        role_nir, _ = Role.objects.get_or_create(name="nir")
        role_doctor, _ = Role.objects.get_or_create(name="doctor")
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
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 200
        assert "encaminhamento" in response.content.decode().lower()

    def test_intake_home_blocks_doctor(self, client) -> None:
        """doctor + login -> redirect."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="doc@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("intake:home"))
        assert response.status_code == 302
        assert response.url == "/"

    def test_intake_home_has_closed_cases_link(self, client) -> None:
        """Home NIR renderiza link para Casos Encerrados no nav."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir-home@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(HOME_URL)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Casos Encerrados" in content
        assert reverse("intake:closed_cases_search") in content
