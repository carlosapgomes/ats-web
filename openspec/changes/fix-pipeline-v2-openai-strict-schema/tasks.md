# Tasks: Corrigir vínculo do strict json_schema aos contratos V2

## Slice vertical

- [ ] Slice 001 — Vincular factories OpenAI aos schemas V2 com teste de contrato (`slices/slice-001-bind-v2-strict-schemas.md`)

## Definition of Done do change

- [ ] `create_openai_llm1_client()` vincula strict schema de `Llm1ResponseV2` (`schema_version` fixo `"2.0"`).
- [ ] `create_openai_llm2_client()` vincula strict schema de `Llm2ResponseV2` (`schema_version` fixo `"2.0"`).
- [ ] Testes de contrato falham contra vínculo 1.1 (evidência RED registrada).
- [ ] Normalização strict validada para os dois schemas V2.
- [ ] Nenhum call site de produção cria cliente OpenAI com schema 1.1.
- [ ] Nenhuma mudança em orchestrator, serviços, prompts, FSM, templates ou migrations.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário com evidência TDD e respostas aos gates de autoavaliação.
- [ ] Commit e push realizados na branch do change.
- [ ] Tag/release candidata publicada com imagem OCI verificada (pós-aprovação do slice).
- [ ] Smoke em produção: 1 caso EDA e 1 colonoscopia chegam a `WAIT_DOCTOR` com `schema_version: "2.0"`.
- [ ] Casos falhos do incidente tratados operacionalmente (encerramento + reapresentação).
