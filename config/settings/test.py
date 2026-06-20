"""Test settings for ATS Web.

Usage:
    # Requires test database container:
    docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

    # Run tests:
    uv run pytest

    # Or explicitly:
    uv run python manage.py check --settings=config.settings.test
"""

import os

import dj_database_url

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["testserver"]

postgres_test_host_port = os.environ.get("POSTGRES_TEST_HOST_PORT", "5433")

DATABASES = {
    "default": dj_database_url.config(
        default=f"postgres://ats_web:ats_web_dev@localhost:{postgres_test_host_port}/ats_web_test",
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
# ALT_CLUSTERS from base.py are preserved for cluster-routing tests.
Q_CLUSTER = {
    "name": "ats",
    "workers": 1,
    "timeout": 900,
    "retry": 1200,
    "save_limit": 250,
    "queue_limit": 50,
    "catch_up": False,
    "poll": 1.0,
    "label": "ATS Pipeline Worker",
    "orm": "default",
    "sync": False,
    "ALT_CLUSTERS": {
        "pdf": {
            "workers": 2,
            "timeout": 180,
            "retry": 300,
            "save_limit": 500,
            "queue_limit": 500,
            "catch_up": False,
            "poll": 1.0,
            "orm": "default",
        },
        "llm": {
            "workers": 1,
            "timeout": 900,
            "retry": 1200,
            "save_limit": 500,
            "queue_limit": 200,
            "catch_up": False,
            "poll": 2.0,
            "orm": "default",
        },
    },
}

# Locmem email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Distinct public/internal URLs so URL-selection tests are not false positives.
# The two values MUST differ to detect regressions in get_account_action_base_url().
PUBLIC_APP_BASE_URL = "https://public.test"
INTERNAL_APP_BASE_URL = "https://internal.test"

# UI: keep tests deterministic regardless of local .env
APP_DISPLAY_NAME = "ATS"

# LLM: Use StaticLlmClient in tests by default
LLM_CLIENT_FACTORY = None  # type: ignore[assignment]
