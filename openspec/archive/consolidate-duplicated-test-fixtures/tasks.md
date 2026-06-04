# Tasks: Consolidar fixtures duplicadas de testes

## Status

Change concluído e arquivado. Slice 001 implementado, verificado, commitado e enviado para `origin/main`.

## Slices

- [x] Slice 001 — Consolidar fixtures comuns de casos e usuários
  (`slices/slice-001-shared-case-user-fixtures.md`)

## Definition of Done

- [x] Duplicações relevantes em `apps/*/tests/conftest.py` foram inventariadas.
- [x] Fixtures comuns foram extraídas para local compartilhado apropriado.
- [x] Apps afetados usam as fixtures compartilhadas.
- [x] Fixtures específicas continuam locais.
- [x] Suíte completa passa.
- [x] Relatório temporário gerado com `REPORT_PATH`.
- [x] Commit e push realizados.

## Validação

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```
