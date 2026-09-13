# Tasks — followup-authorized-procedures-only

Baseline do preflight: HEAD `a2ec444` (change ativo, pós-Slice 006), suíte
completa 3648 passed, gates verdes. ADR-0007 e deltas criados junto com este
change (não são task de implementação).

- [ ] 1.1 Implementar o Slice 001 (`slices/slice-001-authorized-coverage.md`)
  e provar cobertura restrita a rows autorizadas em validador, formulário,
  evento e histórico com eras mistas.
- [ ] 2.1 Gate final do change: `uv run ruff check . && uv run ruff format
  --check . && uv run mypy . && uv run pytest` + `openspec validate
  followup-authorized-procedures-only --strict` + verificação de zero
  migrations novas (`git status` / `apps/*/migrations/`).
