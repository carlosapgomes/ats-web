"""Views for admin_ui: user CRUD and management."""

import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.llm.models import PromptTemplate

from .decorators import admin_or_manager_required, admin_required
from .forms import PromptCreateForm, UserCreateForm, UserUpdateForm

User = get_user_model()


def _count_active_admins() -> int:
    """Conta quantos admins estão ativos no sistema."""
    admin_role = Role.objects.filter(name="admin").first()
    if not admin_role:
        return 0
    return User.objects.filter(
        roles=admin_role,
        account_status="active",
        is_active=True,
    ).count()


@login_required
@admin_or_manager_required
def user_list(request: HttpRequest) -> HttpResponse:
    """Lista de usuários com filtros e busca."""
    users_qs = User.objects.prefetch_related("roles").order_by("username")

    # Filtro por status
    status_filter = request.GET.get("status", "")
    if status_filter:
        users_qs = users_qs.filter(account_status=status_filter)

    # Filtro por papel
    role_filter = request.GET.get("role", "")
    if role_filter:
        role_obj = Role.objects.filter(name=role_filter).first()
        if role_obj:
            users_qs = users_qs.filter(roles=role_obj)

    # Busca por username ou email
    q = request.GET.get("q", "")
    if q:
        users_qs = users_qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    status_choices = User._meta.get_field("account_status").choices
    all_roles = Role.objects.all().order_by("name")

    is_admin = request.session.get("active_role") == "admin"

    return render(
        request,
        "admin_ui/user_list.html",
        {
            "users": users_qs,
            "status_filter": status_filter,
            "role_filter": role_filter,
            "q": q,
            "status_choices": status_choices,
            "all_roles": all_roles,
            "is_admin": is_admin,
        },
    )


@login_required
@admin_required
def user_create(request: HttpRequest) -> HttpResponse:
    """Cria um novo usuário."""
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("admin_ui:user_list")
    else:
        form = UserCreateForm()

    return render(request, "admin_ui/user_form.html", {"form": form, "is_create": True})


@login_required
@admin_required
def user_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Edita email e papéis de um usuário."""
    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário atualizado com sucesso.")
            return redirect("admin_ui:user_list")
    else:
        form = UserUpdateForm(instance=user)

    return render(
        request,
        "admin_ui/user_form.html",
        {"form": form, "is_create": False, "edit_user": user},
    )


@login_required
@admin_required
def user_block(request: HttpRequest, pk: int) -> HttpResponse:
    """Bloqueia um usuário (account_status='blocked', is_active=False).

    Proteções:
    - Não pode bloquear a si mesmo.
    - Não pode bloquear o último admin ativo.
    """
    user = get_object_or_404(User, pk=pk)

    if user.pk == request.user.pk:
        messages.error(request, "Você não pode bloquear a si mesmo.")
        return redirect("admin_ui:user_list")

    # Verifica se é admin e se é o último
    admin_role = Role.objects.filter(name="admin").first()
    if admin_role and user.roles.filter(name="admin").exists():
        if _count_active_admins() <= 1:
            messages.error(request, "Não é possível bloquear o último administrador ativo.")
            return redirect("admin_ui:user_list")

    user.account_status = "blocked"
    user.is_active = False
    user.save(update_fields=["account_status", "is_active"])

    messages.success(request, f"Usuário '{user.username}' bloqueado.")
    return redirect("admin_ui:user_list")


@login_required
@admin_required
def user_unblock(request: HttpRequest, pk: int) -> HttpResponse:
    """Desbloqueia um usuário (account_status='active', is_active=True)."""
    user = get_object_or_404(User, pk=pk)

    user.account_status = "active"
    user.is_active = True
    user.save(update_fields=["account_status", "is_active"])

    messages.success(request, f"Usuário '{user.username}' desbloqueado.")
    return redirect("admin_ui:user_list")


# ── Prompt Views ─────────────────────────────────────────────────────────────────


@login_required
@admin_or_manager_required
def prompt_list(request: HttpRequest) -> HttpResponse:
    """Lista prompts agrupados por nome, com versão ativa destacada."""
    prompts = PromptTemplate.objects.select_related("updated_by").order_by("-name", "-version")

    # Agrupa por nome
    grouped: dict[str, list[PromptTemplate]] = {}
    for p in prompts:
        grouped.setdefault(p.name, []).append(p)

    is_admin = request.session.get("active_role") == "admin"

    return render(
        request,
        "admin_ui/prompt_list.html",
        {
            "grouped": grouped,
            "is_admin": is_admin,
        },
    )


@login_required
@admin_required
def prompt_create(request: HttpRequest) -> HttpResponse:
    """Cria nova versão de prompt com auto-incremento."""
    if request.method == "POST":
        form = PromptCreateForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            content = form.cleaned_data["content"]

            # Auto-increment version
            latest = PromptTemplate.objects.filter(name=name).order_by("-version").first()
            new_version = (latest.version + 1) if latest else 1

            # Desativa versão ativa anterior
            PromptTemplate.objects.filter(name=name, is_active=True).update(is_active=False)

            PromptTemplate.objects.create(  # type: ignore[misc]
                name=name,
                version=new_version,
                content=content,
                is_active=True,
                updated_by=request.user,
            )

            messages.success(request, f"Nova versão (v{new_version}) criada com sucesso.")
            return redirect("admin_ui:prompt_list")
    else:
        form = PromptCreateForm()

    return render(request, "admin_ui/prompt_create.html", {"form": form})


@login_required
@admin_or_manager_required
def prompt_detail(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    """Exibe detalhes de uma versão específica do prompt."""
    prompt = get_object_or_404(PromptTemplate, pk=pk)
    is_admin = request.session.get("active_role") == "admin"

    return render(
        request,
        "admin_ui/prompt_detail.html",
        {
            "prompt": prompt,
            "is_admin": is_admin,
        },
    )


@login_required
@admin_required
def prompt_activate(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    """Ativa uma versão do prompt, desativando as demais do mesmo nome."""
    prompt = get_object_or_404(PromptTemplate, pk=pk)

    # Desativa todas as outras do mesmo nome
    PromptTemplate.objects.filter(name=prompt.name, is_active=True).exclude(pk=prompt.pk).update(is_active=False)

    prompt.is_active = True
    prompt.updated_by = request.user  # type: ignore[assignment]
    prompt.save(update_fields=["is_active", "updated_by"])

    messages.success(request, f"Prompt '{prompt.name}' v{prompt.version} ativado.")
    return redirect("admin_ui:prompt_detail", pk=prompt.pk)


@login_required
@admin_required
def prompt_deactivate(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    """Desativa uma versão do prompt."""
    prompt = get_object_or_404(PromptTemplate, pk=pk)

    prompt.is_active = False
    prompt.updated_by = request.user  # type: ignore[assignment]
    prompt.save(update_fields=["is_active", "updated_by"])

    messages.success(request, f"Prompt '{prompt.name}' v{prompt.version} desativado.")
    return redirect("admin_ui:prompt_detail", pk=prompt.pk)
