# Slice 6: Pipeline Orchestrator + django-q2 Task

> **Status**: DONE
> **Depende de**: Slices 1-5 todos implementados
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 3 (FSM), seção 4.1 (fluxo intake), seção 5.1 (eventos)
3. `apps/cases/models.py` — Case, CaseStatus, FSM transitions
4. `apps/llm/models.py` — PromptTemplate.get_active()
5. `apps/intake/views.py` — intake_home (onde o upload dispara a pipeline)

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Todos os componentes da pipeline estão prontos: LLM client, policy engine, scope detection, LLM1/Llm2 services. Agora juntamos tudo no orchestrator.

### Sua Tarefa

1. Criar `run_pipeline(case_id)` que orquestra toda a pipeline
2. Criar django-q2 `@task` que chama `run_pipeline`
3. Disparar task automaticamente após upload no `intake_home`
4. Gerar eventos de auditoria em cada etapa
5. Persistir artifacts no Case

### Arquivos a Criar/Modificar

```
apps/pipeline/orchestrator.py             # Criar (run_pipeline)
apps/pipeline/tasks.py                    # Criar (django-q2 @task)
apps/pipeline/tests/test_orchestrator.py  # Criar (testes de integração)
apps/intake/views.py                      # MODIFICAR: disparar task após upload
config/settings/base.py                   # MODIFICAR: Q2 cluster settings
```

### Detalhes Técnicos

#### apps/pipeline/orchestrator.py

```python
def run_pipeline(case_id: uuid.UUID) -> None:
    """Orquestra toda a pipeline LLM para um caso.

    FSM flow:
        LLM_STRUCT → LLM_SUGGEST → R2_POST_WIDGET
                     └→ FAILED (se erro em qualquer etapa)
    """
    case = Case.objects.get(case_id=case_id)

    try:
        # 1. Run LLM1 (structured extraction)
        llm1_result = _run_llm1(case)
        case.structured_data = llm1_result.structured_data
        case.summary_text = llm1_result.summary_text
        case.save()
        _record_event(case, "LLM1_OK", payload={...})

        # 2. Scope detection
        scope_result = classify_exam_scope(
            llm1_structured_data=case.structured_data,
            cleaned_text=case.extracted_text,
            case_id=str(case.case_id),
            agency_record_number=case.agency_record_number,
        )

        if scope_result is not None:
            # Non-EDA or unknown → manual review, skip LLM2
            case.suggested_action = scope_result
            case.save()
            _record_event(case, "EDA_SCOPE_GATED_MANUAL_REVIEW", payload=scope_result)
            # Transition to R2_POST_WIDGET (will be handled differently in Phase 3)
            case.ready_for_doctor()
            case.save()
            return

        # 3. Transition to LLM_SUGGEST
        case.llm1_complete(success=True, user=None)
        case.save()

        # 4. Run preop policy (deterministic)
        preop_decision = evaluate_eda_preop_policy(structured_data=case.structured_data)
        _record_event(case, "EDA_PREOP_POLICY_DECISION", payload=preop_decision)

        # 5. Run LLM2 (suggestion)
        llm2_result = _run_llm2(case)
        suggested_action = llm2_result.suggested_action

        # 6. Reconciliation
        reconciled = _apply_reconciliation(case, suggested_action, preop_decision)
        _record_contradictions(case, reconciled)

        # 7. Support synthesis
        support_context = synthesize_eda_support_context(structured_data=case.structured_data)
        reconciled["support_recommendation"] = support_context.support_recommendation
        reconciled["asa"] = {
            "bucket": support_context.asa_bucket,
            "display_text": support_context.asa_display,
        }

        # 8. Attach preop gate
        reconciled["preop_gate"] = preop_decision

        case.suggested_action = reconciled
        case.save()

        # 9. LLM2 complete → transition
        case.llm2_complete(success=True, user=None)
        case.save()

        _record_event(case, "LLM2_OK", payload={...})

        # 10. Ready for doctor
        case.ready_for_doctor()
        case.save()
        _record_event(case, "CASE_READY_FOR_DOCTOR")

    except Exception as e:
        case.status = CaseStatus.FAILED
        case.save()
        _record_event(case, "PIPELINE_FAILED", payload={"error": str(e)})
```

**Nota**: A FSM tem transições `llm1_complete`, `llm2_complete`, `ready_for_doctor` já definidas no `apps/cases/models.py`. Verificar se `_record_event` usa o padrão `_pending_event` existente ou `CaseEvent.objects.create()`.

#### apps/pipeline/tasks.py

```python
from django_q2.tasks import async_task

def enqueue_pipeline(case_id: uuid.UUID) -> None:
    """Enqueue pipeline task via django-q2."""
    async_task("apps.pipeline.tasks.execute_pipeline", str(case_id))

def execute_pipeline(case_id_str: str) -> None:
    """Entry point for django-q2 worker."""
    from apps.pipeline.orchestrator import run_pipeline
    run_pipeline(uuid.UUID(case_id_str))
```

#### apps/intake/views.py — MODIFICAR

No `intake_home`, após upload + extração de texto, **remover** as transições FSM manuais (start_processing, start_extraction, extraction_complete) e substituir por:

```python
# FSM: NEW → R1_ACK_PROCESSING → EXTRACTING
case.start_processing(user=user)
case.save()
case.start_extraction(user=user)
case.save()

# Extrair texto do PDF
extracted = extract_pdf_text(case.pdf_file.path)
case.extracted_text = extracted
case.agency_record_extracted_at = timezone.now()
case.save()

# Disparar pipeline assíncrona
case.extraction_complete(success=True, user=user)
case.save()

# Enfileirar pipeline LLM
from apps.pipeline.tasks import enqueue_pipeline
enqueue_pipeline(case.case_id)
```

**Atenção**: O Case já transita para `LLM_STRUCT` via `extraction_complete`. A pipeline pegará a partir desse estado.

### TDD — Testes

#### test_orchestrator.py

1. `test_pipeline_full_run`: caso com texto EDA → LLM1 + LLM2 + policy → R2_POST_WIDGET
2. `test_pipeline_llm1_failure`: LLM1 falha → FAILED + evento LLM1_FAILED
3. `test_pipeline_scope_gated`: non-EDA → scope gated + R2_POST_WIDGET (sem LLM2)
4. `test_pipeline_persist_structured_data`: structured_data salvo no Case
5. `test_pipeline_persist_suggested_action`: suggested_action salvo no Case
6. `test_pipeline_persist_summary_text`: summary_text salvo no Case
7. `test_pipeline_generates_events`: LLM1_OK, EDA_PREOP_POLICY_DECISION, LLM2_OK, etc.
8. `test_pipeline_preop_deny_overrides_llm2_accept`: policy engine deny → suggested_action.suggestion = deny
9. `test_pipeline_support_synthesis_saved`: support_recommendation no suggested_action
10. `test_enqueue_pipeline_creates_task`: enqueue_pipeline chama async_task

### Critérios de Sucesso

```bash
uv run pytest -v
# Esperado: todos passando, zero regressão

# Smoke test:
uv run python manage.py runserver --settings=config.settings.dev
# 1. Upload PDF como NIR
# 2. Caso vai para LLM_STRUCT
# 3. Se django-q2 rodando: pipeline executa automaticamente
# 4. Caso transita para R2_POST_WIDGET
# 5. suggested_action preenchido no Case
```

### Relatório

Gere `/tmp/slice-pipeline-006-report.md`.
Informe `REPORT_PATH=/tmp/slice-pipeline-006-report.md`.
