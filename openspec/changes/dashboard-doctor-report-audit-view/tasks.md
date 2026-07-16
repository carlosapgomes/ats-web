<!-- markdownlint-disable MD013 -->

# Tasks: Relatório automático médico reconstruído no detalhe do dashboard

## Slice vertical

- [x] Slice 001 — Preparação compartilhada + relatório textual colapsável no detalhe do dashboard (`slices/slice-001-reconstructed-doctor-report-dashboard-detail.md`)

## Definition of Done do change

- [x] Doctor e dashboard usam preparação compartilhada das entradas do `DoctorReportPresenter`.
- [x] `manager` e `admin` veem o relatório reconstruído no detalhe de caso que possui `CASE_READY_FOR_DOCTOR`.
- [x] O card começa recolhido e usa Bootstrap Collapse com atributos ARIA coerentes.
- [x] O texto contém contexto e os sete blocos técnicos do relatório médico.
- [x] A UI informa que o conteúdo é reconstruído e não é snapshot imutável.
- [x] Casos sem `CASE_READY_FOR_DOCTOR` não mostram o card.
- [x] O template compartilhado não expõe o card no contexto NIR.
- [x] Conteúdo clínico/LLM permanece escapado; nenhuma utilização de `safe` foi adicionada.
- [x] JSON completo, snapshot, prompt versioning e persistência nova permanecem fora de escopo.
- [x] Nenhum model, migration, FSM, prompt, policy, permissão, rota ou endpoint foi alterado.
- [x] Testes relevantes foram adicionados em TDD e passam.
- [x] Quality gate do `AGENTS.md` foi executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Pytest final tem exit code 0, zero failures/errors e contagem de `passed` maior ou igual ao baseline.
- [x] Relatório `/tmp/dashboard-doctor-report-audit-view-slice-001-report.md` foi criado com evidências e handoff para terceiro LLM.
- [x] Commit e push foram realizados somente após todos os gates verdes.

## Regra de execução

Implementar somente um slice por vez. Como este change possui um único slice, ao concluí-lo o implementador deve informar `REPORT_PATH`, parar e aguardar revisão do planner. Se qualquer gate falhar, não marcar esta task e não fazer commit/push.
