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

from config.settings.db import get_db_config

from .base import *  # noqa: F401,F403

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("true", "1", "yes")

# Console email backend for development (no actual email sending)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Allow PDF embedded in same-origin <embed>/<iframe> (dev only)
X_FRAME_OPTIONS = "SAMEORIGIN"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-not-for-production")
ALLOWED_HOSTS = ["*"]

postgres_host_port = os.environ.get("POSTGRES_HOST_PORT", "5432")

DATABASES = {
    "default": get_db_config(
        default_db_host="localhost",
        default_db_port=postgres_host_port,
        default_db_name="ats_web_dev",
        default_db_password="ats_web_dev",
        conn_max_age=0,
        conn_health_checks=False,
    )
}
