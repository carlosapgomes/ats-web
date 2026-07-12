<!-- markdownlint-disable MD013 -->

# Tasks: Badges compactos e próximo passo no dashboard

## Slices verticais

- [x] Slice 001 — Cards do dashboard: badge compacto + próximo passo
  (`slices/slice-001-dashboard-card-badges-next-step.md`)
- [x] Slice 002 — Detalhe do caso: Resultado Final mobile sem overflow
  (`slices/slice-002-result-final-badge-mobile.md`)

## Definition of Done do change

- [x] Badge longo de `ward_icu_backup` não sobrepõe data/hora nos cards mobile do dashboard. (Slice 001)
- [x] Cards do dashboard usam label compacto apenas em badges, sem alterar opções completas do médico. (Slice 001)
- [x] Cards do dashboard mostram sub-badge/indicador de próximo passo operacional pendente. (Slice 001)
- [x] Próximo passo é derivado do status atual sem novo campo/migration. (Slice 001)
- [x] Card `Resultado Final` no detalhe não transborda o badge no mobile. (Slice 002)
- [x] Texto completo/explicativo do fluxo permanece disponível fora do badge quando aplicável. (Slice 002)
- [x] Sem alteração de FSM, models, migrations, permissões, filtros ou queries.
- [x] Testes relevantes passam.
- [x] Quality gate executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado por slice e `REPORT_PATH` informado.
- [x] Commit e push realizados por slice somente após todos os gates.

## Observação para implementadores

Implementar um slice por vez. Não iniciar o próximo slice sem confirmação explícita do planner/usuário. Se qualquer gate falhar, não marcar a task como concluída e não fazer commit/push.
