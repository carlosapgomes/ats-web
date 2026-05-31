# Tasks: Filas compartilhadas com reserva temporária de casos

## Status

Change planejado. Implementar **um slice por vez**, seguindo TDD e aguardando confirmação explícita do usuário antes de iniciar o próximo slice.

## Slices

- [x] Slice 001 — Scheduler role guard (`slices/slice-001-scheduler-role-guard.md`)
- [x] Slice 002 — Médico: lease básico end-to-end (`slices/slice-002-doctor-basic-lease.md`)
- [x] Slice 003 — Médico: heartbeat, idle detection e release (`slices/slice-003-doctor-heartbeat-release.md`)
- [x] Slice 004 — Agendador: lease end-to-end e ciência operacional segura (`slices/slice-004-scheduler-lease.md`)
- [ ] Slice 005 — NIR: casos operacionais compartilhados (`slices/slice-005-nir-shared-operational-cases.md`)
- [ ] Slice 006 — NIR: lease para confirmação de recebimento (`slices/slice-006-nir-receipt-lease.md`)
- [ ] Slice 007 — Hardening, auditoria cruzada e quality gate final (`slices/slice-007-hardening-quality-closeout.md`)

## Definition of Done do Change

- [ ] Views do scheduler exigem papel ativo `scheduler`.
- [ ] Campos de lease foram adicionados ao `Case` via migration enxuta.
- [ ] Serviço de lock centralizado existe em `apps/cases/services.py` ou local equivalente justificado.
- [ ] Médico adquire lock ao abrir decisão.
- [ ] Médico só submete decisão com lock válido por `user + token + context`.
- [ ] Fila médica mostra lock ativo e bloqueia ação para outro usuário.
- [ ] Heartbeat médico renova lock somente com atividade recente.
- [ ] Agendador adquire lock ao abrir confirmação.
- [ ] Agendador só submete confirmação/negação com lock válido.
- [ ] Fila do agendador mostra lock ativo e bloqueia ação para outro usuário.
- [ ] Ciência operacional de vinda imediata fica protegida por papel e idempotente sob concorrência.
- [ ] Todos os NIR veem todos os casos operacionais (`status != CLEANED`) de todos os NIR.
- [ ] NIR consegue abrir detalhe de qualquer caso operacional compartilhado (`status != CLEANED`).
- [ ] NIR só confirma recebimento com lock válido.
- [ ] Locks expirados voltam a ficar disponíveis.
- [ ] `WORK_LOCK_EXPIRED` registra quem estava com o caso quando expirou.
- [ ] Heartbeats não criam evento de auditoria repetitivo.
- [ ] Testes TDD cobrem concorrência crítica por papel.
- [ ] Quality gate completo executado: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- [ ] Cada slice gerou relatório temporário com snippets antes/depois e informou `REPORT_PATH`.
- [ ] Cada slice atualizou este `tasks.md` apenas ao final da implementação.
- [ ] Cada slice teve commit e push, conforme `AGENTS.md`.

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
