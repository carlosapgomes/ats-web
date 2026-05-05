# Slice 1: Bootstrap do Projeto Django

> **Status**: DONE
> **Change**: `openspec/changes/bootstrap-django-ats-core/`
> **Design**: `openspec/changes/bootstrap-django-ats-core/design.md`

---

## Leitura Obrigatória Antes de Implementar

Antes de escrever qualquer código, leia estes arquivos na ordem:

1. `AGENTS.md` — regras do projeto, stack, comandos de validação, política de testes
2. `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` — decisão arquitetural aceita
3. `docs/DOMAIN_ANALYSIS.md` — análise completa de domínio (entidades, estados, transições, eventos, permissões, telas)

Estes documentos dão o contexto de **por que** cada modelo, estado e regra existe.
Sem lê-los, você não terá contexto do domínio clínico (triagem EDA, políticas de pré-operatório, fluxo NIR-médico-agendador).

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em um projeto **greenfield** chamado `ats-web` localizado em `/home/carlos/projects/ats-web/`. Este é um sistema de triagem médica (ATS) que será reimplementado em Django web.

O diretório atual contém apenas arquivos de documentação (nenhum código Python ou Django ainda):

```
ats-web/
├── AGENTS.md              # Regras do projeto (LEIA PRIMEIRO)
├── PROJECT_CONTEXT.md     # Contexto do sistema
├── docs/                  # Documentação
├── openspec/              # Specs e changes
├── prompts/               # Prompts (vazio)
├── scripts/               # Scripts (vazio)
├── tests/                 # Tests (vazio)
├── README.md
└── (mais nada)
```

### Sua Tarefa

Criar a **estrutura base do projeto Django** com `uv`, de forma que
`uv run python manage.py check --settings=config.settings.dev` passe sem erros.

### Stack Obrigatório (ler de `AGENTS.md`)

- Python 3.13+
- Django 5.2+
- django-fsm, django-q2
- PostgreSQL 17+ (em dev: SQLite é aceitável para este slice)
- uv como gerenciador de pacotes
- pytest, ruff, mypy nas dev dependencies

### Arquivos a Criar (idealmente <= 8 arquivos)

```
pyproject.toml                        # dependências + config do projeto
manage.py                             # entry point Django
config/__init__.py
config/settings/__init__.py
config/settings/base.py               # settings comuns
config/settings/dev.py                # settings de desenvolvimento (SQLite ok)
config/urls.py                        # URLconf raiz
config/wsgi.py                        # WSGI entry point
config/asgi.py                        # ASGI entry point
```

### Detalhes Técnicos

#### pyproject.toml

```toml
[project]
name = "ats-web"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "django>=5.2,<6",
    "django-fsm",
    "django-q2",
    "psycopg[binary]",  # PostgreSQL adapter
    "whitenoise",       # static files em produção
    "python-dotenv",    # leitura de .env
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-django",
    "ruff",
    "mypy",
    "django-stubs",
]

[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.dev"
pythonpath = ["."]

[tool.mypy]
plugins = ["mypy_django_plugin.main"]
python_version = "3.13"
strict = true

[tool.django-stubs]
django_settings_module = "config.settings.dev"
```

#### config/settings/base.py

Settings base com:
- `BASE_DIR` apontando para a raiz do projeto
- `INSTALLED_APPS` com `django.contrib.admin`, `django.contrib.auth`, etc.
- `ROOT_URLCONF = "config.urls"`
- `WSGI_APPLICATION = "config.wsgi.application"`
- `AUTH_USER_MODEL = "accounts.User"` (preparar para o slice 2)
- `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`
- `LANGUAGE_CODE = "pt-br"`
- `TIME_ZONE = "America/Bahia"`
- `USE_I18N = True`
- `USE_TZ = True`
- `STATIC_URL = "static/"`
- `MEDIA_URL = "media/"`
- `MEDIA_ROOT = BASE_DIR / "media"`
- Templates dirs apontando para `BASE_DIR / "templates"`
- `django-fsm` e `django-q2` NÃO precisam estar em INSTALLED_APPS (django-fsm não requer, django-q2 será configurado depois)

#### config/settings/dev.py

```python
from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = "dev-secret-key-not-for-production"
ALLOWED_HOSTS = ["*"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}
```

#### config/urls.py

```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
```

#### manage.py

Standard Django manage.py com `settings=config.settings.dev` como default.

### Critérios de Sucesso (Self-Eval Gates)

Execute na ordem e verifique cada um:

```bash
# Gate 1: dependências instaladas
uv sync
# Esperado: sucesso sem erros

# Gate 2: Django check passa
uv run python manage.py check --settings=config.settings.dev
# Esperado: "System check identified no issues (0 silenced)."

# Gate 3: Migration inicial (django contrib)
uv run python manage.py migrate --settings=config.settings.dev
# Esperado: migrations aplicadas, db.sqlite3 criado
# NOTA: vai warn sobre AUTH_USER_MODEL porque accounts app não existe ainda.
# Isso é esperado e será resolvido no slice 2.
# Para este slice, comente AUTH_USER_MODEL em base.py para o check passar,
# e descomente após criar o modelo User no slice 2.
```

### Ordem de Implementação

1. Criar `pyproject.toml`
2. Rodar `uv sync`
3. Criar diretório `config/` com `__init__.py`, `settings/`, `urls.py`, `wsgi.py`, `asgi.py`
4. Criar `manage.py`
5. Rodar `uv run python manage.py check --settings=config.settings.dev`
6. Ajustar até passar sem erros

### NOTA sobre AUTH_USER_MODEL

Para este slice, **comente** a linha `AUTH_USER_MODEL = "accounts.User"` em
`base.py` com um comentário `# TODO: uncomment after accounts app is created (slice 2)`.
O slice 2 vai descomentar quando criar o app accounts.

### O que NÃO fazer

- Não criar apps Django ainda (accounts, cases, llm vem nos slices seguintes).
- Não configurar django-q2 ainda (vem depois).
- Não criar templates ainda (vem no slice 5).
- Não criar `.env` ou `.env.example` (não é necessário em dev com SQLite).

### Relatório

Ao finalizar, gere um relatório em `/tmp/slice-001-report.md` contendo:

```markdown
# Slice 1 Report: Bootstrap do Projeto Django

## Arquivos Criados/Modificados
(liste cada arquivo com descrição breve)

## Gates Executados
(cole output de cada gate)

## Problemas Encontrados e Resoluções
(descreva se houve)

## Snippets Relevantes
(fragmentos de código chave criados)
```

Informe o path do relatório como `REPORT_PATH=/tmp/slice-001-report.md`.
