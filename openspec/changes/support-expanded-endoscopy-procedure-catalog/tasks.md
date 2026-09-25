# Tasks: Catálogo ampliado de procedimentos endoscópicos

## 0. Precondições do change

- [ ] 0.1 Obter aceite humano da `ADR-0010`, mudar seu status para `Accepted` e verificar o índice `docs/adr/README.md` antes de qualquer código.
- [ ] 0.2 Criar `feature/support-expanded-endoscopy-procedure-catalog`, registrar `BASE_REF`, confirmar working tree adequada e executar baseline global uma única vez se não houver CI verde confiável; registrar comandos/resultados no relatório do Slice 001.
- [ ] 0.3 Atualizar `PROJECT_CONTEXT.md` para registrar este change como alvo ainda não implantado, distinguindo baseline 3.0/quatro tipos do objetivo 4.0/dez tipos; verificar por revisão do diff.

## 1. Catálogo e contrato gravável

- [ ] 1.1 Implementar o Slice 001 (`slices/slice-001-v4-cutover-preserves-existing-workflow.md`) e provar catálogo/matriz/migration, writer strict 4.0, adapters históricos e fluxo EDA/Colonoscopia até o médico sem regressão.

## 2. Seleção pesquisável e variações de EDA

- [ ] 2.1 Implementar o Slice 002 (`slices/slice-002-searchable-intake-control.md`) e provar combobox acessível no upload atual, busca sem acentos, fallback SSR e validação por código exato.
- [ ] 2.2 Implementar o Slice 003 (`slices/slice-003-eda-capsule-dilation-to-doctor.md`) e provar EDA + Cápsula/EDA + Dilatação do intake ao médico, incluindo precedência conservadora, profile EDA e local anatômico informativo.
- [ ] 2.3 Implementar o Slice 004 (`slices/slice-004-gastrostomy-infection-review.md`) e provar EDA + GTT do intake ao médico com resultados normais visíveis, alerta explicitamente sustentado e invariância de policy/recomendação/FSM.

## 3. Retossigmoidoscopia

- [ ] 3.1 Implementar o Slice 005 (`slices/slice-005-rectosigmoidoscopy-family-to-doctor.md`) e provar as três identidades de Retossigmoidoscopia do intake ao médico com profile de Colonoscopia, pacote indivisível e combinações proibidas fail-closed.

## 4. Jornadas por ator

- [ ] 4.1 Implementar o Slice 006 (`slices/slice-006-doctor-catalog-decisions-and-history.md`) e provar decisão/troca médica pelo catálogo, combobox de destino, atomicidade, ausência de rerun e histórico por código exato.
- [ ] 4.2 Implementar o Slice 007 (`slices/slice-007-nir-correction-and-catalog-queues.md`) e provar correção/reenvio pesquisável, acompanhamento, resposta final, encerrados e filtros NIR pelas identidades exatas.
- [ ] 4.3 Implementar o Slice 008 (`slices/slice-008-doctor-scheduler-followup-catalog.md`) e provar filtros/badges médicos e CHD, histórico/agendamento/follow-up de todo o catálogo e agendamento casado exclusivamente para EDA + Colonoscopia.
- [ ] 4.4 Implementar o Slice 009 (`slices/slice-009-manager-analytics-expanded-catalog.md`) e provar categorias case-level exclusivas, filtros dimensionais e volumes por componente sem agregar famílias.

## 5. Operação e encerramento

- [ ] 5.1 Implementar o Slice 010 (`slices/slice-010-coordinated-cutover-and-final-gate.md`) e verificar prompts 4.0, drenagem/prechecks, ausência de novas flags, inventário de pressupostos, smoke das onze seleções e runbook fix-forward.
- [ ] 5.2 Executar uma única vez o gate final `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`, seguido de `openspec validate support-expanded-endoscopy-procedure-catalog --strict`, `git diff --check` e `git status --short`; registrar resultados no relatório final.
- [ ] 5.3 Revisar evidências de todos os slices, atualizar somente checkboxes comprovados, gerar relatório final com snippets antes/depois, fazer commit/push rastreáveis, informar `REPORT_PATH` e parar para aprovação humana antes de arquivar.

## Regra de execução

- Implementar exatamente um slice vertical por vez em RED → GREEN → REFACTOR.
- Criar/ajustar os testes listados antes do RED; RED válido é falha de assertion pelo comportamento ausente, não erro de collection ou arquivo inexistente.
- Worker não altera `tasks.md`, não faz commit/push e não antecipa slice futuro.
- Reviewer independente verifica BEHAVIOR, TESTS, SCOPE e DESIGN; o parent atualiza checkbox e cria commit somente após verdict aceito.
- Cada slice produz relatório markdown temporário com comandos/resultados e para; o próximo exige confirmação explícita.
- Expansão para FSM, permissions, nova persistência clínica, processamento de anexos, flags ou blast radius substancial exige escalonamento antes de editar.
