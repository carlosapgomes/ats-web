# Slice 002: Prompt LLM1 — não rastrear “Sem Exame” e datar todos os exames rastreados

## Contexto zero para implementador

O LLM1 extrai dados estruturados e gera `tracked_exams[]` em `apps/pipeline/llm1_service.py`.

O prompt atual já orienta:

- identificar `tracked_exams`;
- usar `exam_datetime_iso` para recência;
- incluir datas no resumo narrativo quando disponíveis.

Foi observado que o LLM pode colocar em `tracked_exams` linhas como:

```text
ECG: Sem Exame
RX: Sem Exame
Ecocardio: Sem Exame
```

Isso é indesejado. Essas linhas são evidência de ausência de exame, não exames realizados/rastreados.

Este slice deve reforçar o prompt LLM1. A proteção determinística do presenter deve ter sido feita no Slice 001.

## Objetivo do slice

Adicionar instrução explícita ao prompt canônico/default e ao prompt renderizado final do LLM1 para:

1. incluir em `tracked_exams` apenas exames efetivamente realizados ou resultados disponíveis;
2. não incluir entradas cujo resultado indique ausência de exame;
3. preencher `exam_datetime_iso` para todo exame rastreado quando houver data/hora associada, não apenas para o mais recente.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/pipeline/llm1_service.py`
2. `apps/pipeline/tests/test_llm1_service.py`
3. `apps/llm/tests/test_seed_prompts.py`

Não é esperado alterar `apps/llm/management/commands/seed_prompts.py`, porque ele já importa `LLM1_DEFAULT_USER_PROMPT` de `apps.pipeline.llm1_service`. Em deploy greenfield com banco zerado, `seed_prompts` criará `llm1_user` usando o default atualizado.

## Requisitos funcionais

### R1. Prompt renderizado deve proibir ausência em `tracked_exams`

A string final gerada por `_render_user_prompt(...)` deve conter instrução semanticamente equivalente a:

```text
Em tracked_exams, inclua apenas exames efetivamente realizados ou resultados disponíveis. Não inclua entradas cujo resultado indique ausência de exame, como "Sem Exame", "não realizado", "não consta", "ausente", "sem laudo" ou equivalentes; use essas menções apenas como evidência de ausência em campos de pré-check quando aplicável.
```

### R2. Prompt renderizado deve pedir data para todos os exames rastreados

A string final gerada por `_render_user_prompt(...)` deve conter instrução semanticamente equivalente a:

```text
Para todo exame incluído em tracked_exams, preencha exam_datetime_iso quando houver data/hora associada no laudo, não apenas para o exame mais recente.
```

### R3. Prompt default deve conter reforço curto

Atualizar `LLM1_DEFAULT_USER_PROMPT` com versão curta das duas regras, porque production greenfield usará banco zerado e `seed_prompts` criará `llm1_user` a partir desse default.

### R4. Não alterar schema

Não adicionar campos novos. Manter `schema_version 1.1` e o contrato atual:

```text
tracked_exams[] = {"exam_type", "exam_label", "result_value", "exam_datetime_iso", "is_most_recent", "source_text_hint"}
```

### R5. Não alterar LLM2

Não tocar `apps/pipeline/llm2_service.py` neste slice.

### R6. Não sobrescrever prompts ativos existentes

Não modificar `seed_prompts` para sobrescrever prompts existentes. O comando deve continuar idempotente.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos em `apps/pipeline/tests/test_llm1_service.py`

1. `test_render_user_prompt_prohibits_absent_exam_entries_in_tracked_exams`
   - chamar `_render_user_prompt(...)`;
   - assertar que o prompt final contém:
     - `tracked_exams`;
     - `Sem Exame` ou `sem exame`;
     - `não realizado` ou `nao realizado`;
     - `não consta` ou `nao consta`;
     - instrução clara para não incluir essas entradas como exames rastreados.

2. `test_render_user_prompt_requires_datetime_for_all_tracked_exams_when_available`
   - chamar `_render_user_prompt(...)`;
   - assertar que o prompt final contém:
     - `exam_datetime_iso`;
     - `todo exame` ou equivalente;
     - `não apenas para o exame mais recente` ou equivalente.

3. `test_default_user_prompt_prohibits_absent_exam_entries_and_requires_all_dates`
   - assertar que `LLM1_DEFAULT_USER_PROMPT` contém versão curta das regras.

### Teste obrigatório em `apps/llm/tests/test_seed_prompts.py`

4. `test_llm1_user_seed_uses_updated_default_prompt_for_tracked_exam_hardening`
   - provar que `DEFAULT_CONTENTS["llm1_user"]` é `LLM1_DEFAULT_USER_PROMPT` ou contém as mesmas regras;
   - assertar presença de `sem exame`/ausência e `exam_datetime_iso`/todos os exames no conteúdo semeado.

Não criar teste complexo de banco para re-seed.

## Restrições estritas

- Não alterar `apps/pipeline/schemas/llm1.py`.
- Não alterar `apps/pipeline/llm2_service.py`.
- Não alterar presenter neste slice.
- Não criar migração.
- Não sobrescrever prompts ativos existentes no banco.
- Não alterar parser JSON, validação Pydantic ou language guard.
- Não trocar schema version.
- Não adicionar campos como `exam_absent` ou `exam_date_display`.

## Critérios de sucesso

- [ ] Testes novos falham antes da alteração e passam após.
- [ ] Prompt renderizado final proíbe ausência de exame em `tracked_exams`.
- [ ] Prompt renderizado final pede `exam_datetime_iso` para todo exame rastreado quando disponível.
- [ ] `LLM1_DEFAULT_USER_PROMPT` contém as regras para deploy greenfield.
- [ ] Seed default de `llm1_user` permanece alinhado ao default atualizado.
- [ ] Schema LLM1 permanece inalterado.
- [ ] LLM2 não foi alterado.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. A instrução de não incluir “Sem Exame” em `tracked_exams` fica no prompt renderizado mesmo se o template ativo no banco for antigo? Onde?
2. O default usado por deploy greenfield foi atualizado? Qual teste prova?
3. O schema LLM1 foi alterado? Se sim, está errado.
4. O LLM2 foi alterado? Se sim, está errado.
5. O comando `seed_prompts` continua sem sobrescrever prompts existentes?
6. Qual teste prova que `exam_datetime_iso` deve ser preenchido para todos os exames rastreados quando houver data?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/harden-tracked-exam-reporting/proposal.md, design.md, tasks.md and slices/slice-002-llm1-tracked-exam-hardening.md.
Implement ONLY Slice 002. Assume Slice 001 is already complete; do not edit presenter code.
Use TDD strictly: first add failing tests proving (1) the final rendered LLM1 user prompt prohibits absent-exam entries such as Sem Exame/Não realizado/Não consta in tracked_exams, (2) the final prompt requires exam_datetime_iso for every tracked exam when a date is available, not only the most recent, (3) LLM1_DEFAULT_USER_PROMPT contains the short rules, and (4) seed default for llm1_user points to the updated LLM1_DEFAULT_USER_PROMPT for greenfield deploy. Then make the minimal prompt change in apps/pipeline/llm1_service.py.
Do not change schemas, LLM2, JSON parser, validation, database, migrations, presenter, templates, FSM, policy, or decision logic.
Do not make seed_prompts overwrite active DB prompts. It may remain unchanged because llm1_user seed content imports LLM1_DEFAULT_USER_PROMPT.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/harden-tracked-exam-reporting/tasks.md marking Slice 002 complete only if all gates pass.
Create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
