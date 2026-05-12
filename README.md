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

## Ambiente de Desenvolvimento

> Tudo roda em Docker. Não é necessário instalar Python ou uv no host.

### Primeira vez

```bash
# 1. Subir todos os serviços (db + web + worker)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Rodar migrations
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py migrate --settings=config.settings.dev

# 3. Criar superuser
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec web \
  uv run python manage.py createsuperuser --settings=config.settings.dev

# 4. Acessar http://localhost:8080
```

### Comandos do dia-a-dia

```bash
# Subir
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Logs do web
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f web

# Logs do worker (pipeline django-q2)
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f worker

# Parar
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

O diretório do projeto é montado como volume no container (`.` → `/app`), então
edições no host refletem imediatamente no servidor (auto-reload).

### Ambiente de Testes

```bash
# Subir banco de teste (porta 5433, dados efêmeros)
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Rodar testes (no host, com uv)
uv run pytest

# Derrubar e limpar dados
docker compose -f docker-compose.yml -f docker-compose.test.yml down -v
```

### Produção

```bash
# Subir todos os serviços (db + web + worker)
# Requer: DJANGO_SECRET_KEY, POSTGRES_PASSWORD no .env ou env vars
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Rodar migrations
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web \
  uv run python manage.py migrate --settings=config.settings.prod

# Coletar estáticos
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web \
  uv run python manage.py collectstatic --noinput --settings=config.settings.prod
```

## Quality Gate

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Arquitetura Docker

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   web (:8000)    │  │    worker       │  │   db (:5432)    │
│─────────────────│  │─────────────────│  │─────────────────│
│ Dev:  runserver │  │ django-q2       │  │ PostgreSQL 17   │
│ Prod: gunicorn  │  │ qcluster        │  │ + unaccent      │
│ Vol: . → /app   │  │ Vol: . → /app   │  │ Dev: persist    │
│                  │  │                  │  │ Test: tmpfs     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
       rede interna Docker (ats-web-dev / ats-web-prod)
```
