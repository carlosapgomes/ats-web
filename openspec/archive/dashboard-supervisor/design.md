# Design: Dashboard Supervisor

## Decisões

### D1: Novo app `apps/dashboard/`

App dedicado para o dashboard. Segue o padrão dos demais apps.

### D2: URL namespace `dashboard:`

```
/dashboard/                → dashboard:index          (dashboard + tabela de casos)
/dashboard/<uuid:id>/      → dashboard:case_detail    (detalhe admin de qualquer caso)
```

### D3: Dashboard view — queries agregadas

Métricas do dia (ou período filtrado):

```python
from django.db.models import Count, Q, Avg, F
from django.db.models.functions import ExtractEpoch

# Total hoje
total = Case.objects.filter(created_at__date=today).count()

# Aceitos (APPT_CONFIRMED + WAIT_R1_CLEANUP_THUMBS + CLEANED com doctor_decision=accept)
accepted = Case.objects.filter(
    created_at__date=today,
    doctor_decision="accept",
).exclude(status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.FAILED]).count()

# Negados
denied = Case.objects.filter(
    created_at__date=today,
    status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.APPT_DENIED],
).count()

# Em andamento
in_progress = Case.objects.filter(
    created_at__date=today,
    status__in=[CaseStatus.NEW, CaseStatus.WAIT_DOCTOR, CaseStatus.WAIT_APPT, ...],
).count()

# Por etapa
waiting_doctor = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count()
waiting_appt = Case.objects.filter(status=CaseStatus.WAIT_APPT).count()
waiting_confirm = Case.objects.filter(status=CaseStatus.WAIT_R1_CLEANUP_THUMBS).count()

# Fluxo de admissão
scheduled_count = Case.objects.filter(doctor_admission_flow="scheduled").count()
immediate_count = Case.objects.filter(doctor_admission_flow="immediate").count()

# Tempo médio: upload → decisão médica
# (CaseEvent CASE_CREATED timestamp → CaseEvent DOCTOR_ACCEPT timestamp)
```

### D4: Tabela de casos com filtros e paginação

```python
qs = Case.objects.select_related("created_by").order_by("-created_at")

# Filtros
if status_filter:
    qs = qs.filter(status=status_filter)
if date_from:
    qs = qs.filter(created_at__date__gte=date_from)
if date_to:
    qs = qs.filter(created_at__date__lte=date_to)

paginator = Paginator(qs, 25)
```

### D5: Case detail admin — reutilizar lógica

Criar `dashboard:case_detail` que aceita qualquer UUID de caso (sem `created_by` filter).
Reutiliza o template `intake/case_detail.html` com contexto idêntico mas:
- Sem botão "Confirmar Recebimento" (`can_confirm_receipt=False`)
- Header com link "Voltar para Dashboard"

### D6: Access control — manager + admin

Decorator ou verificação inline: usuário precisa ter `active_role` em `("manager", "admin")`.

### D7: home_view redirect

Atualizar `apps/accounts/views.py`: manager e admin → `redirect("dashboard:index")`.

### D8: Tempos médios via CaseEvent

Calcular tempos médios a partir dos CaseEvents:
- Upload → Decisão Médica: diff entre `CASE_CREATED` e `DOCTOR_ACCEPT`/`DOCTOR_DENY`
- Decisão → Agendamento: diff entre `DOCTOR_ACCEPT` e `APPT_CONFIRMED`/`APPT_DENIED`
- Ciclo Total: diff entre `CASE_CREATED` e `FINAL_REPLY_POSTED`

Usar `CaseEvent.objects.filter(...)` com aggregation. Se não houver eventos suficientes,
mostrar "—" em vez de calcular.

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/dashboard/__init__.py` | novo |
| `apps/dashboard/apps.py` | novo |
| `apps/dashboard/urls.py` | novo |
| `apps/dashboard/views.py` | novo |
| `templates/dashboard/index.html` | novo |
| `config/urls.py` | modificado |
| `config/settings/base.py` | modificado (INSTALLED_APPS) |
| `apps/accounts/views.py` | modificado (home_view redirect) |

## Orçamento de testes

- Testes de dashboard view (auth, métricas, filtros, paginação): ~10
- Testes de case detail admin: ~3
- Testes de redirect home_view: ~2
- Total estimado: ~15 novos testes
