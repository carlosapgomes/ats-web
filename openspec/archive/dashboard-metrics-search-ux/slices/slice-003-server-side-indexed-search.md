<!-- markdownlint-disable MD013 -->

# Slice 003: Busca server-side indexada

## Contexto zero para implementador

Este slice depende dos Slices 001 e 002 completos. O dashboard já deve ter:

- duração humana;
- labels nos filtros de data;
- seletor `metrics_date` para métricas.

Agora precisamos adicionar busca server-side no card "Todos os Casos" por nome
do paciente ou número de ocorrência. A busca deve funcionar sem JavaScript e
ser preparada para banco grande com índices PostgreSQL.

Arquivos principais:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `apps/dashboard/tests/test_dashboard.py`
- nova migration em `apps/cases/migrations/`

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-metrics-search-ux/proposal.md`
- `openspec/changes/dashboard-metrics-search-ux/design.md`
- `openspec/changes/dashboard-metrics-search-ux/tasks.md`
- slices anteriores deste change
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Manager/admin abre dashboard
→ digita pelo menos 3 caracteres em "Buscar por nome ou registro"
→ submete o formulário
→ servidor filtra casos por nome do paciente ou número de ocorrência
→ filtros, paginação e permissões continuam funcionando
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `apps/dashboard/tests/test_dashboard.py`
4. `apps/cases/migrations/0011_dashboard_case_search_indexes.py`

Se precisar tocar `apps/cases/models.py`, justificar no relatório. Preferir
migration `RunSQL` para índices funcionais se isso evitar mudar o model apenas
para declarar índices complexos.

## Requisitos funcionais

### R1. Query string de busca

Usar parâmetro:

```text
search=<termo>
```

Regras:

- aplicar `strip()`;
- limitar o termo normalizado a tamanho razoável, por exemplo 100 caracteres;
- filtrar somente se o termo tiver 3 ou mais caracteres;
- com 1 ou 2 caracteres, não filtrar e mostrar ajuda visual;
- com termo vazio, não filtrar.

### R2. Campos pesquisados

Pesquisar server-side em:

- nome do paciente dentro de `structured_data["patient"]["name"]`;
- `agency_record_number`.

A busca deve ser case-insensitive. Accent-insensitive é desejável, mas não
obrigatório neste slice.

### R3. Composição com filtros existentes

A busca deve compor com:

- `status`;
- `date_from`;
- `date_to`;
- `attention=1`;
- `metrics_date`, preservando a seleção de métricas;
- paginação.

Links de paginação devem preservar `search` quando presente.

### R4. UI do formulário

Adicionar campo visível no formulário de "Todos os Casos":

- label: `Buscar por nome ou registro`;
- input `name="search"`;
- placeholder opcional: `Digite ao menos 3 caracteres`.

O botão de limpar filtros deve aparecer quando `search` estiver preenchido,
mesmo que nenhum outro filtro esteja ativo.

### R5. Índices PostgreSQL

Criar migration reversível que:

1. habilita extensão `pg_trgm`;
2. cria índice GIN trigram para `lower(agency_record_number)`;
3. cria índice GIN trigram para
   `lower((structured_data #>> '{patient,name}'))`.

Exemplo conceitual:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ... USING gin (lower(agency_record_number) gin_trgm_ops);
CREATE INDEX ... USING gin (lower((structured_data #>> '{patient,name}')) gin_trgm_ops);
```

Preferir `CREATE INDEX CONCURRENTLY` com `atomic = False` para reduzir lock em
produção. Se não usar concurrent, justificar no relatório.

### R6. Sem busca dinâmica ainda

Este slice não deve criar JavaScript nem partial SSR. A busca deve funcionar por
submit tradicional.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

Testes mínimos:

1. Dashboard contém label `Buscar por nome ou registro` e input `name="search"`.
2. `?search=ana` encontra caso cujo nome do paciente contém `Ana`.
3. `?search=ocor` encontra caso por `agency_record_number`.
4. Busca é case-insensitive.
5. `?search=an` não filtra e mostra ajuda de mínimo de 3 caracteres.
6. Busca compõe com `status`.
7. Busca compõe com `date_from`/`date_to`.
8. Busca compõe com `attention=1`, se o filtro de atenção existir na branch.
9. Paginação preserva `search` nos links.
10. `metrics_date` é preservado ao submeter filtros da lista.
11. Migration contém criação de `pg_trgm` e dos dois índices esperados.

## Dicas de implementação

Para nome do paciente, os testes podem criar `Case` com:

```python
structured_data={"patient": {"name": "Ana Maria"}}
```

Para query ORM, uma opção é anotar expressão textual do JSON e aplicar busca em
lowercase. Mantenha a expressão compatível com os índices sempre que possível.

Não use busca client-side. Não carregue todos os casos para filtrar em Python.

## Critérios de sucesso

- [ ] Testes foram escritos antes da implementação e falharam inicialmente.
- [ ] Busca por nome é server-side.
- [ ] Busca por registro é server-side.
- [ ] Termos com menos de 3 caracteres não filtram.
- [ ] Busca compõe com filtros existentes e paginação.
- [ ] Índices `pg_trgm` existem em migration reversível.
- [ ] Sem JavaScript neste slice.
- [ ] Sem Django REST Framework ou endpoint JSON.
- [ ] Quality gate do `AGENTS.md` passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Qual teste prova busca por nome?
2. Qual teste prova busca por registro?
3. Qual teste prova que termo com 2 caracteres não filtra?
4. Como a busca compõe com status/data/attention?
5. Quais índices foram criados e qual SQL/migration os cria?
6. Foi usado filtro em Python após carregar casos? Se sim, está errado.
7. Foi criado JavaScript? Se sim, está fora de escopo.
8. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-metrics-search-ux/proposal.md, design.md, tasks.md and slices/slice-001 through slice-003.
Assume Slices 001 and 002 are complete. Implement ONLY Slice 003.
Use TDD: first add failing tests for server-side search and index migration, then implement minimal code.
Follow clean code, DRY and YAGNI. Do not create JavaScript or dynamic partials in this slice.
Add search=<term> to the existing dashboard list filters. Apply filtering only for trimmed terms with at least 3 characters.
Search server-side by patient name in structured_data.patient.name and agency_record_number. Do not filter in Python after loading cases.
Add a reversible PostgreSQL migration with pg_trgm GIN indexes for lower(agency_record_number) and lower((structured_data #>> '{patient,name}')). Prefer concurrent indexes with atomic = False or justify otherwise.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Create a detailed temporary markdown report with before/after snippets and self-evaluation answers.
Run markdownlint-cli2 only on markdown files you create, such as the temporary report. Do not lint or rewrite existing markdown broadly.
Commit and push only implementation files created/changed for this slice. Do not commit OpenSpec files before final archival of the change.
Return REPORT_PATH=<path> and stop. Do not start the next slice without explicit confirmation.
```
