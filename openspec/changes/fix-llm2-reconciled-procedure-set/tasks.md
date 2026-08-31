<!-- markdownlint-disable MD013 -->

# Tasks: Alinhar o contexto do LLM2 ao conjunto reconciliado

## Slice vertical

- [x] Slice 001 — Projetar contexto canônico, explicitar conjunto e aplicar retry fail-closed do LLM2 (`slices/slice-001-canonicalize-llm2-procedure-set.md`)

## Definition of Done do change — implementação

- [x] A visão efêmera enviada ao LLM2 filtra `requested_procedures` pelo conjunto reconciliado em ordem canônica.
- [x] `Case.structured_data` e `result1.structured_data` permanecem inalterados para auditoria.
- [x] O prompt LLM2 contém a lista JSON explícita do conjunto reconciliado e exige exatamente uma recomendação por item, sem extras.
- [x] LLM1 com ambos + reconciliação EDA-only chega a `WAIT_DOCTOR` com apenas EDA na visão do LLM2.
- [x] LLM1 com ambos + reconciliação Colonoscopia-only chega a `WAIT_DOCTOR` com apenas Colonoscopia na visão do LLM2.
- [x] Reconciliação combinada continua chegando a `WAIT_DOCTOR` com os dois itens.
- [x] Caminho exato continua usando uma tentativa LLM2 inicial.
- [x] `procedure set mismatch` possui tipo de erro próprio e não depende de matching da mensagem.
- [x] Primeiro mismatch pode ser corrigido por exatamente um retry específico.
- [x] Segundo mismatch falha de forma controlada, sem `suggested_action` parcial.
- [x] Erros de JSON/schema/IDs e duplicatas não consomem retry de conjunto.
- [x] Retry de idioma pt-BR permanece limitado e funcional; máximo de chamadas é finito.
- [x] Nenhuma regex/alias de detecção, reconciliação, policy, schema, FSM, model, migration, prompt versionado ou fila foi alterado.
- [x] Nenhum mecanismo de recuperação/reprocessamento de `FAILED` foi criado.
- [x] TDD RED → GREEN → REFACTOR foi comprovado no relatório.
- [x] Checks de inspeção obrigatórios foram executados e interpretados.
- [x] Quality gate completo passou:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [x] `openspec validate fix-llm2-reconciled-procedure-set --strict` e `git diff --check` passaram.
- [x] Relatório `/tmp/fix-llm2-reconciled-procedure-set-slice-001-report.md` foi criado com matriz, baseline, RED/GREEN, snippets, inspeções, gates e handoff para terceiro LLM.
- [x] Commit rastreável e push da branch do change foram realizados.

## Pós-aprovação do slice — operação (não executar durante implementação)

- [ ] Release/deploy realizado sem migration.
- [ ] Smoke EDA-only, Colonoscopia-only e combinado concluído com chegada a `WAIT_DOCTOR`.
- [ ] Ocorrências `5025447`, `5027759` e `5028231` reapresentadas uma única vez após o deploy.
- [ ] Registros antigos em `FAILED` preservados sem edição/reabertura.

## Regra de atualização

O implementador marca o Slice 001 e somente os itens da Definition of Done de implementação depois de comprovar todos os critérios do arquivo de slice. Os itens operacionais permanecem desmarcados até execução humana pós-aprovação. Qualquer falha mantém o slice incompleto; não marcar parcialmente, não fazer commit/push e não acessar produção para contornar o gate.
