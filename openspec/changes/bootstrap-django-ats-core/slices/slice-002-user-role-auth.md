# Slice 2: Modelos User + Role + Autenticação

> **Status**: DONE
> **Depende de**: Slice 1
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
O **Slice 1** já foi executado: a estrutura base do projeto está funcional
com `pyproject.toml`, `config/settings/`, `manage.py`.

Leia `AGENTS.md` para regras do projeto.

### Sua Tarefa

Criar o app `accounts` com modelos `User` e `Role`, views de login/logout
com seleção de papel ativo, e troca de papel via `/switch-role/`.

### Arquivos a Criar/Modificar (idealmente <= 10)

```
apps/accounts/__init__.py
apps/accounts/models.py            # User + Role
apps/accounts/views.py             # login, logout, switch_role
apps/accounts/urls.py              # URLs de autenticação
apps/accounts/forms.py             # LoginForm, RoleSelectForm
apps/accounts/admin.py             # admin registration
apps/accounts/apps.py              # AppConfig
apps/accounts/middleware.py        # ActiveRoleMiddleware (stub)
config/settings/base.py            # adicionar accounts app, descomentar AUTH_USER_MODEL
config/urls.py                     # incluir accounts.urls
templates/accounts/login.html      # tela de login
templates/accounts/switch_role.html # tela de seleção de papel
```

### Detalhes Técnicos

#### apps/accounts/models.py

```python
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """Papel do usuário no sistema. Um usuário pode ter múltiplos papéis."""
    name = models.CharField(max_length=20, unique=True)

    ROLE_CHOICES = [
        ("nir", "NIR"),
        ("doctor", "Médico"),
        ("scheduler", "Agendador"),
        ("manager", "Supervisor"),
        ("admin", "Administrador"),
    ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """Usuário customizado com multi-role."""
    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    account_status = models.CharField(
        max_length=10,
        choices=[
            ("active", "Active"),
            ("blocked", "Blocked"),
            ("removed", "Removed"),
        ],
        default="active",
    )

    def get_active_role(self) -> str | None:
        """Retorna o papel ativo da sessão. Usado em views/middleware."""
        # Este método é um helper. O papel ativo real fica na sessão.
        return None

    @property
    def is_account_active(self) -> bool:
        return self.account_status == "active" and self.is_active
```

#### apps/accounts/views.py

Implementar 3 views:

1. **login_view** (`GET/POST /login/`):
   - GET: renderizar form de login (email + senha)
   - POST: autenticar via `django.contrib.auth.authenticate(username=..., password=...)`
   - Se sucesso: verificar quantos roles o usuário tem
     - 1 role: setar `request.session["active_role"]` e redirecionar para `/`
     - 0 roles: redirecionar para `/switch-role/` (edge case)
     - N roles: redirecionar para `/switch-role/`
   - Se falha: re-renderizar form com erro

2. **logout_view** (`POST /logout/`):
   - `django.contrib.auth.logout(request)`
   - Redirecionar para `/login/`

3. **switch_role_view** (`GET/POST /switch-role/`):
   - Login required
   - GET: listar papéis do usuário como cards/botões
   - POST: receber `role` via form, validar que está em `user.roles.all()`
   - Setar `request.session["active_role"] = role_name`
   - Redirecionar para `/`

#### config/settings/base.py — mudanças

1. Descomentar `AUTH_USER_MODEL = "accounts.User"`
2. Adicionar `"apps.accounts"` em `INSTALLED_APPS`
3. Adicionar `LOGIN_URL = "/login/"`
4. Adicionar `LOGIN_REDIRECT_URL = "/"`
5. Adicionar `LOGOUT_REDIRECT_URL = "/login/"`

#### apps/accounts/middleware.py — ActiveRoleMiddleware

Middleware leve que garante que `request.session["active_role"]` existe
se o usuário está autenticado. Se não existe e o usuário tem roles,
redireciona para `/switch-role/`.

```python
class ActiveRoleMiddleware:
    """Garante papel ativo na sessão para usuários autenticados."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and "active_role" not in request.session
            and not request.path.startswith("/login")
            and not request.path.startswith("/switch-role")
            and not request.path.startswith("/admin")
            and not request.path.startswith("/static")
        ):
            # Se tem exatamente 1 role, setar automaticamente
            roles = list(request.user.roles.values_list("name", flat=True))
            if len(roles) == 1:
                request.session["active_role"] = roles[0]
            elif len(roles) > 1:
                from django.shortcuts import redirect
                return redirect("/switch-role/")
        return self.get_response(request)
```

Adicionar em `MIDDLEWARE` após `AuthenticationMiddleware`:
`"apps.accounts.middleware.ActiveRoleMiddleware"`

#### Templates

**templates/accounts/login.html**: Form simples com Bootstrap 5.3:
- Campo email (username)
- Campo senha
- Botão "Entrar"
- Mensagens de erro

**templates/accounts/switch_role.html**: Cards com Bootstrap 5.3:
- "Escolha com qual papel deseja entrar:"
- Botões para cada role do usuário
- Labels em português (NIR, Médico, Agendador, Supervisor, Administrador)

### TDD — Testes a Escrever PRIMEIRO

Criar `apps/accounts/tests/` com:

1. **test_models.py**:
   - `test_create_user_with_role`: criar user, atribuir role, verificar M2M
   - `test_user_without_roles`: user sem roles não quebra
   - `test_user_account_status_default`: default é "active"

2. **test_views.py**:
   - `test_login_page_renders`: GET /login/ retorna 200
   - `test_login_valid_credentials`: POST com credenciais válidas redireciona
   - `test_login_invalid_credentials`: POST com credenciais inválidas mostra erro
   - `test_login_single_role_auto_select`: user com 1 role vai direto para /
   - `test_login_multiple_roles_redirects_to_switch`: user com N roles vai para /switch-role/
   - `test_logout_redirects_to_login`: POST /logout/ redireciona para /login/
   - **test_switch_role_valid_role**: POST com role válido seta na sessão
   - **test_switch_role_invalid_role**: POST com role não atribuído rejeita
   - **test_switch_role_requires_login**: GET /switch-role/ sem auth redireciona para login

3. **test_middleware.py**:
   - `test_middleware_redirects_to_switch_when_no_active_role`: sem active_role na sessão
   - `test_middleware_auto_sets_single_role`: user com 1 role seta automaticamente
   - `test_middleware_skips_login_paths`: /login/ não é interceptado

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: migrations criadas e aplicadas
uv run python manage.py makemigrations accounts --settings=config.settings.dev
uv run python manage.py migrate --settings=config.settings.dev
# Esperado: sem erros

# Gate 2: Django check
uv run python manage.py check --settings=config.settings.dev
# Esperado: "System check identified no issues (0 silenced)."

# Gate 3: testes passam
uv run pytest apps/accounts/tests/ -v
# Esperado: todos os testes passando

# Gate 4: login funcional (smoke test manual)
uv run python manage.py createsuperuser --settings=config.settings.dev
# Criar user, atribuir role "admin", testar login via browser
```

### Relatório

Ao finalizar, gere `/tmp/slice-002-report.md` com:

```markdown
# Slice 2 Report: Modelos User + Role + Autenticação

## Arquivos Criados/Modificados
(liste cada arquivo)

## Gates Executados
(cole output)

## Testes
(cole output de pytest -v)

## Problemas Encontrados e Resoluções

## Snippets Relevantes
```

Informe `REPORT_PATH=/tmp/slice-002-report.md`.
