# Slice 002 — Integração da barreira na extração PDF assíncrona

## Objetivo

Integrar o detector do Slice 001 no worker de extração PDF para impedir que documentos fora do padrão de regulação acionem o pipeline LLM.

## Escopo

Arquivos previstos:

- `apps/intake/tasks.py`
- `apps/intake/pdf_utils.py` ou novo helper de metadados de extração, se necessário
- `apps/intake/tests/test_pdf_extraction_task.py`

## Fora de Escopo

- Não alterar upload síncrono.
- Não alterar UI além do necessário para preservar comportamento existente.
- Não implementar OCR.

## Critérios de Sucesso

- Quando a barreira passa, o fluxo atual permanece: `R1_ACK_PROCESSING → EXTRACTING → LLM_STRUCT` e `enqueue_pipeline()` é chamado.
- Quando a barreira falha:
  - `enqueue_pipeline()` não é chamado;
  - `case.extracted_text` é persistido;
  - `case.suggested_action.decision == manual_review_required`;
  - `reason_code == invalid_regulation_report`;
  - status final é `WAIT_R1_CLEANUP_THUMBS`;
  - eventos incluem `REGULATION_REPORT_GATE_FAILED`, `SCOPE_GATE_BYPASS` e `FINAL_REPLY_POSTED`.
- Registro artificial por fallback não é salvo como código de regulação em caso barrado.

## Decisão Técnica Esperada

A implementação deve evitar tratar timestamp fallback como registro real. Se necessário, refatorar `strip_watermark_and_extract_record()` com compatibilidade ou criar helper novo que informe `record_number_source`.

## Gates de Autoavaliação

- [ ] Nenhum PDF inválido consome LLM.
- [ ] FSM continua válida, sem manipulação direta indevida de `status`.
- [ ] Eventos são persistidos antes/depois das transições conforme padrão existente.
- [ ] Falhas de extração técnica continuam levando a `FAILED` como hoje.
- [ ] Casos já em `LLM_STRUCT` continuam usando recovery path de enqueue.

## Prompt para Implementador LLM

```text
Implemente somente o Slice 002 do change openspec/changes/regulation-report-intake-gate.
Leia AGENTS.md, PROJECT_CONTEXT.md, proposal.md, design.md e slice-001.
Assuma que evaluate_regulation_report_text() já existe.
Use TDD em apps/intake/tests/test_pdf_extraction_task.py: teste falha da barreira sem enqueue_pipeline, suggested_action manual_review_required, status WAIT_R1_CLEANUP_THUMBS e eventos esperados; teste também que sucesso da barreira preserva enqueue_pipeline.
Integre a barreira em apps/intake/tasks.py após extrair/limpar o texto e antes de enqueue_pipeline().
Se necessário, refatore apps/intake/pdf_utils.py para distinguir registro explícito de fallback sem quebrar testes existentes.
Não altere upload web.
Rode testes focados e quality checks dos arquivos tocados.
Gere relatório em /tmp/ats-web-slice-002-extraction-gate-integration-report.md.
Commit/push e pare.
```

## Validação Recomendada

```bash
uv run pytest apps/intake/tests/test_pdf_extraction_task.py apps/intake/tests/test_regulation_gate.py -q
uv run ruff check apps/intake/tasks.py apps/intake/pdf_utils.py apps/intake/regulation_gate.py apps/intake/tests/test_pdf_extraction_task.py apps/intake/tests/test_regulation_gate.py
uv run ruff format --check apps/intake/tasks.py apps/intake/pdf_utils.py apps/intake/regulation_gate.py apps/intake/tests/test_pdf_extraction_task.py apps/intake/tests/test_regulation_gate.py
uv run mypy apps/intake/tasks.py apps/intake/pdf_utils.py apps/intake/regulation_gate.py apps/intake/tests/test_pdf_extraction_task.py apps/intake/tests/test_regulation_gate.py
```
