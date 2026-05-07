# Slice 1: App scheduler + queue view + templates + auto-transition

## Objetivo

Criar o app `apps/scheduler/` com a view de fila, template alinhado ao mock,
e adicionar a transição automática `R3_POST_REQUEST → WAIT_APPT` no doctor submit.

## Arquivos a criar

### 1. `apps/scheduler/` (app scaffold)
- `__init__.py`
- `apps.py` (`SchedulerConfig`)
- `urls.py` — namespace `scheduler`
- `views.py` — `scheduler_queue` view

### 2. `config/urls.py`
Adicionar `path("scheduler/", include("apps.scheduler.urls"))`

### 3. `config/settings/base.py`
Adicionar `"apps.scheduler"` em `INSTALLED_APPS`

### 4. `templates/scheduler/queue.html`
Alinhar com `demo-reference/scheduler/queue.html`:
- Header "Agendamento" com nav pills (Pendentes / Confirmados Hoje / Histórico)
- Alert com contagem de solicitações
- Cards com `.patient-name`, `.summary-box` (diagnóstico, decisão médica, suporte, fluxo), `.waiting-time`
- Botão "Agendar" linkando para `scheduler:confirm`
- Seção "Confirmados Hoje" com tabela (paciente, registro, data agendada, suporte, status)
- `{% extends "base.html" %}` — não standalone!

### 5. `apps/doctor/views.py`
Adicionar `case.scheduler_request_posted(user=request.user)` após `ready_for_scheduler()`
no `doctor_submit`, para que o caso avance automaticamente de `R3_POST_REQUEST` para `WAIT_APPT`.

### 6. `apps/accounts/views.py`
Atualizar `home_view`: `scheduler` → `redirect("scheduler:queue")`

## Contexto dos cards (queue view)

```python
# Pendentes: WAIT_APPT
Case.objects.filter(status=CaseStatus.WAIT_APPT).order_by("created_at")

# Confirmados hoje
Case.objects.filter(
    status__in=[APPT_CONFIRMED, APPT_DENIED],
    scheduler=scheduler_user,
    events__event_type__startswith="APPT_",
    events__timestamp__date=today,
).distinct()
```

Cada card precisa exibir: dados paciente + diagnóstico + decisão médica + suporte + fluxo + tempo de espera.

Para exibir decisão médica, usar os campos já persistidos:
- `case.doctor_decision` → "ACEITAR" / "NEGAR" (usar DOCTOR_DECISION_MAP)
- `case.doctor_support_flag` → mapear (none/anesthesist/anesthesist_icu → PT)
- `case.doctor_admission_flow` → mapear (scheduled/immediate → PT)

## Critérios de sucesso

- [ ] App scheduler registrado e acessível
- [ ] `/scheduler/` retorna 200 para scheduler
- [ ] `/scheduler/` redireciona para login se não autenticado
- [ ] Queue template estende `base.html` e alinha com mock
- [ ] Cards mostram dados do paciente + decisão médica + tempo de espera
- [ ] `home_view` redireciona scheduler para `/scheduler/`
- [ ] Doctor submit agora avança até `WAIT_APPT` automaticamente
- [ ] Testes: queue view (4-5), auto-transition (2), redirect (1)
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 8
