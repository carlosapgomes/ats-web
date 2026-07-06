# Tasks: Busca rápida client-side na fila médica pendente

## Slice vertical

- [ ] Slice 001 — Implementar filtro dinâmico client-side na aba médica `Pendentes` (`slices/slice-001-client-side-pending-filter.md`)

## Definition of Done do change

- [ ] Campo de busca aparece na aba médica `Pendentes`.
- [ ] Campo de busca não aparece na aba `Decididos Hoje`.
- [ ] Cards pendentes possuem contrato HTML explícito para busca por nome e `agency_record_number`.
- [ ] Filtro por nome funciona de forma case-insensitive e accent-insensitive.
- [ ] Filtro por ocorrência funciona usando `agency_record_number`.
- [ ] Botão `Limpar` remove filtro sem exigir apagar letra por letra.
- [ ] Tecla `Esc` no input limpa o filtro.
- [ ] UI mostra quando há filtro ativo e quantos pacientes estão visíveis.
- [ ] Auto-refresh HTMX reaplica o filtro atual enquanto o usuário permanece na página.
- [ ] Filtro não é persistido em URL, sessão, localStorage, sessionStorage ou cookie.
- [ ] Nenhuma regra de lock, decisão médica, FSM, rota ou consulta server-side foi alterada.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário com snippets antes/depois, evidência TDD, resultados dos gates e respostas aos gates de autoavaliação.
- [ ] Commit e push realizados após implementação.
