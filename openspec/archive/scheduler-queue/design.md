# Design: Fila do Agendador (Scheduler Queue)

## Decisões

### D1: Novo app `apps/scheduler/`

App dedicado para views do agendador. Mesmo padrão de `apps/doctor/` com
`@login_required` (role check no decorator ou middleware).

### D2: URL namespace `scheduler:`

```
/scheduler/                 → scheduler:queue       (lista de casos WAIT_APPT)
/scheduler/<uuid:id>/       → scheduler:confirm     (tela de confirmação)
/scheduler/<uuid:id>/submit/ → scheduler:submit      (POST da decisão)
```

### D3: Transição automática R3_POST_REQUEST → WAIT_APPT

Quando o médico aceita (`doctor_submit`), hoje fazemos:
```python
case.ready_for_scheduler(user=request.user)  # → R3_POST_REQUEST
```

Precisamos adicionar logo após:
```python
case.scheduler_request_posted(user=request.user)  # → WAIT_APPT
```

Assim o caso fica disponível na fila do scheduler imediatamente após o médico aceitar.
Isso é uma mudança em `apps/doctor/views.py` — 1 linha.

### D4: Queue view — query e contexto

Busca casos em `WAIT_APPT`, ordenados por `created_at`. Para cada caso:
- Patient name/age/gender (via `structured_data`)
- Diagnóstico (via `summary_text`)
- Decisão médica (`doctor_decision`, `doctor_support_flag`, `doctor_admission_flow`)
- Tempo de espera (desde `created_at`)

Confirmados hoje: cases com `APPT_CONFIRMED`/`APPT_DENIED` decididos pelo scheduler hoje.

### D5: Confirm view — duas colunas

Esquerda (contexto):
- Dados do paciente (tabela)
- Decisão médica (summary boxes: decisão, suporte, fluxo)

Direita (formulário):
- Form Django: `decision` (confirm/deny), `appointment_date`, `appointment_time`, `notes`, `reason`
- Validação condicional: date+time obrigatórios se confirm; reason obrigatório se deny
- JS: toggle de seções + modal de confirmação

### D6: Submit — FSM transition + persist

```python
case.appointment_status = "confirmed"  # or "denied"
case.scheduler = request.user
case.appointment_decided_at = timezone.now()

if decision == "confirm":
    case.appointment_at = datetime.combine(date, time)
    case.appointment_instructions = notes
    case.scheduler_decide(appointment_status="confirmed", user=request.user)
else:
    case.appointment_reason = reason
    case.scheduler_decide(appointment_status="denied", user=request.user)

case.save()
```

### D7: home_view redirect para scheduler

Atualizar `apps/accounts/views.py`: `scheduler` → `redirect("scheduler:queue")`.

### D8: Intranet guard

`scheduler` é papel restrito à intranet (já configurado no middleware).
O decorator `@login_required` basta — o middleware já bloqueia IPs externos.

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/scheduler/__init__.py` | novo |
| `apps/scheduler/apps.py` | novo |
| `apps/scheduler/views.py` | novo |
| `apps/scheduler/forms.py` | novo |
| `apps/scheduler/urls.py` | novo |
| `templates/scheduler/queue.html` | novo |
| `templates/scheduler/confirm.html` | novo |
| `static/js/scheduler_confirm.js` | novo |
| `config/urls.py` | modificado (incluir scheduler urls) |
| `config/settings/base.py` | modificado (INSTALLED_APPS) |
| `apps/doctor/views.py` | modificado (adicionar scheduler_request_posted) |
| `apps/accounts/views.py` | modificado (home_view redirect) |

## Orçamento de testes

- Testes de view (queue + confirm + submit): ~12
- Testes de form (validação condicional): ~5
- Testes de FSM (scheduler_decide): ~3
- Testes de transição automática (doctor submit → WAIT_APPT): ~2
- Testes de redirect home_view: ~1
- Total estimado: ~23 novos testes
