<!-- markdownlint-disable MD013 -->

# Slice 001: Seletor de período para métricas do dashboard

## Contexto zero para implementador

Projeto Django SSR em `/projects/dev/ats-web`. O dashboard gerencial fica em:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `templates/dashboard/_case_list.html`
- `static/js/dashboard_search.js`
- `apps/dashboard/tests/test_dashboard.py`

O change arquivado `openspec/archive/dashboard-metrics-search-ux/` adicionou:

- `metrics_date=YYYY-MM-DD` para métricas diárias;
- card `Tempo Médio`;
- busca server-side e busca dinâmica SSR parcial;
- preservação de filtros e paginação.

Há também um bugfix recente no cálculo de `Ciclo Total`: `cleanup_completed_at` é preenchido nos casos novos e o dashboard usa fallback para `CaseEvent(event_type="CLEANUP_COMPLETED")` em casos antigos.

## Objetivo do slice

Entregar verticalmente:

```text
Manager/admin abre /dashboard/
→ vê seletor de período das métricas
→ escolhe Hoje, 7 dias, 30 dias ou Tudo
→ cards e tempos médios recalculam
→ filtros/busca/lista continuam preservando o período selecionado
```

## Arquivos esperados

Idealmente tocar apenas:

1. `apps/dashboard/views.py`
2. `templates/dashboard/index.html`
3. `templates/dashboard/_case_list.html` se paginação precisar trocar `metrics_date` por `metrics_period`
4. `static/js/dashboard_search.js` somente se teste mostrar perda do parâmetro
5. `apps/dashboard/tests/test_dashboard.py`

Não tocar models, migrations, FSM, permissões ou outros apps.

## Requisitos funcionais

### R1. Query param de período

Adicionar suporte a:

```text
/dashboard/?metrics_period=today
/dashboard/?metrics_period=7d
/dashboard/?metrics_period=30d
/dashboard/?metrics_period=all
```

Valor ausente ou inválido deve cair para `today` sem erro.

### R2. Bounds locais

Implementar período usando dia local configurado no Django, não `date.today()` nem data UTC.

- `today`: início do dia local atual até início do próximo dia local.
- `7d`: início local de hoje menos 6 dias até início do próximo dia local.
- `30d`: início local de hoje menos 29 dias até início do próximo dia local.
- `all`: sem filtro temporal.

### R3. Cards principais

`_compute_summary()` deve usar casos criados no período (`created_at`). Para `all`, todos os casos.

Manter as regras atuais de contagem por campos imutáveis:

- aceitos: `doctor_decision="accept"` excluindo `appointment_status="denied"` e admin-closed;
- negados: `doctor_decision="deny"` ou `appointment_status="denied"`, excluindo admin-closed;
- encerrados admin: evento `CASE_ADMINISTRATIVELY_CLOSED`;
- em andamento: total - aceitos - negados - admin-closed.

Atualizar label do total:

- `today`: `Total hoje`
- `7d`: `Total 7 dias`
- `30d`: `Total 30 dias`
- `all`: `Total geral`

### R4. Fluxo de admissão

`_compute_admission_flow()` deve usar casos aceitos criados no período (`created_at`). Para `all`, todos os casos aceitos.

### R5. Tempo médio por conclusão de etapa

`_compute_average_times()` deve usar o período sobre o timestamp de conclusão da etapa:

- `Upload → Decisão Médica`: `doctor_decided_at` no período.
- `Decisão → Agendamento`: `appointment_decided_at` no período.
- `Ciclo Total`: `completed_at_for_metrics` no período, onde:
  - primeiro usar `cleanup_completed_at`;
  - se vazio, usar primeiro evento `CLEANUP_COMPLETED` do caso.

Para `all`, não aplicar filtro temporal.

Adicionar texto auxiliar no card: `Etapas concluídas no período`.

### R6. Template e preservação de filtros

Trocar `Data das métricas` por `Período das métricas`.

A UI deve mostrar opções:

- `Hoje`
- `7 dias`
- `30 dias`
- `Tudo`

O período ativo deve ser visualmente identificável.

Preservar `metrics_period` em:

- form de filtros da lista;
- link `Atenção necessária`;
- paginação;
- busca dinâmica/fallback SSR.

Remover dependência visual de `metrics_date`. Não é necessário manter o input de data.

## TDD obrigatório

Antes de implementar, adicionar testes falhando em `apps/dashboard/tests/test_dashboard.py`.

### Testes mínimos

1. `test_metrics_period_default_is_today`
   - cria caso hoje e caso ontem;
   - `_compute_summary(period="today")` ou GET default conta apenas hoje.

2. `test_metrics_period_7d_includes_last_7_local_days`
   - caso criado há 6 dias entra;
   - caso criado há 7 dias completos fica fora.

3. `test_metrics_period_30d_includes_last_30_local_days`
   - caso criado há 29 dias entra;
   - caso criado há 30 dias completos fica fora.

4. `test_metrics_period_all_includes_all_cases`
   - caso antigo entra em `all`.

5. `test_invalid_metrics_period_falls_back_to_today`
   - GET `/dashboard/?metrics_period=invalid` retorna 200 e marca `Hoje` como ativo.

6. `test_average_upload_to_decision_filters_by_doctor_decided_at`
   - caso criado antigo mas decidido hoje entra em `today`;
   - caso criado hoje mas decidido ontem não entra em `today`.

7. `test_average_decision_to_schedule_filters_by_appointment_decided_at`
   - caso agendado hoje entra mesmo se criado/decidido pelo médico antes.

8. `test_average_total_cycle_filters_by_cleanup_completion_timestamp`
   - caso criado antes mas concluído hoje entra em `today`.

9. `test_total_cycle_period_uses_cleanup_completed_event_fallback`
   - caso histórico sem `cleanup_completed_at`, com evento `CLEANUP_COMPLETED` no período, entra no cálculo.

10. `test_template_has_metrics_period_selector`
    - GET `/dashboard/` contém `Período das métricas`, `Hoje`, `7 dias`, `30 dias`, `Tudo`.

11. `test_case_filter_form_preserves_metrics_period`
    - GET `/dashboard/?metrics_period=30d` contém hidden `name="metrics_period" value="30d"` no form da lista.

12. `test_attention_link_preserves_metrics_period`
    - GET `/dashboard/?metrics_period=7d&search=ana` mantém ambos no link de atenção.

13. `test_partial_pagination_preserves_metrics_period`
    - com casos suficientes para paginação e `metrics_period=all`, links de página preservam o parâmetro.

## Critérios de sucesso

- [ ] TDD seguido: testes novos falham antes da implementação e passam após.
- [ ] `metrics_period` normaliza valores inválidos para `today`.
- [ ] UI mostra os 4 períodos e destaca o ativo.
- [ ] Cards principais usam `created_at` no período.
- [ ] Tempos médios usam timestamps de conclusão da etapa no período.
- [ ] `Ciclo Total` preserva fallback via evento para casos históricos.
- [ ] Filtros, link de atenção, paginação e busca dinâmica preservam `metrics_period`.
- [ ] Nenhuma migration criada.
- [ ] Sem alteração de permissões, FSM ou filas operacionais.
- [ ] Quality gate passa.

## Gates de autoavaliação

Antes de finalizar, responder no relatório:

1. O período usa dia local (`timezone.localdate()` / timezone configurado) ou UTC/data do sistema?
2. `Tempo Médio` filtra por conclusão da etapa, não por `created_at`? Quais testes provam?
3. `Ciclo Total` ainda cobre casos antigos sem `cleanup_completed_at`? Qual teste prova?
4. `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`?
5. `metrics_period` é preservado em filtros, atenção, paginação e busca dinâmica?
6. Alguma migration/model/FSM/permissão foi alterada? Não deveria.

## Comandos de validação

Executar pelo menos:

```bash
uv run pytest apps/dashboard/tests/test_dashboard.py -q
uv run ruff check apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py
uv run ruff format --check apps/dashboard/views.py apps/dashboard/tests/test_dashboard.py
uv run mypy apps/dashboard
```

Antes de finalizar o slice, executar o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório esperado

Criar relatório temporário em:

```text
/tmp/ats-web-slice-001-dashboard-metrics-period-selector-report.md
```

O relatório deve conter:

- resumo do problema;
- snippets antes/depois dos helpers principais;
- evidência dos testes RED/GREEN;
- comandos de validação e resultados;
- respostas aos gates de autoavaliação.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/dashboard-metrics-period-selector/proposal.md, design.md, tasks.md and slices/slice-001-metrics-period-selector.md.
Implement ONLY Slice 001.
Use vertical slicing and TDD: first add failing tests in apps/dashboard/tests/test_dashboard.py, then implement the minimum changes in apps/dashboard/views.py and templates/dashboard/index.html (plus _case_list.html/static/js only if required to preserve metrics_period).
Replace the metrics_date UI with metrics_period=today|7d|30d|all. Summary/admission_flow use created_at period bounds; average times use completion timestamps: doctor_decided_at, appointment_decided_at and cleanup_completed_at/event fallback. Keep Aguardando por etapa as current snapshot. Do not touch models, migrations, FSM, queues or permissions.
Run validations, create /tmp/ats-web-slice-001-dashboard-metrics-period-selector-report.md, commit and push, then reply REPORT_PATH and stop.
```
