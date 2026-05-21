# Tasks: Upload Múltiplo NIR com Extração PDF Assíncrona

## Status

Change criado após validação com usuário solicitando upload simultâneo de múltiplos PDFs no NIR. O desenho aprovado usa `django-q2` com clusters separados (`pdf` e `llm`) e mantém FSM/`CaseEvent` como fonte de verdade operacional.

## Slices

- [ ] Slice 001 — Clusters django-q2 e Compose (`slices/slice-001-q2-clusters-and-compose.md`)
- [ ] Slice 002 — Task assíncrona de extração PDF (`slices/slice-002-pdf-extraction-task.md`)
- [ ] Slice 003 — Backend de upload múltiplo (`slices/slice-003-multi-upload-backend.md`)
- [ ] Slice 004 — UI/JS de upload múltiplo (`slices/slice-004-multi-upload-ui.md`)
- [ ] Slice 005 — Hardening operacional e quality gate (`slices/slice-005-operational-hardening-and-quality.md`)

## Definition of Done do Change

- [ ] NIR consegue selecionar/enviar múltiplos PDFs em uma submissão.
- [ ] A request web não executa extração de texto de PDF.
- [ ] Cada PDF válido cria exatamente um `Case`.
- [ ] Cada `Case` inicia em fluxo FSM rastreável (`NEW → R1_ACK_PROCESSING`).
- [ ] Extração PDF roda em background pelo cluster `pdf`.
- [ ] Pipeline LLM roda em background pelo cluster `llm`.
- [ ] `web` e `pdf_worker` compartilham `MEDIA_ROOT` em produção.
- [ ] Falha de um PDF não derruba o lote inteiro.
- [ ] Tasks são idempotentes o suficiente para retry.
- [ ] Limites por arquivo e por lote estão centralizados e testados.
- [ ] Testes cobrem upload de lote com múltiplos PDFs.
- [ ] Quality gate completo executado.
- [ ] Relatórios dos slices gerados.

## Comandos Globais de Validação

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```
