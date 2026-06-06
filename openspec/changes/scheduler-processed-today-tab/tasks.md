# Tasks: Aba Processados Hoje na fila do agendador

## Slice vertical

- [x] Slice 001 — Implementar aba `Processados Hoje`, remover `Histórico` e adicionar detalhe read-only (`slices/slice-001-processed-today-tab.md`)

## Definition of Done do change

- [ ] `Histórico` removido da navegação do agendador.
- [ ] `Pendentes` e `Processados Hoje` são abas/links funcionais em `/scheduler/`.
- [ ] `Confirmados Hoje` removido/renomeado para `Processados Hoje`.
- [ ] `Processados Hoje` lista casos confirmados e recusados pelo agendador logado no dia local atual.
- [ ] Query de processados hoje não depende de `status` FSM transitório.
- [ ] Lista usa cards de pacientes, não tabela mínima.
- [ ] Cada card processado hoje tem ação `Ver detalhes`.
- [ ] Detalhe read-only do agendador usa o padrão visual de supervisor/admin.
- [ ] Agendador não acessa detalhes de casos processados por outro agendador.
- [ ] Auto-refresh respeita a aba ativa.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário.
- [ ] Commit e push realizados após implementação.
