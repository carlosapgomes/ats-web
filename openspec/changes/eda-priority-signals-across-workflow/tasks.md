# Tasks: Sinalizações prioritárias de EDA em todo o fluxo operacional

## Ordem obrigatória

Implementar somente o próximo slice incompleto. Cada slice exige confirmação explícita do usuário/planner antes do seguinte.

- [x] Slice 001 — Ecoendoscopia percorre contrato, scope, policy padrão e relatório médico (`slices/slice-001-echoendoscopy-eda-flow.md`)
- [ ] Slice 002 — Sinalizações canônicas persistidas, backfill de abertos e badges na fila médica (`slices/slice-002-persisted-signals-doctor-queue.md`)
- [ ] Slice 003 — Topo e corpo do relatório médico usam os sinais persistidos (`slices/slice-003-doctor-report-priority-signals.md`)
- [ ] Slice 004 — Badges persistidos acompanham o caso no CHD (`slices/slice-004-scheduler-priority-signals.md`)
- [ ] Slice 005 — Badges persistidos acompanham o caso no NIR (`slices/slice-005-nir-priority-signals.md`)

## Definition of Done do change

### Contrato, scope e policy

- [ ] `echoendoscopy` é subtipo LLM1 válido e alinhado entre procedimento e rulebook.
- [ ] Prompt default e prompt renderizado final reconhecem sinônimos e pedem menção no resumo.
- [ ] Ecoendoscopia isolada é EDA suportada e não cai em revisão manual por tipo desconhecido.
- [ ] Ecoendoscopia com punção/PAAF/biópsia/FNA/FNB permanece ecoendoscopia.
- [ ] EDA/ecoendoscopia solicitada prevalece quando o relatório também menciona exame fora de escopo.
- [ ] Solicitação exclusivamente fora de EDA preserva revisão manual.
- [ ] Ecoendoscopia segue exames mínimos, thresholds e gates padrão.
- [ ] Corpo estranho é o único subtipo com bypass preservado.

### Sinalizações e persistência

- [ ] `Case.priority_signals` persiste coleção versionada, ordenada e deduplicada.
- [ ] Códigos suportados: `foreign_body`, `caustic_ingestion`, `pediatric`, `echoendoscopy`, `esophageal_dilation`, `gastrostomy`.
- [ ] Múltiplos sinais coexistem sem enums combinatórios.
- [ ] Novos casos resolvem/persistem sinais após LLM1 e antes do scope/policy.
- [ ] `LLM1_OK` registra apenas os códigos resolvidos, sem texto clínico adicional.
- [ ] Migration faz backfill idempotente apenas de `status != CLEANED`.
- [ ] Casos `CLEANED` preexistentes permanecem sem backfill.
- [ ] Payload ausente/malformado rende nenhum badge, sem erro 500.

### Apresentação

- [ ] Partial SSR compartilhado renderiza badges Bootstrap em ordem canônica.
- [ ] Corpo estranho e ingestão cáustica usam a mesma ênfase visual.
- [ ] Pediatria inclui idade quando disponível.
- [ ] Ecoendoscopia, dilatação e gastrostomia recebem destaque operacional consistente.
- [ ] Fila médica exibe badges antes de abrir o caso.
- [ ] Relatório médico exibe badges no topo.
- [ ] Resumo clínico e achados críticos recebem linhas determinísticas apropriadas.
- [ ] CHD vê badges na fila, confirmação e detalhes aplicáveis.
- [ ] NIR vê badges na lista, detalhe operacional/resultado e detalhe encerrado quando persistidos.
- [ ] Casos sem sinais não exibem container vazio.

### Não regressão

- [ ] Sem alteração de FSM, permissões, locks ou decisão médica.
- [ ] Sem atribuição automática de triador/executor.
- [ ] Sem validação de dias/turnos de agenda.
- [ ] Sem implementação de colonoscopia.
- [ ] Sem reexecução de LLM no backfill.
- [ ] Sem negativa automática por ingestão cáustica.
- [ ] Quality gate completo passa em cada slice.
- [ ] Relatório temporário por slice contém baseline, RED/GREEN, snippets, inspeções, quality gate e handoff para terceiro LLM.
- [ ] Cada slice concluído possui commit rastreável e push antes do próximo.

## Regras para implementadores

- Ler `AGENTS.md`, `PROJECT_CONTEXT.md`, proposal, design, spec, tasks e o slice ativo.
- Seguir literalmente o protocolo DeepSeek4-Flash do slice.
- TDD obrigatório: RED → GREEN → REFACTOR.
- Aplicar clean code, DRY e YAGNI; não criar abstrações ou automações futuras.
- Tocar o mínimo de arquivos; qualquer extra exige justificativa no relatório.
- Marcar somente o slice concluído após todos os gates passarem.
- Se qualquer condição automática de INCOMPLETO ocorrer: não marcar task, não fazer commit/push e reportar bloqueio com evidência.
- Gerar `REPORT_PATH=/tmp/eda-priority-signals-slice-00N-report.md`.
- Parar e pedir confirmação explícita antes do próximo slice.
