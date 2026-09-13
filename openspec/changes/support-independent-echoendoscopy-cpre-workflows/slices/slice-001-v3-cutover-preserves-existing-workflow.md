# Slice 001 — Cutover 3.0 preserva o fluxo EDA/Colonoscopia

## Objetivo

Migrar um processamento existente completo de EDA/Colonoscopia para catálogo/matriz centralizados e writer strict 3.0, chegando à avaliação médica sem regressão. As flags especializadas permanecem desligadas; o slice entrega compatibilidade operacional ponta a ponta, não infraestrutura isolada.

## Contexto necessário

- `AGENTS.md`
- `design.md`: D1–D8, D15 e Migration Plan/Cutover
- specs `procedure-combination-policy` e `procedure-neutral-analysis`
- domínio `CaseProcedure`, schemas/services/orchestrator 2.0 e testes do change combinado
- seed dos quatro prompts neutros

## Requisitos verificáveis

- **R1:** catálogo contém quatro tipos e uma única ordem/matriz; migration contém somente o `AlterField` esperado, sem `RunPython`, `RunSQL`, `SeparateDatabaseAndState` ou backfill, e forward migration preserva rows, JSON clínico e histórico legado existentes.
- **R2:** somente cinco conjuntos são válidos e agendamento casado exige igualdade exata com EDA+Colonoscopia.
- **R3:** tipos desconhecidos/duplicatas/conjuntos inválidos não são filtrados silenciosamente pela reconciliação.
- **R4:** schemas strict 3.0 aceitam os quatro tipos e evidência abdominal tipada; leitores 1.1/2.0 permanecem.
- **R5:** policy 3.0 agrega falhas preservando `reason_code` primário e mantém exatamente o comportamento EDA/Colonoscopia; profiles/rules especializadas serão ativadas apenas nos slices verticais próprios.
- **R6:** novos jobs EDA, Colonoscopia e EDA+Colonoscopia usam uma chamada 3.0 por estágio e chegam a `WAIT_DOCTOR` com o comportamento atual.
- **R7:** quatro prompts 3.0 são semeados idempotentemente; nenhum histórico é apagado.
- **R8:** flags especializadas continuam false/sem opções visuais.

## Escopo e blast radius

```yaml
expected_files:
  - apps/cases/models.py
  - apps/cases/procedures.py
  - apps/cases/exam_profiles.py
  - apps/cases/migrations/00xx_*.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/scope_detection.py
  - apps/pipeline/schemas/llm1_v3.py
  - apps/pipeline/schemas/llm2_v3.py
  - apps/pipeline/schemas/adapters.py
  - apps/pipeline/policy/eda_preop_policy.py
  - apps/pipeline/policy/procedure_policy.py
  - apps/pipeline/policy/__init__.py
  - apps/pipeline/llm1_service_v3.py
  - apps/pipeline/llm2_service_v3.py
  - apps/pipeline/orchestrator.py
  - apps/pipeline/llm.py
  - apps/llm/management/commands/seed_prompts.py
  - apps/cases/tests/test_case_procedure.py
  - apps/cases/tests/test_specialized_procedure_migration.py
  - apps/pipeline/tests/test_v3_existing_workflow.py
  - apps/pipeline/tests/test_llm_v3_contracts.py
allowed_incidental_files:
  - apps/pipeline/tests/test_orchestrator.py
  - apps/pipeline/tests/test_llm_client.py
  - apps/pipeline/tests/test_colonoscopy_pipeline.py
  - apps/pipeline/tests/test_slice_002_pipeline.py
  - apps/doctor/tests/test_slice_003_procedure_decision.py
  - apps/doctor/reporting.py
  - apps/doctor/forms.py
  - apps/doctor/presenters.py
  - apps/doctor/views.py
file_cap: 31
out_of_scope:
  - intake/detecção especializada
  - proveniência e precedência EDA+Eco/CPRE
  - troca médica especializada
  - UI/filtros especializados
```

O cap alto é justificado pelo cutover indivisível de um writer strict. Se excedido, parar antes de editar extras e pedir redimensionamento. Alterar FSM, roles ou reescrever 1.1/2.0 é bloqueante.

**Emenda aprovada pelo parent durante a execução (escalonamento via stop rule):** o cutover strict 3.0 exige migrar fixtures/mocks de testes de integraação de schema 2.0 para 3.0 — superfície subestimada no planejamento. Aprovada a Opção A (migração mecânica de fixtures + mock renomeado `_run_v2_pipeline`→`_run_v3_pipeline`), sem decisão de produto e preservando toda a cobertura de regressão. Cap elevado 23→27; adicionados `scope_detection.py` aos esperados e os 3 arquivos de teste acima aos incidentais. Nenhum teste foi arquivado/removido.

**Segunda emenda (parent):** 4 gates literais `schema_version == "2.0"` na superfície médica (`apps/doctor/reporting.py`, `apps/doctor/forms.py`, `apps/doctor/presenters.py`, `apps/doctor/views.py`) fariam TODO caso novo EDA/Colon (agora 3.0) cair no modo legado de relatório/decisão — regressão direta do objetivo "chegar à avaliação médica sem regressão". Aprovada generalização para `{"2.0", "3.0"}` via helper único, sem mudar comportamento 2.0. Cap 27→31. Sem isso, o cutover não fecha (Opção B degradada foi vetada).

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1 | migration/test | inspeção estática exige exatamente o `AlterField` previsto e proíbe operações de dados; `MigrationExecutor` prova snapshots idênticos de rows EDA/Colon, JSON 1.1/2.0 e evento/sinal Eco legado após forward migration |
| R2–R3 | model/procedures/reconciliation | enum, cinco conjuntos, unknown misto e par exato |
| R4/R5 | schemas/adapters/policy | strict normalization, estrutura de imagem, agregação e regressão EDA/Colon |
| R6/R7 | services/orchestrator/seed | EDA/Colon/combinado end-to-end com cliente fake e seed duplo |
| R8 | diff/intake atual | flags/opções especializadas ausentes |

## RED

1. Criar/ajustar primeiro os testes listados no blast radius.
2. Executar `uv run pytest apps/pipeline/tests/test_v3_existing_workflow.py apps/pipeline/tests/test_llm_v3_contracts.py apps/cases/tests/test_case_procedure.py apps/cases/tests/test_specialized_procedure_migration.py -q`.
3. Falha esperada: assertions sobre enum/matriz/schema 3.0/cutover falham. `file not found`, import/collection acidental ou ausência do teste não contam como RED.

## GREEN / verificação local

- Repetir o comando RED com exit code 0.
- `uv run pytest apps/pipeline/tests/test_orchestrator.py apps/pipeline/tests/test_colonoscopy_pipeline.py apps/pipeline/tests/test_slice_002_pipeline.py apps/pipeline/tests/test_eda_preop_policy.py apps/pipeline/tests/test_eda_policy.py -q`
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` (complementar; não substitui as assertions de operações/forward migration).
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R8 provados.
- [ ] Migration possui somente o `AlterField` esperado e o teste forward prova zero mutação dos dados/histórico existentes.
- [ ] Unknown junto de EDA não é reduzido a EDA válida.
- [ ] EDA/Colon chegam ao médico por writer 3.0.
- [ ] Nenhum intake especializado foi exposto.
- [ ] Diff ficou no cap aprovado.

## Handoff

Registrar cutover, matriz, compatibilidade, comandos e `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-001-report.md`. Parar; Slice 002 exige review aceito e confirmação explícita.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 001**: preserve EDA/Colonoscopia ponta a ponta durante o cutover strict 3.0, com catálogo/matriz fechados, unknown fail-closed e leitura 1.1/2.0. Crie primeiro os testes do RED, faça o mínimo para GREEN, refatore, rode os gates listados e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push, não exponha Eco/CPRE nem inicie o Slice 002; entregue o handoff ao parent e pare para review/confirmação.
