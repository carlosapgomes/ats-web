# Design: Separar identidade do app do título de página (`<h1>`)

**Change ID**: `page-title-heading`

## Contexto

Após o change `mobile-header-navbar`, o `navbar-brand` contém `{% block subtitle %}` que varia por página. Textos longos alteram a altura do header e empurram os ícones da direita (sino/avatar/toggler) para baixo, criando inconsistência visual no mobile. Além disso, o `subtitle` tornou-se de facto o único identificador de página, e desde o Slice 002 é um `<span>` — várias páginas estão sem `<h1>` no outline.

A solução separa as duas responsabilidades: o header fica só com a identidade constante; o título por-página vira `<h1>` no `<main>`.

## Arquivos afetados

- `templates/base.html` — remove `{% block subtitle %}` do header; adiciona `<h1 class="page-title">` no `<main>`.
- `static/css/app.css` — classe `.page-title`; estabilização do header.
- 23 templates — rename do bloco `subtitle` → `page_title`.
- `tests/test_base_header_navbar.py` — teste de que header não tem mais `block subtitle`.
- `tests/test_page_title.py` (novo) — renderização do `base.html` com/sem `page_title`.

Sem mudanças em `models.py`, `views.py`, `urls.py`, `services.py` ou FSM.

## Solução técnica

### `templates/base.html`

**Antes:**
```html
<a href="/" class="navbar-brand ...">
  <img src="{% static 'icons/icon-192.png' %}" ... alt="">
  <div class="d-flex flex-column">
    <span class="app-header__title">{{ app_display_name }}</span>
    <span class="app-header__subtitle">{% block subtitle %}Sistema de Regulação Hospitalar CHD{% endblock %}</span>
  </div>
</a>
...
<main class="app-shell container pb-5">
    {% if messages %}...{% endif %}
    {% block content %}{% endblock %}
</main>
```

**Depois:**
```html
<a href="/" class="navbar-brand ...">
  <img src="{% static 'icons/icon-192.png' %}" ... alt="">
  <div class="d-flex flex-column">
    <span class="app-header__title">{{ app_display_name }}</span>
    <span class="app-header__subtitle">Sistema de Regulação Hospitalar CHD</span>
  </div>
</a>
...
<main class="app-shell container pb-5">
    {% if messages %}...{% endif %}
    {% block page_title %}
    <h1 class="page-title">{{ page_title }}</h1>
    {% endblock %}
    {% block content %}{% endblock %}
</main>
```

**Decisão de implementação do bloco:** o `<h1>` fica **dentro** do `{% block page_title %}` default em `base.html`. Templates filhos que quiserem omitir o `<h1>` (ex.: já têm título próprio) podem sobrescrever o bloco com vazio. Para definir só o texto, o filho usa:

```html
{% block page_title %}Meu Título{% endblock %}
```

…mas isso omitiria o `<h1>`. Para preservar o `<h1>` com texto do filho, duas opções:

- **Opção I (recomendada):** filho define `{% block page_title %}Texto{% endblock %}` e o `base.html` envolve com `<h1>`:
  ```html
  {% block page_title %}{% if page_title %}<h1 class="page-title">{{ page_title }}</h1>{% endif %}{% endblock %}
  ```
  Mas `page_title` viria de variável de contexto, não do bloco.

- **Opção II (mais simples para migração mecânica):** o `base.html` provê um bloco `page_title_block` cujo default é vazio; o filho injeta o `<h1>` inteiro:
  ```html
  {# base.html #}
  {% block page_title %}{% endblock %}
  {# filho #}
  {% block page_title %}<h1 class="page-title">Meu Título</h1>{% endblock %}
  ```
  Migração mecânica: `{% block subtitle %}X{% endblock %}` → `{% block page_title %}<h1 class="page-title">X</h1>{% endblock %}`.

**Adoção: Opção II** — migração trivial (append/prepend de tag), `<h1>` explícito por template (claridade), e templates sem override naturalmente não têm `<h1>` (default do bloco vazio).

### `static/css/app.css`

```css
/* Título de página (<h1> no <main>) */
.page-title {
  margin: 0 0 1rem;
  font-family: "Merriweather Sans", sans-serif;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--hospital-primary);
  line-height: 1.2;
}

@media (max-width: 767.98px) {
  .page-title { font-size: 1.1rem; }
}

@media (max-width: 575.98px) {
  .page-title { font-size: 1rem; margin-bottom: 0.75rem; }
}
```

### Estabilização do header

Com a remoção do `{% block subtitle %}`, o `navbar-brand` passa a ter conteúdo **constante** (nome + tagline fixa). A altura do header torna-se determinística. Regras mobile existentes (`app-header__subtitle { font-size: 0.8rem }` em <768px, `0.75rem` em <576px) continuam válidas para a tagline fixa.

### Migração dos 23 templates

Operação puramente mecânica por template:
- Localizar `{% block subtitle %}TEXTO{% endblock %}`.
- Substituir por `{% block page_title %}<h1 class="page-title">TEXTO</h1>{% endblock %}`.
- Onde `TEXTO` contiver variáveis/template tags (`{{ case.agency_record_number }}`), preservar intacto dentro do `<h1>`.

### Caso especial: `notifications.html`

Tem `<h2>` no conteúdo (linha 21). Avaliar no slice do módulo `accounts` se o `<h2>` vira `<h2>` subordinado ao novo `<h1>` (sem conflito) ou se consolida.

## Testabilidade

`tests/test_page_title.py` (Slice 0):

1. `base.html` renderizado sem `page_title` → não contém `<h1 class="page-title">`.
2. `base.html` renderizado com `page_title` definido → contém `<h1 class="page-title">Texto</h1>`.
3. Header (`navbar-brand`) **não** contém `{% block subtitle %}` (apenas tagline fixa).
4. Tagline fixa `"Sistema de Regulação Hospitalar CHD"` presente no header.

Por módulo (Slices 1–4): teste de caracterização que renderiza um template representativo e verifica `<h1 class="page-title">` com o texto esperado.

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| `<h1>` duplicado em página que já tem `<h1>` | Slice por módulo inspeciona cada template; consolidar onde houver conflito. |
| Migração mecânica introduz erro de sintaxe Django | Slice por módulo + `pytest` (renderização) por template. |
| Texto com `|truncatechars` dentro de `<h1>` quebra layout | Preservar filtro; validar no slice `scheduler` (que usa `truncatechars`). |
| Tagline fixa "esconde" o contexto | O `<h1>` no `<main>` repõe o contexto com mais proeminência. |
| Regressão visual (espaçamento) ao adicionar `<h1>` | CSS `.page-title` com margens controladas; verificação visual por slice. |

## Não objetivos (deferidos)

- Adicionar `<h1>` a páginas que hoje não têm override de subtitle (login, profile, home, etc.) — change futuro.
- Reescrever/redigir os textos dos títulos.
- Refatorar subnavs ou cards.

## Sequência de implementação

Ver `tasks.md`. Slice 0 (infraestrutura) habilita os demais; Slices 1–4 migram por módulo (accounts, intake, scheduler, doctor/admin_ui/dashboard). Cada slice é independente após o Slice 0.
