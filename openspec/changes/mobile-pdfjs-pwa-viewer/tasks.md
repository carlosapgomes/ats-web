# Tasks: Visualizador PDF interno para PWA mobile com PDF.js

## Slices verticais

- [x] Slice 001 — Médico: PDF principal da decisão médica com viewer mobile interno (`slices/slice-001-doctor-primary-pdf-viewer.md`)
- [x] Slice 002 — NIR + dashboard: PDFs principais em detalhes operacionais/históricos/gerenciais (`slices/slice-002-intake-dashboard-primary-pdf-viewer.md`)
- [x] Slice 003 — CHD/scheduler: PDF principal no detalhe de processados (`slices/slice-003-scheduler-primary-pdf-viewer.md`)
- [x] Slice 003b — Follow-up técnico: consolidar validação de `next` dos PDF viewers antes dos anexos (`slices/slice-003b-consolidate-pdf-viewer-next-validation.md`)
- [x] Slice 004 — Anexos PDF: viewer mobile interno para anexos clínicos PDF (`slices/slice-004-pdf-attachments-viewer.md`)
- [x] Slice 005 — NIR histórico: anexos PDF de casos encerrados com viewer mobile interno (`slices/slice-005-closed-case-attachment-pdf-viewer.md`)

## Definition of Done do change

- [x] Desktop preserva embed nativo de PDF nas superfícies alteradas (scheduler).
- [x] Mobile/PWA usa página interna do app, sem `target="_blank"`, para PDFs cobertos (scheduler).
- [ ] Viewer interno usa PDF.js com Vanilla JS, sem framework frontend. (Slice 001)
- [ ] PDF.js foi vendorizado em `static/vendor/pdfjs/` ou houve justificativa técnica documentada no relatório. (Slice 001)
- [ ] Viewer renderiza páginas em canvas com lazy rendering/controle de carga. (Slice 001)
- [x] Viewer tem botão “Voltar” no topo e no rodapé (compartilhado).
- [x] URL de retorno é validada ou canônica; não depende apenas de `history.back()`.
- [x] Validação de `next` dos PDF viewers usa helper compartilhado único, sem helpers locais divergentes ou validação inline.
- [x] Fallback de erro permite tentar abrir a rota protegida do PDF original (compartilhado).
- [x] Rotas de viewer e PDF preservam autorização por papel.
- [x] Nenhuma rota passa a expor `MEDIA_URL` ou caminho físico do arquivo.
- [x] Respostas PDF tocadas têm `Cache-Control: no-store` e mantêm `Content-Type: application/pdf`.
- [ ] Anexos PDF em detalhe histórico NIR (`closed_case_detail.html`) usam viewer interno no mobile e rota histórica autorizada no desktop.
- [x] Testes relevantes adicionados/ajustados seguindo TDD.
- [x] Quality gate do AGENTS.md executado por slice:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Cada slice atualizou este `tasks.md` ao concluir.
- [x] Cada slice gerou relatório markdown temporário com evidências RED/GREEN, snippets antes/depois e gates.
- [x] Cada slice fez commit e push, e parou para revisão antes do próximo slice.
