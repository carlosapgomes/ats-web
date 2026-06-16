"""Development settings for ATS Web.

Usage:
    # Default (local docker postgres):
    uv run python manage.py check --settings=config.settings.dev

    # Custom DB port published on host:
    POSTGRES_HOST_PORT=15432 uv run python manage.py check --settings=config.settings.dev

    # Custom DB URL (env var):
    DATABASE_URL=postgres://user:pass@host:5432/dbname uv run python manage.py check --settings=config.settings.dev
"""

import os

import dj_database_url

from .base import *  # noqa: F401,F403

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("true", "1", "yes")

# Allow PDF embedded in same-origin <embed>/<iframe> (dev only)
X_FRAME_OPTIONS = "SAMEORIGIN"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-not-for-production")
ALLOWED_HOSTS = ["*"]

postgres_host_port = os.environ.get("POSTGRES_HOST_PORT", "5432")

DATABASES = {
    "default": dj_database_url.config(
        default=f"postgres://ats_web:ats_web_dev@localhost:{postgres_host_port}/ats_web_dev",
        conn_max_age=0,
        conn_health_checks=False,
    )
}
