"""Tests for template rendering and structure."""

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import get_template

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


@pytest.mark.django_db
class TestAuthenticatedTemplate:
    """Tests that verify authenticated user elements in templates."""

    def test_authenticated_user_sees_role_badge(self, client) -> None:
        """Navbar shows role badge for authenticated users."""
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
        """Navbar has logout form/button for authenticated users."""
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
        """Navbar shows 'Trocar papel' link when user has multiple roles."""
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
        """Navbar does NOT show 'Trocar papel' when user has only 1 role."""
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
