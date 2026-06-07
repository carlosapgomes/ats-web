# Tasks: Encerramento administrativo e filtro de atenção

## Slices verticais

- [x] Slice 001 — Encerramento administrativo auditável no detalhe do dashboard (`slices/slice-001-administrative-closure.md`)
- [ ] Slice 002 — Filtro `Atenção necessária` na listagem inicial do dashboard (`slices/slice-002-attention-filter.md`)

## Definition of Done do change

- [ ] Supervisor/admin conseguem encerrar administrativamente caso não `CLEANED` pelo detalhe do dashboard.
- [ ] Ação exige motivo/justificativa obrigatória.
- [ ] Encerramento administrativo move o caso para `CLEANED`.
- [ ] Caso encerrado administrativamente sai das filas operacionais de NIR, médico e agendador.
- [ ] Lock operacional é limpo quando o caso é encerrado administrativamente.
- [ ] Evento `CASE_ADMINISTRATIVELY_CLOSED` é criado com payload auditável.
- [ ] Timeline mostra label compreensível para o novo evento.
- [ ] Usuários sem papel ativo `manager`/`admin` não conseguem acionar a rota POST.
- [ ] Dashboard tem filtro/preset `Atenção necessária`.
- [ ] Filtro inclui casos `FAILED`, estados intermediários antigos, waits antigos e locks expirados.
- [ ] Filtro exclui `CLEANED`.
- [ ] Cards filtrados exibem motivo compacto da atenção.
- [ ] Testes relevantes adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório de cada slice gerado em markdown temporário.
- [ ] Commit e push realizados após cada slice.
