"""Password reset views with rate limiting on POST.

Uses Django native PasswordResetView/Done/Confirm/Complete views
with custom templates and rate limiting on POST.
"""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.urls import reverse

# Rate limit cache prefix
RATE_LIMIT_CACHE_PREFIX = "pwreset_rate_limit"


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
    """PasswordResetView with rate limiting on POST."""

    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.html"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = "password_reset_done"

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
