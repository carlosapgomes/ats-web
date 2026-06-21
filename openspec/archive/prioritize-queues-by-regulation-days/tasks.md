# Tasks: Priorizar filas por “Dias em tela” do relatório de regulação

## Status

Change concluído e arquivado. 2 slices verticais, ambos validados antes do arquivamento.

## Slices

- [x] Slice 001 — Extração persistida + fila médica priorizada (`slices/slice-001-extracao-persistencia-fila-medica.md`)
- [x] Slice 002 — Fila do agendador priorizada (`slices/slice-002-fila-agendador-priorizada.md`)

## Definition of Done do Change

- [x] Campo persistente `Case.regulation_days_on_screen` criado como inteiro positivo opcional e indexado.
- [x] Parser determinístico extrai `Dias em tela: N` do texto do PDF.
- [x] Parser retorna o maior valor quando há múltiplas ocorrências.
- [x] Parser retorna `None` quando o dado está ausente.
- [x] Extração de PDF persiste o valor em casos novos.
- [x] Casos existentes com `extracted_text` são preenchidos por migration/data backfill.
- [x] Fila médica `WAIT_DOCTOR` ordena por maior `Dias em tela`, `NULL` por último, `created_at` como desempate.
- [x] Fila médica exibe `Dias em tela: N` no card quando disponível.
- [x] Fila do agendador `WAIT_APPT` ordena por maior `Dias em tela`, `NULL` por último, `created_at` como desempate.
- [x] Fila do agendador exibe `Dias em tela: N` no card `WAIT_APPT` quando disponível.
- [x] Vinda imediata no agendador continua no topo absoluto e não é reordenada por `Dias em tela`.
- [x] Testes relevantes adicionados/atualizados por slice.
- [x] Quality gate do `AGENTS.md` executado ou falhas justificadas.
- [x] Relatório temporário de cada slice gerado e `REPORT_PATH` informado.
- [x] Commit e push realizados por slice.

## Status final do change

Change concluído e arquivado. 2 slices verticais (médico + agendador), ambos revisados independentemente antes do arquivamento.

### Commits

- `5036c5a` — Slice 001: campo `Case.regulation_days_on_screen` (`PositiveIntegerField`, nullable, indexed) + migration `0010` com backfill idempotente (`elidable=True`, batches de 500) + parser determinístico `extract_regulation_days_on_screen` em `pdf_utils.py` (maior ocorrência, `None` se ausente) + persistência em `_do_extraction` + ordenação `WAIT_DOCTOR` `DESC NULLS LAST, created_at ASC` + badge “Dias em tela: N” nos cards médicos (14 testes)
- `e097c3c` — Slice 002: ordenação `WAIT_APPT` `DESC NULLS LAST, created_at ASC` + badge nos cards do agendador + `regulation_days_on_screen` em `_build_case_card` + teste de vinda imediata permanecendo no topo absoluto (5 testes)

### Resumo do entregue

- `Case.regulation_days_on_screen` (`PositiveIntegerField`, `null/blank/db_index`, sem `default` — `0` é valor válido ≠ `NULL`) + migration `0010_add_regulation_days_on_screen` com `RunPython` backfill (regex local estável, sem importar `pdf_utils`; apenas casos com `extracted_text` e campo `NULL`; `iterator(chunk_size=500)`; `elidable=True`)
- Parser puro `extract_regulation_days_on_screen(text)` em `apps/intake/pdf_utils.py`: regex `\bDias\s+em\s+tela\s*:\s*(\d+)\b` com `re.IGNORECASE`, retorna `max(matches)` ou `None`
- Persistência em `apps/intake/tasks.py::_do_extraction` usando `cleaned_text`
- Fila médica `WAIT_DOCTOR` ordenada por `F("regulation_days_on_screen").desc(nulls_last=True), "created_at"` + badge “Dias em tela: N” no template médico
- Fila do agendador `WAIT_APPT` ordenada igualmente + badge no template do agendador (apenas cards `WAIT_APPT`, não nos de vinda imediata)
- Vinda imediata do agendador permanece no topo absoluto (`immediate_notice_qs` inalterada, renderizada antes de `pending_cases`)
- 1493 testes passando (+20 neste change: 8 parser + 3 persistência + 4 fila médica + 5 fila agendador); ruff/mypy/format verdes; FSM, locks, parser de registro e workflows estruturados inalterados

### Limitações aceitas

- Parser extrai `3` de `“Dias em tela: 3.5”` (o `\b` após `\d+` casa na fronteira `3`/`.`). PDFs reais sempre trazem inteiros; sem impacto operacional. Não normalizado porque o dado de origem é inteiro por especificação do relatório de regulação.
- Badge de “Dias em tela” aparece apenas em cards `WAIT_APPT`/`WAIT_DOCTOR`, não em cards de vinda imediata do agendador (por design do Slice 002; `regulation_days_on_screen` está disponível no dict do card compartilhado, mas o template não o renderiza na seção de vinda imediata).
- Sem reprocessamento de PDF quando `extracted_text` já existe (fora de escopo do proposal); casos existentes são cobertos pelo backfill da migration a partir de `extracted_text`.
- Não soma dias desde upload ao número do PDF (por decisão funcional confirmada no proposal — prioridade é apenas o número impresso no relatório).
