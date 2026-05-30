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
    """Verifica se o IP está dentro de qualquer range da intranet.

    INTRANET_IP_RANGE suporta múltiplos ranges separados por vírgula:
        "127.0.0.0/8,192.168.15.0/24"
    """
    ip_range = getattr(settings, "INTRANET_IP_RANGE", None)
    if not ip_range:
        # Se não configurado, bloquear papéis restritos por segurança
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except (ValueError, TypeError):
        return False
    for cidr in ip_range.split(","):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if addr in network:
                return True
        except (ValueError, TypeError):
            continue
    return False


class IntranetGuardMiddleware:
    """Bloqueia acesso de papéis restritos (nir, scheduler) fora da intranet.

    Regras (em ordem):
    1. Não autenticado → passa
    2. active_role não é nir/scheduler → passa
    3. Path é EXEMPT (login, logout, switch-role) → passa
    4. Usuário tem qualquer papel não-restrito → passa (bypass multi-role)
    5. IP é intranet → passa
    6. Senão → 403
    """

    def __init__(self, get_response):  # type: ignore[no-untyped-def]
        self.get_response = get_response

    def __call__(self, request):  # type: ignore[no-untyped-def]
        if not request.user.is_authenticated:
            return self.get_response(request)

        active_role = request.session.get("active_role")
        if active_role not in INTRANET_RESTRICTED_ROLES:
            return self.get_response(request)

        # Exempt paths: login, logout, switch-role sempre acessíveis
        if request.path in EXEMPT_PATHS:
            return self.get_response(request)

        client_ip = _get_client_ip(request)  # type: ignore[no-untyped-call]

        # IP da intranet → acesso liberado independente dos papéis
        if _is_intranet_ip(client_ip):  # type: ignore[no-untyped-call]
            return self.get_response(request)

        # Bypass multi-role: se o usuário tem qualquer papel não-restrito,
        # não bloquear — ele pode acessar com papel elevado de qualquer lugar.
        try:
            user_roles = set(request.user.roles.values_list("name", flat=True))
        except ValueError:
            # Usuário sem pk (ex: instância não salva em testes).
            # Tratar como se tivesse apenas papéis restritos.
            user_roles = set()
        if user_roles - INTRANET_RESTRICTED_ROLES:
            return self.get_response(request)

        logger.warning(
            "intranet_guard_blocked user=%s role=%s ip=%s path=%s",
            request.user.pk,
            active_role,
            client_ip,
            request.path,
        )
        return HttpResponseForbidden("Acesso restrito à rede interna do hospital.")


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
