# syntax=docker/dockerfile:1

# ── Base: Python + uv ──────────────────────────────────────────────
FROM python:3.13-slim AS base

# uv installer needs curl
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install system deps for psycopg and pymupdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (layer cache)
COPY pyproject.toml uv.lock* ./

# Install dependencies (production only)
RUN uv sync --frozen --no-dev --no-install-project

# Copy project source
COPY . .

# Collect static files (needed for production)
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
RUN uv run python manage.py collectstatic --noinput

# Default: production entrypoint
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
EXPOSE 8000

CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
