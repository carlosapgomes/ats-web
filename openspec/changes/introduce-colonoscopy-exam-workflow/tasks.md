# Tasks: Introduzir colonoscopia como tipo de exame suportado

## Branch obrigatória

Todo o change deve ser implementado e enviado a partir de:

```text
feature/colonoscopy-exam-workflow
```

Se o branch atual for outro, o implementador deve parar e reportar `INCOMPLETE/BLOQUEADO`; não criar branch alternativo sem aprovação do planner.

## Regra de execução

- Implementar exatamente um slice por vez.
- Não iniciar o próximo slice sem revisão do `REPORT_PATH` e confirmação explícita.
- Marcar checkbox somente depois de baseline, RED, GREEN, REFACTOR, inspeções, quality gate, relatório, commit e push.
- Falha em qualquer gate mantém o item desmarcado.

## Slices verticais

- [x] Slice 001 — Medicamentos relevantes no relatório médico (`slices/slice-001-medication-safety-alert.md`)
- [ ] Slice 002 — Tipo explícito no intake e rastreabilidade inicial (`slices/slice-002-explicit-exam-type-intake.md`)
- [ ] Slice 003 — Colonoscopia percorre pipeline e decisão médica (`slices/slice-003-colonoscopy-to-doctor.md`)
- [ ] Slice 004 — Filtros médicos por tipo com busca preservada (`slices/slice-004-doctor-exam-type-filters.md`)
- [ ] Slice 005 — Filtros CHD em pendentes, processados e histórico (`slices/slice-005-scheduler-exam-type-filters.md`)
- [ ] Slice 006 — Correção de tipo e reprocessamento auditável (`slices/slice-006-exam-type-correction-reprocess.md`)
- [ ] Slice 007 — Filtros NIR e tipo no reenvio corrigido (`slices/slice-007-nir-type-filters-resubmission.md`)
- [ ] Slice 008 — Breakdown gerencial, documentação e rollout (`slices/slice-008-dashboard-breakdown-rollout.md`)

## Definition of Done do change

### Dados e intake

- [ ] `Case.exam_type` distingue EDA/colonoscopia e casos históricos foram backfillados como EDA sem reprocessamento.
- [ ] Upload exige escolha explícita e aplica um tipo ao lote inteiro.
- [ ] Backend rejeita tipo inválido e colonoscopia quando a flag de intake está desligada.
- [ ] Flag bloqueia apenas novos uploads, nunca processamento de casos existentes.

### Pipeline e clínica

- [ ] Colonoscopia é reconhecida por aliases aprovados e chega ao médico.
- [ ] Referência histórica ao outro exame não cria mismatch/mixed falso.
- [ ] Solicitações atuais EDA+colonoscopia no mesmo PDF são bloqueadas.
- [ ] Policy comum é separada por perfil; colonoscopia não recebe exceção de corpo estranho.
- [ ] Prior-case lookup considera o mesmo tipo.
- [ ] Colonoscopia preserva somente sinais prioritários aplicáveis.
- [ ] Fluxos pediátrico, médico e CHD existentes funcionam igualmente.

### Medicamentos

- [ ] Medicamentos explicitamente descritos são extraídos com evidência.
- [ ] Anticoagulantes/antiagregantes produzem alerta médico claro.
- [ ] Medicamentos não alteram automaticamente sugestão/decisão e não geram orientação de suspensão.

### UI/UX

- [ ] Tipo é visível em cards/detalhes relevantes.
- [ ] Médico filtra Pendentes/Decididos Hoje por tipo.
- [ ] Busca médica preserva termo ao trocar tipo e possui botão de limpeza imediata.
- [ ] CHD filtra todas as pendências, Processados Hoje e histórico por tipo.
- [ ] Histórico CHD lista recentes por tipo mesmo sem termo.
- [ ] NIR filtra casos operacionais e encerrados por tipo.
- [ ] Reenvio corrigido permite tipo diferente do original.

### Correção e auditoria

- [ ] NIR corrige tipo somente antes de `WAIT_DOCTOR`/em manual review seguro.
- [ ] Mesmo caso é reprocessado sem novo upload e sem reextrair PDF.
- [ ] Artefatos derivados são invalidados; PDF, anexos, texto e timeline são preservados.
- [ ] Eventos append-only registram mismatch, correção e reprocessamento.
- [ ] Concorrência com worker/lock é recusada ou serializada com segurança.

### Dashboard e operação

- [ ] Métricas consolidadas permanecem corretas.
- [ ] Breakdown por EDA/colonoscopia respeita período e semântica de accepted/denied/admin-closed.
- [ ] Tabela gerencial filtra por tipo compondo com filtros existentes.
- [ ] Manual, contexto e runbook de deploy/rollback foram atualizados.

### Qualidade e evidência

- [ ] Todos os slices seguiram TDD RED → GREEN → REFACTOR.
- [ ] Todos os relatórios temporários foram gerados e revisados.
- [ ] Cada relatório comprova baseline vs final, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Quality gate completo passou em cada slice.
- [ ] Cada slice foi commitado e enviado ao branch remoto antes do próximo.
- [ ] ADR-0003 e specs permanecem alinhadas com a implementação final.
