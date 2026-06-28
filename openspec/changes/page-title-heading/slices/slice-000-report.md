# Relatório do Slice 000 — Infraestrutura: header constante + `<h1 class="page-title">`

## Resumo

Slice concluído com sucesso. Infraestrutura para títulos por página preparada: tagline do header tornada constante, bloco `{% block page_title %}` adicionado no `<main>`, CSS `.page-title` criado, e testes de regressão passando.

## Arquivos modificados (3 + 1 ajuste)

### 1. `templates/base.html` (modificado)

**Antes:**
```html
<span class="app-header__subtitle">{% block subtitle %}Sistema de Regulação Hospitalar CHD{% endblock %}</span>
...
    {% if messages %}
    ...
    {% endif %}

    <!-- Content -->
    {% block content %}{% endblock %}
```

**Depois:**
```html
<span class="app-header__subtitle">Sistema de Regulação Hospitalar CHD</span>
...
    {% if messages %}
    ...
    {% endif %}

    {% block page_title %}{% endblock %}

    <!-- Content -->
    {% block content %}{% endblock %}
```

### 2. `static/css/app.css` (modificado)

Adicionada classe `.page-title` após `.app-header__subtitle`:

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
```

E responsivos dentro dos media queries existentes:

- `@media (max-width: 767.98px)`: `.page-title { font-size: 1.1rem; }`
- `@media (max-width: 575.98px)`: `.page-title { font-size: 1rem; margin-bottom: 0.75rem; }`

### 3. `tests/test_page_title.py` (novo)

3 testes implementados:

| Teste | Descrição |
|-------|-----------|
| `test_header_has_constant_tagline_no_subtitle_block` | Tagline fixa sem bloco no header |
| `test_no_page_title_by_default` | Nenhum `<h1>` sem definir o bloco |
| `test_page_title_renders_h1_when_defined` | `<h1 class="page-title">` aparece quando template define o bloco |

### 4. `apps/intake/tests/test_supplemental_attachment_views.py` (ajuste)

Teste `test_nir_can_post_supplemental_attachment` verificava texto `"Detalhes do encaminhamento"` que vinha do `{% block subtitle %}` do template `intake/case_detail.html`. Ajustado para verificar `"Anexo complementar adicionado"` (evento de timeline comprovando o redirect correto).

## Quality Gate

| Ferramenta | Resultado |
|------------|-----------|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 174 files already formatted |
| `mypy .` | ✅ Success: no issues found in 193 source files |
| `pytest` | ✅ **1616 passed**, 0 failed, 812 warnings |

## Critérios de Sucesso

- [x] 3 testes novos em `tests/test_page_title.py` passam.
- [x] `tests/test_base_header_navbar.py` continua passando (14/14).
- [x] `uv run pytest` verde (1616 passed).
- [x] Header renderiza tagline fixa, sem `{% block subtitle %}`.
- [x] `<h1 class="page-title">` aparece quando um template define `{% block page_title %}`.
- [x] Quality gate: ruff, ruff format, mypy, pytest.

## Gates de Autoavaliação

- [x] Nenhum template filho quebra (23 com `{% block subtitle %}` — apenas deixam de renderizar o subtitle; `<h1>` ainda não aparece até os slices 1–4).
- [ ] Commit rastreável — pendente.
