# Slice 001: Banner SSR de erro com âncora nativa

## Handoff com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md` e os artefatos deste change. Inspecione:

- `templates/doctor/decision.html` — linha ~12 (`{% block content %}`), linha
  ~37 (botão âncora existente `#doctor-decision-form`), linha ~314 (form);
- `static/js/decision.js` — bloco atual de scroll `data-scroll-to-errors`;
- `apps/doctor/tests/test_views.py` — testes `test_decision_page_without_errors_has_no_scroll_marker`
  e `test_submit_with_validation_error_marks_form_for_scroll` (serão substituídos).

### Motivo

O scroll automático (`scrollIntoView` na carga) não rolou em teste manual de
produção. A tela já usa âncora nativa confiável (“Ir para decisão”). O banner
no topo é determinístico e dispensa JS.

## Escopo (cap: 3 arquivos de código)

1. `templates/doctor/decision.html` — remove marcador do form; adiciona banner.
2. `static/js/decision.js` — remove o bloco de scroll do marcador.
3. `apps/doctor/tests/test_views.py` — substitui os dois testes de marcador
   por testes de banner.

Além destes, apenas `tasks.md` deste change. Outro arquivo → PARE/INCOMPLETO.

## Protocolo obrigatório (TDD)

### 1. RED

Substitua os dois testes de scroll por:

- `test_submit_with_validation_error_shows_error_banner`: POST inválido
  re-renderiza (200) com o texto do banner (ex.: `id="decision-error-banner"`)
  e com `href="#doctor-decision-form"` dentro dele; NÃO contém
  `data-scroll-to-errors`.
- `test_decision_page_without_errors_has_no_error_banner`: GET sem erro não
  contém `decision-error-banner`.

Registre a falha: `uv run pytest apps/doctor/tests/test_views.py -q -k banner`.

### 2. GREEN

Template:

- Remova `{% if form.errors %} data-scroll-to-errors{% endif %}` da tag form.
- Logo após `{% block content %}` / abertura de `doctor-decision-layout` (topo
  do conteúdo), adicione:
  `{% if form.errors %}` banner `alert alert-danger` com
  `id="decision-error-banner"`, mensagem de erro e contagem
  (`{{ form.errors|length }}`) e `<a class="btn ..." href="#doctor-decision-form">Ir para o formulário</a>` `{% endif %}`.

JS: remova o bloco que lê `data-scroll-to-errors` (mantenha o restante).

### 3. REFACTOR

Banner acessível (`role="alert"`), estilo coerente com Bootstrap 5.3 usado no
projeto. Sem código morto.

## Gates de autoavaliação

1. Testes falharam no RED? Cole a saída.
2. O banner só aparece com erro? Mostre os dois testes.
3. Sobrou referência a `data-scroll-to-errors`? (`rg -n data-scroll-to-errors` → vazio.)
4. Quality gate completo passou? Cole resumo.

## Quality gates obrigatórios

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Relatório

Salvar em `/tmp/fix-doctor-decision-error-banner-slice-001-report.md`.

## Commit

Mensagem: `fix(doctor): exibir banner de erro com âncora no topo da decisão médica`.
Push na branch `feature/fix-doctor-decision-error-banner`.
