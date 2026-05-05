# Slice 2: App Intake + Decorator role_required

> **Status**: TODO
> **Depende de**: Slice 1 (tema hospitalar)
> **Change**: `openspec/changes/intake-nir/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 8 (permissões), seção 3 (FSM), seção 4 (fluxos)
3. `apps/accounts/middleware.py` — como active_role funciona na sessão
4. `apps/cases/models.py` — modelo Case, CaseStatus, FSM transitions

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`. Fase 0 completa + Slice 1 (tema hospitalar).
Apps existentes: `accounts`, `cases`, `llm`.

### Sua Tarefa

1. Criar app `apps/intake/` com estrutura mínima
2. Criar decorator `@role_required("nir")` reutilizável em `apps/accounts/decorators.py`
3. Configurar URLs do intake em `config/urls.py`
4. Criar view placeholder `intake_home` que renderiza "Em construção"

### Arquivos a Criar/Modificar (idealmente <= 6)

```
apps/intake/__init__.py           # Criar
apps/intake/apps.py               # Criar (IntakeConfig)
apps/intake/views.py              # Criar (intake_home placeholder)
apps/intake/urls.py               # Criar
apps/intake/tests/__init__.py     # Criar
apps/intake/tests/test_decorators.py  # Testes do role_required
apps/accounts/decorators.py       # Criar (role_required decorator)
config/settings/base.py           # MODIFICAR: adicionar "apps.intake" em INSTALLED_APPS
config/urls.py                    # MODIFICAR: incluir intake URLs
```

### Detalhes Técnicos

#### apps/accounts/decorators.py

```python
from django.contrib import messages
from django.shortcuts import redirect

def role_required(*allowed_roles: str):
    """Decorator que verifica se o active_role está entre os permitidos.

    Uso:
        @login_required
        @role_required("nir")
        def my_view(request): ...

        @login_required
        @role_required("doctor", "manager")
        def my_view(request): ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            active_role = request.session.get("active_role")
            if active_role not in allowed_roles:
                messages.error(request, "Você não tem permissão para acessar esta página.")
                return redirect("/")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

Nota: `role_required` NÃO substitui `@login_required`. Deve ser usado depois dele.

#### apps/intake/apps.py

```python
from django.apps import AppConfig

class IntakeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.intake"
```

#### apps/intake/views.py

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.decorators import role_required

@login_required
@role_required("nir")
def intake_home(request):
    """Dashboard do NIR — lista de casos e upload."""
    # Placeholder — será implementado nos próximos slices
    return render(request, "intake/intake_home.html", {})
```

#### apps/intake/urls.py

```python
from django.urls import path
from . import views

app_name = "intake"

urlpatterns = [
    path("", views.intake_home, name="home"),
]
```

#### config/urls.py

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("cases/", include("apps.intake.urls")),  # ← NOVO
]
```

#### templates/intake/intake_home.html

Estender `base.html`, usar header subtitle "Upload de encaminhamentos e acompanhamento de casos".
Conteúdo placeholder: card com "Em construção — upload de PDF em breve".

### TDD — Testes a Escrever PRIMEIRO

#### apps/intake/tests/test_decorators.py

1. `test_role_required_allows_correct_role`: nir acessa view → 200
2. `test_role_required_blocks_wrong_role`: doctor acessa view nir → redirect + mensagem de erro
3. `test_role_required_blocks_no_role`: sem active_role → redirect
4. `test_role_required_allows_multiple_roles`: decorator aceita lista de roles
5. `test_intake_home_requires_login`: GET /cases/ sem login → redirect /login/
6. `test_intake_home_allows_nir`: nir + login → 200
7. `test_intake_home_blocks_doctor`: doctor + login → redirect

### Critérios de Sucesso

```bash
uv run python manage.py check --settings=config.settings.dev
uv run pytest -v
# Esperado: todos passando, zero regressão
```

### Relatório

Gere `/tmp/slice-intake-002-report.md`.
Informe `REPORT_PATH=/tmp/slice-intake-002-report.md`.
