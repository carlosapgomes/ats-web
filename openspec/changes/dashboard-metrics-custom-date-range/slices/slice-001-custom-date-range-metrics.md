<!-- markdownlint-disable MD013 -->

# Slice 001: Data e intervalo personalizados para métricas do dashboard

## Contexto zero para implementador

Projeto Django SSR em `/projects/dev/ats-web`.

Leia primeiro:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/dashboard-metrics-custom-date-range/proposal.md`
4. `openspec/changes/dashboard-metrics-custom-date-range/design.md`
5. `openspec/changes/dashboard-metrics-custom-date-range/tasks.md`
6. este arquivo de slice

O dashboard gerencial fica principalmente em:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `templates/dashboard/_case_list.html`
- `static/js/dashboard_search.js`
- `apps/dashboard/tests/test_dashboard.py`

Estado funcional esperado antes deste slice:

- `Período das métricas` já possui presets `Hoje`, `7 dias`, `30 dias`, `Tudo` via `metrics_period=today|7d|30d|all`.
- Cards principais e fluxo de admissão usam `created_at` dentro do período.
- `Tempo Médio` usa timestamp de conclusão da etapa dentro do período.
- `Aguardando por etapa` é snapshot atual e deve continuar assim.
- Busca dinâmica do dashboard é SSR parcial via header `X-ATS-Partial: case-list`, sem API JSON/DRF/SPA.

## Objetivo do slice

Entregar verticalmente:

```text
Manager/admin abre /dashboard/
→ vê presets atuais de período das métricas
→ pode abrir/usar a opção Personalizado
→ aplica uma data específica OU um intervalo de datas
→ cards/fluxo/tempos médios recalculam pelo período escolhido
→ filtros, atenção, paginação e busca dinâmica continuam preservando esse período
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html`
4. `static/js/dashboard_search.js`
5. `apps/dashboard/tests/test_dashboard.py`

Não tocar models, migrations, FSM, permissões, filas, settings ou outros apps.

Se precisar ampliar o escopo, registre a justificativa no relatório antes de codar além desses arquivos.

## Requisitos funcionais

### R1. Presets sem regressão

Continuar aceitando:

```text
/dashboard/?metrics_period=today
/dashboard/?metrics_period=7d
/dashboard/?metrics_period=30d
/dashboard/?metrics_period=all
```

Valor ausente deve continuar usando `today`.

### R2. Data específica personalizada

Aceitar:

```text
/dashboard/?metrics_period=custom_date&metrics_date=2026-07-12
```

Semântica:

- usar dia local completo de `metrics_date`;
- start inclusivo: início local de `2026-07-12`;
- end exclusivo: início local de `2026-07-13`.

### R3. Intervalo personalizado inclusivo

Aceitar:

```text
/dashboard/?metrics_period=custom_range&metrics_start=2026-07-01&metrics_end=2026-07-12
```

Semântica:

- `metrics_start` e `metrics_end` são inclusivos para o usuário;
- internamente usar start inclusivo no início local de `metrics_start`;
- internamente usar end exclusivo no início local do dia seguinte a `metrics_end`.

### R4. Fallback seguro

Estas queries devem retornar HTTP 200 e cair para `today`:

```text
?metrics_period=invalid
?metrics_period=custom_date
?metrics_period=custom_date&metrics_date=abc
?metrics_period=custom_range
?metrics_period=custom_range&metrics_start=2026-07-01
?metrics_period=custom_range&metrics_start=2026-07-12&metrics_end=2026-07-01
```

Exibir feedback discreto quando o usuário tentou um personalizado inválido, por exemplo:

```text
Período personalizado inválido. Exibindo métricas de hoje.
```

Não usar exception, redirect obrigatório ou erro 400.

### R5. Métricas preservam a semântica atual

A mudança só altera bounds temporais.

- `_compute_summary(...)`: filtrar casos por `created_at` no período.
- `_compute_admission_flow(...)`: filtrar casos aceitos por `created_at` no período.
- `_compute_average_times(...)`:
  - `Upload → Decisão Médica`: filtrar por `doctor_decided_at` no período;
  - `Decisão → Agendamento`: filtrar por `appointment_decided_at` no período;
  - `Ciclo Total`: filtrar por `cleanup_completed_at` com fallback para evento `CLEANUP_COMPLETED` no período.
- `_compute_stage_waiting()`: não aplicar período; continuar snapshot atual.

### R6. UI/UX SSR

Manter os presets visíveis como ação rápida.

Adicionar opção `Personalizado` contendo dois fluxos simples:

1. `Data específica`
   - input `type="date"` para `metrics_date`;
   - hidden `metrics_period=custom_date`;
   - botão `Aplicar`.
2. `Intervalo`
   - inputs `type="date"` para `metrics_start` e `metrics_end`;
   - hidden `metrics_period=custom_range`;
   - botão `Aplicar`.

Preferência de UI:

- usar `<details>` nativo ou seção compacta Bootstrap;
- abrir/realçar a área quando o período ativo for customizado ou houver erro;
- não depender de React/Vue/HTMX/SPA;
- JavaScript customizado só se necessário para preservar query params na busca dinâmica.

Exibir label legível do período ativo, por exemplo:

- `Métricas de hoje`
- `Métricas dos últimos 7 dias`
- `Métricas de 12/07/2026`
- `Métricas de 01/07/2026 a 12/07/2026`

### R7. Preservação de query string

Preservar `metrics_period`, `metrics_date`, `metrics_start`, `metrics_end` em:

- form de filtros da lista;
- link `Atenção necessária`;
- paginação de `_case_list.html`;
- busca dinâmica em `static/js/dashboard_search.js`;
- fallback SSR de submit tradicional.

Ao clicar em preset (`today`, `7d`, `30d`, `all`), não carregar valores antigos de `metrics_date`, `metrics_start`, `metrics_end`.

## TDD obrigatório

Siga RED → GREEN → REFACTOR.

Antes de implementar, adicione testes falhando em `apps/dashboard/tests/test_dashboard.py`. Rode um subconjunto para confirmar RED. Depois implemente o mínimo para passar. Por fim, refatore com cuidado.

### Testes mínimos

1. `test_metrics_custom_date_counts_cases_created_on_selected_local_day`
   - cria caso na data selecionada e caso fora dela;
   - GET com `metrics_period=custom_date&metrics_date=YYYY-MM-DD` conta apenas o dia selecionado.

2. `test_metrics_custom_range_counts_cases_created_in_inclusive_range`
   - cria caso no início, no fim e fora do intervalo;
   - GET com `custom_range` inclui início/fim e exclui fora.

3. `test_metrics_custom_date_average_filters_by_stage_completion_date`
   - caso criado antes mas decidido na data selecionada entra em `Upload → Decisão Médica`;
   - caso criado na data mas decidido fora não entra.

4. `test_metrics_custom_range_average_filters_by_stage_completion_range`
   - pelo menos uma média usa timestamp de conclusão dentro do intervalo;
   - provar que não é `created_at` que está filtrando a média.

5. `test_metrics_custom_range_total_cycle_uses_cleanup_event_fallback`
   - caso histórico sem `cleanup_completed_at`, com evento `CLEANUP_COMPLETED` dentro do intervalo, entra no cálculo.

6. `test_invalid_custom_date_falls_back_to_today_with_feedback`
   - GET com data inválida retorna 200;
   - `Hoje` fica ativo ou label indica hoje;
   - feedback discreto aparece.

7. `test_invalid_custom_range_falls_back_to_today_with_feedback`
   - intervalo invertido retorna 200 e cai para hoje.

8. `test_template_renders_custom_metrics_controls`
   - resposta contém `Personalizado`, `Data específica`, `Intervalo`, `metrics_date`, `metrics_start`, `metrics_end`.

9. `test_metrics_custom_params_preserved_in_case_filter_form`
   - GET customizado contém hidden inputs para `metrics_period` e campos customizados no form da lista.

10. `test_attention_link_preserves_custom_metrics_params`
    - link de atenção mantém `metrics_period=custom_range`, `metrics_start`, `metrics_end` e `search` quando presentes.

11. `test_partial_pagination_preserves_custom_metrics_params`
    - com paginação, links preservam os campos customizados.

12. `test_dashboard_search_js_preserves_custom_metrics_params`
    - validar que `dashboard_search.js` lê e envia `metrics_date`, `metrics_start`, `metrics_end` junto de `metrics_period`.
    - Pode ser teste simples de conteúdo do arquivo se o projeto não tiver teste JS dedicado.

## Critérios de sucesso

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] Data específica personalizada funciona via URL e UI.
- [ ] Intervalo personalizado inclusivo funciona via URL e UI.
- [ ] Fallback para `today` é seguro e testado.
- [ ] Label do período ativo é claro.
- [ ] Presets atuais não regrediram.
- [ ] Cards principais/fluxo usam `created_at` no período.
- [ ] Tempos médios usam conclusão da etapa no período.
- [ ] `Ciclo Total` mantém fallback via evento `CLEANUP_COMPLETED`.
- [ ] `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`.
- [ ] Query params customizados são preservados em filtros, atenção, paginação e busca dinâmica.
- [ ] Nenhuma migration/model/FSM/permissão/API nova foi criada.
- [ ] Código permanece limpo, coeso, DRY e sem abstrações YAGNI.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responda no relatório final:

1. O período customizado usa datas locais (`local_day_bounds`/timezone do Django) ou UTC/data do sistema?
2. O intervalo é inclusivo para o usuário e exclusivo no bound final interno? Qual teste prova?
3. `Tempo Médio` continua filtrando por conclusão da etapa, não por `created_at`? Quais testes provam?
4. O fallback de `Ciclo Total` via evento `CLEANUP_COMPLETED` continuou funcionando? Qual teste prova?
5. `Aguardando por etapa` permaneceu snapshot atual e com badge `ATUAL`?
6. Onde `metrics_date`, `metrics_start` e `metrics_end` são preservados?
7. Algum model, migration, FSM, permissão, API ou endpoint novo foi alterado/criado? Não deveria.
8. O código ficou mais duplicado ou foi reduzido com helpers locais? Explique a decisão.

## Comandos de validação

Executar durante o slice:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -q
uv run ruff check apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py static/js/dashboard_search.js
uv run ruff format --check apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py
uv run mypy apps/dashboard
```

Antes de finalizar, executar o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório esperado

Criar relatório temporário em:

```text
/tmp/ats-web-slice-001-dashboard-metrics-custom-date-range-report.md
```

O relatório deve conter:

- resumo do problema e da solução;
- lista de arquivos alterados;
- snippets antes/depois dos helpers principais e da UI;
- evidência RED/GREEN dos testes;
- comandos de validação executados e resultados;
- respostas completas aos gates de autoavaliação;
- observações de rollback, se necessário.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-metrics-custom-date-range/proposal.md, design.md, tasks.md and slices/slice-001-custom-date-range-metrics.md.
Implement ONLY Slice 001.
Use vertical slicing and TDD: first add failing tests in apps/dashboard/tests/test_dashboard.py, run them to confirm RED, then implement the minimum changes. Keep code clean, DRY, cohesive and avoid YAGNI abstractions.
Add custom metrics periods to the dashboard: metrics_period=custom_date&metrics_date=YYYY-MM-DD and metrics_period=custom_range&metrics_start=YYYY-MM-DD&metrics_end=YYYY-MM-DD. Keep existing presets today|7d|30d|all. Use local-day bounds. Summary/admission_flow keep using created_at period bounds; average times keep using completion timestamps (doctor_decided_at, appointment_decided_at, cleanup_completed_at/event fallback). Keep Aguardando por etapa as current snapshot.
Update templates so the UI shows Personalizado with Data específica and Intervalo, preserves query params in filters/attention/pagination, and update dashboard_search.js to preserve metrics_date/metrics_start/metrics_end in SSR partial search. Do not touch models, migrations, FSM, queues, permissions, DRF/API, SPA, WebSocket or SSE.
Run validations, create /tmp/ats-web-slice-001-dashboard-metrics-custom-date-range-report.md with snippets and RED/GREEN evidence, commit and push, then reply REPORT_PATH and stop.
```
