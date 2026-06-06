# Design: Aba Processados Hoje na fila do agendador

## Estado atual

### Template

`templates/scheduler/queue.html` renderiza pills estáticos:

```html
<span class="nav-link active ...">Pendentes</span>
<span class="nav-link">Confirmados Hoje</span>
<span class="nav-link">Histórico</span>
```

`templates/scheduler/_queue_content.html` renderiza pendentes, vindas imediatas para ciência operacional e, abaixo, uma tabela `Confirmados Hoje`.

### Query atual

`apps/scheduler/views.py::_scheduler_queue_context()` usa:

```python
Case.objects.filter(
    status__in=[CaseStatus.APPT_CONFIRMED, CaseStatus.APPT_DENIED],
    events__event_type__startswith="APPT_",
    events__timestamp__date=today,
)
```

Problemas:

- não filtra explicitamente pelo agendador logado;
- depende de status FSM transitório;
- usa data de evento com `date.today()` em vez de bounds do dia local timezone-aware;
- chama a lista de `Confirmados Hoje`, embora inclua recusas (`APPT_DENIED`).

## Decisões

### D1. Label: `Processados Hoje`

Usar `Processados Hoje` em vez de `Confirmados Hoje`.

Motivo: o termo cobre confirmação e recusa. `Atendidos Hoje` pode ser ambíguo no contexto hospitalar, e `Avaliados Hoje` se confunde com avaliação médica.

### D2. Abas por query string simples

Usar `?tab=pending` e `?tab=processed` em `/scheduler/`.

Rotas:

```text
/scheduler/                         → Pendentes (default)
/scheduler/?tab=pending             → Pendentes
/scheduler/?tab=processed           → Processados Hoje
/scheduler/partials/queue/?tab=...  → partial respeitando aba ativa
```

### D3. Remover `Histórico`

Remover o pill `Histórico` de `templates/scheduler/queue.html`.

Histórico multi-dia permanece fora de escopo.

### D4. Query de processados hoje baseada em campos imutáveis

Criar helper de bounds do dia local, equivalente ao usado no dashboard:

```python
def _local_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    local_day = day or timezone.localdate()
    current_tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(local_day, time.min), current_tz)
    end = start + timedelta(days=1)
    return start, end
```

Consultar casos processados hoje pelo agendador logado:

```python
Case.objects.filter(
    scheduler=scheduler_user,
    appointment_status__in=["confirmed", "denied"],
    appointment_decided_at__gte=start,
    appointment_decided_at__lt=end,
).select_related("doctor", "scheduler", "created_by").order_by("-appointment_decided_at")
```

Não depender de `status__in=[APPT_CONFIRMED, APPT_DENIED]`.

### D5. Contexto separado por aba ativa

`_scheduler_queue_context(request/user)` deve incluir:

```python
{
    "active_tab": "pending" | "processed",
    "pending_cases": [...],
    "immediate_notice_cases": [...],
    "processed_today": [...],
    "pending_count": ...,
    "immediate_notice_count": ...,
    "processed_today_count": ...,
    "total_notice_count": ...,
}
```

Contadores podem ser calculados independentemente da aba para alimentar badges. As listas devem ser renderizadas conforme `active_tab`.

### D6. Partial renderiza somente a aba ativa

`templates/scheduler/_queue_content.html` deve renderizar:

- se `active_tab == "pending"`: alerta, vindas imediatas para ciência operacional e cards `WAIT_APPT`;
- se `active_tab == "processed"`: cards de processados hoje.

Remover a tabela antiga `Confirmados Hoje` abaixo dos pendentes.

### D7. Detalhe read-only para agendador

Adicionar rotas no namespace scheduler:

```text
/scheduler/processed/<uuid:case_id>/      → scheduler:processed_detail
/scheduler/processed/<uuid:case_id>/pdf/  → scheduler:processed_pdf
```

Regras de autorização:

- `@login_required`
- `@role_required("scheduler")`
- caso deve ter `scheduler=request.user` e `appointment_status` em `confirmed/denied`;
- se não for caso processado pelo agendador logado, retornar 404.

Não restringir o detalhe apenas ao dia atual: a lista é de hoje, mas um link recém-renderizado deve continuar válido após cruzar meia-noite.

### D8. Reuso do detalhe supervisor/admin

Renderizar o mesmo template compartilhado usado pelo dashboard:

```text
templates/intake/case_detail.html
```

Parametrizar para agendador:

```python
"show_intake_nav": False,
"back_url": reverse("scheduler:queue") + "?tab=processed",
"back_label": "← Voltar aos processados hoje",
"pdf_url": reverse("scheduler:processed_pdf", args=[case.case_id]),
"can_confirm_receipt": False,
```

A view deve montar contexto equivalente ao `dashboard_case_detail`, incluindo:

- `events` enriquecidos;
- `steps` e `current_step_idx`;
- `status_label` e `status_css`;
- `result_info`;
- `patient_name`;
- `origin_unit`.

Implementação aceitável no slice:

1. **Preferida:** extrair helper compartilhado de detalhe read-only para reduzir duplicação entre dashboard, médico e scheduler.
2. **Aceitável para slice enxuto:** replicar contexto mínimo no app scheduler usando os mesmos maps importados de `apps.intake.views`, justificando no relatório.

### D9. Cards de processados hoje

Cada card deve mostrar:

- paciente;
- registro;
- idade/sexo;
- horário do processamento (`appointment_decided_at`);
- status do processamento (`Confirmado` ou `Recusado`);
- data/hora agendada se confirmado;
- motivo se recusado;
- suporte/fluxo;
- médico responsável;
- botão `Ver detalhes`.

## Arquivos previstos

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `apps/scheduler/views.py` | modificado | aba ativa, query correta, detalhe read-only, PDF |
| `apps/scheduler/urls.py` | modificado | rotas `processed_detail` e `processed_pdf` |
| `templates/scheduler/queue.html` | modificado | pills como links, remover Histórico, `Processados Hoje` |
| `templates/scheduler/_queue_content.html` | modificado | render condicional por aba, cards processados |
| `apps/scheduler/tests/test_views.py` | modificado | testes de abas, query, detalhe e autorização |

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Nome da aba não refletir negócio | Usar `Processados Hoje`, neutro para confirmado/recusado |
| Agendador acessar caso de outro agendador | Query com `scheduler=request.user`; teste 404 |
| Dia UTC vs local | Usar bounds timezone-aware do dia local |
| Polling voltar para pendentes | `hx-get` com `?tab={{ active_tab }}` |
| Duplicação de detalhe read-only | Preferir helper compartilhado; se não, documentar duplicação no relatório |
