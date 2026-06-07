# Tasks: Endurecer exibição e extração de exames rastreados

## Slices verticais

- [x] Slice 001 — Presenter: filtrar ausência de exame e mostrar data em todos os exames válidos (`slices/slice-001-presenter-tracked-exam-hardening.md`)
- [ ] Slice 002 — Prompt LLM1: não rastrear “Sem Exame” e datar todos os exames rastreados (`slices/slice-002-llm1-tracked-exam-hardening.md`)

## Definition of Done do change

- [ ] Relatório médico não exibe “Sem exame”/“não realizado” como exame rastreado recente.
- [ ] Exame válido com data mostra data mesmo quando `is_most_recent=false`.
- [ ] Exame válido mais recente mostra data e destaque de mais recente.
- [ ] Data inválida ou ausente não quebra o presenter.
- [ ] Prompt renderizado do LLM1 orienta a não incluir ausência de exame em `tracked_exams`.
- [ ] `LLM1_DEFAULT_USER_PROMPT` contém a regra para deploy greenfield.
- [ ] Seed default de `llm1_user` permanece alinhado ao default atualizado.
- [ ] Schema LLM1/LLM2 permanece inalterado.
- [ ] LLM2 permanece inalterado.
- [ ] Testes relevantes adicionados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatórios dos slices gerados em markdown temporário.
- [ ] Commit e push realizados após cada slice implementado.
