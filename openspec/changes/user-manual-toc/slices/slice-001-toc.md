# Slice 001: TOC navegável (web) + índice no PDF

## Objetivo

Gerar índice automático no manual: web clicável com âncoras + índice textual no PDF.

## TDD

### RED (testes primeiro)

Web (`apps/accounts/tests/test_user_manual_toc.py`):
- heading recebe `id`.
- TOC com `<a href="#slug">`.
- ids únicos em duplicatas.
- slug ASCII sem acento.

PDF (`tests/test_user_manual_artifacts.py`):
- PDF contém "Índice".

### GREEN

Implementar em `apps/accounts/manual.py` e `scripts/build_user_manual_pdf.py`.

### REFACTOR

Clean code, DRY (função `_slugify` compartilhada conceitualmente).

## Critérios de sucesso

- [ ] 5 testes novos passam.
- [ ] Testes existentes continuam passando.
- [ ] Quality gate verde.
