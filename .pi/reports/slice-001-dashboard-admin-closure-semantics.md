# Relatório do Slice: Separar encerramento administrativo em resultado final, badges e cards de totalização

**Data:** 2026-06-17  
**Branch:** main  
**Commit:** 7ed372f  
**Arquivos tocados:** 4 (mais spec/design existentes)

---

## Snippets Antes/Depois

### 1. `apps/dashboard/views.py` — `_compute_summary()`

**Antes:**
```python
accepted = today_cases.filter(doctor_decision="accept").exclude(appointment_status="denied").count()
denied = today_cases.filter(Q(doctor_decision="deny") | Q(appointment_status="denied")).count()
in_progress = total_today - accepted - denied

return {
    "total_today": total_today,
    "accepted": accepted,
    "denied": denied,
    "in_progress": in_progress,
}
```

**Depois:**
```python
admin_closed_ids = set(
    CaseEvent.objects.filter(
        event_type="CASE_ADMINISTRATIVELY_CLOSED",
        case__in=today_cases,
    ).values_list("case_id", flat=True).distinct()
)
admin_closed_count = len(admin_closed_ids)

accepted = today_cases.filter(doctor_decision="accept").exclude(appointment_status="denied").exclude(pk__in=admin_closed_ids).count()
denied = today_cases.filter(Q(doctor_decision="deny") | Q(appointment_status="denied")).exclude(pk__in=admin_closed_ids).count()
in_progress = total_today - accepted - denied - admin_closed_count

return {
    "total_today": total_today,
    "accepted": accepted,
    "denied": denied,
    "administratively_closed": admin_closed_count,
    "in_progress": in_progress,
}
```

### 2. `apps/dashboard/views.py` — `_compute_result()`

**Antes:**
```python
def _compute_result(case: Case) -> tuple[str, str]:
    """Computa label e classe CSS (Bootstrap badge) do resultado final."""
    # Scope-gated manual review
    if (...manual_review...):
        return ...
    ...
```

**Depois:**
```python
def _has_admin_close_event(case: Case) -> bool:
    return case.events.filter(event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()

def _compute_result(case: Case) -> tuple[str, str]:
    """... Prioridade: 1. Admin closure, 2. Scope-gated, ..."""
    if _has_admin_close_event(case):
        return ("🔒 Encerrado administrativamente", "bg-secondary")
    ...
```

### 3. `apps/dashboard/views.py` — `dashboard_case_detail()`

**Antes:** Admin closure não era detectada. Resultado final sempre seguia regras normais (scope-gated, doctor_denied, accepted_scheduled etc.).

**Depois:** Primeiro check do `result_info`:
```python
if _has_admin_close_event(case):
    admin_event = case.events.filter(event_type="CASE_ADMINISTRATIVELY_CLOSED").first()
    result_info = {
        "type": "administratively_closed",
        "reason_text": ...,
        "reason_code": ...,
        "previous_status": ...,
    }
```
E todos os branches seguintes têm guarda `elif result_info is None and ...`

### 4. `templates/intake/case_detail.html`

**Antes:** Não havia branch para `administratively_closed`.

**Depois:** Novo branch no Resultado Final:
```html
{% if result_info.type == "administratively_closed" %}
  <span class="badge bg-secondary fs-6 px-3 py-2">🔒 Encerrado administrativamente</span>
  <p>Caso removido das filas operacionais...</p>
  {% if result_info.reason_text %}<div>Motivo: {{ result_info.reason_text }}</div>{% endif %}
  {% if result_info.previous_status %}<div>Status anterior: {{ result_info.previous_status }}</div>{% endif %}
{% elif result_info.type == "manual_review_required" %}
  ...
```

### 5. `templates/dashboard/index.html`

**Antes:** 4 cards: Total Hoje, Aceitos, Negados, Em Andamento.

**Depois:** 5 cards — adicionado:
```html
<div class="col-6 col-md-3">
  <div class="card p-3 text-center">
    <div style="font-size:2rem; font-weight:700; color:var(--hospital-secondary);">
      {{ summary.administratively_closed }}
    </div>
    <div class="text-muted small">Encerrados admin.</div>
  </div>
</div>
```

---

## Resultados dos Testes

- **4 novos testes**: ✅ Todos passam
- **1195 testes totais**: ✅ Sem regressões
- **Cobertura do cenário 11/1/0/4/6**: ✅ `test_summary_separates_administrative_closed_from_in_progress`

## Quality Gate

| Ferramenta | Resultado |
|-----------|-----------|
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ 145 files already formatted |
| `mypy .` | ✅ Success: no issues found |
| `pytest` | ✅ 1195 passed |

## Autoavaliação

1. **Diferenciação CLEANED**: Pelo evento `CASE_ADMINISTRATIVELY_CLOSED` no `CaseEvent`, não pelo status FSM.
2. **Prioridade administrativa**: Em `_compute_result()` (badge) e `dashboard_case_detail()` (result_info), o check admin vem antes de qualquer outro.
3. **Caso accept+confirmado admin-closed**: Conta como `administratively_closed`, não como `accepted`.
4. **Em Andamento sem admin-closed**: `in_progress` exclui `admin_closed_count` — zero vazamento.
5. **Prova do cenário 11/1/0/4/6**: Teste `test_summary_separates_administrative_closed_from_in_progress` com asserts exatos.

---

**REPORT_PATH:** `/projects/dev/ats-web/.pi/reports/slice-001-dashboard-admin-closure-semantics.md`
