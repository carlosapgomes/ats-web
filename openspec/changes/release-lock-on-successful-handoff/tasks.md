# Tasks: Liberar lock após handoff operacional bem-sucedido

## Status

Slice 001 concluído.

## Slices

- [x] Slice 001 — Release backend pós-submit médico/agendador (`slices/slice-001-release-backend-pos-submit.md`)

## Definition of Done do Change

- [x] `doctor_submit` libera lock após submit válido e transições FSM concluídas.
- [x] `doctor_submit` preserva lock em formulário inválido, token inválido ou token ausente.
- [x] Scheduler consegue assumir imediatamente caso aceito pelo médico para agendamento.
- [x] `scheduler_submit` libera lock após submit válido e transições FSM concluídas.
- [x] `scheduler_submit` preserva lock em formulário inválido, token inválido ou token ausente.
- [x] NIR consegue assumir imediatamente caso finalizado pelo scheduler.
- [x] Eventos `WORK_LOCK_RELEASED` são registrados apenas em releases explícitos.
- [x] Nenhum comportamento de Cancelar/pagehide/heartbeat foi alterado.
- [x] Testes relevantes passam.
- [x] Quality gate do `AGENTS.md` executado ou limitações registradas no relatório.
- [x] Relatório temporário do slice criado e `REPORT_PATH` informado.
- [x] Commit e push realizados pelo implementador.

## Comandos de validação recomendados

```bash
uv run pytest apps/doctor/tests apps/scheduler/tests apps/intake/tests/test_nir_receipt_lease.py apps/cases/tests/test_lock_service.py -q
uv run ruff check apps/doctor apps/scheduler apps/cases apps/intake
uv run ruff format --check apps/doctor apps/scheduler apps/cases apps/intake
uv run mypy apps/doctor apps/scheduler apps/cases apps/intake
```

Quality gate completo, se viável:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```
