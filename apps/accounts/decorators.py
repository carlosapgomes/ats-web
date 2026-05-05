"""Decorators for the accounts app."""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def role_required(*allowed_roles: str):
    """Decorator que verifica se o active_role está entre os permitidos.

    Uso:
        @login_required
        @role_required("nir")
        def my_view(request): ...

        @login_required
        @role_required("doctor", "manager")
        def my_view(request): ...

    Nota: role_required NÃO substitui @login_required. Deve ser usado depois dele.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            active_role = request.session.get("active_role")
            if active_role not in allowed_roles:
                messages.error(request, "Você não tem permissão para acessar esta página.")
                return redirect("/")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
