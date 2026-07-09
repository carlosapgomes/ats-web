<!-- markdownlint-disable MD013 MD014 MD022 MD026 MD031 MD032 MD040 MD060 -->

# Relatório Slice 002 — Métricas por data selecionada

## Arquivos tocados

1. `apps/dashboard/views.py` — adicionado parâmetro `day` nos helpers, parse de `metrics_date` na view
2. `templates/dashboard/index.html` — adicionado formulário de data, label dinâmico, badge ATUAL, hidden inputs
3. `apps/dashboard/tests/test_dashboard.py` — 9 testes novos para o Slice 002

Nenhum arquivo extra foi tocado.

## Snippets antes/depois

### views.py — Helpers com parâmetro day

**Antes:**
```python
def _compute_summary() -> dict[str, int]:
    start, end = _local_day_bounds()
```

**Depois:**
```python
def _compute_summary(day: date | None = None) -> dict[str, int]:
    start, end = _local_day_bounds(day)
```

### views.py — _compute_average_times com filtro de data

**Antes:**
```python
def _compute_average_times() -> dict[str, str]:
    decided_qs = Case.objects.exclude(doctor_decided_at=None).annotate(...)
    scheduled_qs = Case.objects.filter(...)
    completed_qs = Case.objects.exclude(cleanup_completed_at=None).annotate(...)
```

**Depois:**
```python
def _compute_average_times(day: date | None = None) -> dict[str, str]:
    cases_qs = Case.objects.all()
    if day is not None:
        start, end = _local_day_bounds(day)
        cases_qs = cases_qs.filter(created_at__gte=start, created_at__lt=end)
    decided_qs = cases_qs.exclude(doctor_decided_at=None).annotate(...)
    scheduled_qs = cases_qs.filter(...)
    completed_qs = cases_qs.exclude(cleanup_completed_at=None).annotate(...)
```

### views.py — dashboard_index com metrics_date

**Antes:**
```python
summary = _compute_summary()
admission_flow = _compute_admission_flow()
avg_times = _compute_average_times()
```

**Depois:**
```python
raw_metrics_date = request.GET.get("metrics_date", "")
metrics_date: date | None = None
metrics_date_str = ""
if raw_metrics_date:
    try:
        metrics_date = date.fromisoformat(raw_metrics_date)
        metrics_date_str = raw_metrics_date
    except (ValueError, TypeError):
        metrics_date = None

summary = _compute_summary(day=metrics_date)
admission_flow = _compute_admission_flow(day=metrics_date)
avg_times = _compute_average_times(day=metrics_date)

if metrics_date is not None:
    total_label = f"Total em {metrics_date.strftime('%d/%m/%Y')}"
else:
    total_label = "Total Hoje"
```

### Template — formulário de data das métricas

**Antes:** (não existia)

**Depois:**
```html
<div class="row g-3 mb-3">
  <div class="col-12">
    <form method="get" class="d-flex gap-2 align-items-center flex-wrap">
      <label for="metrics_date" class="form-label mb-0 small fw-semibold">Data das métricas</label>
      <input type="date" name="metrics_date" id="metrics_date" ...>
      <button type="submit" class="btn btn-sm btn-hospital-outline">Aplicar</button>
      {% if metrics_date %}
      <a href="{% url 'dashboard:index' %}" class="btn btn-sm btn-outline-secondary">Hoje</a>
      {% endif %}
      <!-- hidden inputs preservam filtros existentes -->
    </form>
  </div>
</div>
```

### Template — label "Total Hoje" → "Total em DD/MM/AAAA"

**Antes:** `<div class="text-muted small">Total Hoje</div>`

**Depois:** `<div class="text-muted small">{{ total_label }}</div>`

### Template — badge ATUAL no card "Aguardando por etapa"

**Antes:** `<h6 class="text-muted small mb-2">AGUARDANDO POR ETAPA</h6>`

**Depois:** `<h6 class="text-muted small mb-2">AGUARDANDO POR ETAPA <span class="badge bg-secondary">ATUAL</span></h6>`

### Template — hidden input metrics_date no form de filtros

**Antes:** (não existia)

**Depois:** `{% if metrics_date %}<input type="hidden" name="metrics_date" value="{{ metrics_date }}">{% endif %}`

## Autoavaliação

### 1. Quais métricas são afetadas por `metrics_date`?
- **Summary cards** (total, aceitos, negados, encerrados admin, em andamento)
- **Fluxo de admissão** (agendado vs imediato)
- **Tempos médios** (upload→decisão, decisão→agendamento, ciclo total)

### 2. Quais métricas não são afetadas e por quê?
- **"Aguardando por etapa"** — é snapshot atual da fila, não histórico. Não faz sentido filtrar por data.
- **Lista "Todos os Casos"** — já tem filtros próprios `date_from`/`date_to`. `metrics_date` é independente.
- **Card de atenção** — é snapshot operacional de casos suspeitos.

### 3. Qual teste prova que ontem exclui casos de hoje?
`test_metrics_date_yesterday_counts_only_yesterday`:
- Cria 1 caso ontem e 1 caso hoje
- Chama `_compute_summary(day=yesterday)`
- Assert que `total_today == 1` (só o caso de ontem)

### 4. Qual teste prova que data inválida não gera 500?
`test_invalid_metrics_date_does_not_break`:
```python
response = client.get(reverse("dashboard:index") + "?metrics_date=invalid-date")
assert response.status_code == 200
```

### 5. O formulário de filtros da lista preserva `metrics_date`?
Sim. Testado em `test_case_filter_form_preserves_metrics_date`:
- GET com `?metrics_date=2026-07-01`
- Verifica que `value="2026-07-01"` existe no HTML

### 6. Houve tentativa de reconstruir histórico por `CaseEvent`?
Não. O slice usa apenas `created_at` para filtrar casos no dia selecionado.

### 7. O relatório contém snippets antes/depois dos pontos principais?
Sim, acima.

## Quality Gate

- [x] `ruff check .` — All checks passed
- [x] `ruff format --check .` — All files formatted
- [x] `mypy apps/dashboard/` — Success: no issues found
- [x] `pytest apps/dashboard/tests/test_dashboard.py` — 116 passed
