"""Tests for IntranetGuardMiddleware."""

from typing import Any

from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.accounts.middleware import IntranetGuardMiddleware

User = get_user_model()


def _make_request(user=None, active_role=None, ip="1.2.3.4") -> Any:
    """Helper: cria um request mock com user, session active_role, e REMOTE_ADDR."""
    factory = RequestFactory()
    request = factory.get("/")
    request.META["REMOTE_ADDR"] = ip
    request.user = user or User()
    if active_role:
        request.session = {"active_role": active_role}
    else:
        request.session = {}
    return request


def _make_middleware() -> IntranetGuardMiddleware:
    """Cria uma instância do middleware com get_response falso."""

    def dummy_get_response(request: Any) -> None:
        return None

    return IntranetGuardMiddleware(dummy_get_response)


class TestIntranetGuardMiddleware:
    """Tests for IntranetGuardMiddleware."""

    def test_doctor_role_allowed_from_any_ip(self):
        """doctor + IP externo → passa pelo middleware (não bloqueia)."""
        from apps.accounts.models import Role

        user = User(username="doctor@test.com")
        assert Role(name="doctor")  # ensure role exists

        request = _make_request(user=user, active_role="doctor", ip="1.2.3.4")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None  # passes through

    def test_manager_role_allowed_from_any_ip(self):
        """manager + IP externo → passa."""
        from apps.accounts.models import Role

        user = User(username="manager@test.com")
        assert Role(name="manager")

        request = _make_request(user=user, active_role="manager", ip="8.8.8.8")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None

    def test_admin_role_allowed_from_any_ip(self):
        """admin + IP externo → passa."""
        from apps.accounts.models import Role

        user = User(username="admin@test.com")
        assert Role(name="admin")

        request = _make_request(user=user, active_role="admin", ip="9.9.9.9")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None

    def test_nir_role_blocked_from_external_ip(self):
        """nir + IP externo (1.2.3.4) → 403."""
        from apps.accounts.models import Role

        user = User(username="nir@test.com")
        assert Role(name="nir")

        request = _make_request(user=user, active_role="nir", ip="1.2.3.4")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is not None
        assert response.status_code == 403

    def test_scheduler_role_blocked_from_external_ip(self):
        """scheduler + IP externo → 403."""
        from apps.accounts.models import Role

        user = User(username="scheduler@test.com")
        assert Role(name="scheduler")

        request = _make_request(user=user, active_role="scheduler", ip="1.2.3.4")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is not None
        assert response.status_code == 403

    def test_nir_role_allowed_from_intranet_ip(self, settings):
        """nir + IP interno (10.0.0.1) → 200."""
        from apps.accounts.models import Role

        settings.INTRANET_IP_RANGE = "10.0.0.0/8"
        user = User(username="nir@test.com")
        assert Role(name="nir")

        request = _make_request(user=user, active_role="nir", ip="10.0.0.1")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None  # allowed through

    def test_scheduler_role_allowed_from_intranet_ip(self, settings):
        """scheduler + IP interno → passa."""
        from apps.accounts.models import Role

        settings.INTRANET_IP_RANGE = "10.0.0.0/8"
        user = User(username="scheduler@test.com")
        assert Role(name="scheduler")

        request = _make_request(user=user, active_role="scheduler", ip="10.0.0.42")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None

    def test_no_intranet_range_configured_blocks_restricted_roles(self, settings):
        """Sem INTRANET_IP_RANGE → nir bloqueado (segurança)."""
        from apps.accounts.models import Role

        settings.INTRANET_IP_RANGE = ""
        user = User(username="nir@test.com")
        assert Role(name="nir")

        request = _make_request(user=user, active_role="nir", ip="10.0.0.1")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is not None
        assert response.status_code == 403

    def test_unauthenticated_user_not_blocked(self, settings):
        """Usuário não autenticado → passa pelo middleware."""
        from django.contrib.auth.models import AnonymousUser

        settings.INTRANET_IP_RANGE = "10.0.0.0/8"
        request = _make_request(user=AnonymousUser(), active_role=None, ip="1.2.3.4")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None

    def test_no_active_role_not_blocked(self, settings):
        """Autenticado sem active_role → passa (ActiveRoleMiddleware cuida disso)."""
        settings.INTRANET_IP_RANGE = "10.0.0.0/8"
        user = User(username="multi@test.com")

        request = _make_request(user=user, active_role=None, ip="1.2.3.4")
        middleware = _make_middleware()

        response = middleware(request)
        assert response is None
