# Slice 002: Dashboard Display — Implementation Report

## Summary

Added card for latest periodic summary on the dashboard index page and created a new paginated history page at `/dashboard/summaries/`.

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `apps/dashboard/views.py` | Modified | Added `SupervisorSummary` import, `latest_summary` to context, new `dashboard_summaries` view |
| `apps/dashboard/urls.py` | Modified | Added `path("summaries/", ...)` route |
| `templates/dashboard/index.html` | Modified | Added summary card with period, metrics, and "Ver todos" link |
| `templates/dashboard/summaries.html` | **New** | Paginated table with all summary columns and status badge |
| `apps/dashboard/tests/test_dashboard.py` | Modified | Added 13 new tests (2 classes) |

## Before/After

### views.py — dashboard_index now includes `latest_summary`

**Before:**
```python
    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
            ...
        },
    )
```

**After:**
```python
    latest_summary = SupervisorSummary.objects.order_by("-window_end").first()

    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
            ...
            "latest_summary": latest_summary,
        },
    )
```

### views.py — New `dashboard_summaries` view

```python
@login_required
@role_required("manager", "admin")
def dashboard_summaries(request: HttpRequest) -> HttpResponse:
    """Página com histórico paginado de resumos de supervisão."""
    summaries_qs = SupervisorSummary.objects.order_by("-window_end")
    paginator = Paginator(summaries_qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "dashboard/summaries.html",
        {
            "page_obj": page_obj,
            "summaries": page_obj,
        },
    )
```

### urls.py — New route

**Before:**
```python
path("", views.dashboard_index, name="index"),
path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
```

**After:**
```python
path("", views.dashboard_index, name="index"),
path("summaries/", views.dashboard_summaries, name="summaries"),
path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
```

### index.html — Summary card (after sub-metrics, before case table)

New HTML block:
```html
{% if latest_summary %}
<div class="row g-3 mb-4">
  <div class="col-12">
    <div class="card p-3">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <h6 class="text-muted small mb-1">ÚLTIMO RESUMO</h6>
          <span class="text-muted small">
            {{ latest_summary.window_start|date:"d/m/Y H:i" }} — {{ latest_summary.window_end|date:"d/m/Y H:i" }}
          </span>
        </div>
        <a href="{% url 'dashboard:summaries' %}" class="btn btn-sm btn-hospital-outline">Ver todos os resumos</a>
      </div>
      <div class="row g-2 mt-2 text-center">
        <div class="col">
          <div style="font-size:1.25rem; font-weight:700;">{{ latest_summary.patients_received }}</div>
          <div class="text-muted small">Recebidos</div>
        </div>
        <div class="col">
          <div style="font-size:1.25rem; font-weight:700;">{{ latest_summary.accepted_scheduled }}</div>
          <div class="text-muted small">Aceitos</div>
        </div>
        <div class="col">
          <div style="font-size:1.25rem; font-weight:700;">{{ latest_summary.refused }}</div>
          <div class="text-muted small">Recusados</div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endif %}
```

### summaries.html — New template

Full paginated table with columns: Período, Recebidos, Processados, Avaliados, Aceitos, Imediata, Recusados, Em Andamento, Status (badge). Extends `base.html` with nav pills.

## Test Coverage (13 new tests)

**TestDashboardSummaryCard** (3 tests):
- Card appears when summary exists
- Card shows correct metrics data
- Card hides when no summaries exist

**TestDashboardSummariesView** (10 tests — 7 new + 3 inherited from decorator):
- Accessible for manager/admin
- Blocked for NIR, doctor
- Lists with pagination (25 per page)
- Shows status badges (Enviado/Pendente)
- Requires login

## Quality Gate

- ✅ ruff check: All checks passed
- ✅ ruff format --check: All files formatted
- ✅ mypy: No issues found
- ✅ pytest: 506 passed (13 new + 493 existing)

## Commit

```
feat(dashboard): add summary card and paginated history page
