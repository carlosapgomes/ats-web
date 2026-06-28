# Design: Título dinâmico da página "Decididos Hoje" do Médico

## Contexto

A fila médica tem duas abas servidas pela mesma view `doctor_queue` via `?tab=pending`
(default) e `?tab=decided`. O título da página é **estático** em
`templates/doctor/queue.html`:

```django
{% block page_title %}<h1 class="page-title">Casos aguardando decisão</h1>{% endblock %}
```

Resultado: quando o médico clica em **"Decididos Hoje"**, a página lista os casos já
decididos no dia, mas o título continua "Casos aguardando decisão" — contraditório, já
que esses casos não estão mais aguardando nada.

### Decisão de produto (confirmada)
- Aba `pending` → título **"Casos aguardando decisão"** (mantido)
- Aba `decided` → título **"Casos decididos hoje"**

## Objetivo

Tornar o `<h1 class="page-title">` (e o `<title>` do navegador) dinâmicos conforme
`active_tab`, sem alterar layout, navegação nem comportamento de polling HTMX.

## Decisões de Design

### Onde resolver
O `active_tab` já está disponível no contexto da view
(`_doctor_queue_context` → `ctx["active_tab"]`, em `apps/doctor/views.py:245`), então a
solução é puramente de template — **nenhuma mudança em Python**.

### Template
Em `templates/doctor/queue.html`, substituir o bloco estático por lógica condicional
sobre `active_tab`:

```django
{% block page_title %}
  <h1 class="page-title">
    {% if active_tab == 'decided' %}Casos decididos hoje{% else %}Casos aguardando decisão{% endif %}
  </h1>
{% endblock %}
```

- `else` cobre tanto `pending` quanto valor ausente/default (robusto: default da view é
  `"pending"`, então em prática `else == pending`).

### `<title>` do navegador
Para consistência (aba do navegador/aba do sistema), atualizar também o `block title`:

```django
{% block title %}
  {% if active_tab == 'decided' %}Casos decididos hoje{% else %}Casos aguardando decisão{% endif %}
   — Médico · {{ app_display_name }}
{% endblock %}
```

### HTMX
O partial `doctor/_queue_content.html` (retornado por `doctor_queue_partial`) **não** inclui
o `page_title`. Logo, o título só muda em navegação full-page (clique no link da aba) —
que é exatamente o comportamento desejado, pois o polling HTMX de 20s não troca de aba.

## Slices

| # | Escopo | Arquivos |
|---|--------|----------|
| S1 | Título dinâmico (`page_title` + `<title>`) | `templates/doctor/queue.html` |

Slice único (≤ 1 arquivo). Sem mudança em models/views/services.

## Testes

### TDD — RED primeiro
Teste de template/view em `apps/doctor/tests/` (ou onde estão os testes de `doctor_queue`)
afirmando:

1. `?tab=pending` → HTML contém `<h1 ...>Casos aguardando decisão</h1>` e
   `<title>...Casos aguardando decisão... — Médico · ...`.
2. `?tab=decided` → HTML contém `<h1 ...>Casos decididos hoje</h1>` e
   `<title>...Casos decididos hoje... — Médico · ...`.
3. Sem `?tab` (default) → título de `pending` (contrato do default).

### Verde
Implementar o template conforme acima.

## Critérios de sucesso / Self-eval gates

- [ ] `?tab=decided` mostra "Casos decididos hoje" no `<h1>` e no `<title>`.
- [ ] `?tab=pending` (e default) mantém "Casos aguardando decisão".
- [ ] Polling HTMX não afeta o título (partial não o inclui).
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` verde.
- [ ] Nenhum arquivo Python alterado.

## Não-escopo

- Não alterar rótulos das abas (`_nav.html`).
- Não alterar o título do scheduler (outra view, outro padrão).
- Não internacionalizar/tornar configurável por settings — string fixa no template, no
  mesmo padrão já existente.
