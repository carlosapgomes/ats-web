# Tasks: Alinhar anotações UUID em parâmetros de rota

## Status

Change planejado. Implementar um slice enxuto.

## Slices

- [x] Slice 001 — Ajustar type hints de views com converters UUID
  (`slices/slice-001-align-view-uuid-annotations.md`)

## Definition of Done

- [ ] Views com rotas `<uuid:...>` foram inventariadas.
- [ ] Parâmetros correspondentes foram anotados como `uuid.UUID`.
- [ ] Casos que são payload textual permaneceram `str`.
- [ ] `mypy` passa.
- [ ] Testes passam.
- [ ] Relatório temporário gerado com `REPORT_PATH`.
- [ ] Commit e push realizados.

## Validação

```bash
uv run mypy .
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
