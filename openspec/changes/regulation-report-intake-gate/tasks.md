# Tasks: Barreira de Aceitação para PDFs de Relatório de Regulação

## Status

Change criado após análise exploratória de 12 PDFs de regulação e 4 PDFs não-regulatórios em diretórios temporários locais. A feature deve impedir que documentos PDF fora do padrão de relatório de regulação consumam pipeline LLM ou cheguem à fila médica.

## Slices

- [ ] Slice 001 — Detector determinístico de relatório de regulação (`slices/slice-001-regulation-detector.md`)
- [ ] Slice 002 — Integração da barreira na extração PDF assíncrona (`slices/slice-002-extraction-gate-integration.md`)
- [ ] Slice 003 — Resultado NIR, auditoria e UX para documento inválido (`slices/slice-003-nir-result-and-audit.md`)
- [ ] Slice 004 — Hardening operacional, docs e quality gate (`slices/slice-004-hardening-docs-quality.md`)

## Definition of Done do Change

- [ ] PDFs de relatório de regulação passam pela barreira antes do LLM.
- [ ] PDFs fora do padrão de regulação não acionam `enqueue_pipeline()`.
- [ ] Documento barrado gera `suggested_action.decision = manual_review_required`.
- [ ] Documento barrado não entra na fila médica.
- [ ] Documento barrado chega ao NIR em `WAIT_R1_CLEANUP_THUMBS` com motivo claro.
- [ ] `CaseEvent` registra falha da barreira com evidências não sensíveis.
- [ ] Relatório de regulação cujo exame seja colonoscopia/CPRE passa pela barreira e segue para scope gate existente.
- [ ] Número de registro por fallback técnico não é tratado como evidência de regulação válida.
- [ ] Testes cobrem detector, task de extração, FSM/eventos e UI mínima do NIR.
- [ ] Quality gate completo executado.
- [ ] Relatórios dos slices gerados.

## Comandos Globais de Validação

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```
