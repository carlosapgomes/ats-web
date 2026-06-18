"""Password reset views with rate limiting and custom email context.

Uses Django native PasswordResetView/Done/Confirm/Complete views
with custom templates and rate limiting on POST.
"""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.urls import reverse

from .models import User

# Rate limit cache prefix
RATE_LIMIT_CACHE_PREFIX = "pwreset_rate_limit"
# Public role names — users with any of these get PUBLIC_APP_BASE_URL
PUBLIC_ROLE_NAMES = {"doctor", "manager", "admin"}


def get_account_action_base_url(user: User) -> str:
    """Return the appropriate base URL for account action emails.

    Users with any public role (doctor, manager, admin) get the public URL.
    Users with only restricted roles (nir, scheduler) get the internal URL.
    """
    role_names = set(user.roles.values_list("name", flat=True))
    if role_names & PUBLIC_ROLE_NAMES:
        return settings.PUBLIC_APP_BASE_URL
    return settings.INTERNAL_APP_BASE_URL


def _is_rate_limited(ip: str, email: str) -> bool:
    """Check if this request is rate limited.

    Rate limiting keyed by IP and normalized email.
    Returns True if rate limited.
    """
    limit = settings.PASSWORD_RESET_RATE_LIMIT
    window = settings.PASSWORD_RESET_RATE_WINDOW

    email_key = f"{RATE_LIMIT_CACHE_PREFIX}:email:{email.lower().strip()}"
    ip_key = f"{RATE_LIMIT_CACHE_PREFIX}:ip:{ip}"

    email_count = cache.get(email_key, 0)
    ip_count = cache.get(ip_key, 0)

    if email_count >= limit or ip_count >= limit:
        return True

    # Increment counters
    cache.set(email_key, email_count + 1, window)
    cache.set(ip_key, ip_count + 1, window)

    return False


class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    """PasswordResetView with rate limiting and custom email context."""

    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.html"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = "password_reset_done"
    from_email = None  # Will use DEFAULT_FROM_EMAIL

    def form_valid(self, form):  # type: ignore[no-untyped-def]
        """Apply rate limiting before processing the form.

        If rate limited, still redirect to done page (no enumeration).
        """
        ip = self.get_client_ip()
        email = form.cleaned_data.get("email", "")

        if _is_rate_limited(ip, email):
            # Silently ignore: redirect to done page without sending email
            return super(auth_views.PasswordResetView, self).form_valid(form)

        return super().form_valid(form)

    def get_client_ip(self) -> str:
        """Extract client IP from request, respecting proxy headers."""
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
        if x_forwarded_for:
            return str(x_forwarded_for.split(",")[0].strip())
        return str(self.request.META.get("REMOTE_ADDR", "127.0.0.1"))

    def get_success_url(self) -> str:
        """Return the URL to redirect to after successful form submission."""
        return str(reverse(self.success_url))

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add site domain to context for email template."""
        context = super().get_context_data(**kwargs)
        user = context.get("user")
        if user and user.is_authenticated:
            # Use user's roles to determine base URL
            context["base_url"] = get_account_action_base_url(user)
        else:
            context["base_url"] = settings.PUBLIC_APP_BASE_URL
        return context


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """PasswordResetDoneView with custom template."""

    template_name = "accounts/password_reset_done.html"


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """PasswordResetConfirmView with custom template."""

    template_name = "accounts/password_reset_confirm.html"
    success_url = "password_reset_complete"

    def get_success_url(self) -> str:
        """Return the resolved URL for success redirect."""
        return reverse(self.success_url)


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """PasswordResetCompleteView with custom template."""

    template_name = "accounts/password_reset_complete.html"
