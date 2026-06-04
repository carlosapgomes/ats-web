# Tasks: Alinhar anotações UUID em parâmetros de rota

## Status

Change concluído e arquivado. Slice 001 implementado, verificado, commitado e enviado para `origin/main`.

## Slices

- [x] Slice 001 — Ajustar type hints de views com converters UUID
  (`slices/slice-001-align-view-uuid-annotations.md`)

## Definition of Done

- [x] Views com rotas `<uuid:...>` foram inventariadas.
- [x] Parâmetros correspondentes foram anotados como `uuid.UUID`.
- [x] Casos que são payload textual permaneceram `str`.
- [x] `mypy` passa.
- [x] Testes passam.
- [x] Relatório temporário gerado com `REPORT_PATH`.
- [x] Commit e push realizados.

## Validação

```bash
uv run mypy .
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
