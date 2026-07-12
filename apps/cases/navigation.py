"""Shared navigation helpers for safe URL resolution across apps."""

from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme


def resolve_safe_next_url(request: HttpRequest, fallback_url: str, *, param_name: str = "next") -> str:
    """Return a same-host next URL from query string or the fallback URL.

    Rules:
    - Read ``request.GET.get(param_name, "")``.
    - Accept only URLs considered safe by ``url_has_allowed_host_and_scheme``.
    - Use ``allowed_hosts={request.get_host()}``.
    - Use ``require_https=request.is_secure()``.
    - Return ``fallback_url`` when ``next`` is absent, empty, external,
      protocol-relative (``//evil``) or unsafe.
    - Always returns ``str``, never ``None``.
    """
    raw_next = request.GET.get(param_name, "")
    if raw_next and url_has_allowed_host_and_scheme(
        url=raw_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return raw_next
    return fallback_url
