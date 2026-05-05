# Slice 5: Detalhe do Caso — Dados + PDF Inline + Timeline

> **Status**: DONE
> **Depende de**: Slice 4 (lista de casos)
> **Change**: `openspec/changes/intake-nir/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 9 (telas), seção 3.3 (eventos de auditoria)
3. `demo-reference/nir/case-detail.html` — layout completo com timeline
4. `apps/cases/models.py` — Case, CaseEvent, CaseStatus
5. `demo-reference/css/styles.css` — `.timeline-event`, `.steps-bar`

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Upload e lista de casos funcionando. Agora precisamos da tela de detalhe.

### Sua Tarefa

1. View `case_detail` que mostra dados do caso + PDF inline + timeline de CaseEvents
2. Stepper de progresso mostrando em qual etapa o caso está
3. Timeline vertical com eventos do CaseEvent (estilo demo-reference)
4. Botão "Confirmar Recebimento" quando status = WAIT_R1_CLEANUP_THUMBS

### Arquivos a Criar/Modificar (idealmente <= 5)

```
apps/intake/views.py                    # MODIFICAR: adicionar case_detail + confirm_receipt
apps/intake/urls.py                     # MODIFICAR: adicionar URL case/<uuid:case_id>/
templates/intake/case_detail.html       # Criar
apps/intake/tests/test_case_detail.py   # Criar
```

### Detalhes Técnicos

#### View case_detail

```python
@login_required
@role_required("nir")
def case_detail(request, case_id):
    case = get_object_or_404(Case, case_id=case_id, created_by=request.user)
    events = case.events.all()  # ordenado por timestamp (Meta.ordering)

    # Stepper: mapear status para etapa do progresso
    STEPS = [
        ("Upload", "NEW"),
        ("Extração IA", "EXTRACTING"),
        ("Avaliação Médica", "WAIT_DOCTOR"),
        ("Agendamento", "WAIT_APPT"),
        ("Resultado Final", "WAIT_R1_CLEANUP_THUMBS"),
    ]

    return render(request, "intake/case_detail.html", {
        "case": case,
        "events": events,
        "steps": STEPS,
        "status_labels": STATUS_LABELS,
        "status_css": STATUS_CSS_CLASS,
        "can_confirm_receipt": case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    })
```

#### View confirm_receipt

```python
@login_required
@role_required("nir")
def confirm_receipt(request, case_id):
    case = get_object_or_404(Case, case_id=case_id, created_by=request.user)
    if request.method == "POST" and case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        case.cleanup_triggered(user=request.user)
        case.save()
        case.cleanup_completed(user=request.user)
        case.save()
        messages.success(request, "Recebimento confirmado. Caso concluído.")
    return redirect("intake:case_detail", case_id=case.case_id)
```

#### URLs

```python
urlpatterns = [
    path("", views.intake_home, name="home"),
    path("my-cases/", views.my_cases, name="my_cases"),
    path("case/<uuid:case_id>/", views.case_detail, name="case_detail"),
    path("case/<uuid:case_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
]
```

#### Template case_detail.html

Estrutura seguindo `demo-reference/nir/case-detail.html`:

1. **Card topo**: nome (agency_record_number), status badge, data de criação
2. **Stepper**: `.steps-bar` com etapas done/current/future baseado no status atual
3. **Timeline**: `.timeline-event` para cada CaseEvent, com dot colorido por actor_type
   - `system` → teal (`.system`)
   - `human` com role → cor por papel (doctor=primary, scheduler=success, reception=warning)
4. **PDF viewer**: embed do PDF com `<iframe>` ou `<object>`, colapsável
5. **Ações**:
   - Se `WAIT_R1_CLEANUP_THUMBS`: botão "Confirmar Recebimento"
   - Link "Voltar para lista"

#### Mapeamento de cores do timeline dot

```python
EVENT_DOT_COLORS = {
    "CASE_CREATED": "reception",
    "CASE_START_PROCESSING": "system",
    "CASE_START_EXTRACTION": "system",
    "CASE_EXTRACTION_OK": "system",
    "CASE_EXTRACTION_FAILED": "system",
    "LLM1_OK": "system",
    "LLM2_OK": "system",
    "CASE_READY_FOR_DOCTOR": "system",
    "DOCTOR_ACCEPT": "doctor",
    "DOCTOR_DENY": "doctor",
    "CASE_READY_FOR_SCHEDULER": "system",
    "SCHEDULER_REQUEST_POSTED": "system",
    "APPT_CONFIRMED": "scheduler",
    "APPT_DENIED": "scheduler",
    "FINAL_REPLY_POSTED": "system",
    "CLEANUP_TRIGGERED": "system",
    "CLEANUP_COMPLETED": "system",
}
```

### TDD — Testes

1. `test_case_detail_renders`: GET case/<uuid>/ → 200
2. `test_case_detail_shows_record_number`: HTML contém agency_record_number
3. `test_case_detail_shows_status`: HTML contém status label em português
4. `test_case_detail_shows_timeline`: HTML contém eventos de auditoria
5. `test_case_detail_shows_pdf`: HTML tem embed/iframe do PDF
6. `test_case_detail_404_other_user`: caso de outro usuário → 404
7. `test_case_detail_404_nonexistent`: UUID inexistente → 404
8. `test_confirm_receipt_transitions`: POST confirm → CLEANED
9. `test_confirm_receipt_only_when_waiting`: POST confirm em status errado → sem efeito
10. `test_confirm_receipt_shows_button`: WAIT_R1_CLEANUP_THUMBS → botão aparece
11. `test_confirm_receipt_hides_button`: outro status → botão não aparece
12. `test_case_detail_requires_nir`: doctor → blocked

### Critérios de Sucesso

```bash
uv run pytest -v
# Smoke: logar NIR, criar caso via upload, clicar "Ver detalhes"
# - Stepper mostra progresso
# - Timeline com eventos
# - PDF visível inline
```

### Relatório

Gere `/tmp/slice-intake-005-report.md`.
Informe `REPORT_PATH=/tmp/slice-intake-005-report.md`.
