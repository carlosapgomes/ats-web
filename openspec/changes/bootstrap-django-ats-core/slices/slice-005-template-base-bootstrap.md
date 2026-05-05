# Slice 5: Template Base + Bootstrap 5.3

> **Status**: DONE
> **Depende de**: Slice 2 (login/logout views)
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
Os **Slices 1-4** já foram executados:
- Estrutura base + accounts (User/Role/auth) + cases (Case FSM) + intranet guard

Leia `AGENTS.md` para regras do projeto.

### Sua Tarefa

Criar o template base HTML com Bootstrap 5.3 (via CDN), incluindo header com
badge do papel ativo, avatar com dropdown (trocar papel, logout), e uma
home page que redireciona conforme o papel ativo.

### Arquivos a Criar/Modificar (idealmente <= 8)

```
templates/base.html                      # template base com Bootstrap 5.3
templates/home.html                      # página inicial (placeholder por papel)
templates/accounts/login.html            # MODIFICAR/RECRIAR: login com Bootstrap
templates/accounts/switch_role.html      # MODIFICAR/RECRIAR: seleção de papel com Bootstrap
apps/accounts/views.py                   # MODIFICAR: adicionar home_view
apps/accounts/urls.py                    # MODIFICAR: adicionar URL da home
static/css/app.css                       # CSS customizado mínimo
static/js/app.js                         # JS vanilla mínimo
```

### Detalhes Técnicos

#### templates/base.html

Template base Bootstrap 5.3 com:

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#0d6efd">
    <title>{% block title %}ATS{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{% static 'css/app.css' %}" rel="stylesheet">
    <!-- PWA manifest -->
    <link rel="manifest" href="/manifest.json">
</head>
<body>
    <!-- Navbar fixa -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">ATS</a>
            {% if user.is_authenticated %}
            <div class="d-flex align-items-center">
                <!-- Badge do papel ativo -->
                <span class="badge bg-primary me-3">{{ active_role_display }}</span>
                <!-- Avatar dropdown -->
                <div class="dropdown">
                    <button class="btn btn-outline-light dropdown-toggle" type="button"
                            data-bs-toggle="dropdown">
                        {{ user.get_full_name|default:user.username }}
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        {% if user.roles.count > 1 %}
                        <li><a class="dropdown-item" href="/switch-role/">Trocar papel</a></li>
                        <li><hr class="dropdown-divider"></li>
                        {% endif %}
                        <li>
                            <form method="post" action="/logout/">
                                {% csrf_token %}
                                <button class="dropdown-item" type="submit">Sair</button>
                            </form>
                        </li>
                    </ul>
                </div>
            </div>
            {% endif %}
        </div>
    </nav>

    <!-- Messages -->
    <div class="container mt-3">
        {% if messages %}
        {% for message in messages %}
        <div class="alert alert-{{ message.tags }} alert-dismissible fade show">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
        {% endif %}
    </div>

    <!-- Content -->
    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{% static 'js/app.js' %}"></script>
</body>
</html>
```

#### Home por papel

`apps/accounts/views.py` — adicionar `home_view`:

```python
ROLE_HOME_URLS = {
    "nir": "/cases/my-cases/",
    "doctor": "/doctor/queue/",
    "scheduler": "/scheduler/queue/",
    "manager": "/dashboard/",
    "admin": "/dashboard/",
}

def home_view(request):
    """Redireciona para a home do papel ativo."""
    active_role = request.session.get("active_role")
    if not active_role:
        return redirect("/switch-role/")
    url = ROLE_HOME_URLS.get(active_role, "/dashboard/")
    # Por enquanto, como as URLs destino não existem, renderizar placeholder
    # Quando os apps forem criados nos próximos changes, trocar para redirect
    return render(request, "home.html", {
        "active_role": active_role,
        "active_role_display": ROLE_DISPLAY_NAMES.get(active_role, active_role),
    })
```

Para este slice, `home.html` mostra um placeholder com o nome do papel e
"Em construção" para cada fila. Os apps reais serão criados em changes seguintes.

#### ROLE_DISPLAY_NAMES

```python
ROLE_DISPLAY_NAMES = {
    "nir": "NIR",
    "doctor": "Médico",
    "scheduler": "Agendador",
    "manager": "Supervisor",
    "admin": "Administrador",
}
```

Adicionar ao context processor para estar disponível em todos os templates.

#### static/css/app.css

CSS customizado mínimo:
- Body background suave
- Navbar ajustes
- Cards de papel no switch-role

#### static/js/app.js

JS vanilla mínimo (vazio por enquanto, preparado para PWA).

### TDD — Testes a Escrever PRIMEIRO

1. **test_views.py** (adicionar aos existentes):
   - `test_home_redirects_by_role`: GET / com papel ativo renderiza home
   - `test_home_without_role_redirects_to_switch`: GET / sem active_role → /switch-role/
   - `test_home_shows_role_name`: home mostra nome do papel em português

2. **test_templates.py** (novo):
   - `test_base_template_renders_bootstrap`: base.html contém link do Bootstrap CDN
   - `test_base_template_shows_role_badge`: navbar mostra badge do papel
   - `test_base_template_shows_logout`: navbar tem botão de logout
   - `test_base_template_switch_role_link`: se múltiplos roles, mostra link "Trocar papel"

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: Django check
uv run python manage.py check --settings=config.settings.dev

# Gate 2: testes
uv run pytest -v

# Gate 3: smoke test visual
uv run python manage.py runserver --settings=config.settings.dev
# Abrir http://127.0.0.1:8000/login/ e verificar:
# - Formulário de login renderiza com Bootstrap
# - Após login, home mostra badge do papel
# - Avatar dropdown funciona
```

### Relatório

Gere `/tmp/slice-005-report.md`.
Informe `REPORT_PATH=/tmp/slice-005-report.md`.
