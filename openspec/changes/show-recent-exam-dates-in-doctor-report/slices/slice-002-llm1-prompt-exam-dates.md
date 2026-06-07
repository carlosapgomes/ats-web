# Slice 002: Reforço do prompt LLM1 para resumo narrativo com data dos exames

## Contexto zero para implementador

O LLM1 é responsável por extrair dados estruturados e gerar `summary.one_liner` e `summary.bullet_points`.

Arquivos relevantes:

- `apps/pipeline/llm1_service.py`
- `apps/pipeline/tests/test_llm1_service.py`
- `apps/llm/management/commands/seed_prompts.py`

O prompt atual já exige `tracked_exams[]` com `exam_datetime_iso` e já orienta usar data/hora para determinar recência. Porém, ele não explicita que o resumo narrativo deve incluir a data quando mencionar exames recentes.

Este slice deve reforçar o prompt. A correção determinística do presenter já deve ter sido feita no Slice 001.

## Objetivo do slice

Adicionar instrução explícita no prompt canônico/default e no prompt final renderizado do LLM1 para evitar resumos vagos como:

```text
Exames mais recentes sem alterações relevantes.
```

quando a data estiver disponível.

O comportamento desejado é orientar o LLM a escrever algo como:

```text
Exames mais recentes de 01/12/2025 sem alterações relevantes.
```

ou equivalente.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/pipeline/llm1_service.py`
2. `apps/pipeline/tests/test_llm1_service.py`
3. `apps/llm/tests/test_seed_prompts.py`

Não é esperado alterar `apps/llm/management/commands/seed_prompts.py`, porque ele já importa `LLM1_DEFAULT_USER_PROMPT` de `apps.pipeline.llm1_service`. Em deploy greenfield com banco zerado, `seed_prompts` criará `llm1_user` usando o default atualizado. Se alterar `seed_prompts.py`, justificar no relatório.

## Requisitos funcionais

### R1. Prompt renderizado deve conter instrução explícita

A string final gerada por `_render_user_prompt(...)` deve conter instrução semanticamente equivalente a:

```text
Ao mencionar exames no summary.one_liner ou summary.bullet_points, sempre inclua a data do exame quando ela estiver disponível no laudo ou em exam_datetime_iso. Nunca escreva apenas "exames mais recentes" se a data estiver disponível; escreva "exames mais recentes de DD/MM/AAAA" ou equivalente.
```

A instrução deve ficar próxima ao bloco atual sobre `tracked_exams`.

### R2. Prompt default deve conter reforço curto

Atualizar obrigatoriamente `LLM1_DEFAULT_USER_PROMPT` com uma versão curta da instrução. Como o projeto está em cenário greenfield e o deploy partirá de banco zerado, isso garante que `seed_prompts` criará o prompt ativo `llm1_user` já correto.

Além disso, o prompt renderizado final também deve conter a instrução em `_render_user_prompt`, para que a regra fique garantida mesmo se no futuro o template ativo do banco for editado ou ficar desatualizado.

### R3. Não alterar schema

Não adicionar campos novos. Manter `schema_version 1.1` e o contrato atual:

```text
tracked_exams[] = {"exam_type", "exam_label", "result_value", "exam_datetime_iso", "is_most_recent", "source_text_hint"}
```

### R4. Não alterar LLM2

Não tocar `apps/pipeline/llm2_service.py` neste slice.

### R5. Não tentar atualizar prompts ativos no banco

Não modificar `seed_prompts` para sobrescrever prompts existentes. O comando é idempotente e deve continuar pulando prompts já existentes.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos em `apps/pipeline/tests/test_llm1_service.py`

1. `test_render_user_prompt_requires_exam_dates_in_summary_when_available`
   - chamar `_render_user_prompt(...)` diretamente ou por meio do serviço, conforme padrão atual dos testes;
   - assertar que o prompt final contém:
     - `summary.one_liner`;
     - `summary.bullet_points`;
     - `data do exame` ou `data dos exames`;
     - `exam_datetime_iso`;
     - uma proibição clara contra escrever apenas `exames mais recentes` quando houver data.

2. `test_default_user_prompt_mentions_exam_dates_for_narrative_summary`
   - assertar presença de orientação curta em `LLM1_DEFAULT_USER_PROMPT`.
   - Este teste é obrigatório, pois deploy greenfield com banco zerado usa esse default via `seed_prompts`.

### Teste obrigatório em `apps/llm/tests/test_seed_prompts.py`

Adicionar ou ajustar teste simples de alinhamento seed/default:

- provar que `DEFAULT_CONTENTS["llm1_user"]` continua apontando para `LLM1_DEFAULT_USER_PROMPT`;
- provar que o conteúdo default semeado para `llm1_user` contém a instrução sobre data dos exames no resumo narrativo.

Não criar teste complexo de banco para re-seed e não alterar o comportamento idempotente do comando.

## Restrições estritas

- Não alterar `apps/pipeline/schemas/llm1.py`.
- Não alterar `apps/pipeline/llm2_service.py`.
- Não alterar presenter neste slice.
- Não criar migração.
- Não sobrescrever prompts ativos existentes no banco. Para deploy greenfield, o banco zerado receberá o default atualizado pelo seed normal.
- Não alterar comportamento do parser JSON, validação Pydantic ou language guard.
- Não trocar schema version.
- Não adicionar campos como `exam_date_display` ou similares.

## Critérios de sucesso

- [ ] Teste novo falha antes da alteração e passa após.
- [ ] Prompt renderizado final exige datas no resumo narrativo quando disponíveis.
- [ ] Prompt mantém schema 1.1 e campos atuais.
- [ ] LLM2 não foi alterado.
- [ ] Seed continua idempotente e, em banco zerado, criará `llm1_user` com o default atualizado.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. A instrução fica no prompt renderizado mesmo se o template ativo no banco for antigo? Onde?
2. O schema LLM1 foi alterado? Se sim, está errado.
3. O LLM2 foi alterado? Se sim, está errado.
4. O comando `seed_prompts` continua sem sobrescrever prompts existentes?
5. Qual teste prova que um banco greenfield receberá `llm1_user` com o default atualizado?
6. Qual teste prova a presença da instrução no prompt final?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/show-recent-exam-dates-in-doctor-report/proposal.md, design.md, tasks.md and slices/slice-002-llm1-prompt-exam-dates.md.
Implement ONLY Slice 002. Assume Slice 001 is already complete; do not edit presenter code.
Use TDD strictly: first add failing tests proving (1) the final rendered LLM1 user prompt requires exam dates in summary.one_liner/summary.bullet_points when available, (2) LLM1_DEFAULT_USER_PROMPT contains the short instruction, and (3) seed default for llm1_user points to the updated LLM1_DEFAULT_USER_PROMPT for greenfield deploy. Then make the minimal prompt change in apps/pipeline/llm1_service.py.
Do not change schemas, LLM2, JSON parser, validation, database, migrations, presenter, templates, FSM, policy, or decision logic.
Do not make seed_prompts overwrite active DB prompts. It may remain unchanged because llm1_user seed content imports LLM1_DEFAULT_USER_PROMPT.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/show-recent-exam-dates-in-doctor-report/tasks.md marking Slice 002 complete only if all gates pass.
Create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
