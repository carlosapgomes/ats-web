<!-- markdownlint-disable MD013 -->

# Tasks: Seletor de período para métricas do dashboard

## Slice vertical

- [ ] Slice 001 — Trocar data única por período (`Hoje`, `7 dias`, `30 dias`, `Tudo`) e ajustar cálculo de tempos médios (`slices/slice-001-metrics-period-selector.md`)

## Definition of Done do change

- [ ] `metrics_period=today|7d|30d|all` aceito pela view.
- [ ] Valor ausente/ inválido cai para `today` sem erro.
- [ ] Template mostra opções `Hoje`, `7 dias`, `30 dias`, `Tudo`.
- [ ] Cards principais usam casos criados no período selecionado.
- [ ] `Tempo Médio` filtra por conclusão da etapa no período.
- [ ] `Ciclo Total` usa `cleanup_completed_at` com fallback para evento `CLEANUP_COMPLETED`.
- [ ] Card `Aguardando por etapa` continua snapshot atual e rotulado `ATUAL`.
- [ ] Filtros da lista preservam `metrics_period`.
- [ ] Link `Atenção necessária` preserva `metrics_period`.
- [ ] Busca dinâmica/fallback SSR preserva `metrics_period`.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário.
- [ ] Commit e push realizados após implementação.
