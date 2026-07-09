<!-- markdownlint-disable MD013 -->

# Design: Seletor de período para métricas do dashboard

## Estado atual

`apps/dashboard/views.py::dashboard_index()` lê `metrics_date` e passa `day` para:

- `_compute_summary(day=metrics_date)`
- `_compute_admission_flow(day=metrics_date)`
- `_compute_average_times(day=metrics_date)`

`_compute_summary()` e `_compute_admission_flow()` usam bounds do dia local sobre `created_at`. `_compute_average_times()` atualmente filtra por `created_at` quando `day` é fornecido, e sem `day` considera todos os dados.

O template `templates/dashboard/index.html` mostra um `<input type="date" name="metrics_date">`.

## Decisões

### D1. Query param canônico

Adicionar `metrics_period` com valores aceitos:

| Valor | Label | Semântica |
| --- | --- | --- |
| `today` | Hoje | dia local atual |
| `7d` | 7 dias | hoje + 6 dias anteriores |
| `30d` | 30 dias | hoje + 29 dias anteriores |
| `all` | Tudo | sem limite temporal |

Valor ausente ou inválido deve virar `today`.

### D2. Helper de período

Criar helper pequeno em `apps/dashboard/views.py`:

```python
METRICS_PERIOD_CHOICES = {
    "today": "Hoje",
    "7d": "7 dias",
    "30d": "30 dias",
    "all": "Tudo",
}

def _normalize_metrics_period(raw: str | None) -> str:
    return raw if raw in METRICS_PERIOD_CHOICES else "today"

def _metrics_period_bounds(period: str) -> tuple[datetime | None, datetime | None]:
    ...
```

Para `today`, reaproveitar `_local_day_bounds(timezone.localdate())`.
Para `7d`, start = início local de hoje - 6 dias; end = início local de amanhã.
Para `30d`, start = início local de hoje - 29 dias; end = início local de amanhã.
Para `all`, `(None, None)`.

### D3. Filtragem reutilizável

Criar helper para aplicar bounds quando existirem:

```python
def _filter_between(qs, field_name: str, start: datetime | None, end: datetime | None):
    if start is not None:
        qs = qs.filter(**{f"{field_name}__gte": start})
    if end is not None:
        qs = qs.filter(**{f"{field_name}__lt": end})
    return qs
```

Manter o helper local ao dashboard; não criar abstração global.

### D4. Cards principais por `created_at`

Renomear internamente os helpers para receber `period` ou `start/end` em vez de `day`.

`_compute_summary(period)`:

- base: `Case.objects.all()` filtrado por `created_at` no período;
- `total_today` pode permanecer como chave de contexto por compatibilidade de template, mas label deve mudar para `Total hoje`, `Total 7 dias`, `Total 30 dias`, `Total geral`.

`_compute_admission_flow(period)`:

- base: casos com `doctor_decision="accept"`, filtrados por `created_at` no período;
- para `all`, sem filtro de data.

### D5. Tempo médio por timestamp de conclusão da etapa

`_compute_average_times(period)` deve calcular cada média com uma base temporal própria:

1. `upload_to_decision`
   - casos com `doctor_decided_at__isnull=False`;
   - filtro do período em `doctor_decided_at`;
   - duração: `doctor_decided_at - created_at`.

2. `decision_to_schedule`
   - casos com `doctor_decided_at` e `appointment_decided_at` preenchidos;
   - filtro do período em `appointment_decided_at`;
   - duração: `appointment_decided_at - doctor_decided_at`.

3. `total_cycle`
   - anotar `completed_at_for_metrics = Coalesce(cleanup_completed_at, Subquery(CLEANUP_COMPLETED.timestamp))`;
   - filtro do período em `completed_at_for_metrics`;
   - duração: `completed_at_for_metrics - created_at`.

Essa regra evita excluir ciclos concluídos hoje apenas porque o caso foi criado antes.

### D6. Template

Substituir o form de data por botões/pills ou `<select>` simples. Preferência: botões para comparação rápida.

Exemplo conceitual:

```django
<div class="btn-group btn-group-sm" role="group" aria-label="Período das métricas">
  {% for value, label in metrics_period_choices %}
    <a href="?metrics_period={{ value }}" class="btn ...">{{ label }}</a>
  {% endfor %}
</div>
```

Como o dashboard possui outros filtros, os links devem preservar `status`, `date_from`, `date_to`, `attention` e `search` quando presentes.

Aceitável usar `<form method="get"><select name="metrics_period">...` se for mais simples preservar parâmetros.

### D7. Preservação em filtros e busca dinâmica

Atualizar hidden inputs e links:

- form de filtros da lista deve enviar `metrics_period`;
- link `Atenção necessária` deve preservar `metrics_period`;
- paginação no partial deve preservar `metrics_period` se já preservava `metrics_date`;
- JS de busca dinâmica deve continuar carregando a URL atual e não descartar `metrics_period`.

### D8. Compatibilidade com `metrics_date`

Não é necessário manter a UI de `metrics_date`. Para compatibilidade branda, se `metrics_date` ainda vier na query string, a implementação pode ignorar e usar `metrics_period`. Não criar redirecionamento.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Mudança semântica confundir usuários | Labels claros: `Período das métricas`; texto auxiliar no card `Tempo Médio`: `etapas concluídas no período` |
| `today` gerar médias vazias | Disponibilizar `7 dias`, `30 dias`, `Tudo`; default `today` por compatibilidade operacional |
| Query com subquery de evento ficar pesada | Apenas no cálculo agregado do dashboard; usar `cleanup_completed_at` preferencialmente e fallback por evento; sem endpoint dinâmico parcial para métricas |
| Quebrar busca dinâmica | Testes de preservação de `metrics_period` e regressão do partial |

## Rollback

Reverter mudanças em:

- `apps/dashboard/views.py`
- `templates/dashboard/index.html`
- `static/js/dashboard_search.js` se alterado
- `apps/dashboard/tests/test_dashboard.py`

Sem migration prevista.
