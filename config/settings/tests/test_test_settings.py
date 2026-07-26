"""Testes isolados da configuração de banco do settings de teste.

Usa subprocesso para garantir import fresco do Django settings,
sem interferência de monkeypatch em processo atual.
"""

import json
import os
import subprocess
import sys
from typing import Any, cast

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

    Usa sys.executable e DJANGO_SETTINGS_MODULE para isolar
    completamente o ambiente de settings do processo atual.
    """
    merged = os.environ.copy()
    merged.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    if env:
        merged.update(env)

    # Remove variáveis genéricas hostis que possam vazar do processo pai
    # (o subprocesso as receberá explicitamente nos testes)
    for hostile_key in ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
        merged.pop(hostile_key, None)

    result = subprocess.run(
        [sys.executable, "-c", _PROBE_CODE],
        capture_output=True,
        text=True,
        timeout=15,
        env=merged,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Subprocesso falhou (exit={result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


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
        assert cfg["PORT"] == 5433 or str(cfg["PORT"]) == "5433"
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
        # Deve ignorar DATABASE_URL e usar default test
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
        assert cfg["PORT"] == 5433 or str(cfg["PORT"]) == "5433"
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
        assert cfg["PORT"] == 6543 or str(cfg["PORT"]) == "6543"
        assert cfg["NAME"] == "custom_test"
        assert cfg["USER"] == "test_user"
