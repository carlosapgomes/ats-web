# Tasks: Endurecer exibição e extração de exames rastreados

## Slices verticais

- [x] Slice 001 — Presenter: filtrar ausência de exame e mostrar data em todos os exames válidos (`slices/slice-001-presenter-tracked-exam-hardening.md`)
- [x] Slice 002 — Prompt LLM1: não rastrear “Sem Exame” e datar todos os exames rastreados (`slices/slice-002-llm1-tracked-exam-hardening.md`)

## Definition of Done do change

- [x] Relatório médico não exibe “Sem exame”/“não realizado” como exame rastreado recente.
- [x] Exame válido com data mostra data mesmo quando `is_most_recent=false`.
- [x] Exame válido mais recente mostra data e destaque de mais recente.
- [x] Data inválida ou ausente não quebra o presenter.
- [x] Prompt renderizado do LLM1 orienta a não incluir ausência de exame em `tracked_exams`.
- [x] `LLM1_DEFAULT_USER_PROMPT` contém a regra para deploy greenfield.
- [x] Seed default de `llm1_user` permanece alinhado ao default atualizado.
- [x] Schema LLM1/LLM2 permanece inalterado.
- [x] LLM2 permanece inalterado.
- [x] Testes relevantes adicionados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatórios dos slices gerados em markdown temporário.
- [x] Commit e push realizados após cada slice implementado.
