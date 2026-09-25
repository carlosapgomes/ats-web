# Slice 001 — Cutover 4.0 preserva o fluxo existente

## Objetivo

Entregar a fundação executável do change: catálogo/matriz de dez identidades, migration somente de schema e writer strict 4.0, provando que EDA, Colonoscopia e EDA + Colonoscopia continuam processando até a fila/relatório médico. Nenhuma nova identidade precisa estar exposta no intake neste slice.

O footprint maior é inevitável: enum/migration, strict schema, serviços, prompts e orchestrator precisam mudar juntos para não deixar um writer incompatível entre commits.

## Contexto necessário

Ler antes de editar:

- `design.md`: D1–D5, D13–D15 e Migration Plan;
- `specs/procedure-combination-policy/spec.md`;
- `specs/procedure-neutral-analysis/spec.md`;
- `apps/cases/models.py`, `apps/cases/procedures.py`, `apps/cases/exam_profiles.py`;
- `apps/pipeline/schemas/llm1_v3.py`, `llm2_v3.py`, `adapters.py`;
- `apps/pipeline/llm1_service_v3.py`, `llm2_service_v3.py`, `orchestrator.py`;
- `apps/llm/management/commands/seed_prompts.py`;
- testes v3/catálogo existentes citados abaixo.

Pré-condições: ADR-0010 aceita, `BASE_REF` registrado e baseline global executado uma única vez quando aplicável.

## Requisitos verificáveis

- **R1:** `ProcedureType` e o catálogo contêm exatamente os dez códigos/labels/ordem do design; `max_length` comporta o maior código e a migration não contém data migration/backfill.
- **R2:** a matriz aceita qualquer singleton canônico e somente `{eda, colonoscopy}` como conjunto multi-item; desconhecido e qualquer outro par falham explicitamente; `selection_key`/paired usam igualdade exata.
- **R3:** schemas LLM1/LLM2 4.0 strict aceitam dez identidades, proíbem duplicata e preservam detalhes tipados aplicáveis; production dispatch e prompts seedados usam 4.0.
- **R4:** adapters/presenters continuam lendo 1.1/2.0/3.0 sem reescrita e reconhecem 4.0; v3 permanece somente para leitura.
- **R5:** EDA, Colonoscopia e EDA + Colonoscopia completam análise 4.0 até o médico com uma extração comum, recomendação por row e sem regressão de policy.
- **R6:** nenhuma flag nova, FSM, permission ou coluna clínica é criada; sinais históricos permanecem legíveis.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/models.py
  - apps/cases/procedures.py
  - apps/cases/exam_profiles.py
  - apps/cases/migrations/0021_*.py
  - apps/pipeline/schemas/llm1_v4.py
  - apps/pipeline/schemas/llm2_v4.py
  - apps/pipeline/schemas/adapters.py
  - apps/pipeline/llm1_service_v4.py
  - apps/pipeline/llm2_service_v4.py
  - apps/pipeline/orchestrator.py
  - apps/llm/management/commands/seed_prompts.py
  - apps/cases/tests/test_expanded_procedure_catalog.py
  - apps/pipeline/tests/test_llm_v4_contracts.py
  - apps/pipeline/tests/test_v4_existing_workflow.py
  - apps/llm/tests/test_seed_prompts.py
allowed_incidental_files:
  - imports/reexports mínimos exigidos pelo novo serviço 4.0
  - migration graph test/downgrade precheck já existente, se a migration o exigir
out_of_scope:
  - expor novas opções no intake
  - detecção de pacotes/Retossigmoidoscopia
  - painel GTT, detalhe de dilatação, combobox, filas ou analytics
```

Cap esperado: até 18 arquivos, justificado pelo cutover strict coordenado. Se for necessário editar templates, FSM, permissions, scheduler/dashboard ou criar persistência clínica, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1–R2 | `models.py`, `procedures.py`, migration | `test_expanded_procedure_catalog.py` |
| R3 | `llm1_v4.py`, `llm2_v4.py`, services, seed | `test_llm_v4_contracts.py`, `test_seed_prompts.py` |
| R4 | `adapters.py` | testes de payloads 1.1/2.0/3.0/4.0 |
| R5 | `orchestrator.py` e services 4.0 | `test_v4_existing_workflow.py` |
| R6 | diff/inventário | `rg` focado + regressões v3 |

## RED

1. Criar os três novos arquivos de teste e ajustar `test_seed_prompts.py` antes de implementar.
2. Comando:

```bash
uv run pytest \
  apps/cases/tests/test_expanded_procedure_catalog.py \
  apps/pipeline/tests/test_llm_v4_contracts.py \
  apps/pipeline/tests/test_v4_existing_workflow.py \
  apps/llm/tests/test_seed_prompts.py -q
```

3. Falha esperada: ausência dos códigos/migration/módulos 4.0, dispatch ainda 3.0 e matriz fechada em quatro tipos. Erro de collection por typo não é RED válido.

## GREEN / verificação local

```bash
uv run pytest \
  apps/cases/tests/test_expanded_procedure_catalog.py \
  apps/pipeline/tests/test_llm_v4_contracts.py \
  apps/pipeline/tests/test_v4_existing_workflow.py \
  apps/llm/tests/test_seed_prompts.py -q

uv run pytest \
  apps/cases/tests/test_case_procedure.py \
  apps/cases/tests/test_specialized_procedure_migration.py \
  apps/pipeline/tests/test_llm_v3_contracts.py \
  apps/pipeline/tests/test_v3_existing_workflow.py \
  apps/pipeline/tests/test_colonoscopy_pipeline.py -q

uv run ruff check apps/cases apps/pipeline apps/llm
uv run ruff format --check apps/cases apps/pipeline apps/llm
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
```

Checks de contrato não adequadamente cobertos por unit test:

```bash
rg -n "NEW_.*FLAG|INTAKE_ENABLED" apps/cases apps/pipeline apps/llm
rg -n "RunPython|RunSQL" apps/cases/migrations/0021_*.py
```

O primeiro comando não pode revelar flag criada por este slice; o segundo não pode revelar operação de dados.

## Critérios de aceitação

- [ ] R1–R2: catálogo/matriz/migration são exatos e fail-closed.
- [ ] R3: writer/prompt strict 4.0 está ativo e validado.
- [ ] R4: readers 1.1/2.0/3.0 permanecem verdes sem reescrita.
- [ ] R5: os três fluxos existentes chegam ao médico sob 4.0.
- [ ] R6: nenhuma superfície futura, flag, FSM ou persistência clínica foi antecipada.

## Handoff

Worker com contexto fresco implementa somente este slice, registra RED/GREEN/refactor e arquivos tocados em relatório temporário, e não altera `tasks.md`, não faz commit/push e não inicia o Slice 002. Reviewer independente verifica BEHAVIOR/TESTS/SCOPE/DESIGN e bloqueia qualquer cutover parcial ou backfill.
