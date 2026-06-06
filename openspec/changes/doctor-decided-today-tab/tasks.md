# Tasks: Aba Decididos Hoje na fila médica

## Slice vertical

- [x] Slice 001 — Implementar aba `Decididos Hoje`, remover `Histórico` e adicionar detalhe read-only (`slices/slice-001-decided-today-tab.md`)

## Definition of Done do change

- [x] `Histórico` removido da navegação médica.
- [x] `Pendentes` e `Decididos Hoje` são abas/links funcionais em `/doctor/`.
- [x] `Decididos Hoje` lista casos decididos pelo médico logado no dia local atual.
- [x] Query de decididos hoje não depende de `status` FSM transitório.
- [x] Casos aceitos/negados que avançaram para estados posteriores continuam listados.
- [x] Cada caso decidido hoje tem ação `Ver detalhes`.
- [x] Detalhe read-only do médico usa o padrão visual de supervisor/admin.
- [x] Médico não acessa detalhes de casos decididos por outro médico.
- [x] Auto-refresh respeita a aba ativa.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário.
- [x] Commit e push realizados após implementação.
