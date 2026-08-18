<!-- markdownlint-disable MD013 -->

# Tasks: Casos ativos por padrão e paginação compacta no dashboard

## Slice vertical

- [x] Slice 001 — Escopo ativo/histórico e paginação server-side compacta end-to-end (`slices/slice-001-active-scope-compact-pagination.md`)

## Definition of Done do change

- [x] Sem `case_scope`, a lista mostra todos os casos não `CLEANED`, sem restringir ao dia atual.
- [x] `case_scope=all` torna casos `CLEANED` novamente consultáveis na lista.
- [x] `case_scope` inválido usa fallback seguro `active`.
- [x] Escopo visível compõe com busca, procedimento, status, datas e atenção.
- [x] `case_scope=all` é preservado na paginação, troca de métricas e busca parcial.
- [x] O backend mantém 20 casos por página.
- [x] Paginação usa faixa elidida limitada, sem renderizar todos os números.
- [x] Navegação contém primeira/última/atual/vizinhas, reticências não clicáveis e Anterior/Próxima.
- [x] Resumo `Exibindo X–Y de Z casos` corresponde ao queryset filtrado.
- [x] Fallback SSR sem JavaScript continua funcional.
- [x] Permissões manager/admin, métricas, modelos e FSM permanecem inalterados.
- [x] Nenhum model, migration, URL, dependência ou framework frontend foi adicionado.
- [x] TDD RED → GREEN → REFACTOR foi comprovado no relatório.
- [x] Checks de inspeção obrigatórios foram executados e interpretados.
- [x] Quality gate completo passou:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [x] Relatório `/tmp/dashboard-active-cases-compact-pagination-slice-001-report.md` foi criado com evidências e handoff para terceiro LLM.
- [x] Commit rastreável e push da branch atual foram realizados.

## Revisão do planner após auditoria independente

- [x] Auditor independente reexecutou testes alvo, testes de dashboard, Ruff, formatter, mypy e pytest completo.
- [x] Resultado reproduzido: `3158 passed`, zero falhas/erros e HEAD remoto `a235ea5`.
- [x] Exceção de escopo aceita explicitamente pelo planner: `apps/dashboard/tests/test_procedure_analytics.py` foi o sexto arquivo funcional porque fixtures históricas desse mesmo app usam `CaseStatus.CLEANED`; adicionar `case_scope=all` aos seis GETs afetados era necessário para preservar o propósito e os asserts das regressões sob o novo default ativo.
- [x] A exceção é mínima, não altera código de produção e não autoriza ampliações semelhantes sem consulta prévia em slices futuros.
- [x] Divergência cosmética do relatório registrada: foram adicionados 19 testes, não 23; o delta verificável é `3139 → 3158`.
- [x] Implementação do Slice 001 aprovada sem replay.

## Regra de atualização

Marque o slice e os itens da Definition of Done somente depois de todos os critérios, inspeções e gates do arquivo do slice passarem. Qualquer falha mantém este change incompleto. Exceções de protocolo exigem decisão explícita e rastreável do planner, como registrado acima.
