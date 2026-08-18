<!-- markdownlint-disable MD013 -->

# Tasks: Casos ativos por padrão e paginação compacta no dashboard

## Slice vertical

- [ ] Slice 001 — Escopo ativo/histórico e paginação server-side compacta end-to-end (`slices/slice-001-active-scope-compact-pagination.md`)

## Definition of Done do change

- [ ] Sem `case_scope`, a lista mostra todos os casos não `CLEANED`, sem restringir ao dia atual.
- [ ] `case_scope=all` torna casos `CLEANED` novamente consultáveis na lista.
- [ ] `case_scope` inválido usa fallback seguro `active`.
- [ ] Escopo visível compõe com busca, procedimento, status, datas e atenção.
- [ ] `case_scope=all` é preservado na paginação, troca de métricas e busca parcial.
- [ ] O backend mantém 20 casos por página.
- [ ] Paginação usa faixa elidida limitada, sem renderizar todos os números.
- [ ] Navegação contém primeira/última/atual/vizinhas, reticências não clicáveis e Anterior/Próxima.
- [ ] Resumo `Exibindo X–Y de Z casos` corresponde ao queryset filtrado.
- [ ] Fallback SSR sem JavaScript continua funcional.
- [ ] Permissões manager/admin, métricas, modelos e FSM permanecem inalterados.
- [ ] Nenhum model, migration, URL, dependência ou framework frontend foi adicionado.
- [ ] TDD RED → GREEN → REFACTOR foi comprovado no relatório.
- [ ] Checks de inspeção obrigatórios foram executados e interpretados.
- [ ] Quality gate completo passou:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Relatório `/tmp/dashboard-active-cases-compact-pagination-slice-001-report.md` foi criado com evidências e handoff para terceiro LLM.
- [ ] Commit rastreável e push da branch atual foram realizados.

## Regra de atualização

Marque o slice e os itens da Definition of Done somente depois de todos os critérios, inspeções e gates do arquivo do slice passarem. Qualquer falha mantém este change incompleto.
