"""Tests for profile and password change flow (Slice 002).

TDD: These tests must fail before implementation and pass after.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestProfileAccess:
    """R1: Profile requires authentication and shows basic data."""

    def test_profile_requires_login(self, client) -> None:
        """Anonymous user is redirected to login when accessing profile."""
        url = reverse("profile")
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_authenticated_user_can_view_profile(self, client) -> None:
        """Logged in user can view profile with basic user data."""
        User.objects.create_user(username="jose", password="pass123!")
        assert client.login(username="jose", password="pass123!")
        response = client.get(reverse("profile"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "jose" in content


@pytest.mark.django_db
class TestBaseNavigationLink:
    """R2: Base template links to profile when authenticated."""

    def test_base_navigation_links_to_profile(self, client) -> None:
        """When authenticated, base template contains link to profile."""
        user = User.objects.create_user(username="navuser", password="pass123!")
        client.force_login(user)
        # Use profile page (authenticated, renders base template)
        response = client.get(reverse("profile"))
        assert response.status_code == 200
        content = response.content.decode()
        # Should contain a link to the profile URL
        profile_url = reverse("profile")
        assert profile_url in content


@pytest.mark.django_db
class TestPasswordChange:
    """R3/R4: Password change with current password and session preservation."""

    def test_password_change_requires_current_password(self, client) -> None:
        """Wrong current password does not change password and shows error."""
        User.objects.create_user(username="changetest", password="OldPass123!")
        assert client.login(username="changetest", password="OldPass123!")

        response = client.post(
            reverse("password_change"),
            {
                "old_password": "WrongPass456!",
                "new_password1": "NewPass789!",
                "new_password2": "NewPass789!",
            },
        )
        assert response.status_code == 200  # Form re-rendered with errors
        content = response.content.decode()
        # Should show error about wrong password
        assert "erro" in content.lower() or "incorreta" in content.lower() or "inválida" in content.lower()

    def test_password_change_success_keeps_current_session(self, client) -> None:
        """Successful password change preserves current session."""
        User.objects.create_user(username="sessuser", password="OldPass123!")
        assert client.login(username="sessuser", password="OldPass123!")

        response = client.post(
            reverse("password_change"),
            {
                "old_password": "OldPass123!",
                "new_password1": "NewStr0ng!Pass",
                "new_password2": "NewStr0ng!Pass",
            },
        )
        # After success, should redirect to done page
        assert response.status_code == 302
        done_url = reverse("password_change_done")
        assert done_url in response.url

        # Follow redirect
        response = client.get(done_url)
        assert response.status_code == 200

        # Next request should still be authenticated (session preserved)
        response = client.get(reverse("profile"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "sessuser" in content

    def test_password_change_old_password_fails_new_password_works(self, client) -> None:
        """After change, login with old password fails and new password works."""
        User.objects.create_user(username="oldnewuser", password="OldPass123!")
        assert client.login(username="oldnewuser", password="OldPass123!")

        # Change password
        client.post(
            reverse("password_change"),
            {
                "old_password": "OldPass123!",
                "new_password1": "NewStr0ng!Pass",
                "new_password2": "NewStr0ng!Pass",
            },
        )

        # Logout
        client.logout()

        # Login with old password should fail
        assert not client.login(username="oldnewuser", password="OldPass123!")

        # Login with new password should work
        assert client.login(username="oldnewuser", password="NewStr0ng!Pass")


@pytest.mark.django_db
class TestPasswordVisibilityToggle:
    """R5: Password change form has show/hide password toggle."""

    def test_password_change_form_has_password_visibility_toggle(self, client) -> None:
        """Password change page has toggle elements for all password fields."""
        User.objects.create_user(username="toguser", password="OldPass123!")
        assert client.login(username="toguser", password="OldPass123!")

        response = client.get(reverse("password_change"))
        assert response.status_code == 200
        content = response.content.decode()
        # Should reference the password visibility toggle JavaScript
        assert "toggle" in content.lower() or "mostrar" in content.lower()
        # Should load the password-toggle.js script
        assert "password-toggle.js" in content
