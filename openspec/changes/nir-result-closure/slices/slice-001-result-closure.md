# Slice 1: Resultado final + auto-transição + nome do paciente

## Objetivo

Adicionar seção de resultado final no case_detail, auto-transição para WAIT_R1_CLEANUP_THUMBS
nos submits do doctor e scheduler, e nome do paciente no topo.

## Arquivos a modificar

### 1. `apps/intake/views.py` — `case_detail`

Adicionar `result_info` ao contexto quando o caso tem resultado final:

```python
# Cálculo do resultado
result_info = None
terminal_with_result = case.status in (
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    CaseStatus.CLEANED,
)
if case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result:
    result_info = {
        "type": "accepted_scheduled",
        "appointment_at": case.appointment_at,
        "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
        "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
        "instructions": case.appointment_instructions or "",
    }
elif case.status == CaseStatus.APPT_DENIED:
    result_info = {"type": "appt_denied", "reason": case.appointment_reason}
elif case.status == CaseStatus.DOCTOR_DENIED:
    result_info = {"type": "doctor_denied", "reason": case.doctor_reason}
elif case.status == CaseStatus.FAILED:
    result_info = {"type": "failed"}
```

Adicionar `patient_name` extraído de `structured_data["patient"]["name"]`.

### 2. `templates/intake/case_detail.html`

- **Top Info**: usar `patient_name` como título (se disponível), fallback para extracted_text
- **Resultado Final**: nova seção card entre o stepper e a timeline:
  ```html
  {% if result_info %}
  <div class="card p-4 mb-4">
    <h5 class="mb-3">📋 Resultado Final</h5>
    {% if result_info.type == "accepted_scheduled" %}
      <!-- Badge AGENDAMENTO CONFIRMADO, data/hora, suporte, fluxo, instruções -->
    {% elif result_info.type == "appt_denied" %}
      <!-- Badge AGENDAMENTO NEGADO, motivo -->
    {% elif result_info.type == "doctor_denied" %}
      <!-- Badge RECUSADO PELO MÉDICO, motivo -->
    {% elif result_info.type == "failed" %}
      <!-- Badge FALHA NO PROCESSAMENTO -->
    {% endif %}
  </div>
  {% endif %}
  ```
  Alinhar visualmente com o mock.

### 3. `apps/doctor/views.py` — `doctor_submit`

Após FSM deny:
```python
if decision == "deny":
    case.final_reply_posted(user=request.user)
    case.save()
```

### 4. `apps/scheduler/views.py` — `scheduler_submit`

Após FSM confirm/deny:
```python
case.final_reply_posted(user=request.user)
case.save()
```

### 5. `apps/intake/tests/test_case_detail.py`

Testes novos:
- `test_result_shows_accepted_scheduled` — caso APPT_CONFIRMED mostra data + suporte
- `test_result_shows_appt_denied` — caso APPT_DENIED mostra motivo
- `test_result_shows_doctor_denied` — caso DOCTOR_DENIED mostra motivo
- `test_result_shows_failed` — caso FAILED mostra falha
- `test_result_hidden_for_in_progress` — caso WAIT_DOCTOR não mostra resultado
- `test_confirm_receipt_completes_case` — WAIT_R1_CLEANUP_THUMBS → CLEANED
- `test_patient_name_in_top_info` — nome do paciente aparece no topo

### 6. Reutilizar maps do doctor/scheduler

Mover `SUPPORT_FLAG_MAP` e `ADMISSION_FLOW_MAP` para um local compartilhado, ou
redefinir no intake views. Para manter simples, definir no intake views (2 constantes).

## Critérios de sucesso

- [ ] Resultado final visível para APPT_CONFIRMED, APPT_DENIED, DOCTOR_DENIED, FAILED
- [ ] Resultado final oculto para casos em andamento
- [ ] Doctor deny → auto-transição WAIT_R1_CLEANUP_THUMBS
- [ ] Scheduler confirm/deny → auto-transição WAIT_R1_CLEANUP_THUMBS
- [ ] Botão "Confirmar Recebimento" funciona (WAIT_R1_CLEANUP_THUMBS → CLEANED)
- [ ] Nome do paciente aparece no topo quando disponível
- [ ] Template alinhado visualmente com mock
- [ ] Testes: resultado (5), auto-transição (2), confirm (1), nome (1) = ~9
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 5
