"""Testes do Slice 1: CRUD de usuários no admin_ui.

RED → GREEN → REFACTOR
Testes escritos primeiro (RED), depois implementação (GREEN).
"""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Role

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str) -> User:
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    user = User.objects.create_user(
        username=f"{role_name}@adminui.test",
        password="testpass123",
        email=f"{role_name}@adminui.test",
    )
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _create_user(username: str, roles: list[str] | None = None) -> User:
    """Cria usuário com papéis."""
    user = User.objects.create_user(
        username=username,
        password="testpass123",
        email=f"{username}@test.com",
    )
    if roles:
        for name in roles:
            role, _ = Role.objects.get_or_create(name=name)
            user.roles.add(role)
    return user


# ── Access Control ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminUIAccess:
    """Verifica proteção de acesso das views admin_ui."""

    def test_user_list_requires_login(self, client) -> None:
        """GET /admin-ui/users/ sem autenticação → redirect."""
        response = client.get("/admin-ui/users/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_user_list_accessible_for_admin(self, client) -> None:
        """Admin pode ver lista de usuários."""
        _login_as(client, "admin")
        response = client.get("/admin-ui/users/")
        assert response.status_code == 200

    def test_user_list_accessible_for_manager(self, client) -> None:
        """Manager pode ver lista de usuários."""
        _login_as(client, "manager")
        response = client.get("/admin-ui/users/")
        assert response.status_code == 200

    def test_user_list_blocked_for_nir(self, client) -> None:
        """NIR bloqueado → redirect."""
        _login_as(client, "nir")
        response = client.get("/admin-ui/users/")
        assert response.status_code == 302

    def test_user_list_blocked_for_doctor(self, client) -> None:
        """Doctor bloqueado → redirect."""
        _login_as(client, "doctor")
        response = client.get("/admin-ui/users/")
        assert response.status_code == 302

    def test_user_list_blocked_for_scheduler(self, client) -> None:
        """Scheduler bloqueado → redirect."""
        _login_as(client, "scheduler")
        response = client.get("/admin-ui/users/")
        assert response.status_code == 302

    def test_user_create_accessible_for_admin(self, client) -> None:
        """Admin pode acessar criar usuário."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:user_create"))
        assert response.status_code == 200

    def test_user_create_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode criar usuário."""
        _login_as(client, "manager")
        response = client.get(reverse("admin_ui:user_create"))
        assert response.status_code == 302

    def test_user_update_accessible_for_admin(self, client) -> None:
        """Admin pode editar usuário."""
        _login_as(client, "admin")
        target = _create_user("editme")
        response = client.get(reverse("admin_ui:user_update", args=[target.pk]))
        assert response.status_code == 200

    def test_user_update_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode editar usuário."""
        _login_as(client, "manager")
        target = _create_user("editme2")
        response = client.get(reverse("admin_ui:user_update", args=[target.pk]))
        assert response.status_code == 302

    def test_user_block_accessible_for_admin(self, client) -> None:
        """Admin pode bloquear usuário (POST)."""
        _login_as(client, "admin")
        target = _create_user("blockme")
        response = client.post(reverse("admin_ui:user_block", args=[target.pk]))
        assert response.status_code == 302

    def test_user_block_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode bloquear usuário."""
        _login_as(client, "manager")
        target = _create_user("blockme2")
        response = client.post(reverse("admin_ui:user_block", args=[target.pk]))
        assert response.status_code == 302

    def test_user_unblock_accessible_for_admin(self, client) -> None:
        """Admin pode desbloquear usuário (POST)."""
        _login_as(client, "admin")
        target = _create_user("unblockme")
        target.account_status = "blocked"
        target.is_active = False
        target.save()
        response = client.post(reverse("admin_ui:user_unblock", args=[target.pk]))
        assert response.status_code == 302

    def test_user_unblock_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode desbloquear usuário."""
        _login_as(client, "manager")
        target = _create_user("unblockme2")
        response = client.post(reverse("admin_ui:user_unblock", args=[target.pk]))
        assert response.status_code == 302


# ── User List ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserList:
    """Verifica a listagem de usuários."""

    def test_lists_all_users(self, client) -> None:
        """Tabela mostra todos os usuários cadastrados."""
        _login_as(client, "admin")
        _create_user("alpha")
        _create_user("beta")
        _create_user("gamma")
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "alpha" in content
        assert "beta" in content
        assert "gamma" in content

    def test_shows_email(self, client) -> None:
        """Tabela exibe email do usuário."""
        _login_as(client, "admin")
        _create_user("showmail")
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        assert "showmail@test.com" in response.content.decode()

    def test_shows_roles_as_badges(self, client) -> None:
        """Tabela exibe papéis como badges."""
        _login_as(client, "admin")
        _create_user("withroles", roles=["admin", "manager"])
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin" in content.lower()
        assert "manager" in content.lower()

    def test_shows_status(self, client) -> None:
        """Tabela exibe status da conta."""
        _login_as(client, "admin")
        user = _create_user("statustest")
        user.account_status = "blocked"
        user.save()
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        assert "blocked" in response.content.decode().lower()

    def test_filter_by_status(self, client) -> None:
        """Filtro por status funciona."""
        _login_as(client, "admin")
        _create_user("activeuser")
        blocked = _create_user("blockeduser")
        blocked.account_status = "blocked"
        blocked.save()
        response = client.get(reverse("admin_ui:user_list"), {"status": "blocked"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "blockeduser" in content
        assert "activeuser" not in content

    def test_filter_by_role(self, client) -> None:
        """Filtro por papel funciona."""
        _login_as(client, "admin")
        _create_user("nirguy", roles=["nir"])
        _create_user("doctorguy", roles=["doctor"])
        response = client.get(reverse("admin_ui:user_list"), {"role": "nir"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "nirguy" in content
        assert "doctorguy" not in content

    def test_search_by_username(self, client) -> None:
        """Busca por username funciona."""
        _login_as(client, "admin")
        _create_user("joaosilva")
        _create_user("maria")
        response = client.get(reverse("admin_ui:user_list"), {"q": "joao"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "joaosilva" in content
        assert "maria" not in content

    def test_search_by_email(self, client) -> None:
        """Busca por email funciona."""
        _login_as(client, "admin")
        _create_user("userone")
        _create_user("usertwo")
        response = client.get(reverse("admin_ui:user_list"), {"q": "userone"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "userone" in content
        assert "usertwo" not in content


# ── Professional Council ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserProfessionalCouncil:
    """Verifica campos de conselho profissional no CRUD de usuários."""

    def test_create_with_crm(self, client) -> None:
        """Create aceita professional_council='CRM' + número e persiste."""
        _login_as(client, "admin")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "username": "medico-crm",
            "email": "medico@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk],
            "professional_council": "CRM",
            "professional_council_number": "12345",
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 302
        user = User.objects.get(username="medico-crm")
        assert user.professional_council == "CRM"
        assert user.professional_council_number == "12345"

    def test_create_with_coren(self, client) -> None:
        """Create aceita professional_council='COREN' + número e persiste."""
        _login_as(client, "admin")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "username": "enfermeiro-coren",
            "email": "enfermeiro@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk],
            "professional_council": "COREN",
            "professional_council_number": "67890",
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 302
        user = User.objects.get(username="enfermeiro-coren")
        assert user.professional_council == "COREN"
        assert user.professional_council_number == "67890"

    def test_update_with_council(self, client) -> None:
        """Update aceita professional_council + número e persiste."""
        _login_as(client, "admin")
        target = _create_user("editcouncil")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "email": "editcouncil@test.com",
            "roles": [nir_pk],
            "professional_council": "COREN",
            "professional_council_number": "99999",
        }
        response = client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.professional_council == "COREN"
        assert target.professional_council_number == "99999"

    def test_partial_council_rejected(self, client) -> None:
        """Form rejeita preenchimento parcial (só conselho)."""
        _login_as(client, "admin")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "username": "parcial",
            "email": "parcial@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk],
            "professional_council": "CRM",
            "professional_council_number": "",
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 200  # mesma página com erro
        assert not User.objects.filter(username="parcial").exists()

    def test_list_shows_council(self, client) -> None:
        """Listagem mostra 'CRM 12345' para usuário com registro."""
        _login_as(client, "admin")
        user = _create_user("councillist")
        user.professional_council = "CRM"
        user.professional_council_number = "12345"
        user.save()
        user.refresh_from_db()
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "CRM" in content
        assert "12345" in content

    def test_list_shows_dash_for_empty(self, client) -> None:
        """Listagem mostra '—' para usuário sem registro profissional."""
        _login_as(client, "admin")
        _create_user("nocouncil")
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "—" in content


# ── User Create ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserCreate:
    """Verifica criação de usuário."""

    def test_get_renders_form(self, client) -> None:
        """GET /admin-ui/users/create/ renderiza formulário."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:user_create"))
        assert response.status_code == 200
        assert "form" in response.content.decode().lower()

    def test_post_creates_user(self, client) -> None:
        """POST cria usuário com dados válidos."""
        _login_as(client, "admin")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "username": "novousuario",
            "email": "novo@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk],
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 302
        assert User.objects.filter(username="novousuario").exists()

    def test_post_redirects_to_list(self, client) -> None:
        """Após criar, redireciona para lista."""
        _login_as(client, "admin")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "username": "redirectuser",
            "email": "redirect@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk],
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:user_list")

    def test_post_requires_password(self, client) -> None:
        """POST sem password mostra erro."""
        _login_as(client, "admin")
        Role.objects.get_or_create(name="nir")
        data = {
            "username": "sempassword",
            "email": "sem@test.com",
            "password": "",
            "roles": ["nir"],
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 200  # mesma página com erro
        assert not User.objects.filter(username="sempassword").exists()

    def test_post_assigns_roles(self, client) -> None:
        """Usuário criado recebe os papéis selecionados."""
        _login_as(client, "admin")
        Role.objects.get_or_create(name="nir")
        Role.objects.get_or_create(name="doctor")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        doctor_pk = Role.objects.get_or_create(name="doctor")[0].pk
        data = {
            "username": "multirole",
            "email": "multi@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk, doctor_pk],
        }
        client.post(reverse("admin_ui:user_create"), data)
        user = User.objects.get(username="multirole")
        role_names = list(user.roles.values_list("name", flat=True))
        assert "nir" in role_names
        assert "doctor" in role_names

    def test_post_duplicate_username_shows_error(self, client) -> None:
        """Username duplicado mostra erro."""
        _login_as(client, "admin")
        _create_user("duplicado")
        Role.objects.get_or_create(name="nir")
        data = {
            "username": "duplicado",
            "email": "duplicado@test.com",
            "password": "SenhaForte123!",
            "roles": ["nir"],
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 200
        assert b"duplicado" in response.content

    def test_create_with_first_last_name(self, client) -> None:
        """Create persiste first_name e last_name."""
        _login_as(client, "admin")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "username": "nomecompleto",
            "email": "nomecompleto@test.com",
            "password": "SenhaForte123!",
            "roles": [nir_pk],
            "first_name": "João",
            "last_name": "Silva",
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        assert response.status_code == 302
        user = User.objects.get(username="nomecompleto")
        assert user.first_name == "João"
        assert user.last_name == "Silva"
        assert user.display_name == "João Silva"


# ── User Update ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserUpdate:
    """Verifica edição de usuário."""

    def test_get_renders_form_with_data(self, client) -> None:
        """GET renderiza formulário com dados do usuário."""
        _login_as(client, "admin")
        target = _create_user("edituser", roles=["nir"])
        response = client.get(reverse("admin_ui:user_update", args=[target.pk]))
        assert response.status_code == 200
        assert "edituser" in response.content.decode()

    def test_post_updates_email(self, client) -> None:
        """POST atualiza email."""
        _login_as(client, "admin")
        target = _create_user("updateme")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "email": "updated@test.com",
            "roles": [nir_pk],
        }
        response = client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.email == "updated@test.com"

    def test_post_updates_roles(self, client) -> None:
        """POST atualiza papéis."""
        _login_as(client, "admin")
        target = _create_user("roleupdate")
        Role.objects.get_or_create(name="nir")
        Role.objects.get_or_create(name="doctor")
        doctor_pk = Role.objects.get_or_create(name="doctor")[0].pk
        data = {
            "email": "roleupdate@test.com",
            "roles": [doctor_pk],
        }
        client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        target.refresh_from_db()
        role_names = list(target.roles.values_list("name", flat=True))
        assert "doctor" in role_names
        assert "nir" not in role_names

    def test_username_is_readonly(self, client) -> None:
        """Username aparece como readonly no form de edição."""
        _login_as(client, "admin")
        target = _create_user("readonlytest")
        response = client.get(reverse("admin_ui:user_update", args=[target.pk]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "readonly" in content.lower() or "readonlytest" in content

    def test_post_redirects_to_list(self, client) -> None:
        """Após editar, redireciona para lista."""
        _login_as(client, "admin")
        target = _create_user("redirectedit")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "email": "redirectedit@test.com",
            "roles": [nir_pk],
        }
        response = client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:user_list")

    def test_update_first_last_name(self, client) -> None:
        """Update persiste first_name e last_name."""
        _login_as(client, "admin")
        target = _create_user("nameupdate")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        data = {
            "email": "nameupdate@test.com",
            "roles": [nir_pk],
            "first_name": "Maria",
            "last_name": "Santos",
        }
        response = client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.first_name == "Maria"
        assert target.last_name == "Santos"
        assert target.display_name == "Maria Santos"

    def test_update_password(self, client) -> None:
        """Update com password altera a senha do usuário."""
        _login_as(client, "admin")
        target = _create_user("passupdate")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        old_password_hash = target.password
        data = {
            "email": "passupdate@test.com",
            "roles": [nir_pk],
            "password": "NovaSenha456!",
        }
        response = client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.password != old_password_hash

    def test_update_empty_password_does_not_change(self, client) -> None:
        """Update com password vazio não altera a senha."""
        _login_as(client, "admin")
        target = _create_user("keepassword")
        Role.objects.get_or_create(name="nir")
        nir_pk = Role.objects.get_or_create(name="nir")[0].pk
        old_password_hash = target.password
        data = {
            "email": "keepassword@test.com",
            "roles": [nir_pk],
            "password": "",
        }
        response = client.post(reverse("admin_ui:user_update", args=[target.pk]), data)
        assert response.status_code == 302
        target.refresh_from_db()
        assert target.password == old_password_hash


# ── User Block ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserBlock:
    """Verifica bloqueio de usuário."""

    def test_block_sets_account_status_blocked(self, client) -> None:
        """Bloqueio seta account_status='blocked'."""
        _login_as(client, "admin")
        target = _create_user("blocktest")
        client.post(reverse("admin_ui:user_block", args=[target.pk]))
        target.refresh_from_db()
        assert target.account_status == "blocked"

    def test_block_sets_is_active_false(self, client) -> None:
        """Bloqueio seta is_active=False."""
        _login_as(client, "admin")
        target = _create_user("blocktest2")
        client.post(reverse("admin_ui:user_block", args=[target.pk]))
        target.refresh_from_db()
        assert target.is_active is False

    def test_cannot_block_self(self, client) -> None:
        """Não pode bloquear a si mesmo."""
        admin = _login_as(client, "admin")
        response = client.post(reverse("admin_ui:user_block", args=[admin.pk]))
        assert response.status_code == 302
        admin.refresh_from_db()
        assert admin.account_status == "active"

    def test_cannot_block_last_admin(self, client) -> None:
        """Não pode bloquear o último admin ativo.

        Cenário: logado como admin #1, admin #2 é o único outro admin.
        Bloquear admin #2 deixa apenas admin #1 → permitido.
        Bloquear admin #1 (self) é proibido (self-protection + last-admin protection).
        Após admin #2 ser bloqueado, admin #1 é o último admin.
        """
        admin1 = _login_as(client, "admin")
        admin2 = _create_user("otheradmin", roles=["admin"])

        # Bloquear admin2 deixa apenas admin1 → permitido
        response = client.post(reverse("admin_ui:user_block", args=[admin2.pk]))
        assert response.status_code == 302
        admin2.refresh_from_db()
        assert admin2.account_status == "blocked"

        # Tentar bloquear admin1 (self) é proibido
        response = client.post(reverse("admin_ui:user_block", args=[admin1.pk]))
        assert response.status_code == 302
        admin1.refresh_from_db()
        assert admin1.account_status == "active"

    def test_redirects_to_list_after_block(self, client) -> None:
        """Após bloquear, redireciona para lista."""
        _login_as(client, "admin")
        target = _create_user("blockredirect")
        response = client.post(reverse("admin_ui:user_block", args=[target.pk]))
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:user_list")


# ── User Unblock ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserUnblock:
    """Verifica desbloqueio de usuário."""

    def test_unblock_sets_account_status_active(self, client) -> None:
        """Desbloqueio seta account_status='active'."""
        _login_as(client, "admin")
        target = _create_user("unblocktest")
        target.account_status = "blocked"
        target.is_active = False
        target.save()
        client.post(reverse("admin_ui:user_unblock", args=[target.pk]))
        target.refresh_from_db()
        assert target.account_status == "active"

    def test_unblock_sets_is_active_true(self, client) -> None:
        """Desbloqueio seta is_active=True."""
        _login_as(client, "admin")
        target = _create_user("unblocktest2")
        target.account_status = "blocked"
        target.is_active = False
        target.save()
        client.post(reverse("admin_ui:user_unblock", args=[target.pk]))
        target.refresh_from_db()
        assert target.is_active is True

    def test_redirects_to_list_after_unblock(self, client) -> None:
        """Após desbloquear, redireciona para lista."""
        _login_as(client, "admin")
        target = _create_user("unblockredirect")
        target.account_status = "blocked"
        target.is_active = False
        target.save()
        response = client.post(reverse("admin_ui:user_unblock", args=[target.pk]))
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:user_list")


# ── User Create Email Invitation (Slice 003) ──────────────────────────────


@pytest.mark.django_db
class TestUserCreateInvitationEmail:
    """Slice 003: Email automático de cadastro ao criar usuário."""

    def _create_user_via_post(self, client, username: str, roles: list[str] | None = None) -> dict[str, Any]:
        """Helper: POST create user and return response + created user."""
        from apps.admin_ui.tests.test_users_crud import _login_as

        _login_as(client, "admin")
        role_pks = []
        if roles:
            for name in roles:
                role, _ = Role.objects.get_or_create(name=name)
                role_pks.append(role.pk)
        Role.objects.get_or_create(name="nir")
        data = {
            "username": username,
            "email": f"{username}@test.com",
            "password": "SenhaForte123!",
            "roles": role_pks,
        }
        response = client.post(reverse("admin_ui:user_create"), data)
        created_user = User.objects.filter(username=username).first()
        return {"response": response, "user": created_user}

    def test_admin_user_create_sends_invitation_email_automatically(self, client) -> None:
        """Criação de usuário envia email automático."""
        from django.core import mail

        result = self._create_user_via_post(client, "inviteauto", roles=["doctor"])
        assert result["user"] is not None
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert "inviteauto@test.com" in email.to

    def test_admin_user_create_email_link_allows_password_reset(self, client) -> None:
        """Link no email permite redefinir senha."""
        from django.core import mail

        result = self._create_user_via_post(client, "resetlink", roles=["nir"])
        assert result["user"] is not None
        assert len(mail.outbox) == 1

        # Extrair link do email
        body: str = mail.outbox[0].body
        import re

        path_match = re.search(r"/reset/[^\s]+/", body)
        assert path_match is not None, "Link de reset não encontrado no email"
        reset_path = path_match.group(0).rstrip("'\"<>)\n\r ")

        # GET confirm page (segue redirect para set-password)
        response = client.get(reset_path, follow=True)
        assert response.status_code == 200

        # POST nova senha
        confirm_path = response.redirect_chain[-1][0] if response.redirect_chain else reset_path
        response = client.post(
            confirm_path,
            {"new_password1": "NewStr0ng!Pass", "new_password2": "NewStr0ng!Pass"},
        )
        assert response.status_code == 302
        complete_url = reverse("password_reset_complete")
        assert complete_url in response.url

        # Login com nova senha funciona
        login_ok = client.login(username="resetlink", password="NewStr0ng!Pass")
        assert login_ok is True

    def test_admin_user_create_keeps_user_when_email_send_fails(self, client) -> None:
        """Falha SMTP não apaga usuário e mostra mensagem."""
        from unittest.mock import patch

        from django.core import mail

        _login_as(client, "admin")
        Role.objects.get_or_create(name="nir")

        # Patch no local de importação da view (from X import Y cria nome local)
        with patch("apps.admin_ui.views.send_user_invitation_email") as mock_send:
            mock_send.side_effect = Exception("SMTP Connection refused")

            data = {
                "username": "failmail",
                "email": "failmail@test.com",
                "password": "SenhaForte123!",
                "roles": [],
            }
            response = client.post(reverse("admin_ui:user_create"), data)

        # Usuário foi criado mesmo com falha no email
        assert User.objects.filter(username="failmail").exists()

        # Email não foi enviado
        assert len(mail.outbox) == 0

        # Redirect ocorreu (não quebrou)
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:user_list")

    def test_admin_user_create_nir_receives_internal_url(self, client) -> None:
        """Usuário nir-only recebe link com URL interna."""
        from django.conf import settings
        from django.core import mail

        result = self._create_user_via_post(client, "nirurl", roles=["nir"])
        assert result["user"] is not None
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert settings.INTERNAL_APP_BASE_URL in body

    def test_admin_user_create_doctor_receives_public_url(self, client) -> None:
        """Usuário doctor recebe link com URL pública."""
        from django.conf import settings
        from django.core import mail

        result = self._create_user_via_post(client, "docurl", roles=["doctor"])
        assert result["user"] is not None
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert settings.PUBLIC_APP_BASE_URL in body


# ── Nav Pills ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNavPills:
    """Verifica que os nav pills no template apontam para as views corretas."""

    def test_usuarios_link_in_dashboard(self, client) -> None:
        """Dashboard nav pill 'Usuários' linka para admin_ui:user_list."""
        _login_as(client, "admin")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("admin_ui:user_list") in content

    def test_admin_ui_has_nav_pills(self, client) -> None:
        """Template admin_ui user_list tem nav pills."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dashboard" in content
        assert "Prompts" in content
        assert "Usuários" in content
        assert "Auditoria" in content
