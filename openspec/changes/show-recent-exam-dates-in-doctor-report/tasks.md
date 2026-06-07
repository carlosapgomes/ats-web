# Tasks: Mostrar datas dos exames recentes no relatório médico

## Slices verticais

- [x] Slice 001 — Correção determinística do presenter médico (`slices/slice-001-presenter-exam-dates.md`)
- [ ] Slice 002 — Reforço do prompt canônico LLM1 para resumo com data de exames (`slices/slice-002-llm1-prompt-exam-dates.md`)

## Definition of Done do change

- [ ] Presenter médico mostra data de exame recente quando `exam_datetime_iso` está presente.
- [ ] Presenter médico preserva fallback claro quando exame recente não tem data.
- [ ] Presenter médico não quebra com `exam_datetime_iso` inválido.
- [ ] `LLM1_DEFAULT_USER_PROMPT` contém instrução explícita para incluir data no resumo narrativo quando mencionar exames.
- [ ] Prompt renderizado do LLM1 contém instrução explícita para incluir data no resumo narrativo quando mencionar exames.
- [ ] `seed_prompts` em banco zerado criará `llm1_user` com o default atualizado.
- [ ] Não há alteração de schema LLM1/LLM2.
- [ ] Não há alteração de lógica de decisão, FSM, filas ou política EDA.
- [ ] Testes relevantes adicionados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatórios dos slices gerados em markdown temporário.
- [ ] Commit e push realizados após cada slice implementado.
