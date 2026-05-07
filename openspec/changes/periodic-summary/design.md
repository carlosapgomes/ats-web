# Design: Resumo Periódico

## Decisões

### D1: Modelo `SupervisorSummary` em `apps/cases/models.py`

Evitar app novo para 1 modelo. `SupervisorSummary` vive em `apps/cases/` junto com Case/CaseEvent.

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

Unique constraint garante idempotência: não cria duplicata para mesma janela.

### D2: Função de agregação `apps/pipeline/summary.py`

Função pura (sem ORM) que recebe queryset de cases e retorna dict de métricas.
Chamada pela task do django-q2.

```python
def aggregate_window_metrics(cases_qs) -> dict[str, int]:
    return {
        "patients_received": cases_qs.count(),
        "reports_processed": cases_qs.exclude(structured_data__isnull=True).count(),
        "cases_evaluated": cases_qs.exclude(doctor_decision="").count(),
        "accepted_scheduled": cases_qs.filter(doctor_decision="accept", doctor_admission_flow="scheduled").count(),
        "immediate_admission": cases_qs.filter(doctor_decision="accept", doctor_admission_flow="immediate").count(),
        "refused": cases_qs.filter(doctor_decision="deny").count() + cases_qs.filter(appointment_status="denied").count(),
        "in_progress": cases_qs.filter(status__in=IN_PROGRESS_STATUSES).count(),
    }
```

### D3: Resolução de janela via cutoffs

Portado do legado `resolve_previous_summary_window()`. Recebe cutoffs configuráveis
via env var `SUMMARY_CUTOFF_HOURS` (default: `7,13,19,1`).

```python
SUMMARY_CUTOFF_HOURS = [int(h) for h in os.getenv("SUMMARY_CUTOFF_HOURS", "7,13,19,1").split(",")]
```

A lógica resolve a última janela completa antes do momento atual.
Exemplo: se agora são 14h e cutoffs são [7,13,19,1], a janela é [07:00, 13:00).

### D4: Cron job django-q2 — `generate_periodic_summary`

Task registrada no `Q_CLUSTER` via schedule. Executa a cada hora.

```python
# apps/pipeline/tasks.py
def generate_periodic_summary() -> None:
    """Cron task: resolve window, aggregate metrics, persist summary."""
    window = resolve_previous_summary_window(...)
    # Idempotência: usa get_or_create
    summary, created = SupervisorSummary.objects.get_or_create(
        window_start=window.start, window_end=window.end,
        defaults={...metrics...},
    )
```

### D5: Schedule no Django Q2

Configurado via `Q_CLUSTER["schedule"]` ou `django_q.Schedule` model.
Usar o modelo `Schedule` do django-q2 para facilitar criação via migration.

### D6: Exibição no dashboard

- **Dashboard** (`/dashboard/`): card com último resumo gerado (se existir)
- **Histórico** (`/dashboard/summaries/`): lista paginada de resumos

View `dashboard_summaries` adicionada em `apps/dashboard/views.py`.

### D7: Timezone

Usar `TIME_ZONE` do Django (default "America/Sao_Paulo") para converter janelas UTC → local na exibição.
Cálculo de janela usa UTC internamente, exibe em horário local.

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/cases/models.py` | modificado (adicionar SupervisorSummary) |
| `apps/cases/migrations/0003_supervisor_summary.py` | novo |
| `apps/pipeline/summary.py` | novo (aggregate + resolve_window) |
| `apps/pipeline/tasks.py` | modificado (adicionar generate_periodic_summary) |
| `apps/dashboard/views.py` | modificado (summaries + card no dashboard) |
| `apps/dashboard/urls.py` | modificado (summaries route) |
| `templates/dashboard/index.html` | modificado (card último resumo) |
| `templates/dashboard/summaries.html` | novo |
| `config/settings/base.py` | modificado (SUMMARY_CUTOFF_HOURS) |

## Orçamento de testes

- aggregate_window_metrics: ~6
- resolve_previous_summary_window: ~8
- generate_periodic_summary (idempotência): ~3
- Dashboard summaries view: ~4
- Dashboard card: ~2
- Total estimado: ~23 novos testes
