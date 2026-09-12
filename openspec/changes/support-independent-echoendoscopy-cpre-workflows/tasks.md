# Tasks: Ecoendoscopia e CPRE como procedimentos independentes

## 0. Precondições do change

- [x] 0.1 Registrar e aceitar `docs/adr/ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md`, com índice e relação de supersessão parcial da ADR-0004 revisados.
- [ ] 0.2 Criar/usar a branch `feature/support-independent-echoendoscopy-cpre-workflows`, registrar `BASE_REF`, confirmar working tree adequada e executar baseline global uma única vez quando o HEAD não tiver CI verde confiável.

## 1. Catálogo e matriz

- [ ] 1.1 Implementar o Slice 001 (`slices/slice-001-procedure-catalog-and-closed-matrix.md`) e verificar catálogo de quatro tipos, ordem única, matriz fechada, igualdade exata do combinado, mismatch e migration state com os testes focados do slice.

## 2. Contrato e policy

- [ ] 2.1 Implementar o Slice 002 (`slices/slice-002-llm-v3-contract-and-specialized-policy.md`) e verificar schemas 3.0, evidência abdominal tipada, policies de Ecoendoscopia/CPRE, pendências agregadas e compatibilidade de motivo primário.
- [ ] 2.2 Implementar o Slice 003 (`slices/slice-003-v3-cutover-preserves-eda-colonoscopy.md`) e verificar que novos jobs EDA/Colonoscopia usam somente prompts/schemas 3.0 enquanto artefatos 1.1/2.0 continuam legíveis.

## 3. Ecoendoscopia

- [ ] 3.1 Implementar o Slice 004 (`slices/slice-004-echoendoscopy-intake-to-doctor.md`) e verificar NIR → detecção/policy → fila/relatório médico sob `ECHOENDOSCOPY_INTAKE_ENABLED`, incluindo precedência e anexos fora da automação.
- [ ] 3.2 Implementar o Slice 005 (`slices/slice-005-echoendoscopy-doctor-swap-and-downstream.md`) e verificar `trocar e aprovar`, ausência de rerun/repolicy, conjunto final válido, CHD/NIR, evento e mensagem sistêmica sem `UserNotification`.

## 4. CPRE

- [ ] 4.1 Implementar o Slice 006 (`slices/slice-006-cpre-end-to-end.md`) e verificar intake, aliases, policy de USG/TC/RM/CPRM, decisão direta/troca e projeção CHD/NIR sob flag própria.

## 5. Superfícies operacionais

- [ ] 5.1 Implementar o Slice 007 (`slices/slice-007-specialized-queues-analytics-followup.md`) e verificar filtros dimensionais, cards, analytics, agendamento casado exato e follow-up para os quatro tipos, além de inventário sem pressupostos binários indevidos.

## 6. Operação e encerramento

- [ ] 6.1 Implementar o Slice 008 (`slices/slice-008-rollout-rollback-and-final-gate.md`) e verificar runbook, prompts ativos, flags, smoke de Ecoendoscopia antes de CPRE, prechecks de rollback e alinhamento de documentação.
- [ ] 6.2 Executar uma única vez o gate final `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`, seguido de `openspec validate support-independent-echoendoscopy-cpre-workflows --strict`, `git diff --check` e `git status --short`; registrar resultados no relatório final.
- [ ] 6.3 Revisar evidências de todos os slices, atualizar apenas checkboxes comprovados, gerar `REPORT_PATH` final, commit/push rastreáveis e parar para aprovação humana antes de arquivar o change.

## Regra de execução

- Implementar exatamente um slice por vez em RED → GREEN → REFACTOR.
- Worker não altera `tasks.md`, não faz commit/push e não implementa slice futuro.
- Parent/orquestrador atualiza o checkbox somente após review independente aceito, cria commit/push e informa `REPORT_PATH`.
- Expansão de contrato, migration, FSM, permissões, persistência ou blast radius além do previsto exige escalonamento antes de editar.
- Cada slice para após o handoff; o seguinte exige confirmação explícita.
