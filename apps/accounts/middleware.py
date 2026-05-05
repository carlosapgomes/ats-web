"""ActiveRoleMiddleware ensures a role is active for authenticated users."""

from django.shortcuts import redirect

EXEMPT_PATHS = {"/login/", "/logout/", "/switch-role/"}


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
