# Tasks: Upload Múltiplo NIR com Extração PDF Assíncrona

## Status

Change concluído e validado. Criado após validação com usuário solicitando upload simultâneo de múltiplos PDFs no NIR. O desenho aprovado usa `django-q2` com clusters separados (`pdf` e `llm`) e mantém FSM/`CaseEvent` como fonte de verdade operacional.

Validação manual reportada pelo usuário: upload de 2 PDFs simultâneos funcionou corretamente.

## Slices

- [x] Slice 001 — Clusters django-q2 e Compose (`slices/slice-001-q2-clusters-and-compose.md`)
- [x] Slice 002 — Task assíncrona de extração PDF (`slices/slice-002-pdf-extraction-task.md`)
- [x] Slice 003 — Backend de upload múltiplo (`slices/slice-003-multi-upload-backend.md`)
- [x] Slice 004 — UI/JS de upload múltiplo (`slices/slice-004-multi-upload-ui.md`)
- [x] Slice 005 — Hardening operacional e quality gate (`slices/slice-005-operational-hardening-and-quality.md`)

## Definition of Done do Change ✅ Concluído

- [x] NIR consegue selecionar/enviar múltiplos PDFs em uma submissão.
- [x] A request web não executa extração de texto de PDF.
- [x] Cada PDF válido cria exatamente um `Case`.
- [x] Cada `Case` inicia em fluxo FSM rastreável (`NEW → R1_ACK_PROCESSING`).
- [x] Extração PDF roda em background pelo cluster `pdf`.
- [x] Pipeline LLM roda em background pelo cluster `llm`.
- [x] `web` e `pdf_worker` compartilham `MEDIA_ROOT` em produção.
- [x] Falha de um PDF não derruba o lote inteiro.
- [x] Tasks são idempotentes o suficiente para retry.
- [x] Limites por arquivo e por lote estão centralizados e testados.
- [x] Testes cobrem upload de lote com múltiplos PDFs.
- [x] Quality gate completo executado.
- [x] Relatórios dos slices gerados.

## Comandos Globais de Validação

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```
