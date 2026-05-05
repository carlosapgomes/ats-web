# Slice 1: Tema Hospitalar — Paleta + Fontes

> **Status**: TODO
> **Depende de**: Fase 0 completa
> **Change**: `openspec/changes/intake-nir/`

---

## Leitura Obrigatória Antes de Implementar

Antes de escrever qualquer código, leia estes arquivos na ordem:

1. `AGENTS.md` — regras do projeto, stack, comandos de validação, política de testes
2. `docs/adr/ADR-0001-arquitetura-django-web-ssr-ats-triagem-eda.md` — decisão arquitetural aceita
3. `docs/DOMAIN_ANALYSIS.md` — análise completa de domínio
4. `demo-reference/css/styles.css` — paleta hospitalar completa (referência visual)
5. `demo-reference/nir/dashboard.html` — exemplo de uso da paleta

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Você está em `/home/carlos/projects/ats-web/`, um projeto Django greenfield.
A **Fase 0** (bootstrap) foi concluída: apps accounts, cases, llm funcionando, 91 testes passando.

O arquivo `static/css/app.css` atual tem 3 regras mínimas. O `templates/base.html` usa
Bootstrap 5.3 escuro genérico. Precisamos integrar a paleta hospitalar que já existe
em `demo-reference/css/styles.css`.

### Sua Tarefa

1. Mover a paleta hospitalar do `demo-reference/css/styles.css` para `static/css/app.css`
2. Adicionar fontes Google (Merriweather Sans + Source Sans 3) no `base.html`
3. Atualizar `base.html` para usar o header hospitalar com gradiente em vez da navbar escura
4. Garantir que login.html e switch_role.html continuam funcionando

### Arquivos a Modificar (idealmente <= 4)

```
static/css/app.css          # REESCREVER com paleta hospitalar + componentes
templates/base.html         # header hospitalar + fontes Google
templates/accounts/login.html        # pode precisar de ajuste menor
templates/accounts/switch_role.html  # pode precisar de ajuste menor
```

### Detalhes Técnicos

#### static/css/app.css

Copiar do `demo-reference/css/styles.css` os blocos relevantes:

1. **CSS Variables** (`:root` com `--hospital-*`)
2. **Base** (body, headings)
3. **Header** (`.app-header`, `.app-header__title`, `.app-header__subtitle`, `.app-nav`)
4. **Cards** (`.hospital-shell .card`)
5. **Buttons** (`.btn-hospital`, `.btn-hospital-outline`)
6. **Badges & status** (`.status-badge`, `.status-pending`, etc.)
7. **Upload zone** (`.upload-zone`)
8. **Timeline** (`.timeline-event`)
9. **Steps bar** (`.steps-bar`, `.step-item`)
10. **Notification badge** (`.notif-badge`)
11. **Responsive** (`@media` queries)

Adicionar `body { font-family: "Source Sans 3", sans-serif; }` globalmente.
Adicionar classe `.hospital-shell` no body do `base.html`.

**NÃO copiar** seções que não são relevantes ainda:
- `.decision-section` (Fase 3)
- `.summary-box` (Fase 3)
- `.demo-toast` (demo only)

#### templates/base.html

**Antes**: navbar escura genérica Bootstrap.
**Depois**: header hospitalar com gradiente + nav pills + avatar dropdown.

Manter a funcionalidade existente:
- Badge do papel ativo
- Avatar dropdown (Trocar papel + Sair)
- Área de mensagens Django
- `{% block content %}`

Adicionar:
- `<link>` Google Fonts (Merriweather Sans 600;700, Source Sans 3 400;500;600)
- `class="hospital-shell"` no `<body>`
- Header com gradiente linear (ver `demo-reference/nir/dashboard.html`)
- Nav pills para navegação (placeholder por enquanto)

Exemplo de estrutura do header:

```html
<header class="app-header text-white py-3 mb-4">
  <div class="container">
    <div class="d-flex flex-column flex-lg-row justify-content-between gap-3 align-items-lg-start">
      <div>
        <h1 class="app-header__title">ATS</h1>
        <p class="app-header__subtitle">{% block subtitle %}{% endblock %}</p>
      </div>
      {% if user.is_authenticated %}
      <div class="text-lg-end">
        <p class="app-session-meta mb-2">
          {{ user.get_full_name|default:user.username }} · <strong>{{ active_role_display }}</strong>
        </p>
        <div class="d-flex gap-1 justify-content-lg-end">
          {% if user.roles.count > 1 %}
          <a href="/switch-role/" class="btn btn-sm btn-light">Trocar papel</a>
          {% endif %}
          <form method="post" action="/logout/" class="d-inline">
            {% csrf_token %}
            <button type="submit" class="btn btn-sm btn-light">Sair</button>
          </form>
        </div>
      </div>
      {% endif %}
    </div>
    {% block nav %}{% endblock %}
  </div>
</header>
```

### TDD — Testes

1. **test_templates.py** (adicionar/modificar):

   - `test_base_has_hospital_fonts`: base.html contém link Google Fonts
   - `test_base_has_hospital_css_vars`: app.css contém `--hospital-primary`
   - `test_base_has_hospital_header`: header com classe `app-header`
   - `test_base_shows_role_in_header`: header mostra "NIR" ou "Médico"
   - `test_base_shows_username_in_header`: header mostra username
   - `test_login_page_renders_correctly`: login renderiza sem quebrar
   - `test_switch_role_renders_correctly`: switch-role renderiza sem quebrar

### Critérios de Sucesso (Self-Eval Gates)

```bash
# Gate 1: Django check
uv run python manage.py check --settings=config.settings.dev

# Gate 2: testes
uv run pytest -v

# Gate 3: smoke visual
uv run python manage.py runserver --settings=config.settings.dev
# Abrir http://127.0.0.1:8000/login/ e verificar:
# - Header com gradiente azul hospitalar
# - Fontes Merriweather Sans (títulos) e Source Sans 3 (corpo)
# - Botão "Entrar" com estilo btn-hospital
```

### Relatório

Gere `/tmp/slice-intake-001-report.md`.
Informe `REPORT_PATH=/tmp/slice-intake-001-report.md`.
