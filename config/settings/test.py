"""Test settings for ATS Web.

Usage:
    # Requires test database container:
    docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

    # Run tests:
    uv run pytest

    # Or explicitly:
    uv run python manage.py check --settings=config.settings.test
"""

import dj_database_url

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["testserver"]

DATABASES = {
    "default": dj_database_url.config(
        default="postgres://ats_web:ats_web_dev@localhost:5433/ats_web_test",
        conn_max_age=0,
        conn_health_checks=False,
        # Force test database URL regardless of DATABASE_URL env var
        env="TEST_DATABASE_URL",
    )
}

# Hashers mais rápidos para testes
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Permite acesso de localhost para roles restritos (nir, scheduler) nos testes
INTRANET_IP_RANGE = "127.0.0.0/8"

# Desabilita CSRF em testes
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# django-q2: use ORM backend without sync (tasks are queued but not
# executed automatically in tests — prevents pipeline side effects)
Q_CLUSTER = {
    "sync": False,
    "orm": "default",
}

# LLM: Use StaticLlmClient in tests by default
LLM_CLIENT_FACTORY = None  # type: ignore[assignment]
