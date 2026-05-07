# Slice 1: Modelo + agregação + resolve_window + task

## Objetivo

Criar modelo `SupervisorSummary`, funções de agregação e resolução de janela,
e task cron do django-q2 para geração periódica.

## Arquivos

### 1. `apps/cases/models.py` — adicionar SupervisorSummary

```python
class SupervisorSummary(models.Model):
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    patients_received = models.PositiveIntegerField(default=0)
    reports_processed = models.PositiveIntegerField(default=0)
    cases_evaluated = models.PositiveIntegerField(default=0)
    accepted_scheduled = models.PositiveIntegerField(default=0)
    immediate_admission = models.PositiveIntegerField(default=0)
    refused = models.PositiveIntegerField(default=0)
    in_progress = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=[("pending","Pending"),("sent","Sent")], default="sent")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("window_start", "window_end")]
        ordering = ["-window_end"]
```

### 2. `apps/cases/migrations/0003_supervisor_summary.py` — migration

### 3. `apps/pipeline/summary.py` — novo módulo

- `resolve_previous_summary_window(run_at_utc, timezone_name, cutoff_hours)` — portado do legado
  Retorna `(window_start_utc, window_end_utc)`.
- `aggregate_window_metrics(cases_qs)` — recebe queryset, retorna dict de métricas
- `IN_PROGRESS_STATUSES` — lista de statuses considerados "em andamento"

### 4. `apps/pipeline/tasks.py` — adicionar task

- `generate_periodic_summary()` — resolve janela, agrega, persiste via get_or_create
- `enqueue_periodic_summary()` — wrapper para async_task (para schedule django-q2)

### 5. `config/settings/base.py`

- Adicionar `SUMMARY_CUTOFF_HOURS` config (default `"7,13,19,1"`)
- Adicionar `SUMMARY_TIMEZONE` (default `TIME_ZONE`)

## Critérios de sucesso

- [ ] Modelo SupervisorSummary criado com unique_together
- [ ] Migration criada e aplicável
- [ ] `resolve_previous_summary_window` resolve janela corretamente
- [ ] `aggregate_window_metrics` calcula métricas a partir de queryset
- [ ] `generate_periodic_summary` persiste resumo (idempotente)
- [ ] Configuração de cutoffs via env var
- [ ] Testes: ~17 (agregação 6 + resolve_window 8 + task 3)
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 5
