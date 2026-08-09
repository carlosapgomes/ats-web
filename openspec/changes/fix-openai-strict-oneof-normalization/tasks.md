# Tasks: Normalizar oneOf/discriminator para strict mode da OpenAI

## Slice vertical

- [x] Slice 001 — Reescrever `oneOf`→`anyOf` e remover `discriminator` no normalizador com teste de contrato (`slices/slice-001-oneof-anyof-normalization.md`)

## Definition of Done do change

- [x] `_normalize_openai_strict_schema` converte `oneOf` em `anyOf` em qualquer nível.
- [x] `_normalize_openai_strict_schema` remove `discriminator` em qualquer nível.
- [x] Schema normalizado de `Llm1ResponseV2` não contém `oneOf` nem `discriminator` e mantém a união via `anyOf`.
- [x] Modelos Pydantic e validação local (`model_validate`) permanecem inalterados.
- [x] Nenhuma mudança em orchestrator, serviços, prompts, FSM, templates ou migrations.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário com evidência TDD e respostas aos gates de autoavaliação.
- [x] Commit e push realizados na branch do change.
- [ ] Tag/release candidata publicada com imagem OCI verificada (pós-aprovação do slice).
- [ ] Smoke em produção: 1 caso EDA e 1 colonoscopia chegam a `WAIT_DOCTOR` com `schema_version: "2.0"`.
- [ ] Casos falhos do incidente tratados operacionalmente (encerramento + reapresentação).
