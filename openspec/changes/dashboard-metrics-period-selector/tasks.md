<!-- markdownlint-disable MD013 -->

# Tasks: Seletor de período para métricas do dashboard

## Slice vertical

- [x] Slice 001 — Trocar data única por período (`Hoje`, `7 dias`, `30 dias`, `Tudo`) e ajustar cálculo de tempos médios (`slices/slice-001-metrics-period-selector.md`)

## Definition of Done do change

- [x] `metrics_period=today|7d|30d|all` aceito pela view.
- [x] Valor ausente/ inválido cai para `today` sem erro.
- [x] Template mostra opções `Hoje`, `7 dias`, `30 dias`, `Tudo`.
- [x] Cards principais usam casos criados no período selecionado.
- [x] `Tempo Médio` filtra por conclusão da etapa no período.
- [x] `Ciclo Total` usa `cleanup_completed_at` com fallback para evento `CLEANUP_COMPLETED`.
- [x] Card `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`.
- [x] Filtros da lista preservam `metrics_period`.
- [x] Link `Atenção necessária` preserva `metrics_period`.
- [x] Busca dinâmica/fallback SSR preserva `metrics_period`.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário.
- [x] Commit e push realizados após implementação.

## Revisão pós-implementação

Correções aplicadas após verificação do slice:

- Comentário de `static/js/dashboard_search.js` atualizado de `metrics_date` para `metrics_period`.
- Testes de médias fortalecidos para validar valores exatos (`122 h`, `28 h`) em vez de apenas `!= "—"`.
- Uso incorreto de `created_at` em `Case.objects.create(...)` removido dos testes fortalecidos; timestamps agora são ajustados via `update()` helper.
- Helper de teste não utilizado removido.
