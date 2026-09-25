# Slice 001 — Affordances do componente compartilhado provadas na jornada de upload

## Objetivo

Entregar, na superfície de upload (`templates/intake/intake_home.html`), as
affordances visuais do combobox compartilhado: placeholder do input
aprimorado propagado de `data-combobox-placeholder`, hint persistente de
busca associado por `aria-describedby`, chevron CSS-only ligado à expansão,
borda de repouso/hover mais presentes com alvo ≥ 44 px e estado selecionado
na listbox — sem qualquer mudança em contrato POST, options, validação
backend ou semântica ARIA base (D9).

## Contexto necessário

- `static/js/procedure_combobox.js` — `enhance()` cria o input (linhas ~136)
  e já propaga `describedby`; `syncFromSelect()` (~276) sincroniza
  input.value com o select; as rows são construídas em ~171-190.
- `static/css/app.css` — bloco `.procedure-combobox*` (linhas ~1350-1440):
  wrapper `.procedure-combobox` já é `position: relative`; variáveis
  disponíveis: `--hospital-border`, `--hospital-control-border`,
  `--hospital-accent`, `--hospital-accent-light`, `--hospital-primary`,
  `--hospital-surface`.
- `templates/intake/intake_home.html` — select `id="exam-type-select"` com
  `aria-describedby="exam-type-guidance{% if exam_type_error %} exam-type-error{% endif %}"`;
  hint/guidance atual em `#exam-type-guidance` (linha ~46).
- `static/js/tests/procedure_combobox.test.js` — mini-DOM sem dependências;
  cobre teclado/ARIA/normalização. Executa com `node --test`.
- `apps/intake/tests/test_searchable_procedure_upload.py` — cobertura
  canônica Django-side do upload (HTML/POST/re-render/fallback).
- `tests/test_exam_type_badge_css.py` — padrão do teste de guarda de CSS
  (helper `_sem_comentarios`).
- `design.md` deste change: decisões D1-D8. AGENTS §8: vocabulário CSS novo
  exige `app.css` no blast radius e teste de guarda.

## Requisitos verificáveis

- **R1** — O JS propaga `data-combobox-placeholder` do select para o
  atributo `placeholder` do input aprimorado; sem o data-attribute, nenhum
  `placeholder` é definido (compatibilidade).
- **R2** — A row da listbox cujo valor corresponde ao `select.value` recebe
  classe `procedure-combobox__option--selected` e `aria-selected="true"` na
  construção, em `syncFromSelect` (re-render) e após `commit`; as demais rows
  não recebem.
- **R3** — O select de upload ganha
  `data-combobox-placeholder="Digite para buscar — ex.: EDA, cápsula, dilatação…"`
  e um hint `<p class="form-text procedure-combobox__hint"
  id="exam-type-search-hint">Busca ignora acentos e aceita sinônimos
  aprovados. Navegue com ↑ ↓ e confirme com Enter.</p>` abaixo do controle; o
  `aria-describedby` do select passa a incluir `exam-type-search-hint`
  mantendo `exam-type-guidance` e o `exam-type-error` condicional.
- **R4** — CSS (bloco `.procedure-combobox*` de `app.css`):
  chevron `::after` em `.procedure-combobox--enhanced` com rotação via
  `:has(.procedure-combobox__input[aria-expanded="true"])` e
  `pointer-events: none`; padding-right no input para não sobrepor texto;
  borda de repouso `var(--hospital-control-border)` vencendo
  `.hospital-shell .form-control` por especificidade (seletor
  `.hospital-shell .procedure-combobox__input`); `:hover` muda a borda;
  `min-height: 44px` no input; `.procedure-combobox__option--selected` com
  peso 600 e barra à esquerda em accent. *(Emenda pós-review-1: token
  correto é `--hospital-control-border`; ver design D5.)*
- **R5** — Novo guard `tests/test_procedure_combobox_css.py` pina (sem
  comentários) a existência de: `.procedure-combobox__hint`,
  `.procedure-combobox__option--selected`, regra do chevron
  (`procedure-combobox--enhanced:has(` e `::after`), `:hover` do input e
  `min-height` do input.
- **R6** — Testes Node novos: placeholder propagado quando o data-attribute
  existe; ausente quando não existe; classe `--selected` + `aria-selected`
  aplicadas à row do valor selecionado (e removidas de outra após `commit`);
  placeholder permanece no atributo após `syncFromSelect` com valor
  selecionado.
- **R7** — Teste Django do upload estendido: `data-combobox-placeholder`
  presente com o copy da jornada; hint com id
  `exam-type-search-hint` presente; `aria-describedby` referencia hint +
  guidance; no re-render com erro, a associação inclui hint + guidance +
  erro simultaneamente.

## Escopo e expected blast radius

```yaml
expected_files:
  - static/js/procedure_combobox.js
  - static/css/app.css
  - templates/intake/intake_home.html
  - static/js/tests/procedure_combobox.test.js
  - apps/intake/tests/test_searchable_procedure_upload.py
  - tests/test_procedure_combobox_css.py

allowed_incidental_files: []

out_of_scope:
  - templates/case_detail.html, corrected_resubmission.html, decision.html (Slice 002)
  - qualquer mudança em POST/validação backend/catálogo/policy
  - variáveis em :root ou fora do bloco .procedure-combobox*
  - redesenho além do especificado em R4
```

Escalar ao parent (não ampliar o slice) se: precisar alterar semântica ARIA
base (role/teclado), nomes de campos POST, backend, ou se o suporte a
`:has()` exigir mudança de JS além do especificado.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `static/js/procedure_combobox.js` | Node: testes de placeholder |
| R2 | `static/js/procedure_combobox.js` | Node: testes de `--selected`/`aria-selected` |
| R3 | `templates/intake/intake_home.html` | Django: testes de hint/data-attr/describedby |
| R4 | `static/css/app.css` | Guard `tests/test_procedure_combobox_css.py` |
| R5 | `tests/test_procedure_combobox_css.py` | o próprio teste passa |
| R6 | `static/js/tests/procedure_combobox.test.js` | `node --test` |
| R7 | `apps/intake/tests/test_searchable_procedure_upload.py` | pytest focado |

## Plano de testes do slice

### RED (escreva/ajuste primeiro; confirme a falha pelo motivo esperado)

1. `node --test static/js/tests/procedure_combobox.test.js`
   — falha esperada: os testes novos de placeholder e `--selected` falham
   porque o JS atual não define `placeholder` nem marca a row selecionada.
2. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest tests/test_procedure_combobox_css.py -q`
   — falha esperada: vocabulário CSS ainda não existe em `app.css`.
3. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_searchable_procedure_upload.py -q`
   — falha esperada: asserts novos de `data-combobox-placeholder`,
   `#exam-type-search-hint` e `aria-describedby` ampliado falham.

### GREEN / verificação local

- `node --test static/js/tests/procedure_combobox.test.js` — exit 0.
- `POSTGRES_TEST_HOST_PORT=55433 uv run pytest tests/test_procedure_combobox_css.py apps/intake/tests/test_searchable_procedure_upload.py -q` — exit 0.
- `uv run ruff check static/js 2>/dev/null; uv run ruff check tests/test_procedure_combobox_css.py apps/intake/tests/test_searchable_procedure_upload.py && uv run ruff format --check tests/test_procedure_combobox_css.py apps/intake/tests/test_searchable_procedure_upload.py` — exit 0 (JS não passa por ruff; conferir sintaxe com `node --check static/js/procedure_combobox.js`).
- Regressão próxima: `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/ -q -k "searchable or upload"` — exit 0.

Suíte completa NÃO roda neste slice (reservada ao gate final do change).

## Critérios de aceitação

- [ ] R1-R7 verificados pelos testes/checks acima (todos exit 0 no GREEN).
- [ ] Sem mudança em `name`/`id`/options do select; POST inalterado
      (testes existentes de POST/fallback continuam verdes).
- [ ] `aria-expanded`/teclado/`aria-activedescendant` inalterados
      (testes Node existentes continuam verdes).
- [ ] Foco visível existente preservado (regra `:focus-visible` intacta).
- [ ] Blast radius dentro do `expected_files`.

## Contrato de handoff

Worker com contexto fresco: leia `design.md` (D1-D8), este slice e os
arquivos de contexto antes de editar. Siga RED -> GREEN -> REFACTOR. Não
 toque em `tasks.md`, não faça commit/push (o parent faz após review). O
reviewer verifica BEHAVIOR/TESTS/SCOPE/DESIGN com verdict
`BLOCK`/`OK`/`OK with notes`; P2 isolado não reabre ciclo.
