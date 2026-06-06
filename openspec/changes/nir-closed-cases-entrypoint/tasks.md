# Tasks: Tornar acessível a busca NIR de casos encerrados

## Status

Change planejado. Implementar apenas o Slice 001.

## Slices

- [ ] Slice 001 — Expor entrada de Casos Encerrados e corrigir filtro
  operacional (`slices/slice-001-closed-cases-entrypoint.md`)

## Definition of Done

- [ ] `Casos Encerrados` aparece nas telas NIR principais relevantes.
- [ ] `Meus Casos` continua excluindo `CLEANED` da fila operacional.
- [ ] Filtro de status em `Meus Casos` não induz busca por `CLEANED` no lugar
  errado.
- [ ] `/intake/closed-cases/` continua funcionando para busca de casos
  concluídos.
- [ ] Testes relevantes cobrem o ponto de entrada e a separação operacional.
- [ ] Quality gate relevante executado.
- [ ] Relatório temporário gerado com `REPORT_PATH`.
- [ ] Commit e push realizados.

## Validação recomendada

```bash
uv run pytest apps/intake/tests/test_post_schedule_issue.py apps/intake/tests/test_my_cases.py apps/intake/tests/test_nir_shared_operational.py -q
uv run ruff check apps/intake
uv run ruff format --check apps/intake
uv run mypy apps/intake
```

Quality gate completo, se viável:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```
