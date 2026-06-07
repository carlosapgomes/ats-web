# Slice 002: Reforço do prompt canônico LLM1 para resumo narrativo

## Contexto zero para implementador

O Slice 001 adiciona detecção determinística e renderização do alerta de ingestão cáustica/corrosiva no relatório médico a partir de `case.extracted_text`.

Este Slice 002 reforça o prompt do LLM1 para que os resumos narrativos também tendam a mencionar o evento e o tempo desde a ingestão quando o relatório informar. Essa camada é complementar: a tela final não deve depender exclusivamente do LLM para mostrar o alerta.

Arquivos relevantes:

- `apps/pipeline/llm1_service.py`
  - `LLM1_DEFAULT_USER_PROMPT`
  - `_render_user_prompt(...)`
- `apps/pipeline/tests/test_llm1_service.py`
- `apps/llm/management/commands/seed_prompts.py`
  - já importa `LLM1_DEFAULT_USER_PROMPT`; não deve precisar alteração.

## Objetivo do slice

Atualizar o prompt canônico/default do LLM1 para instruir que, quando o relatório mencionar ingestão de substância cáustica/corrosiva, soda cáustica, produto corrosivo ou ácido em contexto de ingestão, o resumo narrativo deve mencionar:

1. o evento;
2. o tempo desde a ingestão, quando disponível no texto;
3. que esse tempo não deve ser transformado em motivo automático de negativa.

## Arquivos esperados

Tocar idealmente apenas:

1. `apps/pipeline/llm1_service.py`;
2. `apps/pipeline/tests/test_llm1_service.py`;
3. opcionalmente `apps/llm/tests/test_seed_prompts.py`, se houver teste existente adequado para provar que o seed usa o default atualizado.

Se alterar `apps/llm/management/commands/seed_prompts.py`, justificar no relatório. Em princípio não é necessário, pois ele já importa o default de `apps.pipeline.llm1_service`.

## Requisitos funcionais

### R1. Atualizar `LLM1_DEFAULT_USER_PROMPT`

Adicionar instrução curta para banco zerado/seed inicial.

Texto alvo sugerido:

```text
Se houver ingestão de substância cáustica/corrosiva, soda cáustica, produto corrosivo ou ácido em contexto de ingestão, mencione o evento no resumo e inclua o tempo desde a ingestão quando disponível.
```

### R2. Atualizar `_render_user_prompt(...)`

Adicionar instrução completa na renderização final, porque essa parte é anexada mesmo quando há prompt ativo no banco.

Texto alvo sugerido:

```text
Se o relatório mencionar ingestão de substância cáustica/corrosiva, soda cáustica, produto corrosivo ou ácido em contexto de ingestão, mencione esse evento no summary.one_liner ou summary.bullet_points e inclua o tempo desde a ingestão quando o texto informar (por exemplo, "há 3 semanas" ou "em 12/05/2026"). Não transforme esse tempo em motivo automático de negativa.
```

### R3. Não alterar schema

Não adicionar campos novos ao JSON LLM1. A informação continua no resumo narrativo e no detector determinístico do Slice 001.

### R4. Não sobrescrever prompts ativos existentes

Não mudar comportamento de `seed_prompts` para sobrescrever prompt existente no banco.

## TDD obrigatório

Antes de implementar, adicionar testes falhando.

### Testes mínimos em `apps/pipeline/tests/test_llm1_service.py`

1. Teste que `LLM1_DEFAULT_USER_PROMPT` contém instrução sobre:
   - `cáustica` ou `caustica`;
   - `corrosiva` ou `corrosivo`;
   - tempo desde ingestão.

2. Teste que `_render_user_prompt(...)` contém instrução sobre:
   - ingestão cáustica/corrosiva;
   - incluir tempo quando disponível;
   - não transformar o tempo em motivo automático de negativa.

Se `_render_user_prompt` for função não pública já testada no arquivo, seguir padrão existente dos testes do projeto.

### Teste opcional de seed

Se já existir teste simples para `seed_prompts`, adicionar assert de que o conteúdo criado para `llm1_user` vem de `LLM1_DEFAULT_USER_PROMPT` e contém a nova instrução. Não criar teste caro se o padrão existente não comportar.

## Restrições estritas

- Não alterar schema LLM1/LLM2.
- Não alterar presenter neste slice, exceto se necessário por falha de integração do Slice 001; nesse caso, justificar.
- Não alterar LLM2, policy, reconciliação, suporte ou FSM.
- Não criar migration.
- Não sobrescrever prompts ativos no banco.
- Não adicionar regra automática de negativa.

## Critérios de sucesso

- [ ] Testes novos falham antes da implementação e passam depois.
- [ ] `LLM1_DEFAULT_USER_PROMPT` contém instrução explícita sobre ingestão cáustica/corrosiva e tempo.
- [ ] Prompt renderizado final contém instrução explícita e inclui a proibição de transformar o tempo em negativa automática.
- [ ] `seed_prompts` continua idempotente e não sobrescreve prompts existentes.
- [ ] Nenhum schema foi alterado.
- [ ] Quality gate completo passa.

## Gates de autoavaliação

Responder no relatório do slice:

1. A instrução aparece no default e no prompt renderizado?
2. O texto deixa claro que o tempo não vira motivo automático de negativa?
3. `seed_prompts` continua sem sobrescrever prompts existentes?
4. Algum schema ou campo JSON novo foi criado? Se sim, está errado.
5. Algum arquivo fora dos esperados foi alterado? Se sim, por quê?

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/highlight-caustic-ingestion-in-doctor-report/proposal.md, design.md, tasks.md and slices/slice-002-prompt-llm1-caustico.md.
Implement ONLY Slice 002 after Slice 001 is complete.
Use TDD strictly: first add failing tests proving LLM1_DEFAULT_USER_PROMPT and rendered user prompt mention caustic/corrosive ingestion and time since ingestion, then minimally update apps/pipeline/llm1_service.py.
Do not alter schemas, LLM2, policy, FSM, database, presenter behavior, queues, notifications or decision logic. Do not overwrite active prompts in the DB. The prompt must explicitly say not to transform time since ingestion into an automatic denial reason.
Run: uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
Update openspec/changes/highlight-caustic-ingestion-in-doctor-report/tasks.md marking Slice 002 and DoD complete only if all gates pass.
Create a detailed temporary markdown report with before/after snippets and answers to the self-evaluation gates.
Commit and push.
Return REPORT_PATH=<path> and stop.
```
