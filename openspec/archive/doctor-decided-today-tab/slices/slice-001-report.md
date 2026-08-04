# Slice 001 — Report: Aba Decididos Hoje + detalhe read-only médico

## Status: ✅ Complete

## Autoavaliação

### 1. A query de `Decididos Hoje` depende de `status`?
**Não.** A query usa `doctor_decided_at__gte=start, doctor_decided_at__lt=end` com bounds do dia local e `doctor_decision__in=["accept", "deny"]`, sem depender de `status__in=[DOCTOR_ACCEPTED, DOCTOR_DENIED]`.

### 2. O template ainda mostra `Histórico`?
**Não.** O pill `Histórico` foi removido de `templates/doctor/queue.html`. Restam apenas `Pendentes` e `Decididos Hoje`.

### 3. O detalhe médico reutiliza o padrão visual de supervisor/admin? Onde?
**Sim.** A view `doctor_decided_detail` em `apps/doctor/views.py` renderiza o mesmo template `intake/case_detail.html` com os mesmos parâmetros:
- `show_intake_nav=False`
- `back_url`, `back_label`, `pdf_url`
- `can_confirm_receipt=False`
- Mesma lógica de `result_info` para status terminais

### 4. A autorização impede acesso a caso de outro médico? Qual teste prova?
**Sim.** A view usa `get_object_or_404(Case, case_id=case_id, doctor=doctor_user, doctor_decision__in=["accept", "deny"])`. O teste `test_doctor_decided_detail_404_for_other_doctor_case` prova que médico B recebe 404 ao acessar caso do médico A.

### 5. O polling HTMX preserva `tab=decided`? Qual teste prova?
**Sim.** O `hx-get` em `queue.html` inclui `?tab={{ active_tab }}`. O teste `test_queue_partial_preserves_decided_tab` prova que o partial com `?tab=decided` retorna apenas conteúdo de decididos.

## Arquivos alterados (5)

### 1. `apps/doctor/views.py`

**Antes:**
```python
from datetime import date
```
```python
DOCTOR_DECISION_STATUSES = [CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED]
```
```python
def _doctor_queue_context(request):
    # query por status__in=DOCTOR_DECISION_STATUSES e events__timestamp__date=today
    decided_qs = Case.objects.filter(
        status__in=DOCTOR_DECISION_STATUSES,
        doctor=doctor_user,
        events__event_type__startswith="DOCTOR_",
        events__timestamp__date=today,
    ).distinct()
    # retornava sempre pendentes + decididos no mesmo contexto
```
- Sem rota de detalhe read-only para médico
- Sem `_local_day_bounds()`
- Sem suporte a `?tab=`

**Depois:**
```python
from datetime import date, datetime, time, timedelta
from django.urls import reverse
from apps.intake.views import (ADMISSION_FLOW_MAP, EVENT_DOT_CSS, EVENT_LABELS,
    STATUS_CSS_CLASS, STATUS_LABELS, STEP_STATUS_INDEX, STEPS, SUPPORT_FLAG_MAP)
```
- Helper `_local_day_bounds()` — bounds timezone-aware do dia local
- `DOCTOR_DECISION_STATUSES` removido (não usado mais)
- `_doctor_queue_context()` agora suporta `?tab=pending|decided` e usa `doctor_decided_at` para query
- `doctor_queue()` calcula ambos os counts para badges de navegação
- `doctor_queue_partial()` respeita `?tab=` 
- Nova view `doctor_decided_detail()` — detalhe read-only com template `intake/case_detail.html`
- `_build_case_card()` inclui `doctor_decided_at`

### 2. `apps/doctor/urls.py`

**Antes:**
```python
urlpatterns = [
    path("", views.doctor_queue, name="queue"),
    path("partials/queue/", views.doctor_queue_partial, name="queue_partial"),
    path("<uuid:case_id>/", views.doctor_decision, name="decision"),
    ...
]
```

**Depois:**
```python
urlpatterns = [
    path("", views.doctor_queue, name="queue"),
    path("partials/queue/", views.doctor_queue_partial, name="queue_partial"),
    path("decided/<uuid:case_id>/", views.doctor_decided_detail, name="decided_detail"),
    path("<uuid:case_id>/", views.doctor_decision, name="decision"),
    ...
]
```

### 3. `templates/doctor/queue.html`

**Antes:**
```html
<span class="nav-link active notif-badge" ...>Pendentes</span>
<span class="nav-link">Decididos Hoje</span>
<span class="nav-link">Histórico</span>
<hx-get="{% url 'doctor:queue_partial' %}"
```

**Depois:**
```html
<a class="nav-link ..." href="{% url 'doctor:queue' %}?tab=pending">Pendentes</a>
<a class="nav-link ..." href="{% url 'doctor:queue' %}?tab=decided">Decididos Hoje</a>
<!-- Histórico removido -->
<hx-get="{% url 'doctor:queue_partial' %}?tab={{ active_tab }}"
```

### 4. `templates/doctor/_queue_content.html`

**Antes:** Renderizava alerta + cards pendentes + seção "Recently Decided" no mesmo bloco.

**Depois:** Renderização condicional por `active_tab`:
- `active_tab == "pending"`: alerta + cards pendentes
- `active_tab == "decided"`: cards de decididos com nome, registro, decisão, suporte/fluxo, horário + botão "Ver detalhes"

### 5. `apps/doctor/tests/test_views.py`

- Adicionados 8 novos testes de TDD:
  - `test_queue_nav_has_functional_decided_tab_and_no_history`
  - `test_decided_today_tab_uses_doctor_decided_at_not_status`
  - `test_decided_today_tab_excludes_other_doctor_cases`
  - `test_pending_tab_does_not_render_decided_list`
  - `test_decided_tab_has_detail_link`
  - `test_doctor_decided_detail_renders_read_only_case_detail`
  - `test_doctor_decided_detail_404_for_other_doctor_case`
  - `test_queue_partial_preserves_decided_tab`
- Atualizados 2 testes existentes para refletir novo comportamento de abas

## Quality Gate

```
ruff check .           → All checks passed
ruff format --check .  → 144 files already formatted
mypy .                 → Success: no issues found in 156 source files
pytest                 → 1088 passed in 15.94s
```
