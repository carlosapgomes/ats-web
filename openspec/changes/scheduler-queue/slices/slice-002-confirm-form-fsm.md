# Slice 2: Confirm view + form + FSM transitions

## Objetivo

Tela de confirmação de agendamento com formulário condicional, FSM transitions e modal.

## Arquivos a criar

### 1. `apps/scheduler/forms.py`

```python
class SchedulerDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[("confirm", "Confirmar"), ("deny", "Negar")])
    appointment_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    appointment_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    notes = forms.CharField(widget=forms.Textarea, required=False)
    reason = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        # Se confirm: appointment_date + appointment_time obrigatórios
        # Se deny: reason obrigatório
```

### 2. `apps/scheduler/views.py` — adicionar `scheduler_confirm` e `scheduler_submit`

- `scheduler_confirm(request, case_id)` — GET: renderiza confirm.html
- `scheduler_submit(request, case_id)` — POST: valida, persiste, transiciona FSM

### 3. `templates/scheduler/confirm.html`

Alinhar com `demo-reference/scheduler/confirm.html`:
- Duas colunas: contexto (esquerda) + formulário (direita)
- Esquerda: dados do caso + decisão médica (summary boxes)
- Direita: radio confirm/deny, seções condicionais (`.decision-section`)
  - Confirm: date picker + time picker + observações
  - Deny: motivo
- Modal de confirmação
- `{% extends "base.html" %}`

### 4. `static/js/scheduler_confirm.js`

JS do mock adaptado:
- Toggle de seções confirm/deny
- Validação client-side (date/time se confirm, reason se deny)
- Modal de confirmação com resumo (data formatada em PT-BR)
- Feedback visual pós-submit

## FSM transitions

```python
# Submit confirm
case.appointment_status = "confirmed"
case.scheduler = request.user
case.appointment_at = datetime.combine(date, time)
case.appointment_instructions = notes
case.appointment_decided_at = timezone.now()
case.scheduler_decide(appointment_status="confirmed", user=request.user)
case.save()

# Submit deny
case.appointment_status = "denied"
case.scheduler = request.user
case.appointment_reason = reason
case.appointment_decided_at = timezone.now()
case.scheduler_decide(appointment_status="denied", user=request.user)
case.save()
```

## Critérios de sucesso

- [ ] `/scheduler/<uuid>/` retorna 200 com formulário para caso em WAIT_APPT
- [ ] `/scheduler/<uuid>/` retorna 404 para caso que não está em WAIT_APPT
- [ ] Form valida: confirm requer date + time; deny requer reason
- [ ] POST confirm → caso transita para APPT_CONFIRMED
- [ ] POST deny → caso transita para APPT_DENIED
- [ ] Campos appointment_status, appointment_at, appointment_instructions, appointment_reason persistidos
- [ ] CaseEvent APPT_CONFIRMED/APPT_DENIED registrado
- [ ] Modal de confirmação funciona
- [ ] Template alinhado visualmente com mock
- [ ] Testes: confirm view (4), form validation (5), FSM (2), submit (4)
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 6
