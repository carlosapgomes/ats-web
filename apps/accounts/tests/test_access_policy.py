"""Tests for the CHD follow-up access policy (slice 001).

Cobre a matriz D6 de ``openspec/changes/followup-chd-access-guard/design.md``
na camada unit: a política pura ``can_access_followup`` (7 linhas da matriz),
o decorator ``followup_access_required`` (bloqueio com flash+redirect e
passagem, consumindo a política única) e a exposição de
``can_access_followup`` pelo context processor ``role_context``.
"""

from secrets import token_hex
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.test import RequestFactory

from apps.accounts.context_processors import role_context
from apps.accounts.decorators import followup_access_required
from apps.accounts.services import can_access_followup

User = get_user_model()


def _user_with_roles(*role_names: str) -> Any:
    """Cria usuário persistido com os papéis informados (username único)."""
    from apps.accounts.models import Role

    user = User.objects.create_user(
        username=f"policy-{token_hex(8)}@test.com",
        password="testpass123",
    )
    for role_name in role_names:
        role, _ = Role.objects.get_or_create(name=role_name)
        user.roles.add(role)
    return user


@followup_access_required
def _dummy_followup_view(request: HttpRequest) -> HttpResponse:
    """View dummy protegida pelo decorator para os testes de R2."""
    return HttpResponse("followup ok")


@pytest.mark.django_db
class TestCanAccessFollowup:
    """R1 — política pura ``can_access_followup`` (linhas da matriz D6)."""

    def test_can_access_followup_manager_with_scheduler_allowed(self) -> None:
        """manager + scheduler com papel ativo manager → True."""
        user = _user_with_roles("manager", "scheduler")
        assert can_access_followup(user, "manager") is True

    def test_can_access_followup_manager_without_scheduler_blocked(self) -> None:
        """manager sem o papel scheduler (sem vínculo CHD) → False."""
        user = _user_with_roles("manager")
        assert can_access_followup(user, "manager") is False

    def test_can_access_followup_admin_exempt_without_scheduler(self) -> None:
        """admin ativo sem possuir scheduler → True (isenção de suporte)."""
        user = _user_with_roles("admin")
        assert can_access_followup(user, "admin") is True

    def test_can_access_followup_admin_with_scheduler_active_manager_allowed(self) -> None:
        """admin + scheduler com papel ativo manager → True."""
        user = _user_with_roles("admin", "scheduler")
        assert can_access_followup(user, "manager") is True

    def test_can_access_followup_scheduler_active_blocked(self) -> None:
        """scheduler ativo (mesmo possuindo manager) → False."""
        user = _user_with_roles("manager", "scheduler")
        assert can_access_followup(user, "scheduler") is False

    @pytest.mark.parametrize("active_role", ["doctor", "nir"])
    def test_can_access_followup_doctor_and_nir_blocked(self, active_role: str) -> None:
        """doctor/nir ativos → False."""
        user = _user_with_roles(active_role)
        assert can_access_followup(user, active_role) is False

    @pytest.mark.parametrize("active_role", ["", "manager", "admin"])
    def test_can_access_followup_anonymous_blocked(self, active_role: str) -> None:
        """Anônimo → False para qualquer papel ativo (admin não isenta anônimo)."""
        anonymous = AnonymousUser()
        assert can_access_followup(anonymous, active_role) is False

    def test_can_access_followup_inactive_manager_with_scheduler_blocked(self) -> None:
        """Usuário inativo (manager+scheduler, papel ativo manager) → False."""
        user = _user_with_roles("manager", "scheduler")
        user.is_active = False
        user.save(update_fields=["is_active"])
        assert can_access_followup(user, "manager") is False

    def test_can_access_followup_inactive_admin_blocked(self) -> None:
        """Usuário inativo admin (papel ativo admin) → False (isenção p/ ativos)."""
        user = _user_with_roles("admin")
        user.is_active = False
        user.save(update_fields=["is_active"])
        assert can_access_followup(user, "admin") is False


@pytest.mark.django_db
class TestFollowupAccessRequired:
    """R2 — decorator específico que consome a política única (D1/D2)."""

    def _build_request(self, rf: RequestFactory, user: Any, *, active_role: str) -> Any:
        request = rf.get("/")
        request.user = user
        request.session = {"active_role": active_role}
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def _assert_blocked(self, request: Any, response: HttpResponse) -> None:
        """Assere bloqueio: 302 para "/" com messages.error (UX do role_required)."""
        redirect_response = cast(HttpResponseRedirect, response)
        assert redirect_response.status_code == 302
        assert redirect_response.url == "/"
        messages = list(get_messages(request))
        assert len(messages) == 1
        assert messages[0].message == "Você não tem permissão para acessar esta página."

    def test_blocks_manager_without_scheduler_with_flash_and_redirect(self, rf: RequestFactory) -> None:
        """manager sem vínculo CHD → 302 `/` + messages.error (UX do role_required)."""
        user = _user_with_roles("manager")
        request = self._build_request(rf, user, active_role="manager")

        response = _dummy_followup_view(request)

        self._assert_blocked(request, response)

    def test_allows_manager_with_scheduler(self, rf: RequestFactory) -> None:
        """manager + scheduler com papel ativo manager → executa a view."""
        user = _user_with_roles("manager", "scheduler")
        request = self._build_request(rf, user, active_role="manager")

        response = _dummy_followup_view(request)

        assert response.status_code == 200
        assert response.content == b"followup ok"

    def test_allows_admin_exempt(self, rf: RequestFactory) -> None:
        """admin ativo sem scheduler → executa a view (isenção D4)."""
        user = _user_with_roles("admin")
        request = self._build_request(rf, user, active_role="admin")

        response = _dummy_followup_view(request)

        assert response.status_code == 200
        assert response.content == b"followup ok"

    def test_blocks_scheduler_active(self, rf: RequestFactory) -> None:
        """scheduler ativo → 302 `/` com flash (papel fora da política)."""
        user = _user_with_roles("manager", "scheduler")
        request = self._build_request(rf, user, active_role="scheduler")

        response = _dummy_followup_view(request)

        self._assert_blocked(request, response)


@pytest.mark.django_db
class TestRoleContextCanAccessFollowup:
    """R3 — ``role_context`` expõe ``can_access_followup`` chamando a política D1."""

    def _build_request(self, rf: RequestFactory, user: Any, *, active_role: str) -> Any:
        request = rf.get("/")
        request.user = user
        request.session = {"active_role": active_role}
        return request

    @pytest.mark.parametrize("active_role", ["", "manager", "admin"])
    def test_can_access_followup_context_anonymous_is_false(self, rf: RequestFactory, active_role: str) -> None:
        """Usuário anônimo → can_access_followup False no contexto."""
        request = self._build_request(rf, AnonymousUser(), active_role=active_role)
        context = role_context(request)
        assert context["can_access_followup"] is False

    def test_can_access_followup_context_manager_with_scheduler_is_true(self, rf: RequestFactory) -> None:
        """manager + scheduler ativo → True no contexto."""
        user = _user_with_roles("manager", "scheduler")
        request = self._build_request(rf, user, active_role="manager")
        context = role_context(request)
        assert context["can_access_followup"] is True

    def test_can_access_followup_context_manager_without_scheduler_is_false(self, rf: RequestFactory) -> None:
        """manager sem vínculo CHD → False no contexto."""
        user = _user_with_roles("manager")
        request = self._build_request(rf, user, active_role="manager")
        context = role_context(request)
        assert context["can_access_followup"] is False

    def test_can_access_followup_context_admin_is_true(self, rf: RequestFactory) -> None:
        """admin ativo sem scheduler → True no contexto."""
        user = _user_with_roles("admin")
        request = self._build_request(rf, user, active_role="admin")
        context = role_context(request)
        assert context["can_access_followup"] is True

    def test_can_access_followup_context_scheduler_active_is_false(self, rf: RequestFactory) -> None:
        """scheduler ativo → False no contexto."""
        user = _user_with_roles("manager", "scheduler")
        request = self._build_request(rf, user, active_role="scheduler")
        context = role_context(request)
        assert context["can_access_followup"] is False

    def test_role_context_still_exposes_active_role_keys(self, rf: RequestFactory) -> None:
        """role_context preserva as chaves ativas (active_role/display)."""
        user = _user_with_roles("manager", "scheduler")
        request = self._build_request(rf, user, active_role="manager")
        context = role_context(request)
        assert context["active_role"] == "manager"
        assert context["active_role_display"] == "Supervisor"
