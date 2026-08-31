<!-- markdownlint-disable MD013 -->

# Tasks: Alinhar o contexto do LLM2 ao conjunto reconciliado

## Slice vertical

- [ ] Slice 001 — Projetar contexto canônico, explicitar conjunto e aplicar retry fail-closed do LLM2 (`slices/slice-001-canonicalize-llm2-procedure-set.md`)

## Definition of Done do change — implementação

- [ ] A visão efêmera enviada ao LLM2 filtra `requested_procedures` pelo conjunto reconciliado em ordem canônica.
- [ ] `Case.structured_data` e `result1.structured_data` permanecem inalterados para auditoria.
- [ ] O prompt LLM2 contém a lista JSON explícita do conjunto reconciliado e exige exatamente uma recomendação por item, sem extras.
- [ ] LLM1 com ambos + reconciliação EDA-only chega a `WAIT_DOCTOR` com apenas EDA na visão do LLM2.
- [ ] LLM1 com ambos + reconciliação Colonoscopia-only chega a `WAIT_DOCTOR` com apenas Colonoscopia na visão do LLM2.
- [ ] Reconciliação combinada continua chegando a `WAIT_DOCTOR` com os dois itens.
- [ ] Caminho exato continua usando uma tentativa LLM2 inicial.
- [ ] `procedure set mismatch` possui tipo de erro próprio e não depende de matching da mensagem.
- [ ] Primeiro mismatch pode ser corrigido por exatamente um retry específico.
- [ ] Segundo mismatch falha de forma controlada, sem `suggested_action` parcial.
- [ ] Erros de JSON/schema/IDs e duplicatas não consomem retry de conjunto.
- [ ] Retry de idioma pt-BR permanece limitado e funcional; máximo de chamadas é finito.
- [ ] Nenhuma regex/alias de detecção, reconciliação, policy, schema, FSM, model, migration, prompt versionado ou fila foi alterado.
- [ ] Nenhum mecanismo de recuperação/reprocessamento de `FAILED` foi criado.
- [ ] TDD RED → GREEN → REFACTOR foi comprovado no relatório.
- [ ] Checks de inspeção obrigatórios foram executados e interpretados.
- [ ] Quality gate completo passou:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] `openspec validate fix-llm2-reconciled-procedure-set --strict` e `git diff --check` passaram.
- [ ] Relatório `/tmp/fix-llm2-reconciled-procedure-set-slice-001-report.md` foi criado com matriz, baseline, RED/GREEN, snippets, inspeções, gates e handoff para terceiro LLM.
- [ ] Commit rastreável e push da branch do change foram realizados.

## Pós-aprovação do slice — operação (não executar durante implementação)

- [ ] Release/deploy realizado sem migration.
- [ ] Smoke EDA-only, Colonoscopia-only e combinado concluído com chegada a `WAIT_DOCTOR`.
- [ ] Ocorrências `5025447`, `5027759` e `5028231` reapresentadas uma única vez após o deploy.
- [ ] Registros antigos em `FAILED` preservados sem edição/reabertura.

## Regra de atualização

O implementador marca o Slice 001 e somente os itens da Definition of Done de implementação depois de comprovar todos os critérios do arquivo de slice. Os itens operacionais permanecem desmarcados até execução humana pós-aprovação. Qualquer falha mantém o slice incompleto; não marcar parcialmente, não fazer commit/push e não acessar produção para contornar o gate.
