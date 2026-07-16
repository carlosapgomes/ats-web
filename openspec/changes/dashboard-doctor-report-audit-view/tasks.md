<!-- markdownlint-disable MD013 -->

# Tasks: Relatório automático médico reconstruído no detalhe do dashboard

## Slice vertical

- [ ] Slice 001 — Preparação compartilhada + relatório textual colapsável no detalhe do dashboard (`slices/slice-001-reconstructed-doctor-report-dashboard-detail.md`)

## Definition of Done do change

- [ ] Doctor e dashboard usam preparação compartilhada das entradas do `DoctorReportPresenter`.
- [ ] `manager` e `admin` veem o relatório reconstruído no detalhe de caso que possui `CASE_READY_FOR_DOCTOR`.
- [ ] O card começa recolhido e usa Bootstrap Collapse com atributos ARIA coerentes.
- [ ] O texto contém contexto e os sete blocos técnicos do relatório médico.
- [ ] A UI informa que o conteúdo é reconstruído e não é snapshot imutável.
- [ ] Casos sem `CASE_READY_FOR_DOCTOR` não mostram o card.
- [ ] O template compartilhado não expõe o card no contexto NIR.
- [ ] Conteúdo clínico/LLM permanece escapado; nenhuma utilização de `safe` foi adicionada.
- [ ] JSON completo, snapshot, prompt versioning e persistência nova permanecem fora de escopo.
- [ ] Nenhum model, migration, FSM, prompt, policy, permissão, rota ou endpoint foi alterado.
- [ ] Testes relevantes foram adicionados em TDD e passam.
- [ ] Quality gate do `AGENTS.md` foi executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Pytest final tem exit code 0, zero failures/errors e contagem de `passed` maior ou igual ao baseline.
- [ ] Relatório `/tmp/dashboard-doctor-report-audit-view-slice-001-report.md` foi criado com evidências e handoff para terceiro LLM.
- [ ] Commit e push foram realizados somente após todos os gates verdes.

## Regra de execução

Implementar somente um slice por vez. Como este change possui um único slice, ao concluí-lo o implementador deve informar `REPORT_PATH`, parar e aguardar revisão do planner. Se qualquer gate falhar, não marcar esta task e não fazer commit/push.
