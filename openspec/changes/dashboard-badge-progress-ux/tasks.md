<!-- markdownlint-disable MD013 -->

# Tasks: Badges compactos e próximo passo no dashboard

## Slices verticais

- [x] Slice 001 — Cards do dashboard: badge compacto + próximo passo
  (`slices/slice-001-dashboard-card-badges-next-step.md`)
- [x] Slice 002 — Detalhe do caso: Resultado Final mobile sem overflow
  (`slices/slice-002-result-final-badge-mobile.md`)

## Definition of Done do change

- [ ] Badge longo de `ward_icu_backup` não sobrepõe data/hora nos cards mobile do dashboard.
- [ ] Cards do dashboard usam label compacto apenas em badges, sem alterar opções completas do médico.
- [ ] Cards do dashboard mostram sub-badge/indicador de próximo passo operacional pendente.
- [ ] Próximo passo é derivado do status atual sem novo campo/migration.
- [ ] Card `Resultado Final` no detalhe não transborda o badge no mobile.
- [ ] Texto completo/explicativo do fluxo permanece disponível fora do badge quando aplicável.
- [ ] Sem alteração de FSM, models, migrations, permissões, filtros ou queries.
- [ ] Testes relevantes passam.
- [ ] Quality gate executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório markdown temporário criado por slice e `REPORT_PATH` informado.
- [ ] Commit e push realizados por slice somente após todos os gates.

## Observação para implementadores

Implementar um slice por vez. Não iniciar o próximo slice sem confirmação explícita do planner/usuário. Se qualquer gate falhar, não marcar a task como concluída e não fazer commit/push.
