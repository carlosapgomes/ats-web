# Tasks: Fluxos de aceite médico com ciência operacional do CHD

## Slice vertical

- [x] Slice 001 — Implementar novos fluxos de admissão sem agendamento, ciência operacional CHD, resultado NIR e métricas separadas (`slices/slice-001-operational-admission-flows.md`)

## Definition of Done do change

- [x] Campo médico `Suporte Necessário` mostra apenas `Nenhum` e `Anestesista`.
- [x] Backend rejeita novo POST com `support_flag=anesthesist_icu`.
- [x] Casos históricos com `anesthesist_icu` continuam exibindo label legada.
- [x] Campo médico `Fluxo de Admissão` mostra os cinco fluxos definidos.
- [x] `accept + scheduled` continua abrindo `WAIT_APPT` para CHD.
- [x] `accept + immediate/pre_icu/ward_icu_backup/pediatric_em` não abre agendamento e vai para resultado NIR.
- [x] CHD vê ciência operacional para todos os fluxos sem agendamento.
- [x] Cada fluxo sem agendamento mostra mensagem específica ao CHD.
- [x] CHD confirma ciência com o mesmo botão para todos os fluxos sem agendamento.
- [x] Histórico CHD de ciências operacionais mostra quem confirmou e quando.
- [x] NIR vê mensagem final específica por fluxo sem agendamento.
- [x] Dashboard mostra os cinco fluxos de admissão separados.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Specs/docs atualizadas quando necessário.
- [x] Relatório do slice gerado em markdown temporário.
- [x] Commit e push realizados após implementação.
