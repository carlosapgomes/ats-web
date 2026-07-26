"""Testes isolados da configuração de banco do settings de teste.

Usa subprocesso para garantir import fresco do Django settings,
sem interferência de monkeypatch em processo atual.
"""

import json
import os
import subprocess
import sys
from typing import Any, cast

# ── Constantes ─────────────────────────────────────────────────────────────

_CONTROLLED_ENV_KEYS = frozenset(
    {
        "DATABASE_URL",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_PASSWORD_FILE",
        "DB_CONN_MAX_AGE",
        "DB_APPLICATION_NAME",
        "TEST_DATABASE_URL",
        "POSTGRES_TEST_HOST_PORT",
        "DJANGO_SETTINGS_MODULE",
    }
)


def _build_probe_environment(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Monta ambiente limpo para subprocesso de probe.

    1. Copia ``os.environ``.
    2. Remove todas as variáveis controladas herdadas (evita contaminação).
    3. Aplica ``overrides`` explícitos do cenário.
    4. Força ``DJANGO_SETTINGS_MODULE=config.settings.test``.
    """
    env = os.environ.copy()
    for key in _CONTROLLED_ENV_KEYS:
        env.pop(key, None)
    if overrides:
        env.update(overrides)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    return env


_PROBE_CODE = r"""
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

# django.setup() pode falhar sem banco — só importamos settings se possível
import django
from django.conf import settings

django.setup()

cfg = settings.DATABASES["default"]
print(json.dumps({key: cfg.get(key) for key in ("ENGINE", "HOST", "PORT", "NAME", "USER")}))
"""


def _run_probe(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Executa o probe em subprocesso e retorna o dict JSON de saída.

    Usa ``_build_probe_environment`` para isolar o ambiente.
    """
    probe_env = _build_probe_environment(env)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE_CODE],
        capture_output=True,
        text=True,
        timeout=15,
        env=probe_env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Subprocesso falhou (exit={result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


class TestBuildProbeEnvironment:
    """Testes unitários do helper de ambiente (sem subprocesso)."""

    def test_removes_controlled_vars_from_parent_except_dsm(self) -> None:
        """Variáveis controladas herdadas (exceto DJANGO_SETTINGS_MODULE) são removidas.

        DJANGO_SETTINGS_MODULE é intencionalmente forçado pela função.
        """
        env = _build_probe_environment()
        for key in _CONTROLLED_ENV_KEYS:
            if key == "DJANGO_SETTINGS_MODULE":
                assert env[key] == "config.settings.test"
            else:
                assert key not in env

    def test_applies_explicit_overrides(self) -> None:
        """Overrides explícitos permanecem após sanitização."""
        env = _build_probe_environment(
            overrides={
                "DATABASE_URL": "postgres://u:p@h:9999/db",
                "DB_HOST": "myhost",
                "DB_PORT": "8888",
            }
        )
        assert env["DATABASE_URL"] == "postgres://u:p@h:9999/db"
        assert env["DB_HOST"] == "myhost"
        assert env["DB_PORT"] == "8888"

    def test_removes_inherited_test_database_url_when_not_overridden(self) -> None:
        """TEST_DATABASE_URL herdada do pai é removida quando o cenário não a fornece."""
        env = _build_probe_environment()
        assert "TEST_DATABASE_URL" not in env

    def test_keeps_explicit_test_database_url(self) -> None:
        """TEST_DATABASE_URL fornecida explicitamente permanece."""
        env = _build_probe_environment(overrides={"TEST_DATABASE_URL": "postgres://tu:tp@td:6543/ct"})
        assert env["TEST_DATABASE_URL"] == "postgres://tu:tp@td:6543/ct"

    def test_django_settings_module_is_forced(self) -> None:
        """DJANGO_SETTINGS_MODULE final é sempre config.settings.test."""
        env = _build_probe_environment()
        assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.test"

    def test_django_settings_module_override_not_possible(self) -> None:
        """Mesmo se passado como override, DJANGO_SETTINGS_MODULE é forçado."""
        env = _build_probe_environment(overrides={"DJANGO_SETTINGS_MODULE": "config.settings.dev"})
        assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.test"

    def test_inherited_db_vars_do_not_leak(self) -> None:
        """DB_* herdados do pai são removidos antes dos overrides."""
        env = _build_probe_environment(
            overrides={
                "DB_HOST": "override-host",
            }
        )
        # O override deve estar presente
        assert env["DB_HOST"] == "override-host"
        # E nenhum DB_* não overrideado deve estar presente
        assert "DB_NAME" not in env


class TestTestSettings:
    """Testa que config.settings.test isola banco de teste de variáveis genéricas."""

    def test_defaults_to_test_db_when_no_env(self) -> None:
        """Sem variáveis de ambiente, default deve ser localhost:5433/ats_web_test."""
        cfg = _run_probe(
            env={
                "POSTGRES_TEST_HOST_PORT": "5433",
            }
        )
        assert cfg["HOST"] == "localhost"
        assert str(cfg["PORT"]) == "5433"
        assert cfg["NAME"] == "ats_web_test"
        assert cfg["USER"] == "ats_web"

    def test_ignores_generic_database_url(self) -> None:
        """DATABASE_URL genérica não afeta o banco de teste."""
        cfg = _run_probe(
            env={
                "DATABASE_URL": "postgres://evil:pass@evil-host:9999/evil_db",
                "POSTGRES_TEST_HOST_PORT": "5433",
            }
        )
        assert cfg["HOST"] == "localhost"
        assert cfg["NAME"] == "ats_web_test"

    def test_ignores_generic_db_vars(self) -> None:
        """DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD genéricos não afetam."""
        cfg = _run_probe(
            env={
                "DB_HOST": "evil-host",
                "DB_PORT": "9999",
                "DB_NAME": "evil_db",
                "DB_USER": "evil_user",
                "DB_PASSWORD": "evil_pass",
                "POSTGRES_TEST_HOST_PORT": "5433",
            }
        )
        assert cfg["HOST"] == "localhost"
        assert str(cfg["PORT"]) == "5433"
        assert cfg["NAME"] == "ats_web_test"
        assert cfg["USER"] == "ats_web"

    def test_honor_test_database_url(self) -> None:
        """TEST_DATABASE_URL vence override e ignora variáveis genéricas."""
        cfg = _run_probe(
            env={
                "TEST_DATABASE_URL": "postgres://test_user:test_pass@test-db:6543/custom_test",
                "DATABASE_URL": "postgres://evil:pass@evil-host:9999/evil_db",
                "DB_HOST": "evil-host",
                "DB_PORT": "9999",
                "DB_NAME": "evil_db",
                "DB_USER": "evil_user",
                "DB_PASSWORD": "evil_pass",
                "POSTGRES_TEST_HOST_PORT": "5433",
            }
        )
        assert cfg["HOST"] == "test-db"
        assert str(cfg["PORT"]) == "6543"
        assert cfg["NAME"] == "custom_test"
        assert cfg["USER"] == "test_user"
