"""Database configuration helper.

Resolves DATABASES["default"] from DATABASE_URL (backward compatible)
or individual DB_* environment variables with Docker/K8s secrets support.
"""

import os
from pathlib import Path
from typing import Any

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def _environment_or_file(name: str, default: str | None = None) -> str:
    """Read *name* from the environment or, as a fallback, from the file
    pointed to by ``{name}_FILE`` (Docker secret / K8s projected volume).

    Returns:
        The secret value.

    Raises:
        ImproperlyConfigured: when neither the variable nor the file is
            available, the file cannot be read, or the file is empty.
    """
    # Check _FILE first: file-based secrets are more secure and take precedence.
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        try:
            secret = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(f"Não foi possível ler o segredo em {file_path}.") from exc
        if not secret:
            raise ImproperlyConfigured(f"O arquivo indicado por {name}_FILE está vazio.")
        return secret

    value = os.environ.get(name)
    if value:
        return value

    if default is not None:
        return default

    return ""


def get_db_config(
    conn_max_age: int = 0,
    conn_health_checks: bool = False,
    default_db_host: str = "db",
    default_db_port: str = "5432",
    default_db_name: str = "ats_web",
    default_db_user: str = "ats_web",
    default_db_password: str | None = None,
    default_application_name: str = "ats_web",
) -> dict[str, Any]:
    """Build the Django DATABASES["default"] dictionary.

    Resolution order:

    1. If ``DATABASE_URL`` is set → use :func:`dj_database_url.parse`
       (backward compatible; query params such as ``?sslmode=require``
       are preserved).
    2. Otherwise, assemble the dict directly from individual ``DB_*``
       variables, *without* constructing an intermediate URL string
       (avoids encoding bugs with special characters in passwords).

    ``DB_CONN_MAX_AGE``, when set, overrides *conn_max_age* in both paths.
    ``DB_APPLICATION_NAME`` is placed in ``OPTIONS["application_name"]``
    on the individual-variables path.
    """
    # ── Path A: DATABASE_URL (backward compatible) ─────────────────────
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        resolved_conn_max_age = int(os.environ.get("DB_CONN_MAX_AGE", str(conn_max_age)))
        return dict(
            dj_database_url.parse(
                database_url,
                conn_max_age=resolved_conn_max_age,
                conn_health_checks=conn_health_checks,
            )
        )

    # ── Path B: individual DB_* variables (dict direct, no URL round-trip) ──
    db_host = os.environ.get("DB_HOST", default_db_host)
    db_port = os.environ.get("DB_PORT", default_db_port)
    db_name = os.environ.get("DB_NAME", default_db_name)
    db_user = os.environ.get("DB_USER", default_db_user)
    db_password = _environment_or_file("DB_PASSWORD", default=default_db_password)

    # Match dj_database_url.config() behaviour: return empty dict when no
    # credentials are available (e.g. during Docker build collectstatic).
    if not db_password:
        return {}

    resolved_conn_max_age = int(os.environ.get("DB_CONN_MAX_AGE", str(conn_max_age)))

    application_name = os.environ.get("DB_APPLICATION_NAME", default_application_name)

    return {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": db_host,
        "PORT": db_port,
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_password,
        "CONN_MAX_AGE": resolved_conn_max_age,
        "CONN_HEALTH_CHECKS": conn_health_checks,
        "OPTIONS": {
            "application_name": application_name,
        },
    }
