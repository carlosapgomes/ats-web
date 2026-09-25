# Tasks: Affordances visuais da seleção de procedimentos

## 0. Precondições do change

- [x] 0.1 Criar `feature/procedure-selection-visual-affordances` a partir do
  `main` (`3e2753a`), registrar `BASE_REF` e confirmar working tree adequada.
  Baseline confiável: gate pós-merge do main executado no dia (4445 testes,
  registrado em `docs/releases/2026-09-25_v0.10.0-rc.1.md`) — reexecutar a
  suíte completa só se a tree divergir. Neste host o pytest exige
  `POSTGRES_TEST_HOST_PORT=55433` (porta 5433 pertence a outro projeto).
  *(BASE_REF `3e2753a`; working tree limpa exceto `.pi/reports/*` não rastreados
  por convenção; baseline herdada do gate do main, sem reexecução.)*

## 1. Slices

- [x] 1.1 Implementar o Slice 001
  (`slices/slice-001-shared-component-upload-affordances.md`) e provar no
  upload: placeholder do input aprimorado, hint persistente associado por
  `aria-describedby`, chevron, bordas/hover/alvo, estado selecionado na
  listbox, guarda de CSS e testes Node — sem alterar contrato POST/ARIA base.
  *(2 rodadas de review; rodada 1 `OK with notes` com 4 P2, um deles
  elevado a correção pelo planner por erro de spec em D5 — token da borda de
  repouso invertido, troca seria no-op visual; D5/R4 emendados e corrigidos
  na rodada 2 junto com fixture Node de 2 ids; veredito final `OK with
  notes`. P2 remanescentes: double scan em `syncSelectedRow`, largura
  cosmética do hint, guard não pina ordem de cascata.)*
- [x] 1.2 Implementar o Slice 002
  (`slices/slice-002-remaining-surfaces-hints.md`) e provar placeholder +
  hint + associação nas superfícies de correção (`case_detail.html`),
  reenvio (`corrected_resubmission.html`) e destino médico
  (`decision.html`), incluindo re-render com erro.
  *(1 rodada de review, veredito `OK with notes`, 0 P0/P1. R2 emendado pelo
  planner ainda na implementação: describedby do reenvio soma o guidance
  pré-existente (`exam-type-guidance exam-type-search-hint`). P2 diferidos:
  erro/guidance do destino médico sem id (escolha deliberada — associar é
  aditivo e fica para polimento futuro); duplicação de helpers de teste
  entre 4 módulos (consolidação fora do blast radius); assert R4 médico em
  escopo de documento em vez de select.)*

## 2. Gate final e encerramento

- [x] 2.1 Gate global: `uv run ruff check . && uv run ruff format --check .`
  e `uv run mypy .` e `POSTGRES_TEST_HOST_PORT=55433 uv run pytest` e
  `node --test static/js/tests/procedure_combobox.test.js`.
  *(2026-09-25: ruff/format OK; mypy 320 arquivos sem issues; node 16/16
  exit 0; pytest 4456 passed — baseline 4445 + 11 novos, 0 falhas.)*
- [x] 2.2 `openspec validate --strict` do change; commit dos artefatos de
  planejamento junto ao encerramento (política do projeto). A implantação
  como `v0.10.0-rc.2` antes da promoção a estável é decisão operacional
  separada.
  *(`valid`; artefatos commitados em `a1fa2f2`.)*
