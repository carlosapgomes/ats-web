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

- [x] Slice 001 — Adicionar `Personalizado` com data específica e intervalo para métricas (`slices/slice-001-custom-date-range-metrics.md`)
  - **Correção pós-revisão** (commit `fix(dashboard)`): UI original quebrada
    (onclick referenciava `input[name=metrics_period]` inexistente no form →
    sempre caía para `today`) foi reescrita como dois mini-forms SSR puros
    (design D7). Adicionados 2 testes obrigatórios ausentes (range por
    conclusão de etapa + fallback `CLEANUP_COMPLETED`), fortalecidos 2 testes
    fracos (asserção sobre `summary.total_today`), adicionado teste estrutural
    de UI + 4 testes de layout reajustados ao novo `id=case-filter-form`.

## Definition of Done do change

- [x] Presets existentes continuam funcionando: `today`, `7d`, `30d`, `all`.
- [x] `metrics_period=custom_date&metrics_date=YYYY-MM-DD` filtra métricas pela data local específica.
- [x] `metrics_period=custom_range&metrics_start=YYYY-MM-DD&metrics_end=YYYY-MM-DD` filtra métricas pelo intervalo local inclusivo.
- [x] Query inválida/missing/invertida retorna 200 e cai para `today` com feedback discreto.
- [x] UI mostra `Personalizado`, `Data específica` e `Intervalo` sem framework JS.
- [x] Período ativo aparece com label legível.
- [x] Cards principais e fluxo de admissão continuam filtrando por `created_at` no período.
- [x] `Tempo Médio` continua filtrando por timestamp de conclusão de etapa no período.
- [x] `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`.
- [x] Filtros da lista preservam `metrics_period`, `metrics_date`, `metrics_start`, `metrics_end`.
- [x] Link `Atenção necessária` preserva os novos parâmetros.
- [x] Paginação preserva os novos parâmetros.
- [x] Busca dinâmica SSR parcial preserva os novos parâmetros.
- [x] Sem migrations, alterações de models, FSM, permissões, DRF, endpoint JSON, SPA, WebSocket ou SSE.
- [x] TDD seguido: testes falham antes da implementação e passam depois.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário com snippets antes/depois e evidências RED/GREEN.
- [x] Commit e push realizados após implementação.
