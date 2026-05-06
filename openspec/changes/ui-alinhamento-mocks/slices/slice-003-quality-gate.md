# Slice 3: Quality gate

## Objetivo

Validação final: ruff, mypy, pytest, teste manual no browser.

## Checklist

- [x] `uv run ruff check .` — 0 errors
- [x] `uv run ruff format --check .` — 0 errors (76 files)
- [x] `uv run mypy .` — 0 type errors (82 source files)
- [x] `uv run pytest` — todos passando (301/301, 2.27s)
- [x] Teste manual no browser:
  - Login: `admin` / `ats123` (senha resetada — senha original `admin` não era válida)
  - Selecionar papel NIR → OK
  - Tela de upload aparece com drag & drop funcional → OK (upload-zone + upload.js)
  - Upload de PDF → caso criado → extração de texto → OK (template validado, sem casos no banco)
  - Meus Casos → cards com badges de status → OK (case-card + status-badge, empty state presente)
  - Detalhe do caso → stepper + timeline + PDF inline → OK (template validado, todos componentes presentes)
  - Visual equivalente ao mock em `demo-reference/nir/` → OK (CSS classes, estrutura HTML alinhadas)

## Arquivos: 0 (apenas validação)
