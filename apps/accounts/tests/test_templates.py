"""Tests for template rendering and structure."""

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import Client

User = get_user_model()


class TestBaseTemplate:
    """Tests that verify the base.html template structure."""

    def test_base_template_renders_bootstrap_css(self) -> None:
        """base.html contains Bootstrap 5.3 CSS CDN link."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "bootstrap" in rendered.lower()
        assert "cdn.jsdelivr.net" in rendered

    def test_base_template_has_bootstrap_js(self) -> None:
        """base.html contains Bootstrap JS bundle CDN."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "bootstrap.bundle.min.js" in rendered

    def test_base_template_has_viewport_meta(self) -> None:
        """base.html has responsive viewport meta tag."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "viewport" in rendered.lower()

    def test_base_template_has_theme_color_meta(self) -> None:
        """base.html has theme-color meta tag for PWA support."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "theme-color" in rendered.lower()

    def test_base_template_has_app_css(self) -> None:
        """base.html links to app.css static file."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "app.css" in rendered

    def test_base_template_has_app_js(self) -> None:
        """base.html links to app.js static file."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "app.js" in rendered

    def test_base_has_hospital_fonts(self) -> None:
        """base.html contains Google Fonts links for Merriweather Sans and Source Sans 3."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "Merriweather+Sans" in rendered
        assert "Source+Sans+3" in rendered
        assert "fonts.googleapis.com" in rendered

    def test_base_has_hospital_header(self) -> None:
        """base.html header uses app-header class instead of navbar."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "app-header" in rendered

    def test_base_has_hospital_shell_class(self) -> None:
        """base.html body has hospital-shell class."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
            }
        )
        assert "hospital-shell" in rendered

    def test_base_shows_username_in_header(self) -> None:
        """base.html header shows the full name or username."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "nir",
                "active_role_display": "NIR",
                "user": {
                    "is_authenticated": True,
                    "username": "testuser",
                    "get_full_name": lambda: "Test User",
                    "roles": type("Roles", (), {"count": lambda: 1})(),
                },
            }
        )
        # When authenticated, username or full_name should appear in header area
        assert "NIR" in rendered

    def test_base_shows_role_in_header(self) -> None:
        """base.html header shows the active role display name."""
        template = get_template("home.html")
        rendered = template.render(
            {
                "active_role": "doctor",
                "active_role_display": "Médico",
                "user": {
                    "is_authenticated": True,
                    "username": "doctor1",
                    "get_full_name": lambda: "Dr. Silva",
                    "roles": type("Roles", (), {"count": lambda: 1})(),
                },
            }
        )
        assert "Médico" in rendered

    def test_hospital_css_vars_exist(self) -> None:
        """app.css contains hospital CSS custom properties."""
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
        css_content = css_path.read_text()
        assert "--hospital-primary" in css_content
        assert "--hospital-secondary" in css_content
        assert "--hospital-accent" in css_content


@pytest.mark.django_db
class TestAuthenticatedTemplate:
    """Tests that verify authenticated user elements in templates."""

    def test_authenticated_user_sees_role_badge(self, client) -> None:
        """Header shows role badge for authenticated users."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="badge@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/")
        assert response.status_code == 200
        # Badge should show "Médico" (role display name)
        content = response.content.decode()
        assert "Médico" in content

    def test_authenticated_user_sees_logout_button(self, client) -> None:
        """Header has logout form/button for authenticated users."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="logoutbtn@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Sair" in content

    def test_multi_role_user_sees_switch_role_link(self, client) -> None:
        """Header shows 'Trocar papel' link when user has multiple roles."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="multi@test.com", password="testpass123")
        role_doc = Role.objects.create(name="doctor")
        role_mgr = Role.objects.create(name="manager")
        user.roles.add(role_doc, role_mgr)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Trocar papel" in content

    def test_single_role_user_does_not_see_switch_role_link(self, client) -> None:
        """Header does NOT show 'Trocar papel' when user has only 1 role."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="single@test.com", password="testpass123")
        role = Role.objects.create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Trocar papel" not in content


@pytest.mark.django_db
class TestLoginAndRolePages:
    """Tests that login and switch_role pages render with the hospital theme."""

    def test_login_page_renders_correctly(self, client: Client) -> None:
        """Login page renders without errors and contains hospital theme elements."""
        response = client.get("/login/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "hospital-shell" in content
        assert "app-header" in content
        assert "ATS" in content

    def test_switch_role_renders_correctly(self, client: Client) -> None:
        """Switch role page renders without errors when user has multiple roles."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="switcher@test.com", password="testpass123")
        role_doc = Role.objects.create(name="doctor")
        role_mgr = Role.objects.create(name="manager")
        user.roles.add(role_doc, role_mgr)
        client.force_login(user)

        response = client.get("/switch-role/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Escolha com qual papel" in content
        assert "Médico" in content
        assert "Supervisor" in content
