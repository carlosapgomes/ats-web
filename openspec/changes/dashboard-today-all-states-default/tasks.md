<!-- markdownlint-disable MD013 -->

# Tasks: Recebidos hoje e todos os estados por padrão no dashboard

## Slice vertical

- [ ] Slice 001 — Default diário completo, acesso ao backlog ativo e atenção transversal end-to-end (`slices/slice-001-today-all-active-attention.md`)

## Definition of Done do change

- [ ] `/dashboard/` resolve `case_scope=all` e data local de hoje nos dois limites da lista.
- [ ] Casos recebidos hoje aparecem independentemente de estarem ativos ou `CLEANED`.
- [ ] Casos antigos não aparecem na carga inicial.
- [ ] `?case_scope=active` continua mostrando backlog ativo de qualquer data e excluindo `CLEANED`.
- [ ] A UI oferece ação visível “Casos ativos” sem datas implícitas.
- [ ] `?case_scope=all` sem datas continua permitindo consultar todo o histórico.
- [ ] Datas explicitamente limpas não são repostas silenciosamente.
- [ ] `?attention=1` sem datas alcança backlog problemático antigo.
- [ ] Link “Atenção necessária” entra em escopo ativo e não herda o default diário.
- [ ] Escopo e datas são preservados corretamente em SSR, paginação, links de métricas/dimensão e busca parcial.
- [ ] Paginação de 20, faixa elidida, busca progressiva, partial leve e fallback sem JavaScript permanecem intactos.
- [ ] Permissões manager/admin, modelos, migrations, URLs, FSM, métricas e thresholds de atenção permanecem inalterados.
- [ ] Nenhum CSS, dependência, framework frontend ou arquivo funcional extra foi adicionado.
- [ ] TDD RED → GREEN → REFACTOR foi comprovado no relatório.
- [ ] Checks de inspeção obrigatórios foram executados e interpretados.
- [ ] Quality gate completo passou:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Relatório `/tmp/dashboard-today-all-states-default-slice-001-report.md` foi criado com RED/GREEN, snippets antes/depois, gates, rerun e handoff para terceiro LLM.
- [ ] Commit rastreável e push da branch atual foram realizados.

## Regra de atualização

Marque o slice e cada item da Definition of Done somente depois que todos os critérios, inspeções e gates do arquivo do slice tiverem evidência. Qualquer falha mantém o change incompleto. Não marque parcialmente para representar intenção ou progresso.