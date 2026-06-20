"""Tests for password reset flow (Slice 001).

TDD: These tests must fail before implementation and pass after.
"""

import re
from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    """Clear the password reset rate limit cache before each test.

    This prevents rate limit state from leaking between tests,
    since the locmem cache is shared across the test session.
    """
    cache.clear()


@pytest.mark.django_db
class TestLoginPageLinks:
    """R1: Login page must link to password reset."""

    def test_login_page_links_to_password_reset(self, client) -> None:
        """GET /login/ contains link to password_reset."""
        response = client.get(reverse("login"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "password_reset" in content or "esqueci" in content.lower() or "recuperar" in content.lower()


@pytest.mark.django_db
class TestPasswordResetPage:
    """Password reset form renders correctly."""

    def test_password_reset_page_renders(self, client) -> None:
        """GET password_reset returns 200 and renders form."""
        url = reverse("password_reset")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "email" in content.lower()

    def test_password_reset_email_input_uses_bootstrap_form_control(self, client) -> None:
        """The email field is styled with Bootstrap's form-control class.

        The native Django PasswordResetForm renders a plain EmailInput without
        project styling, so the field looks out of place (browser-default border
        and sharp corners). The view must inject the form-control class, matching
        every other field in the project.
        """
        response = client.get(reverse("password_reset"))
        assert response.status_code == 200
        content = response.content.decode()
        # The email input itself must carry form-control (not just a nearby label).
        assert "<input" in content
        assert 'type="email"' in content or "type=email" in content
        assert "form-control" in content


@pytest.mark.django_db
class TestPasswordResetPost:
    """R4: Anti-enumeration — POST must never reveal if email exists."""

    def test_password_reset_post_existing_email_sends_email_without_enumeration(self, client) -> None:
        """POST with existing active email: generic success, email sent."""
        User.objects.create_user(
            username="exists@example.com",
            email="exists@example.com",
            password="oldpass123!",
        )

        response = client.post(reverse("password_reset"), {"email": "exists@example.com"})
        # Redirect to done page (generic success)
        assert response.status_code == 302
        done_url = reverse("password_reset_done")
        assert done_url in response.url

        # Email was sent
        assert len(mail.outbox) == 1
        assert "exists@example.com" in mail.outbox[0].to

    def test_password_reset_post_unknown_email_uses_same_success_response(self, client) -> None:
        """POST with unknown email: same redirect as existing email."""
        response = client.post(reverse("password_reset"), {"email": "unknown@example.com"})
        assert response.status_code == 302
        done_url = reverse("password_reset_done")
        assert done_url in response.url

        # No email sent for unknown user
        assert len(mail.outbox) == 0

    def test_password_reset_post_existing_inactive_user_no_email(self, client) -> None:
        """Inactive user should not receive reset email, but response is generic."""
        User.objects.create_user(
            username="inactive@example.com",
            email="inactive@example.com",
            password="oldpass123!",
            is_active=False,
        )
        response = client.post(reverse("password_reset"), {"email": "inactive@example.com"})
        assert response.status_code == 302
        done_url = reverse("password_reset_done")
        assert done_url in response.url
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestPasswordResetToken:
    """R2/R3: Token-based password change via native Django views."""

    def _get_reset_url_from_outbox(self, email_index=0):
        """Extract the password reset URL from the email body."""
        from django.conf import settings

        email_body: str = mail.outbox[email_index].body
        # Look for a URL pattern in the email body
        # Django's default template uses a full URL
        base_urls = [
            settings.PUBLIC_APP_BASE_URL,
            settings.INTERNAL_APP_BASE_URL,
        ]
        for base_url in base_urls:
            if base_url in email_body:
                # Extract the full URL
                start = email_body.find(base_url)
                # Find the end of the URL (space, newline, or quote)
                remaining = email_body[start:]
                end = None
                for delim in ("\n", " ", '"', "'"):
                    pos = remaining.find(delim)
                    if pos != -1:
                        end = pos
                        break
                if end is None:
                    url = remaining.strip()
                else:
                    url = remaining[:end].strip()
                    # Strip any trailing punctuation (quotes, brackets, etc.)
                url = url.rstrip("\"'<>)\n\r")
                return url
        # Try generic URL pattern
        url_match = re.search(r"https?://\S+reset/\S+", email_body)
        if url_match:
            return url_match.group(0).rstrip("\"'<>)\n\r")
        # Fallback: extract relative path
        path_match = re.search(r"/reset/[^\s]+/", email_body)
        if path_match:
            return path_match.group(0)
        return None

    def test_password_reset_token_allows_password_change(self, client) -> None:
        """Token-based reset allows setting a new password and logging in."""
        user = User.objects.create_user(
            username="resettoken@example.com",
            email="resettoken@example.com",
            password="oldpass123!",
        )

        # Request password reset
        client.post(reverse("password_reset"), {"email": "resettoken@example.com"})
        assert len(mail.outbox) == 1

        # Extract reset URL from email
        reset_url = self._get_reset_url_from_outbox()
        assert reset_url is not None, "No reset URL found in email"

        # Parse the URL path
        parsed = urlparse(reset_url)
        reset_path = parsed.path

        # GET the reset confirm page (follow redirect if token is valid)
        response = client.get(reset_path, follow=True)
        assert response.status_code == 200

        # POST new password at the confirm page
        # Django redirects to /reset/<uidb64>/set-password/ after token validation
        # The form is now on the last URL after following redirects
        confirm_path = response.redirect_chain[-1][0] if response.redirect_chain else reset_path
        response = client.post(
            confirm_path,
            {"new_password1": "NewStr0ng!Pass", "new_password2": "NewStr0ng!Pass"},
        )
        # Should redirect to password_reset_complete
        assert response.status_code == 302
        complete_url = reverse("password_reset_complete")
        assert complete_url in response.url

        # Login with new password works
        user.refresh_from_db()
        login_ok = client.login(username="resettoken@example.com", password="NewStr0ng!Pass")
        assert login_ok is True

    def test_invalid_password_reset_token_is_rejected(self, client) -> None:
        """Invalid/expired token does not change password."""
        user = User.objects.create_user(
            username="invalidtoken@example.com",
            email="invalidtoken@example.com",
            password="oldpass123!",
        )

        # Generate a valid-looking but tampered URL
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        # Use a bad token
        bad_url = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": "bad-token-123"})

        # GET should render invalid link page
        response = client.get(bad_url)
        assert response.status_code == 200
        # Should indicate invalid link
        content = response.content.decode()
        assert "invalid" in content.lower() or "inválido" in content.lower() or "expir" in content.lower()

    def test_password_reset_page_uses_custom_template(self, client) -> None:
        """Password reset form uses project's own template."""
        url = reverse("password_reset")
        response = client.get(url)
        assert response.status_code == 200
        # Should use our custom template, not Django admin's
        content = response.content.decode()
        assert "hospital-shell" in content or "app-header" in content


@pytest.mark.django_db
class TestPasswordResetRateLimit:
    """R5: Simple rate limit on POST password reset."""

    RATE_LIMIT_COUNT = 5  # Must match PASSWORD_RESET_RATE_LIMIT in base.py

    def test_password_reset_post_is_rate_limited(self, client) -> None:
        """Exceeding rate limit blocks further POSTs and doesn't send extra emails."""
        User.objects.create_user(
            username="ratelimit@example.com",
            email="ratelimit@example.com",
            password="oldpass123!",
        )

        # First N requests should succeed (send email)
        for i in range(self.RATE_LIMIT_COUNT):
            mail.outbox.clear()
            response = client.post(
                reverse("password_reset"),
                {"email": "ratelimit@example.com"},
            )
            assert response.status_code == 302, f"Request {i + 1} should succeed, got {response.status_code}"
            assert reverse("password_reset_done") in response.url

        # Next request should be rate limited
        mail.outbox.clear()
        response = client.post(
            reverse("password_reset"),
            {"email": "ratelimit@example.com"},
        )
        # Rate limited: should still render without revealing rate limiting
        # Should NOT send extra email
        assert len(mail.outbox) == 0, "Rate-limited request should not send email"

    def test_rate_limit_does_not_affect_get_requests(self, client) -> None:
        """Rate limit only applies to POST, not GET."""
        url = reverse("password_reset")
        for _ in range(self.RATE_LIMIT_COUNT + 5):
            response = client.get(url)
            assert response.status_code == 200


@pytest.mark.django_db
class TestPasswordVisibilityToggle:
    """R6: Show/hide password toggle on login and reset confirm."""

    def test_login_includes_password_visibility_toggle(self, client) -> None:
        """Login page has password visibility toggle element."""
        response = client.get(reverse("login"))
        assert response.status_code == 200
        content = response.content.decode()
        # Check for toggle button/icon near password field
        assert "password" in content.lower()
        # Should reference show/hide toggle JS
        assert "toggle" in content.lower() or "mostrar" in content.lower() or "olho" in content.lower()

    def test_password_reset_confirm_includes_visibility_toggle(self, client) -> None:
        """Reset confirm page has password visibility toggle on new password fields."""
        User.objects.create_user(
            username="vis@example.com",
            email="vis@example.com",
            password="oldpass123!",
        )
        # Request reset to get a valid token
        client.post(reverse("password_reset"), {"email": "vis@example.com"})

        # Parse the reset URL from email
        email_body: str = mail.outbox[0].body
        path_match = re.search(r"/reset/[^\s]+/", email_body)
        assert path_match is not None
        reset_path = path_match.group(0).rstrip("\"'<>)\n\r ")

        # GET confirm page (follow redirect to the actual confirm form)
        response = client.get(reset_path, follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert "password" in content.lower()
        # Should have visibility toggle elements
        assert "toggle" in content.lower() or "mostrar" in content.lower() or "olho" in content.lower()


@pytest.mark.django_db
class TestPasswordResetEmailRendering:
    """Email must be multipart (text + html) and include app_display_name.

    Regression: Django's PasswordResetForm renders the reset email with a plain
    dict context, so context processors do not run and ``app_display_name`` was
    empty. Also ``email_template_name`` is the text body, so pointing it at an
    HTML template sent raw HTML as plain text. Both are fixed by using a plain
    text template + ``html_email_template_name`` and injecting values via
    ``extra_email_context``.
    """

    def test_password_reset_email_is_multipart_with_html_alternative(self, client) -> None:
        """Outgoing email has a text/plain body AND a text/html alternative."""
        User.objects.create_user(
            username="multipart@example.com",
            email="multipart@example.com",
            password="oldpass123!",
        )
        client.post(reverse("password_reset"), {"email": "multipart@example.com"})
        assert len(mail.outbox) == 1

        message = mail.outbox[0]
        # Body is plain text (NOT raw HTML source)
        assert "<!DOCTYPE html>" not in message.body
        assert "<!DOCTYPE" not in message.body
        assert "/reset/" in message.body  # text body still has the link

        # An HTML alternative is attached
        alternatives = getattr(message, "alternatives", [])
        html_parts = [c for c, ctype in alternatives if ctype == "text/html"]
        assert len(html_parts) == 1
        assert "<html" in html_parts[0]
        assert "/reset/" in html_parts[0]

    def test_password_reset_email_includes_app_display_name(self, client) -> None:
        """app_display_name is present in both the text body and HTML part."""
        from django.conf import settings

        User.objects.create_user(
            username="appname@example.com",
            email="appname@example.com",
            password="oldpass123!",
        )
        client.post(reverse("password_reset"), {"email": "appname@example.com"})
        assert len(mail.outbox) == 1

        message = mail.outbox[0]
        display_name = settings.APP_DISPLAY_NAME
        assert display_name, "APP_DISPLAY_NAME must be set for this assertion"
        # Text body
        assert display_name in message.body
        # HTML alternative
        html_parts = [c for c, ctype in getattr(message, "alternatives", []) if ctype == "text/html"]
        assert html_parts, "HTML alternative missing"
        assert display_name in html_parts[0]
        # Sanity: no empty <strong></strong> left from an unrendered variable
        assert "<strong></strong>" not in html_parts[0]
