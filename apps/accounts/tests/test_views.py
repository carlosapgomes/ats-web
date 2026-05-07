"""Tests for accounts views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestLoginView:
    """Tests for the login view."""

    def test_login_page_renders(self, client) -> None:
        """GET /login/ returns 200 and renders login form."""
        response = client.get(reverse("login"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "entrar" in content.lower() or "login" in content.lower()

    def test_login_valid_credentials_single_role(self, client) -> None:
        """POST with valid credentials and 1 role redirects to /."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)

        response = client.post(reverse("login"), {"username": "nir@test.com", "password": "testpass123"})

        assert response.status_code == 302
        assert response.url == "/"

    def test_login_invalid_credentials(self, client) -> None:
        """POST with invalid credentials shows error."""
        User.objects.create_user(username="real@test.com", password="correct123")

        response = client.post(reverse("login"), {"username": "real@test.com", "password": "wrongpass"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "inválid" in content.lower() or "alert-danger" in content.lower()

    def test_login_multiple_roles_redirects_to_switch(self, client) -> None:
        """User with multiple roles is redirected to /switch-role/."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="multi@test.com", password="testpass123")
        role_nir, _ = Role.objects.get_or_create(name="nir")
        role_doctor, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role_nir, role_doctor)

        response = client.post(reverse("login"), {"username": "multi@test.com", "password": "testpass123"})

        assert response.status_code == 302
        assert response.url == reverse("switch_role")

    def test_login_single_role_auto_select(self, client) -> None:
        """User with exactly 1 role goes directly to / with active_role set in session."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="single@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)

        response = client.post(reverse("login"), {"username": "single@test.com", "password": "testpass123"})

        assert response.status_code == 302
        assert response.url == "/"
        assert client.session["active_role"] == "doctor"

    def test_login_user_without_roles_redirects_to_switch(self, client) -> None:
        """User with no roles redirects to switch-role (edge case)."""
        User.objects.create_user(username="norole@test.com", password="testpass123")

        response = client.post(reverse("login"), {"username": "norole@test.com", "password": "testpass123"})

        assert response.status_code == 302
        assert response.url == reverse("switch_role")


@pytest.mark.django_db
class TestLogoutView:
    """Tests for the logout view."""

    def test_logout_redirects_to_login(self, client) -> None:
        """POST /logout/ logs out and redirects to /login/."""
        user = User.objects.create_user(username="logout@test.com", password="testpass123")
        client.force_login(user)

        response = client.post(reverse("logout"))

        assert response.status_code == 302
        assert response.url == reverse("login")


@pytest.mark.django_db
class TestSwitchRoleView:
    """Tests for the switch-role view."""

    def test_switch_role_page_renders(self, client) -> None:
        """GET /switch-role/ renders role selection page."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="switch@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        response = client.get(reverse("switch_role"))

        assert response.status_code == 200

    def test_switch_role_valid_role(self, client) -> None:
        """POST with valid role sets active_role in session and redirects to /."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="valid@test.com", password="testpass123")
        role_nir, _ = Role.objects.get_or_create(name="nir")
        role_doctor, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role_nir, role_doctor)
        client.force_login(user)

        response = client.post(reverse("switch_role"), {"role": "nir"})

        assert response.status_code == 302
        assert response.url == "/"
        assert client.session["active_role"] == "nir"

    def test_switch_role_invalid_role(self, client) -> None:
        """POST with role not assigned to user rejects."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="invalid@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        response = client.post(reverse("switch_role"), {"role": "nir"})

        assert response.status_code == 200  # re-renders with error
        content = response.content.decode()
        assert "inválido" in content.lower() or "erro" in content.lower()

    def test_switch_role_requires_login(self, client) -> None:
        """GET /switch-role/ without auth redirects to login."""
        response = client.get(reverse("switch_role"))

        assert response.status_code == 302
        assert "login" in response.url


@pytest.mark.django_db
class TestHomeView:
    """Tests for the home view (GET /)."""

    def test_home_redirects_to_intake_for_nir(self, client) -> None:
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nirredir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get("/")
        assert response.status_code == 302
        assert response.url == reverse("intake:home")

    def test_home_redirects_to_switch_role_when_no_role(self, client) -> None:
        user = User.objects.create_user(username="norolehome@test.com", password="testpass123")
        client.force_login(user)

        response = client.get("/")
        assert response.status_code == 302
        assert "/switch-role/" in response.url

    def test_home_redirects_scheduler_to_queue(self, client) -> None:
        from apps.accounts.models import Role

        user = User.objects.create_user(username="schedredir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="scheduler")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        response = client.get("/")
        assert response.status_code == 302
        assert response.url == reverse("scheduler:queue")

    def test_home_redirects_to_doctor_queue(self, client) -> None:
        from apps.accounts.models import Role

        user = User.objects.create_user(username="docredir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/")
        assert response.status_code == 302
        assert response.url == reverse("doctor:queue")

    def test_home_without_role_redirects_to_switch(self, client) -> None:
        """GET / without active_role redirects to /switch-role/."""
        user = User.objects.create_user(username="homeless@test.com", password="testpass123")
        client.force_login(user)

        response = client.get("/")

        # Middleware ou view deve redirecionar para switch-role
        assert response.status_code == 302
        assert "/switch-role/" in response.url

    def test_home_shows_role_name(self, client) -> None:
        """GET / redirects nir to intake:home, which renders with role display."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nirhome@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        # home_view redirects nir to intake:home
        response = client.get("/", follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert "NIR" in content

    def test_home_redirects_by_role_shows_display(self, client) -> None:
        """GET / with active_role='nir' redirects to intake:home showing role 'NIR'."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nirhome2@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        # home_view redirects nir to intake:home
        response = client.get("/", follow=True)
        assert response.status_code == 200
        assert "NIR" in response.content.decode()

    def test_home_requires_login(self, client) -> None:
        """GET / without authentication redirects to login."""
        response = client.get("/")

        assert response.status_code == 302
        assert "/login/" in response.url
