# Tasks: Corrigir contadores do dashboard

## Status

Change concluído. 1 slice implementado.

## Slices

- [x] Slice 001 — Reescrever `_compute_summary()` com queries baseadas em decisão (`slices/slice-001-fix-counters.md`)

## Definition of Done do Change

- [x] `_compute_summary()` reescrita usando `doctor_decision` e `appointment_status` em vez de `status` FSM.
- [x] "Negados" captura casos com `doctor_decision="deny"` e `appointment_status="denied"`, mesmo após CLEANED.
- [x] "Aceitos" exclui casos com `appointment_status="denied"`.
- [x] "Aceitos" e "Negados" são mutuamente exclusivos (sem dupla contagem).
- [x] "Em Andamento" é confiável (`total - accepted - denied`).
- [x] Testes existentes do dashboard ajustados e passando.
- [x] Novos testes de regressão cobrindo os bugs identificados.
- [x] Quality gate do `AGENTS.md` executado com sucesso.
- [x] Relatório do slice gerado e `REPORT_PATH` informado.
- [x] Commit e push realizados.
