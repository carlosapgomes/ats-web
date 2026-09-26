# Tasks: Detecção de pistas de procedimentos no corpo do relatório

## 0. Precondições do change

- [x] 0.1 Criar `feature/detect-report-body-procedure-clues` a partir do
  `main`, registrar `BASE_REF` e confirmar working tree adequada (idem
  convenção do change anterior: baseline confiável = gate pós-merge do main;
  reexecutar suíte completa só se a tree divergir). Neste host o pytest exige
  `POSTGRES_TEST_HOST_PORT=55433` (porta 5433 pertence a outro projeto).
  *(BASE_REF `212014d`; working tree limpa exceto `.pi/reports/*` não
  rastreados por convenção e o diretório do change. A tree do main DIVERGIU
  do último gate registrado (rc.1): o merge das affordances visuais
  (`212014d`) veio depois, sem gate pós-merge registrado — suíte completa
  executada uma única vez como baseline: ruff `All checks passed!`, format
  `290 files already formatted`, mypy `Success: no issues found in 320
  source files`, pytest `4456 passed` (146,55 s), node combobox `16 pass /
  0 fail`. Banco de testes `ats-web-test-db-1` healthy na 55433.)*
- [x] 0.2 `openspec validate --strict detect-report-body-procedure-clues`
  verde antes do primeiro slice.
  *(Verde após 5 rodadas de review independente com emendas — última
  execução pós-emenda final; specs delta `procedure-neutral-analysis` e
  `exam-type-correction` validam em `--strict`.)*

## 1. Slices

- [x] 1.1 Implementar o Slice 001
  (`slices/slice-001-justificativa-section-context.md`): seção
  `Justificativa da Transferência` como contexto de solicitação atual no
  detector (upgrade `mention`→`current_request` dentro do span da seção,
  campo `section` na ocorrência incluindo a marcação do campo Motivo,
  correção habilitante de offsets absolutos de cláusula,
  negações/históricos intocados).
  *(2 rodadas de review; rodada 1 `BLOCK` com 1 P1 — fixture do Motivo sem
  terminador `Unid.` e sem assert do endpoint do span — corrigido com
  fixture reordenada ao layout real + testes discriminantes do endpoint e
  de ocorrência pós-`Unid. Origem`; rodada 2 `OK with notes`. P2 adiados:
  terminadores de seção casam como substring sem exigir `:` — risco
  fail-safe documentado; variação ambígua promovida pela seção e demovida
  pelo vínculo local (interação coberta no Slice 002). Focado: 192 passed,
  ruff/format ok, mypy apps/pipeline ok.)*
- [ ] 1.2 Implementar o Slice 002
  (`slices/slice-002-via-link-separators.md`): conectores `via`/`por`/
  `atraves de`/`com uso de` no vínculo variação↔base; o
  relatório-exemplo passa a detectar `rectosigmoidoscopy_dilation` atual.
- [ ] 1.3 Implementar o Slice 003
  (`slices/slice-003-family-umbrella-precedence.md`): precedência
  `family_umbrella_over_colonoscopy` na reconciliação — caso corrigido para
  `rectosigmoidoscopy_dilation` reprocessa e prossegue (fim do loop de
  revisão); declarado `colonoscopy` vira `exam_type_mismatch` claro.
- [ ] 1.4 Implementar o Slice 004
  (`slices/slice-004-structured-item-conflict-gate.md`): item estruturado do
  LLM1 contraditado por ocorrência não-atual gera
  `nir_review`/`conflicting_procedure_evidence` (nunca `proceed`
  silencioso); reason code elegível para correção no intake.
- [ ] 1.5 Implementar o Slice 005
  (`slices/slice-005-nir-review-body-clues.md`): payload de revisão 2.1 com
  `detected_body_clues` e card de correção exibindo as pistas no momento da
  seleção do novo conjunto.

## 2. Gate final e encerramento

- [ ] 2.1 Gate global: `uv run ruff check . && uv run ruff format --check .`
  e `uv run mypy .` e `POSTGRES_TEST_HOST_PORT=55433 uv run pytest`.
- [ ] 2.2 `openspec validate --strict` do change; atualizar specs
  (`procedure-neutral-analysis`, `exam-type-correction`) com os requisitos
  entregues; commit dos artefatos de planejamento junto ao encerramento
  (política do projeto).
- [ ] 2.3 Relatório sumário do change (comportamento novo com o
  relatório-exemplo ponta a ponta: detecção → revisão com pistas → correção →
  proceed) para avaliação antes do arquivamento.
