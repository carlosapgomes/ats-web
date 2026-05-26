# Slice 001 — Prompts Canônicos Legados

## Handoff para Implementador LLM

Você está no projeto Django `ats-web`, uma reimplementação web do legado Matrix `augmented-triage-system`.

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`
4. `openspec/changes/align-llm-contract-and-doctor-routing/proposal.md`
5. `openspec/changes/align-llm-contract-and-doctor-routing/design.md`
6. Este arquivo.

Implemente somente este slice.

## Problema

A pipeline atual busca prompts com nomes errados:

- `llm1_system_prompt`
- `llm1_user_prompt`
- `llm2_system_prompt`
- `llm2_user_prompt`

O legado e o admin UI usam nomes canônicos:

- `llm1_system`
- `llm1_user`
- `llm2_system`
- `llm2_user`

Além disso, os prompts seedados atualmente falam em “relatório de endoscopia”, mas o fluxo correto analisa relatório/encaminhamento clínico de regulação solicitando EDA.

## Objetivo

Alinhar nomes e defaults de prompts ao legado, sem ainda portar validação Pydantic completa.

## Escopo

Alterar apenas o necessário, idealmente:

- `apps/llm/management/commands/seed_prompts.py`
- `apps/pipeline/orchestrator.py`
- testes relacionados em `apps/llm/tests/` e `apps/pipeline/tests/`

Não alterar serviços LLM neste slice, exceto se indispensável para usar os nomes corretos.

## Fonte Legada

Use como referência:

- `/home/carlos/projects/augmented-triage-system/alembic/versions/0005_prompt_templates_ptbr_v3.py`
- `/home/carlos/projects/augmented-triage-system/alembic/versions/0016_prompt_templates_llm1_ptbr_v5.py`
- `/home/carlos/projects/augmented-triage-system/alembic/versions/0018_prompt_templates_llm1_ptbr_v6.py`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm1_service.py`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm2_service.py`

## Requisitos Funcionais

1. `seed_prompts` deve criar exatamente os nomes:
   - `llm1_system`
   - `llm1_user`
   - `llm2_system`
   - `llm2_user`
2. O conteúdo default deve ser baseado nos defaults legados mais recentes.
3. O orchestrator deve buscar os nomes canônicos sem `_prompt`.
4. Se o banco não tiver prompt ativo, fallback de código deve ser compatível com o legado e não com o prompt antigo de “relatório de endoscopia”.
5. O admin UI não deve precisar mudar os nomes, pois já usa os nomes canônicos.

## TDD — Testes RED Esperados

Antes de implementar, adicione/ajuste testes que falhem mostrando:

1. `seed_prompts` cria `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`.
2. `seed_prompts` não cria nomes com `_prompt`.
3. `run_pipeline`/prompt resolver busca `llm1_system` e `llm1_user` quando prompts existem no banco.
4. Fallback não contém “relatório de endoscopia”.

## Critérios de Sucesso

- Prompts com nomes legados são usados pela pipeline.
- Não há novos prompts com sufixo `_prompt` no seed.
- Testes focados passam.
- Nenhuma mudança de fluxo FSM neste slice.

## Comandos de Validação Focados

```bash
uv run pytest apps/llm/tests apps/pipeline/tests/test_orchestrator.py -q
uv run ruff check apps/llm apps/pipeline
uv run mypy apps/llm apps/pipeline
```

Se algum comando amplo falhar por causa pré-existente, registre no relatório.

## Relatório Obrigatório

Crie relatório markdown temporário com:

- resumo do que mudou;
- snippets antes/depois dos nomes de prompts;
- testes executados e resultados;
- riscos ou pendências.

Caminho sugerido:

```text
/tmp/ats-web-slice-001-canonical-prompts-report.md
```

Ao finalizar, responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-001-canonical-prompts-report.md
```

## Stop Rule

Pare após este slice. Não implemente Pydantic, scope gate, presenter médico ou role guard neste slice.
