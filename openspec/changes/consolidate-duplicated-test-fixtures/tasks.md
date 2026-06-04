# Tasks: Consolidar fixtures duplicadas de testes

## Status

Change planejado. Implementar um slice por vez, com TDD quando houver alteração
observável de comportamento de testes.

## Slices

- [ ] Slice 001 — Consolidar fixtures comuns de casos e usuários
  (`slices/slice-001-shared-case-user-fixtures.md`)

## Definition of Done

- [ ] Duplicações relevantes em `apps/*/tests/conftest.py` foram inventariadas.
- [ ] Fixtures comuns foram extraídas para local compartilhado apropriado.
- [ ] Apps afetados usam as fixtures compartilhadas.
- [ ] Fixtures específicas continuam locais.
- [ ] Suíte completa passa.
- [ ] Relatório temporário gerado com `REPORT_PATH`.
- [ ] Commit e push realizados.

## Validação

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```
