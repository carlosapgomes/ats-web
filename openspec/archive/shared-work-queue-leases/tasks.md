# Tasks: Filas compartilhadas com reserva temporária de casos

## Status

Change planejado. Implementar **um slice por vez**, seguindo TDD e aguardando confirmação explícita do usuário antes de iniciar o próximo slice.

## Slices

- [x] Slice 001 — Scheduler role guard (`slices/slice-001-scheduler-role-guard.md`)
- [x] Slice 002 — Médico: lease básico end-to-end (`slices/slice-002-doctor-basic-lease.md`)
- [x] Slice 003 — Médico: heartbeat, idle detection e release (`slices/slice-003-doctor-heartbeat-release.md`)
- [x] Slice 004 — Agendador: lease end-to-end e ciência operacional segura (`slices/slice-004-scheduler-lease.md`)
- [x] Slice 005 — NIR: casos operacionais compartilhados (`slices/slice-005-nir-shared-operational-cases.md`)
- [x] Slice 006 — NIR: lease para confirmação de recebimento (`slices/slice-006-nir-receipt-lease.md`)
- [x] Slice 007 — Dashboard: bugfix de timezone em métricas do dia (`slices/slice-007-dashboard-localdate-bugfix.md`)
- [x] Slice 008 — Hardening, auditoria cruzada e quality gate final (`slices/slice-008-hardening-quality-closeout.md`)
- [x] Slice 009 — Otimização N+1 em lock display das filas (`slices/slice-009-lock-display-query-optimization.md`)

## Definition of Done do Change

- [x] Views do scheduler exigem papel ativo `scheduler`.
- [x] Campos de lease foram adicionados ao `Case` via migration enxuta.
- [x] Serviço de lock centralizado existe em `apps/cases/services.py`.
- [x] Médico adquire lock ao abrir decisão.
- [x] Médico só submete decisão com lock válido por `user + token + context`.
- [x] Fila médica mostra lock ativo e bloqueia ação para outro usuário.
- [x] Heartbeat médico renova lock somente com atividade recente.
- [x] Agendador adquire lock ao abrir confirmação.
- [x] Agendador só submete confirmação/negação com lock válido.
- [x] Fila do agendador mostra lock ativo e bloqueia ação para outro usuário.
- [x] Ciência operacional de vinda imediata fica protegida por papel e idempotente sob concorrência.
- [x] Todos os NIR veem todos os casos operacionais (`status != CLEANED`) de todos os NIR.
- [x] NIR consegue abrir detalhe de qualquer caso operacional compartilhado (`status != CLEANED`).
- [x] NIR só confirma recebimento com lock válido.
- [x] Locks expirados voltam a ficar disponíveis.
- [x] `WORK_LOCK_EXPIRED` registra quem estava com o caso quando expirou.
- [x] Heartbeats não criam evento de auditoria repetitivo.
- [x] Testes TDD cobrem concorrência crítica por papel.
- [x] Dashboard usa dia local para métricas de “hoje” (`_compute_summary` e `_compute_admission_flow`).
- [x] Quality gate completo executado: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- [x] Cada slice gerou relatório temporário com snippets antes/depois e informou `REPORT_PATH`.
- [x] Cada slice atualizou este `tasks.md` apenas ao final da implementação.
- [x] Cada slice teve commit e push, conforme `AGENTS.md`.
- [x] Querysets de filas que renderizam `compute_lock_display()` carregam `locked_by` com `select_related` quando aplicável.

## Comandos globais de validação

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Notas para implementadores

- Use estritamente Django/PostgreSQL/HTMX/Vanilla JS já presentes no projeto.
- Não introduza dependências sem aprovação explícita.
- Não use Django REST Framework.
- Não altere os 17 estados FSM para representar lock.
- Preserve `CaseEvent` como fonte append-only de auditoria.
- Siga clean code: nomes claros, funções pequenas, baixa duplicação.
- Siga DRY sem generalizar prematuramente.
- Siga YAGNI: não criar framework genérico de filas, override admin ou WebSocket neste change.
