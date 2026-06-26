"""Tests for the authenticated user manual page (/manual/) and header link."""

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class TestUserManualPage:
    """Tests for the /manual/ route and its behavior."""

    @pytest.mark.django_db
    def test_user_manual_requires_login(self, client) -> None:
        """GET /manual/ anonymous redirects to login."""
        url = reverse("user_manual")
        response = client.get(url)
        # login_required redirects to /login/?next=/manual/
        assert response.status_code == 302
        assert "/login/" in response.url

    @pytest.mark.django_db
    def test_authenticated_user_can_open_manual(self, client) -> None:
        """Authenticated user with any role can access /manual/ (200)."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get(reverse("user_manual"))
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_manual_page_uses_official_markdown_source(self, client, monkeypatch) -> None:
        """The view reads from docs/manual/manual-usuarios.md.

        We monkeypatch the read function to prove the view calls it.
        """
        original_path = Path(settings.BASE_DIR) / "docs" / "manual" / "manual-usuarios.md"

        # First verify the real file exists
        assert original_path.exists(), f"Official manual source not found at {original_path}"

        # Monkeypatch to return known content
        def mock_read(path=None):
            return "# Manual Testado\n\nConteúdo mockado."

        monkeypatch.setattr(
            "apps.accounts.manual.read_user_manual_markdown",
            mock_read,
        )

        from apps.accounts.models import Role

        user = User.objects.create_user(username="doc@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(reverse("user_manual"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Manual Testado" in content

    def test_manual_renderer_escapes_raw_html(self) -> None:
        """The Markdown renderer escapes raw HTML tags."""
        from apps.accounts.manual import render_manual_markdown_to_html

        malicious_md = "# Título\n\n<script>alert(1)</script>\n\n<p>normal</p>\n\n```\ncode\n```"
        result = render_manual_markdown_to_html(malicious_md)

        # The <script> tag should NOT appear as a raw executable tag
        assert "<script>" not in result or "&lt;script&gt;" in result

        # The text "alert(1)" should be present (escaped or not stripped)
        assert "alert(1)" in result

        # The heading should still render
        assert "Título" in result

        # "normal" text should be present
        assert "normal" in result


class TestUserManualHeaderLink:
    """Tests for the Manual link in the header (base.html)."""

    @pytest.mark.django_db
    def test_header_shows_manual_link_for_authenticated_user(self, client) -> None:
        """Header for authenticated user contains Manual link with target=_blank and rel=noopener."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)

        session = client.session
        session["active_role"] = "nir"
        session.save()

        # Navigate to a page that uses base.html
        response = client.get("/", follow=True)
        assert response.status_code == 200
        content = response.content.decode()

        # Must contain the Manual link
        assert "Manual" in content
        # Must contain the URL
        manual_url = reverse("user_manual")
        assert manual_url in content
        # Must open in new tab
        assert 'target="_blank"' in content
        # Must have rel="noopener"
        assert 'rel="noopener"' in content

    def test_header_does_not_show_manual_link_for_anonymous_login_page(self, client) -> None:
        """Login page (anonymous) does NOT show the authenticated Manual link."""
        response = client.get(reverse("login"))
        assert response.status_code == 200
        content = response.content.decode()

        # The Manual link should NOT be present for anonymous users
        manual_url = reverse("user_manual")
        assert manual_url not in content
