# Slice 2: Decision view + form + FSM transitions

## Objetivo

Tela de decisão médica com formulário condicional, FSM transitions e modal de confirmação.

## Arquivos a criar

### 1. `apps/doctor/forms.py`

```python
class DoctorDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[("accept", "Aceitar"), ("deny", "Negar")])
    support_flag = forms.ChoiceField(choices=[("", "---"), ("none", "Nenhum"), ("anesthesist", "Anestesista"), ("anesthesist_icu", "Anestesista + UTI")], required=False)
    admission_flow = forms.ChoiceField(choices=[("", "---"), ("scheduled", "Agendamento"), ("immediate", "Vinda Imediata")], required=False)
    reason = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        # Se accept: support_flag + admission_flow obrigatórios
        # Se deny: reason obrigatório
```

### 2. `apps/doctor/views.py` — adicionar `doctor_decision` e `doctor_submit`

- `doctor_decision(request, case_id)` — GET: renderiza decision.html com contexto
- `doctor_submit(request, case_id)` — POST: valida form, persiste decisão, transiciona FSM

### 3. `templates/doctor/decision.html`

Alinhar com `demo-reference/doctor/decision.html`:
- Duas colunas: contexto (esquerda) + formulário (direita)
- Contexto: dados paciente, extração IA (summary boxes), PDF inline
- Formulário: radio accept/deny, seções condicionais (`.decision-section`)
- Modal Bootstrap de confirmação

### 4. `static/js/decision.js`

JS do mock adaptado:
- Toggle de seções accept/deny
- Validação client-side
- Modal de confirmação com resumo da decisão
- Feedback visual pós-submit

## FSM transitions

```python
# Submit
case.doctor_decision = decision
case.doctor_support_flag = support_flag
case.doctor_admission_flow = admission_flow
case.doctor_reason = reason
case.doctor_decide(decision=decision, user=request.user)
case.save()

if decision == "accept":
    case.ready_for_scheduler(user=request.user)
    case.save()
```

## Critérios de sucesso

- [ ] `/doctor/<uuid>/` retorna 200 com formulário para caso em WAIT_DOCTOR
- [ ] `/doctor/<uuid>/` retorna 404 para caso que não está em WAIT_DOCTOR
- [ ] Form valida: accept requer support_flag + admission_flow; deny requer reason
- [ ] POST accept → caso transita para WAIT_APPT (via DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT)
- [ ] POST deny → caso transita para DOCTOR_DENIED
- [ ] Campos doctor_decision, doctor_support_flag, doctor_admission_flow, doctor_reason persistidos
- [ ] CaseEvent DOCTOR_ACCEPT/DOCTOR_DENY registrado
- [ ] Modal de confirmação funciona
- [ ] Template alinhado visualmente com mock
- [ ] Testes: decision view (5), form validation (5), FSM (3), submit (5)
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 6
