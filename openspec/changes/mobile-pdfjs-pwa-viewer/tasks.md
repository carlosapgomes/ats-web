# Tasks: Visualizador PDF interno para PWA mobile com PDF.js

## Slices verticais

- [x] Slice 001 — Médico: PDF principal da decisão médica com viewer mobile interno (`slices/slice-001-doctor-primary-pdf-viewer.md`)
- [ ] Slice 002 — NIR + dashboard: PDFs principais em detalhes operacionais/históricos/gerenciais (`slices/slice-002-intake-dashboard-primary-pdf-viewer.md`)
- [ ] Slice 003 — CHD/scheduler: PDF principal no detalhe de processados (`slices/slice-003-scheduler-primary-pdf-viewer.md`)
- [ ] Slice 004 — Anexos PDF: viewer mobile interno para anexos clínicos PDF (`slices/slice-004-pdf-attachments-viewer.md`)

## Definition of Done do change

- [ ] Desktop preserva embed nativo de PDF nas superfícies alteradas.
- [ ] Mobile/PWA usa página interna do app, sem `target="_blank"`, para PDFs cobertos.
- [ ] Viewer interno usa PDF.js com Vanilla JS, sem framework frontend.
- [ ] PDF.js foi vendorizado em `static/vendor/pdfjs/` ou houve justificativa técnica documentada no relatório.
- [ ] Viewer renderiza páginas em canvas com lazy rendering/controle de carga.
- [ ] Viewer tem botão “Voltar” no topo e no rodapé.
- [ ] URL de retorno é validada ou canônica; não depende apenas de `history.back()`.
- [ ] Fallback de erro permite tentar abrir a rota protegida do PDF original.
- [ ] Rotas de viewer e PDF preservam autorização por papel.
- [ ] Nenhuma rota passa a expor `MEDIA_URL` ou caminho físico do arquivo.
- [ ] Respostas PDF tocadas têm `Cache-Control: no-store` e mantêm `Content-Type: application/pdf`.
- [ ] Testes relevantes adicionados/ajustados seguindo TDD.
- [ ] Quality gate do AGENTS.md executado por slice:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Cada slice atualizou este `tasks.md` ao concluir.
- [ ] Cada slice gerou relatório markdown temporário com evidências RED/GREEN, snippets antes/depois e gates.
- [ ] Cada slice fez commit e push, e parou para revisão antes do próximo slice.
