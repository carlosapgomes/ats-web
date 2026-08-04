# Slice 0: Infraestrutura — header constante + `<h1 class="page-title">` no `<main>`

## Objetivo

Preparar a base para a migração dos títulos por página:

1. Remover `{% block subtitle %}` do `navbar-brand`; substituir por tagline **constante**.
2. Adicionar `{% block page_title %}` no topo de `<main>` (default vazio).
3. Adicionar classe CSS `.page-title`.
4. Garantir que templates filhos que ainda definem `{% block subtitle %}` (a serem migrados nos Slices 1–4) não quebrem — o bloco `subtitle` simplesmente deixa de ser renderizado no header.

Este slice **habilita** os Slices 1–4. Após ele, o header já fica com altura constante; os títulos por-página ficam temporariamente invisíveis até a migração de cada template (aceitável: texto volta a aparecer no `<h1>` conforme cada slice de módulo é mergeado).

## Arquivos (3)

- `templates/base.html`
- `static/css/app.css`
- `tests/test_page_title.py` (novo)

## Handoff / prompt para implementador (contexto zero)

> Em `templates/base.html`:
>
> 1. Na linha do `navbar-brand`, troque:
>    ```html
>    <span class="app-header__subtitle">{% block subtitle %}Sistema de Regulação Hospitalar CHD{% endblock %}</span>
>    ```
>    por:
>    ```html
>    <span class="app-header__subtitle">Sistema de Regulação Hospitalar CHD</span>
>    ```
>    (tagline fixa, sem bloco).
>
> 2. No `<main class="app-shell container pb-5">`, **antes** de `{% block content %}{% endblock %}` (e após o bloco de `messages`), adicione:
>    ```html
>    {% block page_title %}{% endblock %}
>    ```
>
> Em `static/css/app.css`, adicione (após o bloco `.app-header__subtitle`):
>
> ```css
> /* Título de página (<h1> no <main>) */
> .page-title {
>   margin: 0 0 1rem;
>   font-family: "Merriweather Sans", sans-serif;
>   font-size: 1.25rem;
>   font-weight: 700;
>   color: var(--hospital-primary);
>   line-height: 1.2;
> }
> ```
>
> E dentro do `@media (max-width: 767.98px)` existente, adicione:
> ```css
> .page-title { font-size: 1.1rem; }
> ```
>
> E dentro do `@media (max-width: 575.98px)` existente, adicione:
> ```css
> .page-title { font-size: 1rem; margin-bottom: 0.75rem; }
> ```
>
> Não toque nos templates filhos (slices seguintes).

## TDD

### RED (`tests/test_page_title.py`)

```python
import pytest
from importlib import import_module
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory

@pytest.fixture
def rf():
    return RequestFactory()

def _build_request(rf):
    request = rf.get("/")
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore()
    return request

def _render(rf, page_title=None, authenticated=True):
    class StubRoles:
        def count(self): return 1
    class StubUser:
        is_authenticated = authenticated
        username = "jose.silva"
        def get_full_name(self): return "José Silva"
        @property
        def roles(self): return StubRoles()
    request = _build_request(rf)
    user = StubUser() if authenticated else AnonymousUser()
    request.user = user
    ctx = {
        "user": user,
        "app_display_name": "ATS CHD",
        "active_role_display": "Médico",
        "notification_unread_count": 0,
    }
    # Se page_title for passado, simula um template filho que define o bloco:
    # para o teste, renderizamos base.html com o bloco extendido via string.
    if page_title is not None:
        # renderiza um snippet que extende base e define page_title
        from django.template.loader import render_to_string
        # uso de string template extendendo base:
        snippet = (
            '{% extends "base.html" %}'
            '{% block page_title %}<h1 class="page-title">' + page_title + '</h1>{% endblock %}'
        )
        from django.template import engines
        django_engine = engines["django"]
        tmpl = django_engine.from_string(snippet)
        with patch("apps.accounts.context_processors.get_unread_notification_count", return_value=0):
            return tmpl.render(ctx, request)
    with patch("apps.accounts.context_processors.get_unread_notification_count", return_value=0):
        return render_to_string("base.html", ctx, request=request)

def test_header_has_constant_tagline_no_subtitle_block(rf):
    html = _render(rf)
    assert "Sistema de Regulação Hospitalar CHD" in html
    assert "{% block subtitle %}" not in html
    # o <span class="app-header__subtitle"> existe mas sem bloco
    assert '<span class="app-header__subtitle">Sistema de Regulação Hospitalar CHD</span>' in html

def test_no_page_title_by_default(rf):
    html = _render(rf)
    assert "page-title" not in html  # nenhum <h1> renderizado sem definir o bloco

def test_page_title_renders_h1_when_defined(rf):
    html = _render(rf, page_title="Meus Casos")
    assert '<h1 class="page-title">Meus Casos</h1>' in html
```

### GREEN

Aplicar as mudanças em `base.html` e `app.css` até os 3 testes passarem.

### REFACTOR

Confirmar que nenhum teste existente quebra (em especial `tests/test_base_header_navbar.py` que checa a estrutura do header — pode haver assertion sobre `block subtitle`; ajustar se necessário).

## Critérios de sucesso

- [ ] 3 testes novos em `tests/test_page_title.py` passam.
- [ ] `tests/test_base_header_navbar.py` continua passando (ajustar se precisar).
- [ ] `uv run pytest` verde.
- [ ] Header renderiza tagline fixa, sem `{% block subtitle %}`.
- [ ] `<h1 class="page-title">` aparece quando um template define `{% block page_title %}`.
- [ ] Quality gate: ruff, ruff format, mypy, pytest.

## Gates de autoavaliação

- [ ] Nenhum template filho quebra (são 23 com `{% block subtitle %}` — eles apenas deixam de renderizar o subtitle; `<h1>` ainda não aparece até os slices 1–4).
- [ ] Commit rastreável (`refactor(header): constant tagline + page_title block in main`).
