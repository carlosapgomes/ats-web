"""Profile and password change views (Slice 002).

Uses Django native PasswordChangeView with custom templates
and session preservation via update_session_auth_hash.
"""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def profile_view(request):  # type: ignore[no-untyped-def]
    """Render the profile page with basic user data."""
    user = request.user
    roles = list(user.roles.values_list("name", flat=True))
    active_role = request.session.get("active_role", "")
    return render(
        request,
        "accounts/profile.html",
        {
            "user_roles": roles,
            "active_role": active_role,
        },
    )


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    """PasswordChangeView with custom template and session preservation.

    Django's PasswordChangeView automatically calls
    update_session_auth_hash() on successful password change,
    preserving the current session.
    """

    template_name = "accounts/password_change_form.html"
    success_url = "password_change_done"

    def get_success_url(self) -> str:
        """Return the resolved URL for success redirect."""
        from django.urls import reverse

        return reverse(self.success_url)
