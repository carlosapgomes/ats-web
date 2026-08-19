<!-- markdownlint-disable MD013 -->

# Tasks: Recebidos hoje e todos os estados por padrão no dashboard

## Slice vertical

- [x] Slice 001 — Default diário completo, acesso ao backlog ativo e atenção transversal end-to-end (`slices/slice-001-today-all-active-attention.md`)

## Definition of Done do change

- [x] `/dashboard/` resolve `case_scope=all` e data local de hoje nos dois limites da lista.
- [x] Casos recebidos hoje aparecem independentemente de estarem ativos ou `CLEANED`.
- [x] Casos antigos não aparecem na carga inicial.
- [x] `?case_scope=active` continua mostrando backlog ativo de qualquer data e excluindo `CLEANED`.
- [x] A UI oferece ação visível “Casos ativos” sem datas implícitas.
- [x] `?case_scope=all` sem datas continua permitindo consultar todo o histórico.
- [x] Datas explicitamente limpas não são repostas silenciosamente.
- [x] `?attention=1` sem datas alcança backlog problemático antigo.
- [x] Link “Atenção necessária” entra em escopo ativo e não herda o default diário.
- [x] Escopo e datas são preservados corretamente em SSR, paginação, links de métricas/dimensão e busca parcial.
- [x] Paginação de 20, faixa elidida, busca progressiva, partial leve e fallback sem JavaScript permanecem intactos.
- [x] Permissões manager/admin, modelos, migrations, URLs, FSM, métricas e thresholds de atenção permanecem inalterados.
- [x] Nenhum CSS, dependência, framework frontend ou arquivo funcional extra foi adicionado.
- [x] TDD RED → GREEN → REFACTOR foi comprovado no relatório.
- [x] Checks de inspeção obrigatórios foram executados e interpretados.
- [x] Quality gate completo passou:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [x] Relatório `/tmp/dashboard-today-all-states-default-slice-001-report.md` foi criado com RED/GREEN, snippets antes/depois, gates, rerun e handoff para terceiro LLM.
- [x] Commit rastreável e push da branch atual foram realizados.

## Regra de atualização

Marque o slice e cada item da Definition of Done somente depois que todos os critérios, inspeções e gates do arquivo do slice tiverem evidência. Qualquer falha mantém o change incompleto. Não marque parcialmente para representar intenção ou progresso.
