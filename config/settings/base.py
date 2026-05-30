"""Base Django settings for ATS Web."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.cases",
    "apps.admin_ui",
    "apps.dashboard",
    "apps.intake",
    "apps.llm",
    "apps.pipeline",
    "apps.doctor",
    "apps.scheduler",
    "django_q",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ActiveRoleMiddleware",
    "apps.accounts.middleware.IntranetGuardMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.role_context",
                "apps.accounts.context_processors.queue_counts",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Bahia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB

# INTAKE limits — upload múltiplo NIR
INTAKE_MAX_FILES_PER_BATCH = 30
INTAKE_MAX_UPLOAD_BYTES_PER_FILE = 20 * 1024 * 1024  # 20 MB
INTAKE_MAX_UPLOAD_BYTES_PER_BATCH = 600 * 1024 * 1024  # 600 MB

# Regulation report gate — deterministic detection thresholds
# Minimum cleaned text length to evaluate as a regulation report
INTAKE_REGULATION_MIN_TEXT_CHARS = 500
# Minimum number of operational section labels that must be present
INTAKE_REGULATION_MIN_OPERATIONAL_SECTIONS = 3

# Intranet Guard
# Range CIDR da intranet (ex: "10.0.0.0/8" ou "192.168.0.0/16")
# Se vazio, papéis nir/scheduler são bloqueados de qualquer IP.
INTRANET_IP_RANGE = os.environ.get("INTRANET_IP_RANGE", "")

# Header do proxy/tunnel com IP real do cliente
# Cloudflare Tunnel padrão usa CF-Connecting-IP
TRUSTED_PROXY_HEADER = os.environ.get("TRUSTED_PROXY_HEADER", "HTTP_CF_CONNECTING_IP")

# LLM Configuration
LLM_CLIENT_FACTORY = "apps.pipeline.llm.create_openai_client"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

# django-q2 — async task queue
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

# Periodic Summary Configuration
# Comma-separated hours (in SUMMARY_TIMEZONE) when summaries are generated.
# Default: 1, 7, 13, 19 (01:00, 07:00, 13:00, 19:00)
SUMMARY_CUTOFF_HOURS = os.environ.get("SUMMARY_CUTOFF_HOURS", "7,13,19,1")

# Timezone for summary window resolution (defaults to project TIME_ZONE)
SUMMARY_TIMEZONE = os.environ.get("SUMMARY_TIMEZONE", TIME_ZONE)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
