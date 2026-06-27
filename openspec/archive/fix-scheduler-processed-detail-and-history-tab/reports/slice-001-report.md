# Relatório Slice 001: Detalhe único do scheduler + mensagem ao NIR em Processados Hoje

## Resumo da mudança

Implementação do Slice 001 do change `fix-scheduler-processed-detail-and-history-tab`:
- `scheduler_processed_detail` deixou de renderizar `intake/case_detail.html` (template NIR)
- Passa a renderizar `scheduler/context_detail.html` (template scheduler read-only)
- Criado helper `_build_scheduler_detail_context` para centralizar montagem de contexto
- Helper reutilizado por `scheduler_context_detail` e `scheduler_processed_detail`
- `Comunicar NIR` agora aparece para qualquer caso no escopo histórico do scheduler (não apenas CLEANED)
- Formulário genérico de comunicação fica oculto quando `Comunicar NIR` está visível

## Arquivos tocados

1. `apps/scheduler/views.py` — principal: helper + refactor de 2 views
2. `apps/scheduler/tests/test_views.py` — 5 novos testes TDD
3. `openspec/changes/fix-scheduler-processed-detail-and-history-tab/tasks.md` — Slice 001 marcado como concluído

## Evidência TDD

### RED phase (testes falhando antes da implementação)

```
FAILED test_scheduler_processed_detail_uses_scheduler_template_not_nir_actions
  → assert 'Reenviar caso corrigido' not in <rendered intake/case_detail.html>
```

### GREEN phase (testes passando após implementação)

```
5 passed, 123 deselected
```

### REFACTOR phase

- Criado `_build_scheduler_detail_context()` que centraliza ~70 linhas de contexto.
- `scheduler_context_detail` e `scheduler_processed_detail` chamam o mesmo helper.
- DRY local: mappers `DOCTOR_DECISION_MAP`, `SUPPORT_FLAG_MAP`, `ADMISSION_FLOW_MAP` são reutilizados.
- Sem refactor amplo horizontal — tocou apenas o necessário.

## Snippets antes/depois

### `scheduler_processed_detail` — antes

```python
# Renderizava intake/case_detail.html com importações internas
from apps.intake.views import (
    ADMISSION_FLOW_MAP, EVENT_DOT_CSS, EVENT_LABELS,
    STATUS_CSS_CLASS, STATUS_LABELS, STEP_STATUS_INDEX,
    STEPS, SUPPORT_FLAG_MAP,
)
# ... ~90 linhas de lógica de resultado final/stepper...
return render(request, "intake/case_detail.html", {...})
```

### `scheduler_processed_detail` — depois

```python
def scheduler_processed_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
        scheduler=request.user,
        appointment_status__in=["confirmed", "denied"],
    )
    back_url = reverse("scheduler:queue") + "?tab=processed"
    back_label = "← Voltar aos processados hoje"
    context = _build_scheduler_detail_context(
        request=request, case=case, back_url=back_url, back_label=back_label,
    )
    return render(request, "scheduler/context_detail.html", context)
```

### `show_historical_message_nir` — antes

```python
"show_historical_message_nir": is_historical and case.status == CaseStatus.CLEANED,
```

### `show_historical_message_nir` — depois (no helper)

```python
can_message_nir = is_historical  # _is_scheduler_historical_case(case)
"show_historical_message_nir": can_message_nir,
```

### Lógica de comunicação — antes (em `scheduler_context_detail`)

```python
can_post_communication = case.status != CaseStatus.CLEANED
```

### Lógica de comunicação — depois (no helper)

```python
can_message_nir = _is_scheduler_historical_case(case)
can_post_communication = case.status != CaseStatus.CLEANED and not can_message_nir
```

## Resposta aos gates de autoavaliação

1. **Qual template `scheduler_processed_detail` renderiza depois da mudança?**
   → `scheduler/context_detail.html`

2. **Que teste prova que `Reenviar caso corrigido` não aparece para scheduler?**
   → `test_scheduler_processed_detail_uses_scheduler_template_not_nir_actions`:
     `assert "Reenviar caso corrigido" not in content`

3. **Que teste prova que `Comunicar NIR` aparece em caso de `Processados Hoje`?**
   → `test_scheduler_processed_detail_shows_message_nir_cta`:
     `assert "Comunicar NIR" in content`

4. **Que teste prova que a mensagem ao NIR não altera `Case.status`?**
   → `test_scheduler_processed_detail_message_nir_creates_message_without_status_change`:
     `assert after_status == before_status`

5. **O formulário genérico de comunicação aparece junto com `Comunicar NIR`?**
   → **Não.** A regra `can_post_communication = case.status != CaseStatus.CLEANED and not can_message_nir`
     bloqueia o formulário genérico quando o CTA específico está visível.

6. **Alguma autorização foi relaxada?** → Não. As mesmas guards permanecem:
   - `@login_required` + `@role_required("scheduler")`
   - `case.scheduler == request.user` em `scheduler_processed_detail`
   - `appointment_status__in=["confirmed", "denied"]` em `scheduler_processed_detail`
   - Notificação OU escopo histórico em `scheduler_context_detail`

7. **Alguma migration/FSM/model foi criado/alterado?** → Não.

8. **Quais comandos de validação foram executados?**
   - ✅ `uv run ruff check .`
   - ✅ `uv run ruff format --check .`
   - ✅ `uv run mypy .`
   - ✅ `uv run pytest` (1580 passed, 0 failed)

## Comandos de validação e resultados

```bash
$ uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
# All checks passed
# Success: no issues found in 190 source files
# 1580 passed in 28.55s
```

## Riscos/Observações

- Nenhum risco identificado. Todos os 128 testes do scheduler passam.
- O `scheduler_processed_detail` perdeu a lógica de `result_info` (stepper final, resultado). 
  O template `context_detail.html` tem seu próprio stepper genérico que funciona sem `result_info`.
- O `_build_scheduler_detail_context` não cobre cenários de casos não-históricos (sem `appointment_status`),
  mas isso é intencional — a view `scheduler_processed_detail` só recebe casos com `appointment_status__in=["confirmed", "denied"]`.
