# Tasks: Busca rápida client-side na fila médica pendente

## Slice vertical

- [x] Slice 001 — Implementar filtro dinâmico client-side na aba médica `Pendentes` (`slices/slice-001-client-side-pending-filter.md`)

## Definition of Done do change

- [x] Campo de busca aparece na aba médica `Pendentes`.
- [x] Campo de busca não aparece na aba `Decididos Hoje`.
- [x] Cards pendentes possuem contrato HTML explícito para busca por nome e `agency_record_number`.
- [x] Filtro por nome funciona de forma case-insensitive e accent-insensitive.
- [x] Filtro por ocorrência funciona usando `agency_record_number`.
- [x] Botão `Limpar` remove filtro sem exigir apagar letra por letra.
- [x] Tecla `Esc` no input limpa o filtro.
- [x] UI mostra quando há filtro ativo e quantos pacientes estão visíveis.
- [x] Auto-refresh HTMX reaplica o filtro atual enquanto o usuário permanece na página.
- [x] Filtro não é persistido em URL, sessão, localStorage, sessionStorage ou cookie.
- [x] Nenhuma regra de lock, decisão médica, FSM, rota ou consulta server-side foi alterada.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário com snippets antes/depois, evidência TDD, resultados dos gates e respostas aos gates de autoavaliação.
- [ ] Commit e push realizados após implementação.
