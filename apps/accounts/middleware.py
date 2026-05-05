"""Middlewares for the accounts app."""

import ipaddress
import logging

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

INTRANET_RESTRICTED_ROLES = {"nir", "scheduler"}

EXEMPT_PATHS = {"/login/", "/logout/", "/switch-role/"}


def _get_client_ip(request):  # type: ignore[no-untyped-def]
    """Extrai IP real do cliente do header configurado ou REMOTE_ADDR."""
    header = getattr(settings, "TRUSTED_PROXY_HEADER", None)
    if header:
        value = request.META.get(header, "")
        if value:
            # X-Forwarded-For pode ter múltiplos IPs; pegar o primeiro
            return value.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _is_intranet_ip(client_ip):  # type: ignore[no-untyped-def]
    """Verifica se o IP está dentro do range da intranet."""
    ip_range = getattr(settings, "INTRANET_IP_RANGE", None)
    if not ip_range:
        # Se não configurado, bloquear papéis restritos por segurança
        return False
    try:
        network = ipaddress.ip_network(ip_range, strict=False)
        addr = ipaddress.ip_address(client_ip)
        return addr in network
    except (ValueError, TypeError):
        return False


class IntranetGuardMiddleware:
    """Bloqueia acesso de papéis restritos (nir, scheduler) fora da intranet."""

    def __init__(self, get_response):  # type: ignore[no-untyped-def]
        self.get_response = get_response

    def __call__(self, request):  # type: ignore[no-untyped-def]
        if request.user.is_authenticated:
            active_role = request.session.get("active_role")
            if active_role in INTRANET_RESTRICTED_ROLES:
                client_ip = _get_client_ip(request)  # type: ignore[no-untyped-call]
                if not _is_intranet_ip(client_ip):  # type: ignore[no-untyped-call]
                    logger.warning(
                        "intranet_guard_blocked user=%s role=%s ip=%s path=%s",
                        request.user.pk,
                        active_role,
                        client_ip,
                        request.path,
                    )
                    return HttpResponseForbidden("Acesso restrito à rede interna do hospital.")
        return self.get_response(request)


class ActiveRoleMiddleware:
    """Garante papel ativo na sessão para usuários autenticados.

    Se o usuário está autenticado mas não tem active_role na sessão:
    - Se tem exatamente 1 role: auto-set
    - Se tem N > 1 roles: redireciona para /switch-role/
    """

    def __init__(self, get_response):  # type: ignore[no-untyped-def]
        self.get_response = get_response

    def __call__(self, request):  # type: ignore[no-untyped-def]
        if (
            request.user.is_authenticated
            and "active_role" not in request.session
            and request.path not in EXEMPT_PATHS
            and not request.path.startswith("/admin/")
            and not request.path.startswith("/static/")
        ):
            roles = list(request.user.roles.values_list("name", flat=True))
            if len(roles) == 1:
                request.session["active_role"] = roles[0]
            elif len(roles) > 1:
                return redirect("/switch-role/")
        return self.get_response(request)
