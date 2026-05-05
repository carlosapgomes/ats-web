# ats-web

Sistema de triagem automatizada para EDA (Endoscopia Digestiva Alta) — reimplantação web Django.

## Documentação

- `AGENTS.md` — regras, stack, comandos, política de testes
- `PROJECT_CONTEXT.md` — contexto executivo do sistema
- `ROADMAP.md` — fases de implementação
- `docs/DOMAIN_ANALYSIS.md` — análise de domínio completa
- `docs/adr/` — decisões arquiteturais

## Stack

Python 3.13+ · Django 5.2+ · PostgreSQL 17+ · Bootstrap 5.3 · Vanilla JS · uv

## Quick Start

```bash
uv sync
uv run python manage.py migrate --settings=config.settings.dev
uv run python manage.py runserver --settings=config.settings.dev
```

## Quality Gate

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```
