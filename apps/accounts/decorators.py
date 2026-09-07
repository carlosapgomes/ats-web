"""Decorators for the accounts app."""

from collections.abc import Callable
from functools import wraps
from typing import Concatenate, cast

from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import redirect

from apps.accounts.services import can_access_followup


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


def followup_access_required[**P, R](
    view_func: Callable[Concatenate[HttpRequest, P], R],
) -> Callable[Concatenate[HttpRequest, P], R]:
    """Exige a política CHD (D1). Empilhar após @login_required +
    @role_required("manager", "admin"). Sem acesso: flash + redirect("/").

    Consome ``can_access_followup`` (apps.accounts.services) — não há segunda
    implementação da composição (papel ativo + posse do papel scheduler).
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> R:
        active_role = request.session.get("active_role") or ""
        if not can_access_followup(request.user, active_role):
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return cast(R, redirect("/"))
        return view_func(request, *args, **kwargs)

    return cast(Callable[Concatenate[HttpRequest, P], R], wrapper)
