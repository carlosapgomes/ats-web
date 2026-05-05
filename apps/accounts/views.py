"""Views for authentication: login, logout, and role switching."""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, RoleSelectForm


def login_view(request):  # type: ignore[no-untyped-def]
    """Handle GET (render form) and POST (authenticate) for login."""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

                roles = list(user.roles.values_list("name", flat=True))

                if len(roles) == 0:
                    # Edge case: user without roles
                    return redirect("switch_role")
                elif len(roles) == 1:
                    # Single role: auto-select
                    request.session["active_role"] = roles[0]
                    return redirect("/")
                else:
                    # Multiple roles: let user pick
                    return redirect("switch_role")
            else:
                messages.error(request, "Email ou senha inválidos.")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):  # type: ignore[no-untyped-def]
    """Logout and redirect to login page."""
    logout(request)
    return redirect("login")


@login_required
def switch_role_view(request):  # type: ignore[no-untyped-def]
    """Allow user to select an active role from their assigned roles."""
    user = request.user
    user_roles = list(user.roles.values_list("name", flat=True))

    if request.method == "POST":
        form = RoleSelectForm(request.POST)
        if form.is_valid():
            role_name = form.cleaned_data["role"]
            if role_name in user_roles:
                request.session["active_role"] = role_name
                return redirect("/")
            else:
                messages.error(request, "Papel inválido ou não atribuído.")
    else:
        form = RoleSelectForm()

    role_labels = {
        "nir": "NIR",
        "doctor": "Médico",
        "scheduler": "Agendador",
        "manager": "Supervisor",
        "admin": "Administrador",
    }

    roles_display = [{"name": role, "label": role_labels.get(role, role)} for role in user_roles]

    return render(
        request,
        "accounts/switch_role.html",
        {"roles": roles_display, "form": form},
    )
