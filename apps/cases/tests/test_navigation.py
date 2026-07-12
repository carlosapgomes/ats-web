"""Tests for the shared navigation helper resolve_safe_next_url."""

import pytest
from django.http import HttpRequest, QueryDict

from apps.cases.navigation import resolve_safe_next_url


@pytest.mark.django_db
class TestResolveSafeNextUrl:
    """Tests for resolve_safe_next_url shared helper."""

    def _make_request(self, host: str = "testserver", secure: bool = False, query_string: str = "") -> HttpRequest:
        """Create a minimal HttpRequest with the given host, secure flag and query string."""
        request = HttpRequest()
        request.META["SERVER_NAME"] = host
        request.META["SERVER_PORT"] = "443" if secure else "80"
        request.META["HTTP_HOST"] = host
        if secure:
            request.META["HTTPS"] = "on"
        # Build GET from the query string so it's mutable for testing
        request.GET = QueryDict(query_string, mutable=False)
        return request

    def test_returns_fallback_for_missing_next(self) -> None:
        """Returns fallback when next is missing from query string."""
        request = self._make_request()
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == fallback

    def test_returns_fallback_for_empty_next(self) -> None:
        """Returns fallback when next is an empty string."""
        request = self._make_request(query_string="next=")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == fallback

    def test_returns_fallback_for_external_url(self) -> None:
        """Returns fallback when next is an external URL."""
        request = self._make_request(query_string="next=https://evil.example.com/phish")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == fallback, f"Expected fallback, got {result!r}"

    def test_returns_fallback_for_protocol_relative_url(self) -> None:
        """Returns fallback when next is a protocol-relative URL (//evil)."""
        request = self._make_request(query_string="next=//evil.example.com/phish")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == fallback, f"Expected fallback, got {result!r}"

    def test_accepts_same_host_absolute_url(self) -> None:
        """Returns the same-host absolute URL when next is safe."""
        request = self._make_request(query_string="next=/some/internal/path/")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == "/some/internal/path/", f"Expected internal path, got {result!r}"

    def test_uses_custom_param_name(self) -> None:
        """Uses a custom param_name instead of default 'next'."""
        request = self._make_request(query_string="redirect_to=/custom/path/")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback, param_name="redirect_to")
        assert result == "/custom/path/", f"Expected custom path, got {result!r}"

    def test_returns_string_never_none(self) -> None:
        """Always returns str, never None."""
        request = self._make_request()
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert isinstance(result, str)
        assert result == fallback

    def test_rejects_ftp_url(self) -> None:
        """Returns fallback when next is an ftp URL."""
        request = self._make_request(query_string="next=ftp://evil.example.com/file")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == fallback

    def test_accepts_same_host_secure_url(self) -> None:
        """Returns the same-host URL even with secure request."""
        request = self._make_request(secure=True, query_string="next=/internal/path/")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == "/internal/path/"

    def test_rejects_external_with_secure_request(self) -> None:
        """Returns fallback when next is external and request is secure."""
        request = self._make_request(secure=True, query_string="next=https://evil.com/phish")
        fallback = "/fallback/"
        result = resolve_safe_next_url(request, fallback)
        assert result == fallback
