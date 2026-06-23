# Tasks: Corrigir apresentação de agendamento cancelado após intercorrência

## Slices verticais

- [x] Slice 001 — Corrigir card e detalhe gerencial para `appointment_status="cancelled"` (`slices/slice-001-dashboard-detail-presentation.md`)

## Definition of Done do change

- [x] Card gerencial mostra “Agendamento cancelado após intercorrência” para `appointment_status="cancelled"`.
- [x] Card gerencial não mostra “Aguardando Agendamento” para esse cenário.
- [x] Detalhe gerencial mostra resultado final de cancelamento para `appointment_status="cancelled"`.
- [x] Detalhe gerencial não mostra “Agendamento Confirmado” para esse cenário.
- [x] Casos `appointment_status="confirmed"` continuam mostrando “Agendamento Confirmado”.
- [x] Sem alterações em FSM, serviços de intercorrência, banco ou migrations.
- [x] TDD executado: RED → GREEN → REFACTOR.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório temporário em markdown criado para revisão por terceiro LLM.
- [x] Commit e push realizados.
