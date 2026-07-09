# Relatório do Slice 003: Busca server-side indexada

## Arquivos tocados

1. `apps/dashboard/views.py` — adicionada lógica de busca com `search` query param
2. `templates/dashboard/index.html` — adicionado input de busca + ajuda visual + preservação em links
3. `apps/dashboard/tests/test_dashboard.py` — 11 novos testes de busca
4. `apps/cases/migrations/0011_dashboard_case_search_indexes.py` — migration com pg_trgm + índices GIN

## Snippets antes/depois

### views.py: import (antes)
```python
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q
```

### views.py: import (depois) — sem mudança de import, lógica inline

### views.py: lógica de busca (antes — sem busca)
```python
    # Tabela de casos — todos, sem filtro de usuario
    cases_qs = Case.objects.select_related("created_by").order_by("-created_at")
```

### views.py: lógica de busca (depois)
```python
    # Busca server-side
    search_raw = request.GET.get("search", "")
    search_term = search_raw.strip()[:100]
    search_min_chars_help = False

    # Tabela de casos — todos, sem filtro de usuario
    cases_qs = Case.objects.select_related("created_by").order_by("-created_at")

    # Filtro de atenção (exclui CLEANED, aplica critérios de atenção)
    if attention_filter:
        cases_qs = cases_qs.exclude(status=CaseStatus.CLEANED).filter(_attention_q(now))

    # Busca: só filtra com 3+ caracteres
    if len(search_term) >= 3:
        search_lower = search_term.lower()
        search_q = Q(agency_record_number__icontains=search_lower) | Q(
            structured_data__patient__name__icontains=search_lower
        )
        cases_qs = cases_qs.filter(search_q)
    elif len(search_term) in (1, 2):
        search_min_chars_help = True
```

### views.py: contexto (antes)
```python
            "attention_count": attention_count,
            "metrics_date": metrics_date_str,
            "total_label": total_label,
```

### views.py: contexto (depois)
```python
            "attention_count": attention_count,
            "metrics_date": metrics_date_str,
            "total_label": total_label,
            "search": search_raw,
            "search_term": search_term,
            "search_min_chars_help": search_min_chars_help,
```

### template: formulário de busca (antes — sem busca)
```html
      <form method="get" class="d-flex gap-2 align-items-center flex-wrap">
        <select name="status" class="form-select form-select-sm" style="width:auto;">
```

### template: formulário de busca (depois)
```html
      <form method="get" class="d-flex gap-2 align-items-center flex-wrap">
        <div class="d-inline-flex flex-column align-items-start">
          <label for="search" class="form-label form-label-sm mb-0 small text-muted">Buscar por nome ou registro</label>
          <input type="search" name="search" id="search" class="form-control form-control-sm" style="width:auto;"
                 value="{{ search }}" placeholder="Digite ao menos 3 caracteres">
        </div>
        <select name="status" class="form-select form-select-sm" style="width:auto;">
```

### template: ajuda visual (antes — sem)
### template: ajuda visual (depois)
```html
  {% if search_min_chars_help %}
  <div class="alert alert-info py-2 mb-3" role="alert">
    Digite ao menos <strong>3 caracteres</strong> para buscar por nome do paciente ou número de registro.
  </div>
  {% endif %}
```

### template: hidden inputs + limpar (antes)
```html
        {% if metrics_date %}<input type="hidden" name="metrics_date" value="{{ metrics_date }}">{% endif %}
        <button type="submit" class="btn btn-sm btn-hospital-outline">Filtrar</button>
        {% if status_filter or date_from or date_to %}
        <a href="{% url 'dashboard:index' %}" class="btn btn-sm btn-outline-secondary">Limpar</a>
        {% endif %}
```

### template: hidden inputs + limpar (depois)
```html
        {% if metrics_date %}<input type="hidden" name="metrics_date" value="{{ metrics_date }}">{% endif %}
        {% if search %}<input type="hidden" name="search" value="{{ search }}">{% endif %}
        <button type="submit" class="btn btn-sm btn-hospital-outline">Filtrar</button>
        {% if status_filter or date_from or date_to or search %}
        <a href="{% url 'dashboard:index' %}" class="btn btn-sm btn-outline-secondary">Limpar</a>
        {% endif %}
```

### template: paginação (antes — sem search)
```html
<a class="page-link" href="?page={{ page_obj.previous_page_number }}{% if status_filter %}&status={{ status_filter }}{% endif %}{% if date_from %}&date_from={{ date_from }}{% endif %}{% if date_to %}&date_to={{ date_to }}{% endif %}{% if attention_filter %}&attention=1{% endif %}{% if metrics_date %}&metrics_date={{ metrics_date }}{% endif %}">Anterior</a>
```

### template: paginação (depois — com search)
```html
<a class="page-link" href="?page={{ page_obj.previous_page_number }}{% if status_filter %}&status={{ status_filter }}{% endif %}{% if date_from %}&date_from={{ date_from }}{% endif %}{% if date_to %}&date_to={{ date_to }}{% endif %}{% if attention_filter %}&attention=1{% endif %}{% if metrics_date %}&metrics_date={{ metrics_date }}{% endif %}{% if search %}&search={{ search|urlencode }}{% endif %}">Anterior</a>
```

### Migration (nova)
```python
class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("cases", "0010_add_regulation_days_on_screen"),
    ]
    operations = [
        migrations.RunSQL(sql="CREATE EXTENSION IF NOT EXISTS pg_trgm", reverse_sql=""),
        migrations.RunSQL(sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS cases_case_arn_trgm_idx ...", reverse_sql="DROP INDEX IF EXISTS cases_case_arn_trgm_idx"),
        migrations.RunSQL(sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS cases_case_patient_name_trgm_idx ...", reverse_sql="DROP INDEX IF EXISTS cases_case_patient_name_trgm_idx"),
    ]
```

## Autoavaliação

### Gates de autoavaliação

1. **Qual teste prova busca por nome?**
   `test_search_by_patient_name` — cria caso com `structured_data={"patient": {"name": "Ana Maria"}}` e verifica que `?search=ana` encontra o caso e exclui outro.

2. **Qual teste prova busca por registro?**
   `test_search_by_agency_record_number` — cria caso com `agency_record_number="OCOR-001"` e verifica que `?search=ocor` encontra.

3. **Qual teste prova que termo com 2 caracteres não filtra?**
   `test_search_min_chars_does_not_filter` — `?search=an` mostra o caso sem filtrar.

4. **Como a busca compõe com status/data/attention?**
   - `test_search_composes_with_status`: `?search=ana&status=NEW` — só mostra caso NEW com nome Ana.
   - `test_search_composes_with_dates`: `?search=ana&date_from=...&date_to=...` — só mostra casos de ontem com nome Ana.
   - `test_search_composes_with_attention`: `?search=ana&attention=1` — só mostra FAILED com nome Ana.

5. **Quais índices foram criados e qual SQL/migration os cria?**
   Migration `0011_dashboard_case_search_indexes.py`:
   - `CREATE EXTENSION IF NOT EXISTS pg_trgm`
   - `CREATE INDEX CONCURRENTLY cases_case_arn_trgm_idx ON cases_case USING gin (lower(agency_record_number) gin_trgm_ops)`
   - `CREATE INDEX CONCURRENTLY cases_case_patient_name_trgm_idx ON cases_case USING gin (lower((structured_data #>> '{patient,name}')) gin_trgm_ops)`

6. **Foi usado filtro em Python após carregar casos?**
   Não. O filtro é aplicado via ORM (Q objects com `__icontains`) antes do `Paginator`.

7. **Foi criado JavaScript?**
   Não. A busca funciona exclusivamente por submit tradicional (form GET). Sem JS, sem partial SSR.

8. **O relatório contém snippets antes/depois dos pontos principais?**
   Sim, acima.

### Critérios de sucesso

- [x] Testes foram escritos antes da implementação e falharam inicialmente.
- [x] Busca por nome é server-side.
- [x] Busca por registro é server-side.
- [x] Termos com menos de 3 caracteres não filtram.
- [x] Busca compõe com filtros existentes e paginação.
- [x] Índices `pg_trgm` existem em migration reversível.
- [x] Sem JavaScript neste slice.
- [x] Sem Django REST Framework ou endpoint JSON.
- [x] Quality gate do `AGENTS.md` passa.

## Resultados dos testes

```
TestDashboardSearch::test_search_form_present PASSED
TestDashboardSearch::test_search_by_patient_name PASSED
TestDashboardSearch::test_search_by_agency_record_number PASSED
TestDashboardSearch::test_search_case_insensitive PASSED
TestDashboardSearch::test_search_min_chars_does_not_filter PASSED
TestDashboardSearch::test_search_composes_with_status PASSED
TestDashboardSearch::test_search_composes_with_dates PASSED
TestDashboardSearch::test_search_composes_with_attention PASSED
TestDashboardSearch::test_pagination_preserves_search PASSED
TestDashboardSearch::test_search_preserves_metrics_date PASSED
TestDashboardSearch::test_empty_search_does_not_filter PASSED
```

## Quality Gate

```bash
$ uv run ruff check .          # All checks passed!
$ uv run ruff format --check . # 175 files already formatted
$ uv run mypy .                # Success: no issues found
$ uv run pytest                # 1745 passed (tudo OK)
```
