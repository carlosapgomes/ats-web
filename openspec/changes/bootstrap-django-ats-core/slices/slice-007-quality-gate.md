# Slice 7: Quality Gate Completo (ruff + mypy + pytest)

> **Status**: TODO
> **Depende de**: Slices 1-6 (todos os apps criados)
> **Change**: `openspec/changes/bootstrap-django-ats-core/`

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

Você está em `/home/carlos/projects/ats-web/`, um projeto Django greenfield.
Os **Slices 1-6** já foram executados:
- Estrutura base + accounts (User/Role/auth) + cases (Case FSM + CaseEvent)
- Intranet guard + template base Bootstrap + llm (PromptTemplate)

Leia `AGENTS.md` para regras do projeto e comandos de validação (seção 2).

### Sua Tarefa

Configurar e garantir que o quality gate completo passe:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Isso pode exigir ajustes em:
- Config do ruff em `pyproject.toml`
- Config do mypy em `pyproject.toml` ou `mypy.ini`
- Ajustes de código para satisfazer ruff e mypy
- Garantir que todos os testes passam

### Arquivos a Criar/Modificar (idealmente <= 3)

```
pyproject.toml              # MODIFICAR: ajustar configs de ruff/mypy se necessário
mypy.ini                    # CRIAR se necessário (alternativa ao pyproject.toml)
conftest.py                 # CRIAR na raiz: pytest-django fixtures compartilhadas
```

### Detalhes Técnicos

#### conftest.py (raiz)

```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_password():
    return "testpass123!"


@pytest.fixture
def user_with_single_role(db, user_password):
    from apps.accounts.models import Role

    role = Role.objects.create(name="admin")
    user = User.objects.create_user(
        username="testuser",
        password=user_password,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def user_with_multiple_roles(db, user_password):
    from apps.accounts.models import Role

    roles = Role.objects.bulk_create(
        [Role(name="doctor"), Role(name="manager")]
    )
    user = User.objects.create_user(
        username="multiuser",
        password=user_password,
    )
    user.roles.add(*roles)
    return user


@pytest.fixture
def authenticated_client(client, user_with_single_role, user_password):
    client.login(username=user_with_single_role.username, password=user_password)
    return client
```

#### Ajustes comuns para mypy com Django

Pode ser necessário criar `mypy.ini` ou ajustar `[tool.mypy]` no pyproject.toml:

```ini
[mypy]
plugins = mypy_django_plugin.main
python_version = 3.13
strict = true
warn_return_any = true
warn_unused_configs = true

[mypy.plugins.django-stubs]
django_settings_module = config.settings.dev

# Ignorar migrations (geradas pelo Django)
[mypy.*.migrations.*]
ignore_errors = true
```

#### Ajustes comuns para ruff

Garantir que `pyproject.toml` tem:

```toml
[tool.ruff]
target-version = "py313"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.lint.isort]
known-first-party = ["config", "apps"]
```

### Passos

1. Rodar `uv run ruff check .` e corrigir todos os erros.
2. Rodar `uv run ruff format --check .` e formatar se necessário (`uv run ruff format .`).
3. Rodar `uv run mypy .` e adicionar stubs/ignores se necessário para código de framework.
4. Rodar `uv run pytest -v` e garantir todos passam.
5. Rodar o gate completo em uma linha e garantir sucesso.

### NOTA sobre ruff format

Se `ruff format --check` encontrar arquivos não formatados, rodar
`uv run ruff format .` para formatar automaticamente.

### NOTA sobre mypy

É comum que mypy reclame de:
- `django.db.models.ForeignKey` resolves (precisa de django-stubs)
- `django_fsm.transition` decorators
- `AbstractUser` fields

Adicionar `# type: ignore[...]` apenas onde não há alternativa e
justificar com comentário.

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: ruff lint
uv run ruff check .
# Esperado: "All checks passed!"

# Gate 2: ruff format
uv run ruff format --check .
# Esperado: "X files already formatted"

# Gate 3: mypy
uv run mypy .
# Esperado: "Success: no issues found in X source files"

# Gate 4: pytest
uv run pytest -v
# Esperado: todos os testes passando, zero falhas

# Gate 5: gate completo (TUDO em uma linha)
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
# Esperado: exit code 0

# Gate 6: git status
git status --short
# Esperado: mostrar apenas arquivos modificados/criados deste slice
```

### Relatório

Gere `/tmp/slice-007-report.md` com:

```markdown
# Slice 7 Report: Quality Gate Completo

## Configurações Aplicadas
(cole trechos relevantes de pyproject.toml / mypy.ini)

## Resultado dos Gates
(cole output de cada gate)

## Correções Necessárias
(liste erros encontrados e como resolveu)

## mypy type: ignore adicionados
(liste cada um com justificativa)

## Contagem Final
- Arquivos .py: X
- Linhas de código: X
- Testes: X passando
- mypy: X files checked, 0 errors
```

Informe `REPORT_PATH=/tmp/slice-007-report.md`.
