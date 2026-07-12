<!-- markdownlint-disable MD013 -->

# Tasks: Data e intervalo personalizados para métricas do dashboard

## Dimensionamento dos slices

Este change deve ser implementado em **1 slice vertical e enxuto**.

Justificativa:

- Escopo localizado no dashboard.
- Sem migration, model, FSM, permissão ou workflow operacional.
- O valor só fica completo quando backend, UI, preservação de query string e testes chegam juntos.
- Dividir por camada seria horizontal; dividir data específica e intervalo faria retrabalho nos mesmos arquivos.

## Slice vertical

- [ ] Slice 001 — Adicionar `Personalizado` com data específica e intervalo para métricas (`slices/slice-001-custom-date-range-metrics.md`)

## Definition of Done do change

- [ ] Presets existentes continuam funcionando: `today`, `7d`, `30d`, `all`.
- [ ] `metrics_period=custom_date&metrics_date=YYYY-MM-DD` filtra métricas pela data local específica.
- [ ] `metrics_period=custom_range&metrics_start=YYYY-MM-DD&metrics_end=YYYY-MM-DD` filtra métricas pelo intervalo local inclusivo.
- [ ] Query inválida/missing/invertida retorna 200 e cai para `today` com feedback discreto.
- [ ] UI mostra `Personalizado`, `Data específica` e `Intervalo` sem framework JS.
- [ ] Período ativo aparece com label legível.
- [ ] Cards principais e fluxo de admissão continuam filtrando por `created_at` no período.
- [ ] `Tempo Médio` continua filtrando por timestamp de conclusão de etapa no período.
- [ ] `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`.
- [ ] Filtros da lista preservam `metrics_period`, `metrics_date`, `metrics_start`, `metrics_end`.
- [ ] Link `Atenção necessária` preserva os novos parâmetros.
- [ ] Paginação preserva os novos parâmetros.
- [ ] Busca dinâmica SSR parcial preserva os novos parâmetros.
- [ ] Sem migrations, alterações de models, FSM, permissões, DRF, endpoint JSON, SPA, WebSocket ou SSE.
- [ ] TDD seguido: testes falham antes da implementação e passam depois.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário com snippets antes/depois e evidências RED/GREEN.
- [ ] Commit e push realizados após implementação.
