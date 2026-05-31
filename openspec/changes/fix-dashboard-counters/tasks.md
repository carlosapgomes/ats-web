# Tasks: Corrigir contadores do dashboard

## Status

Change pendente. 1 slice planejado.

## Slices

- [x] Slice 001 — Reescrever `_compute_summary()` com queries baseadas em decisão (`slices/slice-001-fix-counters.md`)

## Definition of Done do Change

- [ ] `_compute_summary()` reescrita usando `doctor_decision` e `appointment_status` em vez de `status` FSM.
- [ ] "Negados" captura casos com `doctor_decision="deny"` e `appointment_status="denied"`, mesmo após CLEANED.
- [ ] "Aceitos" exclui casos com `appointment_status="denied"`.
- [ ] "Aceitos" e "Negados" são mutuamente exclusivos (sem dupla contagem).
- [ ] "Em Andamento" é confiável (`total - accepted - denied`).
- [ ] Testes existentes do dashboard ajustados e passando.
- [ ] Novos testes de regressão cobrindo os bugs identificados.
- [ ] Quality gate do `AGENTS.md` executado com sucesso.
- [ ] Relatório do slice gerado e `REPORT_PATH` informado.
- [ ] Commit e push realizados.
