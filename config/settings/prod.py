"""Production settings for ATS Web.

Usage (Docker):
    Settings are selected via DJANGO_SETTINGS_MODULE env var.
    No manual flags needed — the Docker image defaults to this module.
"""

import os

import dj_database_url

from .base import *  # noqa: F401,F403

DEBUG = False
_build_secret = "build-time-secret-not-for-use"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _build_secret) or _build_secret
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Security
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = False  # SSL terminates at Cloudflare Tunnel
X_FRAME_OPTIONS = "DENY"

# Static files — WhiteNoise serves them from staticfiles/
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# django-q2 production
Q_CLUSTER = {
    "workers": 2,
    "timeout": 600,
    "retry": 180,
    "save_limit": 500,
    "queue_limit": 100,
    "catch_up": False,
    "poll": 2.0,
    "label": "ATS Pipeline Worker",
    "orm": "default",
}
