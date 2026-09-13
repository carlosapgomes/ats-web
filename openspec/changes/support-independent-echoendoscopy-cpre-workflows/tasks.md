# Tasks: Ecoendoscopia e CPRE como procedimentos independentes

## 0. Precondições do change

- [x] 0.1 Registrar e aceitar `docs/adr/ADR-0006-ecoendoscopia-e-cpre-como-procedimentos-independentes.md`, com índice e relação de supersessão parcial da ADR-0004 revisados.
- [x] 0.2 Atualizar `PROJECT_CONTEXT.md` com o change ativo e o override 3.0, distinguindo explicitamente baseline atual de alvo ainda não implementado.
- [ ] 0.3 Na branch `feature/support-independent-echoendoscopy-cpre-workflows`, registrar `BASE_REF`, confirmar working tree adequada e executar baseline global uma única vez quando o HEAD não tiver CI verde confiável.

## 1. Cutover vertical do fluxo existente

- [x] 1.1 Implementar o Slice 001 (`slices/slice-001-v3-cutover-preserves-existing-workflow.md`) e provar EDA/Colonoscopia ponta a ponta sob catálogo/matriz e writer 3.0, incluindo rejeição explícita de valores desconhecidos e compatibilidade 1.1/2.0.

## 2. Ecoendoscopia

- [ ] 2.1 Implementar o Slice 002 (`slices/slice-002-echoendoscopy-intake-to-doctor.md`) e provar seleção NIR → proveniência/precedência → policy → fila/relatório médico sob flag própria.
- [ ] 2.2 Implementar o Slice 003 (`slices/slice-003-echoendoscopy-doctor-swap-and-downstream.md`) e provar `trocar e aprovar`, ausência de rerun/repolicy, conjunto válido, CHD/NIR, evento e mensagem sistêmica sem `UserNotification`.

## 3. CPRE

- [ ] 3.1 Implementar o Slice 004 (`slices/slice-004-cpre-end-to-end.md`) e provar intake, aliases, policy de USG/TC/RM/CPRM, decisão direta/troca e projeção CHD/NIR sob flag própria.

## 4. Jornadas operacionais por ator

- [ ] 4.1 Implementar o Slice 005 (`slices/slice-005-doctor-specialized-queues.md`) e provar Pendentes/Decididos Hoje com filtros, badges e transformações especializadas pela dimensão correta.
- [ ] 4.2 Implementar o Slice 006 (`slices/slice-006-scheduler-specialized-queues-followup.md`) e provar filas/histórico CHD, agendamento casado exato e pós-procedimento por Ecoendoscopia/CPRE.
- [ ] 4.3 Implementar o Slice 007 (`slices/slice-007-nir-specialized-queues.md`) e provar acompanhamento, correção, encerrados e filtros NIR pelos procedimentos declarados.
- [ ] 4.4 Implementar o Slice 008 (`slices/slice-008-specialized-manager-analytics.md`) e provar categorias exclusivas, filtros e volumes gerenciais para os quatro tipos.

## 5. Operação e encerramento

- [ ] 5.1 Implementar o Slice 009 (`slices/slice-009-rollout-rollback-and-final-gate.md`) e verificar runbook, prompts ativos, flags, smoke Eco antes de CPRE, prechecks de rollback e alinhamento documental.
- [ ] 5.2 Executar uma única vez o gate final `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`, seguido de `openspec validate support-independent-echoendoscopy-cpre-workflows --strict`, `git diff --check` e `git status --short`; registrar resultados no relatório final.
- [ ] 5.3 Revisar evidências de todos os slices, atualizar apenas checkboxes comprovados, gerar `REPORT_PATH` final, commit/push rastreáveis e parar para aprovação humana antes de arquivar o change.

## Regra de execução

- Implementar exatamente um slice vertical por vez em RED → GREEN → REFACTOR.
- Antes do comando RED, criar/ajustar os testes listados no slice; RED válido é falha de assertion pelo comportamento ausente, nunca `file not found` ou erro de collection.
- Worker não altera `tasks.md`, não faz commit/push e não implementa slice futuro.
- Parent/orquestrador atualiza o checkbox somente após review independente aceito, cria commit/push e informa `REPORT_PATH`.
- Expansão de contrato, migration, FSM, permissões, persistência ou blast radius além do previsto exige escalonamento antes de editar.
- Cada slice para após o handoff; o seguinte exige confirmação explícita.
