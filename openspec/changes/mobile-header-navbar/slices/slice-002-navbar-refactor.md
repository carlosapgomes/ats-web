# Slice 002: Refatorar `<header>` para `navbar navbar-expand-lg` (Opção C)

## Objetivo

Substituir o `<header class="app-header">` custom por um `navbar navbar-expand-lg` do Bootstrap, no padrão **híbrido (Opção C)**:

- **Sempre visíveis** (mobile + desktop): marca (logo + nome) + notificação 🔔 + avatar.
- **Colapsáveis em hambúrguer** (apenas < `lg`): nome completo + papel, manual, trocar papel, sair.
- **Desktop (≥992px)**: tudo expandido em linha, sem regressão visual.

Depende de o Slice 001 já ter corrigido o bug do `:has()`.

## Arquivos

- `templates/base.html` (refator do `<header>`).
- `static/css/app.css` (regras do `navbar` sobre o gradiente `.app-header`).
- `tests/test_base_header_navbar.py` (novo — renderização do template).

## Handoff / prompt para implementador (contexto zero)

> Em `templates/base.html`, substitua o bloco `<header class="app-header text-white py-3 mb-4">...</header>` por um `navbar` Bootstrap 5.3 seguindo a **Opção C**:
>
> - `<header class="app-header navbar navbar-expand-lg py-2 mb-4">` com `container` interno.
> - `navbar-brand` (esquerda): `<img src="{% static 'icons/icon-192.png' %}" width="32" height="32" alt="">` + `<span class="app-header__title">{{ app_display_name }}</span>` + `<span class="app-header__subtitle">{% block subtitle %}...{% endblock %}</span>`. Cor branca, sem text-decoration.
> - Bloco à direita (se autenticado), `d-flex align-items-center gap-2`:
>   - Link de notificação: **preservar exatamente** `id="notification-badge"`, classes funcionais (`notification-badge notification-icon-btn`), todos os `data-*` e o SVG interno. Apenas envolvê-lo como `btn btn-sm btn-light`.
>   - Avatar: `<a href="{% url 'profile' %}" class="avatar-circle" aria-label="Perfil">` contendo as iniciais (use `{{ user.get_full_name|default:user.username|slice:":2"|upper }}` ou filtro simples). Texto completo (nome · papel) fica **dentro** do menu colapsável.
>   - `navbar-toggler`: `<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#sessionMenu" aria-controls="sessionMenu" aria-expanded="false" aria-label="Menu da sessão">` com `navbar-toggler-icon`.
> - Menu colapsável: `<div class="collapse navbar-collapse" id="sessionMenu">` contendo:
>   - `<span class="app-session-meta d-block">{{ user.get_full_name|default:user.username }} · <strong>{{ active_role_display }}</strong></span>`
>   - Link para manual (`{% url 'user_manual' %}`).
>   - `{% if user.roles.count > 1 %}` link "Trocar papel" (`/switch-role/`). `{% endif %}`
>   - Form de logout (`/logout/`, POST com `{% csrf_token %}`) com botão "Sair".
>
> Regras de ordem:
> - No desktop, a marca fica à esquerda e o bloco de sessão à direita. Use `ms-auto` no bloco de sessão para empurrá-lo à direita.
> - O `navbar-collapse` no desktop aparece inline (Bootstrap padrão); abaixo de `lg` colapsa sob o toggler.
>
> Em `static/css/app.css`:
> - Garanta que `.app-header` (gradiente) continue aplicável sobre `.navbar`.
> - Garanta que `.app-header .navbar-brand` e `.app-header .nav-link` usem cor branca.
> - Mantenha as regras mobile existentes (`@media (max-width: 767.98px)`) que ajustam `.app-header__title`/`.app-header__subtitle`.
>
> **Preservar**: o bloco `{% block nav %}{% endblock %}` e o `<main class="app-shell container pb-5">` não mudam.
>
> Crie `tests/test_base_header_navbar.py` conforme a seção TDD.

## TDD

### RED (`tests/test_base_header_navbar.py`)

```python
import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory

@pytest.fixture
def rf():
    return RequestFactory()

def _render(rf, authenticated=True, multi_role=True):
    from django.contrib.auth.models import AnonymousUser
    class StubRoles:
        def count(self):
            return 2 if multi_role else 1
    class StubUser:
        is_authenticated = authenticated
        username = "jose.silva"
        def get_full_name(self):
            return "José Silva"
        @property
        def roles(self):
            return StubRoles()
    ctx = {
        "user": StubUser() if authenticated else AnonymousUser(),
        "app_display_name": "ATS CHD",
        "active_role_display": "Médico",
        "notification_unread_count": 0,
    }
    return render_to_string("base.html", ctx, request=rf.get("/"))

def test_header_uses_navbar(rf):
    html = _render(rf)
    assert 'class="app-header navbar navbar-expand-lg' in html

def test_navbar_brand_has_icon_and_name(rf):
    html = _render(rf)
    assert "navbar-brand" in html
    assert "icons/icon-192.png" in html
    assert "ATS CHD" in html

def test_navbar_toggler_targets_session_menu(rf):
    html = _render(rf)
    assert 'data-bs-target="#sessionMenu"' in html
    assert 'aria-controls="sessionMenu"' in html
    assert 'id="sessionMenu"' in html

def test_notification_badge_preserved(rf):
    html = _render(rf)
    assert 'id="notification-badge"' in html
    assert "notification-badge" in html
    assert "data-notifications-badge" in html

def test_logout_form_present(rf):
    html = _render(rf)
    assert 'action="/logout/"' in html

def test_switch_role_only_when_multi_role(rf):
    assert "/switch-role/" in _render(rf, multi_role=True)
    assert "/switch-role/" not in _render(rf, multi_role=False)

def test_unauthenticated_has_no_session_block(rf):
    html = _render(rf, authenticated=False)
    assert "navbar-toggler" not in html
    assert 'action="/logout/"' not in html
```

(Ajustar conforme convenções de fixtures do projeto; URL reverses precisam de `urls` configurado — usar `@pytest.mark.django_db` se necessário.)

### GREEN

Implementar o refator em `base.html` + ajustes de CSS até todos os testes passarem.

### REFACTOR

- Extrair iniciais para filtro/template tag se a lógica `slice:":2"` ficar confusa.
- Consolidar classes de cor em CSS.

## Critérios de sucesso

- [ ] Todos os testes novos em `tests/test_base_header_navbar.py` passam.
- [ ] `uv run pytest` verde (sem regressões).
- [ ] Desktop (≥992px): header em linha única, sem hambúrguer visível, sem regressão visual (checklist manual no relatório).
- [ ] Mobile (<992px): marca + notificação + avatar + hambúrguer em uma linha; sem overflow horizontal.
- [ ] Badge de notificação continua funcionando (estrutura `id`/`data-*` preservada).
- [ ] Quality gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.

## Gates de autoavaliação

- [ ] Verifiquei visualmente (dev server) em 3 larguras: 1280px, 768px, 360px.
- [ ] Confirmei que `notifications.js` ainda atualiza o badge (inspeção no console).
- [ ] Confirmei que o logout ainda funciona (POST).
- [ ] Confirmei que trocar papel só aparece para multi-role.
- [ ] Commit com mensagem rastreável (`feat(header): adopt Bootstrap navbar with hybrid mobile collapse`).
