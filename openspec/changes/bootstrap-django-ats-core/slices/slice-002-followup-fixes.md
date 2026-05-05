# Follow-up: Correções pós Slice 2

> **Prioridade**: antes do Slice 3
> **Motivo**: revisão do planner identificou 3 pontos a corrigir

---

## Correção 1: Remover `User.get_active_role()` (código morto)

O método `get_active_role()` no model `User` retorna sempre `None` e tem comentário
dizendo que o papel ativo fica na sessão. Esse método nunca é chamado e confunde.

**Arquivo**: `apps/accounts/models.py`

**Ação**: remover o método inteiro:

```python
# REMOVER:
def get_active_role(self) -> str | None:
    """Retorna o papel ativo da sessão. Usado em views/middleware."""
    # O papel ativo real fica na sessão, não no model.
    return None
```

---

## Correção 2: Middleware — usar set de paths exatos em vez de startswith

`startswith("/login")` bate em `/login-something`, `/loginpage`, etc.

**Arquivo**: `apps/accounts/middleware.py`

**Ação**: substituir a cadeia de `startswith` por um set de paths exatos:

```python
EXEMPT_PATHS = {"/login/", "/logout/", "/switch-role/", "/admin/", "/static/"}

class ActiveRoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and "active_role" not in request.session
            and request.path not in EXEMPT_PATHS
            and not request.path.startswith("/admin/")  # admin tem sub-paths
            and not request.path.startswith("/static/")  # static tem sub-paths
        ):
            roles = list(request.user.roles.values_list("name", flat=True))
            if len(roles) == 1:
                request.session["active_role"] = roles[0]
            elif len(roles) > 1:
                return redirect("/switch-role/")
        return self.get_response(request)
```

Paths exatos (`/login/`, `/logout/`, `/switch-role/`) + `startswith` apenas para
`/admin/` e `/static/` (que têm sub-paths legítimos).

---

## Correção 3: LoginForm — username field com label correto

O `LoginForm` usa `EmailField` para login, mas o model `AbstractUser.username` é um
`CharField`, não email. Funciona por acidente (Django aceita qualquer string em
`username`). Mas o placeholder diz "seu@email.com" e o label diz "Email", o que é
enganoso se o username não for um email.

**Decisão**: por enquanto, o login é por **username** (não email). Ajustar o form
para refletir a realidade:

**Arquivo**: `apps/accounts/forms.py`

```python
class LoginForm(forms.Form):
    username = forms.CharField(
        label="Usuário",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "nome de usuário",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Sua senha",
        }),
    )
```

**Arquivo**: `templates/accounts/login.html`

Ajustar o label de "Email" para "Usuário" (já que o form field label mudou, o template
deve usar `{{ form.username.label_tag }}` em vez de label hardcoded, ou atualizar o
texto hardcoded).

---

## Gates

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -v
```

Esperado: mesmos 22 testes passando, zero erros.

## Relatório

Gere `/tmp/slice-002-followup-report.md`.
Informe `REPORT_PATH=/tmp/slice-002-followup-report.md`.
