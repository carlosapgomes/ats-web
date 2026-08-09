# Slice 001: Marcador SSR + scroll até o primeiro campo inválido

## Handoff com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md` e os artefatos deste change.
Inspecione obrigatoriamente:

- `templates/doctor/decision.html` — `<form id="decision-form">` (~linha 314),
  campos com `is-invalid`/`invalid-feedback`;
- `static/js/decision.js` — IIFE de inicialização;
- `apps/doctor/tests/test_views.py` — testes existentes de submit inválido
  (ex.: `test_submit_with_observation_over_500_chars_shows_error`,
  `test_submit_invalid_form_preserves_lock`).

### Problema

Após erro de validação no submit, a resposta SSR volta ao topo da página e o
formulário (abaixo do resumo clínico) fica fora da viewport; o médico não vê
os erros.

## Escopo (cap: 3 arquivos de código)

1. `templates/doctor/decision.html` — atributo condicional no form.
2. `static/js/decision.js` — leitura do marcador + scroll/focus.
3. `apps/doctor/tests/test_views.py` — teste SSR do marcador.

Além destes, apenas `tasks.md` deste change. Qualquer outro arquivo → PARE e
reporte INCOMPLETO.

## Protocolo obrigatório (TDD)

### 1. RED

Em `test_views.py`, adicione na classe que cobre submit de decisão (a mesma
dos testes de erro citados) um teste que:

- executa POST em `doctor:submit` com payload sabidamente inválido (use o
  mesmo setup de `test_submit_with_observation_over_500_chars_shows_error`);
- asserta que a resposta re-renderizada contém `data-scroll-to-errors`.

Registre a falha: `uv run pytest apps/doctor/tests/test_views.py -q -k scroll`.

### 2. GREEN

- Template: na tag `<form id="decision-form" ...>`, adicione
  `{% if form.errors %} data-scroll-to-errors{% endif %}`.
- `decision.js`: logo após a guarda `if (!form) return;`, se
  `form.hasAttribute('data-scroll-to-errors')`, encontre
  `form.querySelector('.is-invalid')` e, se existir, chame
  `scrollIntoView({ behavior: 'smooth', block: 'center' })` e
  `el.focus({ preventScroll: true })`.
- Se o teste exigir ajuste de contexto do form na view (ex.: `form.errors`
  disponível no template), NUNCA mude a validação — apenas o render.

### 3. REFACTOR

Código JS coeso com o estilo do arquivo (vanilla, IIFE existente). Sem código
morto.

## Gates de autoavaliação

1. O teste falhou no RED? Cole a saída.
2. O marcador aparece só com erro? Mostre o teste de ausência (GET sem erro)
   — se não existir, adicione-o.
3. A rolagem ocorre apenas quando há `.is-invalid`? Mostre o trecho JS.
4. Quality gate completo passou? Cole resumo.

## Quality gates obrigatórios

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Relatório

Salvar em `/tmp/fix-doctor-decision-scroll-to-form-errors-slice-001-report.md`.

## Commit

Mensagem: `fix(doctor): rolar até o formulário de decisão após erro de validação`.
Push na branch `feature/fix-doctor-decision-scroll-to-form-errors`.
