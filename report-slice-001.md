# Slice Report: Slice 1 — Modelo + Agregação + Resolve Window + Task

## Resumo

Implementação do modelo `SupervisorSummary`, funções de agregação e resolução de janela, e task cron do django-q2 para geração periódica de resumos de supervisão.

## Arquivos Modificados/Criados

| Arquivo | Ação |
|---------|------|
| `apps/cases/models.py` | Adicionado modelo `SupervisorSummary` |
| `apps/cases/migrations/0002_supervisor_summary.py` | Migration do novo modelo |
| `apps/pipeline/summary.py` | **Novo** — funções `resolve_previous_summary_window`, `aggregate_window_metrics`, constante `IN_PROGRESS_STATUSES` |
| `apps/pipeline/tasks.py` | Adicionados `generate_periodic_summary` e `enqueue_periodic_summary` |
| `config/settings/base.py` | Adicionados `SUMMARY_CUTOFF_HOURS` e `SUMMARY_TIMEZONE` |
| `apps/pipeline/tests/test_summary.py` | **Novo** — 17 testes |

## Detalhamento de Implementação

### 1. Modelo `SupervisorSummary` (`apps/cases/models.py`)

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
    status = models.CharField(max_length=10, choices=[...], default="sent")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("window_start", "window_end")]
        ordering = ["-window_end"]
```

### 2. Resolução de Janela (`apps/pipeline/summary.py`)

`resolve_previous_summary_window(run_at_utc, timezone_name, cutoff_hours)` encontra a janela mais recente concluída:

- Converte `run_at_utc` para o timezone alvo
- Encontra o último cutoff ≤ hora local atual
- Calcula o início da janela como o cutoff anterior (com wrap-around para dia anterior)
- Retorna `(window_start_utc, window_end_utc)`

Exemplo: cutoffs `"7,13,19,1"` em America/Bahia, run_at 11:30 BRT → janela 01:00-07:00 BRT

### 3. Agregação de Métricas (`apps/pipeline/summary.py`)

`aggregate_window_metrics(cases_qs)` usa `QuerySet.aggregate` com filtros `Q()`:

- `patients_received`: `Count("pk")` — todos os casos na janela
- `reports_processed`: casos em status LLM_SUGGEST ou além
- `cases_evaluated`: casos em WAIT_DOCTOR ou além
- `accepted_scheduled`: casos APPT_CONFIRMED
- `immediate_admission`: casos com `doctor_admission_flow="immediate"`
- `refused`: DOCTOR_DENIED + APPT_DENIED
- `in_progress`: status em `IN_PROGRESS_STATUSES` (exclui terminais: FAILED, DOCTOR_DENIED, APPT_DENIED, CLEANED)

### 4. Task (`apps/pipeline/tasks.py`)

`generate_periodic_summary(now_utc=None)`:
1. Resolve a janela via `resolve_previous_summary_window`
2. Filtra `Case.objects.filter(created_at__gte=window_start, created_at__lt=window_end)`
3. Agrega métricas via `aggregate_window_metrics`
4. Persiste via `SupervisorSummary.objects.get_or_create` (idempotente)
5. Aceita `now_utc` opcional para testes (freeze time)

`enqueue_periodic_summary()` — wrapper para `async_task` (uso no schedule django-q2)

### 5. Configurações (`config/settings/base.py`)

```python
SUMMARY_CUTOFF_HOURS = os.environ.get("SUMMARY_CUTOFF_HOURS", "7,13,19,1")
SUMMARY_TIMEZONE = os.environ.get("SUMMARY_TIMEZONE", TIME_ZONE)
```

## Testes (17)

- **Resolve Window (8)**: retorna tuple, janela manhã/tarde/noite/madrugada/cedo, respeita timezone, cutoffs customizados
- **Aggregate (6)**: queryset vazio, pacientes recebidos, relatórios processados, agendados aceitos, recusados, em andamento
- **Task (3)**: cria resumo, idempotente, enfileiramento

## Resultados do Quality Gate

- Ruff check: ✅
- Ruff format: ✅
- Mypy: ✅ (0 errors)
- Testes: 496 passed ✅

## Antes/Depois

**Antes**: Sem modelo de resumo, sem task de sumarização periódica.

**Depois**:
- Modelo `SupervisorSummary` com unique_together e 7 métricas
- Função de resolução de janela portada do legado (sem quebra de compatibilidade)
- Agregação eficiente via ORM (single query com `aggregate`)
- Task idempotente via `get_or_create`
- Testes completos (17) com freeze time para determinismo
