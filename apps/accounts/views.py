"""Views for authentication: login, logout, role switching, home, and notifications."""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .context_processors import ROLE_DISPLAY_NAMES
from .forms import LoginForm, RoleSelectForm
from .models import UserNotification


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
                messages.error(request, "Usuário ou senha inválidos.")
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

    roles_display = [{"name": role, "label": ROLE_DISPLAY_NAMES.get(role, role)} for role in user_roles]

    return render(
        request,
        "accounts/switch_role.html",
        {"roles": roles_display, "form": form},
    )


ROLE_HOME_URLS = {
    "nir": "/cases/my-cases/",
    "doctor": "/doctor/",
    "scheduler": "/scheduler/queue/",
    "manager": "/dashboard/",
    "admin": "/dashboard/",
}


@login_required
def home_view(request):  # type: ignore[no-untyped-def]
    """Redireciona para a home do papel ativo."""
    active_role = request.session.get("active_role")
    if not active_role:
        return redirect("/switch-role/")

    if active_role == "nir":
        return redirect("intake:home")
    if active_role == "doctor":
        return redirect("doctor:queue")
    if active_role == "scheduler":
        return redirect("scheduler:queue")
    if active_role == "manager":
        return redirect("dashboard:index")
    if active_role == "admin":
        return redirect("dashboard:index")

    return redirect("/switch-role/")


# ── Notification Views ────────────────────────────────────────────────────


@login_required
def notifications_list(request):  # type: ignore[no-untyped-def]
    """Exibe a lista de notificações do usuário autenticado."""
    notifications = UserNotification.objects.filter(recipient=request.user).select_related(
        "case", "communication_message", "triggered_by"
    )
    unread_count = notifications.filter(read_at__isnull=True).count()
    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications": notifications,
            "unread_count": unread_count,
        },
    )


@login_required
def notification_open(request, notification_id):  # type: ignore[no-untyped-def]
    """Abre uma notificação: marca como lida e redireciona."""
    from .services import resolve_notification_redirect_url

    notification = get_object_or_404(
        UserNotification,
        notification_id=notification_id,
        recipient=request.user,
    )

    # Marcar como lida se ainda não foi
    if notification.read_at is None:
        from django.utils import timezone

        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])

    # Redirecionar com base no papel ativo
    active_role = request.session.get("active_role", "")
    redirect_url = resolve_notification_redirect_url(
        case=notification.case,
        user=request.user,
        active_role=active_role,
    )
    return redirect(redirect_url)


@login_required
def notification_mark_read(request, notification_id):  # type: ignore[no-untyped-def]
    """Marca uma notificação como lida via POST."""
    if request.method != "POST":
        return redirect("notifications")

    notification = get_object_or_404(
        UserNotification,
        notification_id=notification_id,
        recipient=request.user,
    )
    if notification.read_at is None:
        from django.utils import timezone

        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])

    return redirect("notifications")


@login_required
def notifications_mark_all_read(request):  # type: ignore[no-untyped-def]
    """Marca todas as notificações não lidas do usuário como lidas via POST."""
    if request.method != "POST":
        return redirect("notifications")

    from django.utils import timezone

    UserNotification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return redirect("notifications")
