<!-- markdownlint-disable MD013 -->

# Slice 002: Métricas por data selecionada

## Contexto zero para implementador

Este slice depende do Slice 001 completo. O dashboard já deve ter labels de data
no card "Todos os Casos" e duração humana para o card "Tempo médio".

Atualmente as métricas diárias do dashboard usam o dia local atual. Precisamos
permitir que manager/admin escolha uma data e veja as métricas daquele dia, sem
criar uma aba histórica separada.

Arquivos principais:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `apps/dashboard/tests/test_dashboard.py`

Leia antes de implementar:

- `AGENTS.md`
- `PROJECT_CONTEXT.md`
- `openspec/changes/dashboard-metrics-search-ux/proposal.md`
- `openspec/changes/dashboard-metrics-search-ux/design.md`
- `openspec/changes/dashboard-metrics-search-ux/tasks.md`
- `openspec/changes/dashboard-metrics-search-ux/slices/slice-001-dashboard-ux-polish.md`
- este slice

## Objetivo do slice

Entregar fluxo vertical completo:

```text
Manager/admin abre dashboard
→ vê métricas do dia atual por padrão
→ seleciona uma data em "Data das métricas"
→ dashboard recarrega
→ summary, fluxo de admissão e tempos médios refletem a data selecionada
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `apps/dashboard/tests/test_dashboard.py`

Se precisar tocar outro arquivo, justificar no relatório.

## Requisitos funcionais

### R1. Query string de data das métricas

Usar parâmetro:

```text
metrics_date=YYYY-MM-DD
```

Sem parâmetro, usar `timezone.localdate()`.

Com data inválida:

- não quebrar a view;
- voltar para o dia local atual;
- opcionalmente exibir aviso leve no template.

### R2. Helpers recebem data selecionada

Atualizar os helpers para aceitar `day` explicitamente, por exemplo:

```python
def _compute_summary(day: date | None = None) -> dict[str, int]: ...
def _compute_admission_flow(day: date | None = None) -> dict[str, int]: ...
def _compute_average_times(day: date | None = None) -> dict[str, str]: ...
```

`_local_day_bounds(day)` já existe e deve ser reaproveitado.

### R3. Escopo das métricas afetadas

A data selecionada deve afetar:

- summary cards;
- fluxo de admissão;
- tempos médios.

Para tempos médios, filtrar os casos criados no dia selecionado. Não alterar o
critério para buscar por data de decisão neste slice.

A data selecionada não deve afetar:

- lista "Todos os Casos";
- filtro `date_from`/`date_to` da lista;
- `attention=1`;
- card "Aguardando por etapa".

### R4. Rotulagem do snapshot atual

Como "Aguardando por etapa" não é histórico, o template deve deixar claro que é
um snapshot atual, por exemplo:

```text
AGUARDANDO POR ETAPA (ATUAL)
```

Não tentar reconstruir histórico de fila por `CaseEvent` neste slice.

### R5. Formulário de data das métricas

Adicionar controle visível próximo às métricas:

- label: `Data das métricas`;
- input `type="date"` com valor selecionado;
- botão `Aplicar`.

Preservar filtros existentes da lista quando simples, exceto `page`:

- `status`;
- `date_from`;
- `date_to`;
- `attention`.

O formulário da lista deve preservar `metrics_date` via hidden input para não
resetar a data das métricas ao filtrar casos.

### R6. Labels dos cards

Evitar texto enganoso quando a data selecionada não é hoje. O card pode usar:

- `Total no dia`; ou
- `Total em DD/MM/AAAA`.

O importante é não manter apenas `Total Hoje` quando `metrics_date` for outro
dia.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

Testes mínimos:

1. Sem `metrics_date`, dashboard usa o dia local atual.
2. Com `metrics_date` de ontem, summary conta casos criados ontem e exclui hoje.
3. Com `metrics_date`, fluxo de admissão usa apenas casos criados naquela data.
4. Com `metrics_date`, tempos médios usam apenas casos criados naquela data.
5. Data inválida não retorna 500 e volta para o padrão.
6. Template contém label `Data das métricas` e input `name="metrics_date"`.
7. Template deixa claro que "Aguardando por etapa" é atual.
8. Formulário de filtros de casos preserva `metrics_date`.

## Critérios de sucesso

- [ ] Testes foram escritos antes da implementação e falharam inicialmente.
- [ ] Hoje continua sendo o padrão sem query string.
- [ ] `metrics_date=YYYY-MM-DD` muda as métricas diárias esperadas.
- [ ] Filtros da lista continuam independentes.
- [ ] Card de fila atual não é apresentado como histórico.
- [ ] Data inválida não quebra a página.
- [ ] Não foi criada aba histórica separada.
- [ ] Quality gate do `AGENTS.md` passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. Quais métricas são afetadas por `metrics_date`?
2. Quais métricas não são afetadas e por quê?
3. Qual teste prova que ontem exclui casos de hoje?
4. Qual teste prova que data inválida não gera 500?
5. O formulário de filtros da lista preserva `metrics_date`?
6. Houve tentativa de reconstruir histórico por `CaseEvent`? Se sim, está fora
   de escopo.
7. O relatório contém snippets antes/depois dos pontos principais?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-metrics-search-ux/proposal.md, design.md, tasks.md, slices/slice-001-dashboard-ux-polish.md and slices/slice-002-metrics-date-selector.md.
Assume Slice 001 is complete. Implement ONLY Slice 002.
Use TDD: first add failing tests for metrics_date behavior, then implement minimal code.
Follow clean code, DRY and YAGNI. Do not create a historical tab, charts, exports or CaseEvent reconstruction.
Expected files: apps/dashboard/views.py, templates/dashboard/index.html and apps/dashboard/tests/test_dashboard.py.
Use metrics_date=YYYY-MM-DD. Default to timezone.localdate(). Invalid dates must not break the page.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Create a detailed temporary markdown report with before/after snippets and self-evaluation answers.
Run markdownlint-cli2 only on markdown files you create, such as the temporary report. Do not lint or rewrite existing markdown broadly.
Commit and push only implementation files created/changed for this slice. Do not commit OpenSpec files before final archival of the change.
Return REPORT_PATH=<path> and stop. Do not start the next slice without explicit confirmation.
```
