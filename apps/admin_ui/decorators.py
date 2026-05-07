"""Decorators for admin_ui views.

admin_or_manager_required: permite manager (read-only) e admin (full access).
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def admin_or_manager_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Decorator que permite acesso apenas para admin e manager.

    Manager pode acessar views de leitura (user_list).
    Admin pode acessar todas as views (create, update, block, unblock).
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        active_role = request.session.get("active_role")
        if active_role not in ("admin", "manager"):
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect("/")
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Decorator que permite acesso apenas para admin."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        active_role = request.session.get("active_role")
        if active_role != "admin":
            messages.error(request, "Apenas administradores podem realizar esta ação.")
            return redirect("/")
        return view_func(request, *args, **kwargs)

    return wrapper
