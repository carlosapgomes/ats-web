"""Testes do Slice 2: CRUD de prompts no admin_ui.

RED → GREEN → REFACTOR
Testes escritos primeiro (RED), depois implementação (GREEN).
"""

import uuid

import pytest
from django.urls import reverse

from apps.llm.models import PromptTemplate

# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str):
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Role

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username=f"{role_name}_prompt@test",
        password="testpass123",
        email=f"{role_name}_prompt@test",
    )
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _create_prompt(name: str, version: int = 1, is_active: bool = True, content: str | None = None) -> PromptTemplate:
    """Cria um PromptTemplate para teste."""
    return PromptTemplate.objects.create(
        name=name,
        version=version,
        content=content or f"Content for {name} v{version}",
        is_active=is_active,
    )


PROMPT_NAMES = ["llm1_system", "llm1_user", "llm2_system", "llm2_user"]


# ── Access Control ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptAccessControl:
    """Verifica proteção de acesso das views de prompts."""

    def test_prompt_list_requires_login(self, client) -> None:
        """GET /admin-ui/prompts/ sem autenticação → redirect."""
        response = client.get("/admin-ui/prompts/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_prompt_list_accessible_for_admin(self, client) -> None:
        """Admin pode ver lista de prompts."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200

    def test_prompt_list_accessible_for_manager(self, client) -> None:
        """Manager pode ver lista de prompts."""
        _login_as(client, "manager")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200

    def test_prompt_list_blocked_for_nir(self, client) -> None:
        """NIR bloqueado → redirect."""
        _login_as(client, "nir")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 302

    def test_prompt_create_accessible_for_admin(self, client) -> None:
        """Admin pode acessar criar prompt."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:prompt_create"))
        assert response.status_code == 200

    def test_prompt_create_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode criar prompt."""
        _login_as(client, "manager")
        response = client.get(reverse("admin_ui:prompt_create"))
        assert response.status_code == 302

    def test_prompt_detail_accessible_for_admin(self, client) -> None:
        """Admin pode ver detalhe do prompt."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system")
        response = client.get(reverse("admin_ui:prompt_detail", args=[prompt.pk]))
        assert response.status_code == 200

    def test_prompt_detail_accessible_for_manager(self, client) -> None:
        """Manager pode ver detalhe do prompt."""
        _login_as(client, "manager")
        prompt = _create_prompt("llm1_system")
        response = client.get(reverse("admin_ui:prompt_detail", args=[prompt.pk]))
        assert response.status_code == 200

    def test_prompt_activate_accessible_for_admin(self, client) -> None:
        """Admin pode ativar prompt (POST)."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system", version=1, is_active=False)
        response = client.post(reverse("admin_ui:prompt_activate", args=[prompt.pk]))
        assert response.status_code == 302

    def test_prompt_activate_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode ativar prompt."""
        _login_as(client, "manager")
        prompt = _create_prompt("llm1_system", version=1, is_active=False)
        response = client.post(reverse("admin_ui:prompt_activate", args=[prompt.pk]))
        assert response.status_code == 302

    def test_prompt_deactivate_accessible_for_admin(self, client) -> None:
        """Admin pode desativar prompt (POST)."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system")
        response = client.post(reverse("admin_ui:prompt_deactivate", args=[prompt.pk]))
        assert response.status_code == 302

    def test_prompt_deactivate_blocked_for_manager(self, client) -> None:
        """Manager NÃO pode desativar prompt."""
        _login_as(client, "manager")
        prompt = _create_prompt("llm1_system")
        response = client.post(reverse("admin_ui:prompt_deactivate", args=[prompt.pk]))
        assert response.status_code == 302


# ── Prompt List ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptList:
    """Verifica a listagem de prompts."""

    def test_shows_all_prompt_names(self, client) -> None:
        """Lista mostra todos os nomes de prompt agrupados."""
        _login_as(client, "admin")
        for name in PROMPT_NAMES:
            _create_prompt(name)
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200
        content = response.content.decode()
        for name in PROMPT_NAMES:
            assert name in content

    def test_shows_active_version_highlighted(self, client) -> None:
        """Versão ativa aparece destacada na lista."""
        _login_as(client, "admin")
        _create_prompt("llm1_system", version=1, is_active=True)
        _create_prompt("llm1_system", version=2, is_active=False)
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "v1" in content
        assert "v2" in content

    def test_shows_new_version_button_for_admin(self, client) -> None:
        """Admin vê botão 'Nova Versão'."""
        _login_as(client, "admin")
        _create_prompt("llm1_system")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200
        assert "Nova Versão" in response.content.decode()

    def test_manager_cannot_see_new_version_button(self, client) -> None:
        """Manager NÃO vê botão 'Nova Versão'."""
        _login_as(client, "manager")
        _create_prompt("llm1_system")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200
        assert "Nova Versão" not in response.content.decode()

    def test_empty_list_shows_message(self, client) -> None:
        """Lista vazia mostra mensagem."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200
        assert "Nenhum prompt" in response.content.decode()


# ── Prompt Create ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptCreate:
    """Verifica criação de prompt."""

    def test_get_renders_form(self, client) -> None:
        """GET renderiza formulário com campos."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:prompt_create"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "form" in content.lower() or "name" in content.lower()

    def test_post_creates_new_version(self, client) -> None:
        """POST cria nova versão do prompt."""
        _login_as(client, "admin")
        _create_prompt("llm1_system", version=1)
        data = {"name": "llm1_system", "content": "New version content"}
        response = client.post(reverse("admin_ui:prompt_create"), data)
        assert response.status_code == 302
        assert PromptTemplate.objects.filter(name="llm1_system", version=2).exists()

    def test_post_auto_increments_version(self, client) -> None:
        """Versão é auto-incrementada (1 → 2)."""
        _login_as(client, "admin")
        data = {"name": "llm1_user", "content": "First version"}
        client.post(reverse("admin_ui:prompt_create"), data)
        v1 = PromptTemplate.objects.get(name="llm1_user", version=1)
        assert v1.is_active is True

        data2 = {"name": "llm1_user", "content": "Second version"}
        client.post(reverse("admin_ui:prompt_create"), data2)
        assert PromptTemplate.objects.filter(name="llm1_user", version=2).exists()

    def test_post_creates_first_version_as_1(self, client) -> None:
        """Primeira versão de um nome é sempre 1."""
        _login_as(client, "admin")
        data = {"name": "llm2_system", "content": "Brand new prompt"}
        response = client.post(reverse("admin_ui:prompt_create"), data)
        assert response.status_code == 302
        prompt = PromptTemplate.objects.get(name="llm2_system")
        assert prompt.version == 1

    def test_post_redirects_to_list(self, client) -> None:
        """Após criar, redireciona para lista."""
        _login_as(client, "admin")
        data = {"name": "llm2_user", "content": "Redirect test"}
        response = client.post(reverse("admin_ui:prompt_create"), data)
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:prompt_list")

    def test_post_requires_name(self, client) -> None:
        """POST sem name mostra erro."""
        _login_as(client, "admin")
        data = {"name": "", "content": "Some content"}
        response = client.post(reverse("admin_ui:prompt_create"), data)
        assert response.status_code == 200

    def test_post_requires_content(self, client) -> None:
        """POST sem content mostra erro."""
        _login_as(client, "admin")
        data = {"name": "llm1_system", "content": ""}
        response = client.post(reverse("admin_ui:prompt_create"), data)
        assert response.status_code == 200

    def test_new_version_is_active_and_others_deactivated(self, client) -> None:
        """Nova versão fica ativa e desativa as demais do mesmo nome."""
        _login_as(client, "admin")
        _create_prompt("llm1_system", version=1, is_active=True)
        data = {"name": "llm1_system", "content": "New active version"}
        response = client.post(reverse("admin_ui:prompt_create"), data)
        assert response.status_code == 302
        v1 = PromptTemplate.objects.get(name="llm1_system", version=1)
        v2 = PromptTemplate.objects.get(name="llm1_system", version=2)
        assert v1.is_active is False
        assert v2.is_active is True


# ── Prompt Detail ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptDetail:
    """Verifica visualização de detalhe do prompt."""

    def test_shows_metadata(self, client) -> None:
        """Detail mostra nome, versão, status e conteúdo."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system", version=1, content="Test content")
        response = client.get(reverse("admin_ui:prompt_detail", args=[prompt.pk]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "llm1_system" in content
        assert "v1" in content or "1" in content
        assert "Test content" in content

    def test_shows_activate_button_when_inactive(self, client) -> None:
        """Prompt inativo mostra botão 'Ativar'."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system", version=1, is_active=False)
        response = client.get(reverse("admin_ui:prompt_detail", args=[prompt.pk]))
        assert response.status_code == 200
        assert "Ativar" in response.content.decode()

    def test_shows_deactivate_button_when_active(self, client) -> None:
        """Prompt ativo mostra botão 'Desativar'."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system", version=1, is_active=True)
        response = client.get(reverse("admin_ui:prompt_detail", args=[prompt.pk]))
        assert response.status_code == 200
        assert "Desativar" in response.content.decode()

    def test_manager_does_not_see_action_buttons(self, client) -> None:
        """Manager NÃO vê botões Ativar/Desativar."""
        _login_as(client, "manager")
        prompt = _create_prompt("llm1_system", version=1, is_active=True)
        response = client.get(reverse("admin_ui:prompt_detail", args=[prompt.pk]))
        assert response.status_code == 200
        assert "Ativar" not in response.content.decode()
        assert "Desativar" not in response.content.decode()

    def test_returns_404_for_nonexistent(self, client) -> None:
        """UUID inexistente retorna 404."""
        _login_as(client, "admin")
        fake_uuid = uuid.uuid4()
        response = client.get(reverse("admin_ui:prompt_detail", args=[fake_uuid]))
        assert response.status_code == 404


# ── Prompt Activate ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptActivate:
    """Verifica ativação de prompt."""

    def test_activate_sets_is_active_true(self, client) -> None:
        """Ativação seta is_active=True."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system", version=1, is_active=False)
        client.post(reverse("admin_ui:prompt_activate", args=[prompt.pk]))
        prompt.refresh_from_db()
        assert prompt.is_active is True

    def test_activate_deactivates_others(self, client) -> None:
        """Ativar um prompt desativa outros do mesmo nome."""
        _login_as(client, "admin")
        v1 = _create_prompt("llm1_system", version=1, is_active=True)
        v2 = _create_prompt("llm1_system", version=2, is_active=False)
        client.post(reverse("admin_ui:prompt_activate", args=[v2.pk]))
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True

    def test_activate_redirects_to_detail(self, client) -> None:
        """Após ativar, redireciona para detail."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system", version=1, is_active=False)
        response = client.post(reverse("admin_ui:prompt_activate", args=[prompt.pk]))
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:prompt_detail", args=[prompt.pk])


# ── Prompt Deactivate ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptDeactivate:
    """Verifica desativação de prompt."""

    def test_deactivate_sets_is_active_false(self, client) -> None:
        """Desativação seta is_active=False."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system")
        client.post(reverse("admin_ui:prompt_deactivate", args=[prompt.pk]))
        prompt.refresh_from_db()
        assert prompt.is_active is False

    def test_deactivate_redirects_to_detail(self, client) -> None:
        """Após desativar, redireciona para detail."""
        _login_as(client, "admin")
        prompt = _create_prompt("llm1_system")
        response = client.post(reverse("admin_ui:prompt_deactivate", args=[prompt.pk]))
        assert response.status_code == 302
        assert response.url == reverse("admin_ui:prompt_detail", args=[prompt.pk])


# ── Nav Pills ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPromptNavPills:
    """Verifica que os nav pills nos templates apontam para prompt_list."""

    def test_prompts_link_in_dashboard(self, client) -> None:
        """Dashboard nav pill 'Prompts' linka para admin_ui:prompt_list."""
        _login_as(client, "admin")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("admin_ui:prompt_list") in content

    def test_prompts_link_in_user_list(self, client) -> None:
        """User list nav pill 'Prompts' linka para admin_ui:prompt_list."""
        _login_as(client, "admin")
        response = client.get(reverse("admin_ui:user_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("admin_ui:prompt_list") in content

    def test_prompt_list_has_nav_pills(self, client) -> None:
        """Template prompt_list tem nav pills."""
        _login_as(client, "admin")
        _create_prompt("llm1_system")
        response = client.get(reverse("admin_ui:prompt_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dashboard" in content
        assert "Prompts" in content
        assert "Usuários" in content
        assert "Auditoria" in content
