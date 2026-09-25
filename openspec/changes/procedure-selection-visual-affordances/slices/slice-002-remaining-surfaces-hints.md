# Slice 002 — Placeholder e hint persistente nas superfícies de correção, reenvio e destino médico

## Objetivo

Estender às três superfícies restantes as affordances entregues pelo Slice
001 na jornada de upload: `data-combobox-placeholder` da jornada, hint
persistente de busca com id estável e associação por `aria-describedby` ao
select canônico (que hoje não a possui nessas superfícies), preservando
associações de erro já existentes em re-render.

Pré-requisito: Slice 001 mergeado (componente já propaga placeholder e
`describedby` ao input aprimorado; CSS do hint já existe).

## Contexto necessário

- `templates/intake/case_detail.html` — select
  `id="correction-exam-type-select"` com
  `aria-labelledby="correction-exam-type-label"`, primeira option
  "Selecione o novo conjunto de procedimentos…"; sem `aria-describedby`.
- `templates/intake/corrected_resubmission.html` — select
  `id="exam-type-select"` com `aria-labelledby="exam-type-label"`, primeira
  option "Selecione o tipo de exame…"; sem `aria-describedby`.
- `templates/doctor/decision.html` — select `id="destination-procedure"` com
  `aria-labelledby="destination-procedure-label"`, primeira option
  "Selecione..."; sem `aria-describedby`.
- Hint copy uniforme (decisão D3 do `design.md`): `Busca ignora acentos e
  aceita sinônimos aprovados. Navegue com ↑ ↓ e confirme com Enter.`
  marcado como `<p class="form-text procedure-combobox__hint" id="…">`
  abaixo do controle.
- Placeholders por jornada (D2): correção `Buscar novo conjunto de
  procedimentos…`; reenvio `Buscar tipo de exame do novo envio…`; destino
  médico `Buscar procedimento de destino…`.
- Testes de cobertura canônica de cada jornada:
  `apps/intake/tests/test_expanded_procedure_correction.py`,
  `apps/intake/tests/test_corrected_resubmission.py`,
  `apps/doctor/tests/test_expanded_procedure_decision.py`.
- O JS do componente já está pronto (Slice 001) — este slice NÃO toca JS nem
  CSS.

## Requisitos verificáveis

- **R1** — `case_detail.html`: select de correção ganha
  `data-combobox-placeholder="Buscar novo conjunto de procedimentos…"`,
  hint `#correction-exam-type-search-hint` e
  `aria-describedby="correction-exam-type-search-hint"`.
- **R2** — `corrected_resubmission.html`: select ganha
  `data-combobox-placeholder="Buscar tipo de exame do novo envio…"`, hint
  `#exam-type-search-hint` e
  `aria-describedby="exam-type-guidance exam-type-search-hint"`
  (o guidance pré-existente `#exam-type-guidance` — "o tipo anterior não é
  herdado automaticamente" — passa a ser associado, somando como no upload;
  *(emenda pós-implementação: a redação original omitia o guidance, contra o
  intento de D3)*).
- **R3** — `decision.html`: select de destino ganha
  `data-combobox-placeholder="Buscar procedimento de destino…"`, hint
  `#destination-procedure-search-hint` e
  `aria-describedby="destination-procedure-search-hint"`.
- **R4** — Em cada superfície, o teste Django da jornada afirma: presença do
  `data-combobox-placeholder` com o copy exato; presença do hint com id
  estável e classe `procedure-combobox__hint`; `aria-describedby` do select
  referenciando o hint; e, na re-renderização com erro (quando a jornada já
  possui teste de re-render com erro), hint e associação permanecem.

## Escopo e expected blast radius

```yaml
expected_files:
  - templates/intake/case_detail.html
  - templates/intake/corrected_resubmission.html
  - templates/doctor/decision.html
  - apps/intake/tests/test_expanded_procedure_correction.py
  - apps/intake/tests/test_corrected_resubmission.py
  - apps/doctor/tests/test_expanded_procedure_decision.py

allowed_incidental_files: []

out_of_scope:
  - static/js/procedure_combobox.js e static/css/app.css (Slice 001)
  - templates/intake/intake_home.html
  - qualquer mudança em POST/validação backend/catálogo/policy
  - novos blocos CSS (hint já estilizado pelo Slice 001)
```

Escalar ao parent se: algum select precisar de mudança além dos atributos
aditivos especificados; se a associação de erro existente conflitar com o
hint; ou se descobrir uma quinta superfície `data-procedure-combobox`.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `templates/intake/case_detail.html` | pytest correção (asserts de data-attr/hint/describedby) |
| R2 | `templates/intake/corrected_resubmission.html` | pytest reenvio (idem) |
| R3 | `templates/doctor/decision.html` | pytest decisão médica (idem) |
| R4 | os três testes acima | comandos focados abaixo |

## Plano de testes do slice

### RED (escreva/ajuste primeiro; confirme a falha pelo motivo esperado)

1. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_expanded_procedure_correction.py -q`
   — falha esperada nos asserts novos: select sem
   `data-combobox-placeholder`, sem hint, sem `aria-describedby`.
2. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_corrected_resubmission.py -q`
   — falha esperada idem.
3. `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/doctor/tests/test_expanded_procedure_decision.py -q`
   — falha esperada idem.

### GREEN / verificação local

- Os três comandos acima com exit 0.
- `uv run ruff check apps/intake/tests/test_expanded_procedure_correction.py apps/intake/tests/test_corrected_resubmission.py apps/doctor/tests/test_expanded_procedure_decision.py && uv run ruff format --check apps/intake/tests/test_expanded_procedure_correction.py apps/intake/tests/test_corrected_resubmission.py apps/doctor/tests/test_expanded_procedure_decision.py` — exit 0.
- Regressão próxima (jornadas completas): `POSTGRES_TEST_HOST_PORT=55433 uv run pytest apps/intake/tests/test_expanded_procedure_correction.py apps/intake/tests/test_corrected_resubmission.py apps/doctor/tests/test_expanded_procedure_decision.py -q` já cobre; adicionar `apps/doctor/tests/ -q -k "destination or decision"` se houver suite separada do combobox de destino.

Suíte completa NÃO roda neste slice (reservada ao gate final do change).

## Critérios de aceitação

- [ ] R1-R4 verificados pelos testes focados (exit 0 no GREEN).
- [ ] Nenhum atributo existente removido dos três selects (labels,
      `required`, options, POST inalterados — testes existentes verdes).
- [ ] Hint com copy uniforme e id estável em cada superfície.
- [ ] Blast radius dentro do `expected_files`.

## Contrato de handoff

Worker com contexto fresco: leia `design.md` (D2/D3) e este slice antes de
editar. Siga RED -> GREEN -> REFACTOR. Não toque em `tasks.md`, não faça
commit/push (o parent faz após review). O reviewer verifica
BEHAVIOR/TESTS/SCOPE/DESIGN com verdict `BLOCK`/`OK`/`OK with notes`; P2
isolado não reabre ciclo.
