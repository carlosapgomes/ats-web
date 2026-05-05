# Design: Pipeline LLM

> **Change**: `pipeline-llm`
> **Fase**: 2

---

## Decisões de Design

### D1: App `apps/pipeline/` separado do `apps/intake/`

Intake é responsabilidade do NIR (upload + visualização). Pipeline é responsabilidade do sistema (processamento automático). Separar apps mantém coesão:

- `apps/intake/` — views, forms, templates (NIR-facing)
- `apps/pipeline/` — services, policy engine, tasks (system-facing)

### D2: Policy engine como módulo puro (sem Django ORM)

`apps/pipeline/policy/` contém **funções puras** que operam sobre `dict[str, object]`. Zero acoplamento com Django models. Isso permite testar o policy engine da mesma forma que o legado (unit tests com dicts).

```
apps/pipeline/policy/
├── __init__.py
├── eda_preop_policy.py          # evaluate_eda_preop_policy()
├── eda_policy.py                # reconcile_eda_policy()
└── eda_recommendation_synthesis.py  # synthesize_eda_support_context()
```

### D3: LLM client via injeção, não import direto

`apps/pipeline/llm.py` define um `LlmClient` protocol. A implementação real (OpenAI) é injetada via factory function em settings:

```python
# config/settings/base.py
LLM_CLIENT_FACTORY = "apps.pipeline.llm.create_openai_client"
OPENAI_API_KEY = ""       # env var
OPENAI_MODEL = "gpt-4o"   # env var
```

Testes usam `StaticLlmClient` (resposta fixa) ou `RecordingLlmClient` (captura chamadas).

### D4: Pipeline síncrona no slice, async ready

Na Fase 2, a pipeline roda como **django-q2 task** (síncrona dentro do worker). O código usa funções síncronas. Se no futuro precisarmos de async, a separação de concerns (services puros + thin task wrapper) facilita a migração.

### D5: Pipeline orchestrator como função top-level

Uma função `run_pipeline(case_id)` orquestra todas as etapas:

```
run_pipeline(case_id)
  ├── _run_llm1(case) → structured_data, summary_text
  ├── _run_scope_detection(case) → eda | non_eda | unknown
  │     └── if non_eda/unknown: skip LLM2, mark manual_review
  ├── _run_preop_policy(case) → deterministic decision
  ├── _run_llm2(case) → suggestion, rationale
  ├── _run_policy_reconciliation(case) → final suggestion + contradictions
  ├── _run_support_synthesis(case) → ASA + support recommendation
  └── persist + FSM transitions + events
```

### D6: Transições FSM nesta fase

```
LLM_STRUCT (status após upload)
  → LLM_SUGGEST (após LLM1 ok)
  → R2_POST_WIDGET (após LLM2 + policy ok)
  → FAILED (se LLM1 ou LLM2 falham)
```

O status `R2_POST_WIDGET` indica que o caso está pronto para ser apresentado ao médico (Fase 3).

### D7: Eventos de auditoria novos

| Evento | Actor | Quando |
|--------|-------|--------|
| `LLM1_OK` | system | LLM1 completou com sucesso (já existe do Case.save signal) |
| `LLM1_FAILED` | system | LLM1 falhou |
| `LLM2_OK` | system | LLM2 completou com sucesso |
| `LLM2_FAILED` | system | LLM2 falhou |
| `EDA_PREOP_POLICY_DECISION` | system | Policy engine decidiu |
| `EDA_CONTRADICTION_DETECTED` | system | Reconciliation encontrou contradição |
| `EDA_SCOPE_GATED_MANUAL_REVIEW` | system | Exame não-EDA detectado |
| `SUPPORT_SYNTHESIS_RESULT` | system | ASA + support derivation |

---

## Plano de Slices (7 slices)

### Slice 1: App pipeline + LLM client abstraído
- Criar `apps/pipeline/` com estrutura mínima
- `LlmClient` protocol + `StaticLlmClient` + `create_openai_client()`
- Settings: `LLM_CLIENT_FACTORY`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- Testes do client abstraído

### Slice 2: Policy engine — EDA Preop Policy
- Portar `eda_preop_policy.py` fielmente do legado
- Funções puras, zero Django ORM
- Todos os testes do legado portados
- Thresholds, minimum exams, conditional gates, foreign body exception

### Slice 3: Policy engine — Reconciliation + Support Synthesis
- Portar `eda_policy.py` (reconciliation)
- Portar `eda_recommendation_synthesis.py` (support synthesis)
- Testes do legado portados

### Slice 4: Scope Detection
- Portar lógica de scope detection do `process_pdf_case_service.py`
- Keywords: gastrostomia, dilatação, corpo estranho, EDA genérico
- Non-EDA → `manual_review_required`
- Testes do legado portados

### Slice 5: LLM1 Service + LLM2 Service
- `Llm1Service` — carrega prompts, chama LLM, valida JSON, normaliza
- `Llm2Service` — carrega prompts, chama LLM, valida JSON
- JSON parser helper (`decode_llm_json_object`)
- Validação de schema (Pydantic ou manual)
- Testes com `StaticLlmClient`

### Slice 6: Pipeline orchestrator + django-q2 task
- `run_pipeline(case_id)` function
- django-q2 `@task` que chama `run_pipeline`
- Disparo automático no upload (intake_home view)
- FSM transitions + persistência + eventos
- Integração end-to-end

### Slice 7: Quality gate
- ruff + mypy + pytest
- Garantir zero regressão (144+ testes existentes)
- Novos testes de integração da pipeline completa

---

## Arquivos por slice (estimativa)

| Slice | Arquivos novos | Arquivos modificados |
|-------|---------------|---------------------|
| 1 | 5 (app, llm client, tests) | 2 (settings, installed_apps) |
| 2 | 3 (policy module, tests) | 0 |
| 3 | 3 (policy modules, tests) | 0 |
| 4 | 2 (scope detection, tests) | 0 |
| 5 | 5 (llm1, llm2, parser, schemas, tests) | 0 |
| 6 | 3 (orchestrator, task, tests) | 2 (intake views, urls) |
| 7 | 0 | 1 (pyproject.toml se necessário) |
