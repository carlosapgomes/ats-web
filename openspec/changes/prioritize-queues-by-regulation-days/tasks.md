# Tasks: Priorizar filas por “Dias em tela” do relatório de regulação

## Status

Change planejado, aguardando implementação em slices verticais.

## Slices

- [x] Slice 001 — Extração persistida + fila médica priorizada (`slices/slice-001-extracao-persistencia-fila-medica.md`)
- [ ] Slice 002 — Fila do agendador priorizada (`slices/slice-002-fila-agendador-priorizada.md`)

## Definition of Done do Change

- [x] Campo persistente `Case.regulation_days_on_screen` criado como inteiro positivo opcional e indexado.
- [x] Parser determinístico extrai `Dias em tela: N` do texto do PDF.
- [x] Parser retorna o maior valor quando há múltiplas ocorrências.
- [x] Parser retorna `None` quando o dado está ausente.
- [x] Extração de PDF persiste o valor em casos novos.
- [x] Casos existentes com `extracted_text` são preenchidos por migration/data backfill.
- [x] Fila médica `WAIT_DOCTOR` ordena por maior `Dias em tela`, `NULL` por último, `created_at` como desempate.
- [x] Fila médica exibe `Dias em tela: N` no card quando disponível.
- [ ] Fila do agendador `WAIT_APPT` ordena por maior `Dias em tela`, `NULL` por último, `created_at` como desempate.
- [ ] Fila do agendador exibe `Dias em tela: N` no card `WAIT_APPT` quando disponível.
- [ ] Vinda imediata no agendador continua no topo absoluto e não é reordenada por `Dias em tela`.
- [x] Testes relevantes adicionados/atualizados por slice.
- [x] Quality gate do `AGENTS.md` executado ou falhas justificadas.
- [x] Relatório temporário de cada slice gerado e `REPORT_PATH` informado.
- [ ] Commit e push realizados por slice.
