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
- [x] Slice 002 — Tipo explícito no intake e rastreabilidade inicial (`slices/slice-002-explicit-exam-type-intake.md`)
- [x] Slice 003 — Colonoscopia percorre pipeline e decisão médica (`slices/slice-003-colonoscopy-to-doctor.md`)
- [x] Slice 004 — Filtros médicos por tipo com busca preservada (`slices/slice-004-doctor-exam-type-filters.md`)
- [x] Slice 005 — Filtros CHD em pendentes, processados e histórico (`slices/slice-005-scheduler-exam-type-filters.md`)
- [x] Slice 006 — Correção de tipo e reprocessamento auditável (`slices/slice-006-exam-type-correction-reprocess.md`)
- [x] Slice 007 — Filtros NIR e tipo no reenvio corrigido (`slices/slice-007-nir-type-filters-resubmission.md`)
- [x] Slice 008 — Breakdown gerencial, documentação e rollout (`slices/slice-008-dashboard-breakdown-rollout.md`)

## Definition of Done do change

### Dados e intake

- [x] `Case.exam_type` distingue EDA/colonoscopia e casos históricos foram backfillados como EDA sem reprocessamento.
- [x] Upload exige escolha explícita e aplica um tipo ao lote inteiro.
- [x] Backend rejeita tipo inválido e colonoscopia quando a flag de intake está desligada.
- [x] Flag bloqueia apenas novos uploads, nunca processamento de casos existentes.

### Pipeline e clínica

- [x] Colonoscopia é reconhecida por aliases aprovados e chega ao médico.
- [x] Referência histórica ao outro exame não cria mismatch/mixed falso.
- [x] Solicitações atuais EDA+colonoscopia no mesmo PDF são bloqueadas.
- [x] Policy comum é separada por perfil; colonoscopia não recebe exceção de corpo estranho.
- [x] Prior-case lookup considera o mesmo tipo.
- [x] Colonoscopia preserva somente sinais prioritários aplicáveis.
- [x] Fluxos pediátrico, médico e CHD existentes funcionam igualmente.

### Medicamentos

- [x] Medicamentos explicitamente descritos são extraídos com evidência.
- [x] Anticoagulantes/antiagregantes produzem alerta médico claro.
- [x] Medicamentos não alteram automaticamente sugestão/decisão e não geram orientação de suspensão.

### UI/UX

- [x] Tipo é visível em cards/detalhes relevantes.
- [x] Médico filtra Pendentes/Decididos Hoje por tipo.
- [x] Busca médica preserva termo ao trocar tipo e possui botão de limpeza imediata.
- [x] CHD filtra todas as pendências, Processados Hoje e histórico por tipo.
- [x] Histórico CHD lista recentes por tipo mesmo sem termo.
- [x] NIR filtra casos operacionais e encerrados por tipo.
- [x] Reenvio corrigido permite tipo diferente do original.

### Correção e auditoria

- [x] NIR corrige tipo somente antes de `WAIT_DOCTOR`/em manual review seguro.
- [x] Mesmo caso é reprocessado sem novo upload e sem reextrair PDF.
- [x] Artefatos derivados são invalidados; PDF, anexos, texto e timeline são preservados.
- [x] Eventos append-only registram mismatch, correção e reprocessamento.
- [x] Concorrência com worker/lock é recusada ou serializada com segurança.

### Dashboard e operação

- [x] Métricas consolidadas permanecem corretas.
- [x] Breakdown por EDA/colonoscopia respeita período e semântica de accepted/denied/admin-closed.
- [x] Tabela gerencial filtra por tipo compondo com filtros existentes.
- [x] Manual, contexto e runbook de deploy/rollback foram atualizados.

### Qualidade e evidência

- [x] Todos os slices seguiram TDD RED → GREEN → REFACTOR.
- [x] Todos os relatórios temporários foram gerados e revisados.
- [x] Cada relatório comprova baseline vs final, zero failures/errors e `passed_final >= passed_baseline`.
- [x] Quality gate completo passou em cada slice.
- [x] Cada slice foi commitado e enviado ao branch remoto antes do próximo.
- [x] ADR-0003 e specs permanecem alinhadas com a implementação final.
