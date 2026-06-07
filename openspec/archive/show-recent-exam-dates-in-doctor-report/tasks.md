# Tasks: Mostrar datas dos exames recentes no relatório médico

## Slices verticais

- [x] Slice 001 — Correção determinística do presenter médico (`slices/slice-001-presenter-exam-dates.md`)
- [x] Slice 002 — Reforço do prompt canônico LLM1 para resumo com data de exames (`slices/slice-002-llm1-prompt-exam-dates.md`)

## Definition of Done do change

- [x] Presenter médico mostra data de exame recente quando `exam_datetime_iso` está presente.
- [x] Presenter médico preserva fallback claro quando exame recente não tem data.
- [x] Presenter médico não quebra com `exam_datetime_iso` inválido.
- [x] `LLM1_DEFAULT_USER_PROMPT` contém instrução explícita para incluir data no resumo narrativo quando mencionar exames.
- [x] Prompt renderizado do LLM1 contém instrução explícita para incluir data no resumo narrativo quando mencionar exames.
- [x] `seed_prompts` em banco zerado criará `llm1_user` com o default atualizado.
- [x] Não há alteração de schema LLM1/LLM2.
- [x] Não há alteração de lógica de decisão, FSM, filas ou política EDA.
- [x] Testes relevantes adicionados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatórios dos slices gerados em markdown temporário.
- [x] Commit e push realizados após cada slice implementado.
