# Design: Resultado Final NIR + Fechamento

## Decisões

### D1: Resultado final inline no case_detail

Adicionar seção "Resultado Final" no template `intake/case_detail.html` que mostra
dados específicos por tipo de resultado. A view `case_detail` já calcula `can_confirm_receipt`
para o status `WAIT_R1_CLEANUP_THUMBS`. Vamos estender o contexto com dados do resultado.

### D2: Resultado calculado na view

Na view `case_detail`, quando o status é terminal ou pós-terminal, calcular:

```python
result_info = None
if case.status in (APPT_CONFIRMED, WAIT_R1_CLEANUP_THUMBS, CLEANED):
    result_info = {
        "type": "accepted_scheduled",
        "appointment_at": case.appointment_at,
        "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, ...),
        "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, ...),
        "instructions": case.appointment_instructions,
    }
elif case.status == APPT_DENIED:
    result_info = {"type": "appt_denied", "reason": case.appointment_reason}
elif case.status == DOCTOR_DENIED:
    result_info = {"type": "doctor_denied", "reason": case.doctor_reason}
elif case.status == FAILED:
    result_info = {"type": "failed"}
```

### D3: Auto-transição final_reply_posted

Os casos em `APPT_CONFIRMED`, `APPT_DENIED`, `DOCTOR_DENIED`, `FAILED` precisam
transitar automaticamente para `WAIT_R1_CLEANUP_THUMBS` para que o NIR possa ver
o resultado e confirmar.

**Onde chamar**: na view `case_detail` do NIR, ao detectar que o caso está em um
status terminal mas ainda não em `WAIT_R1_CLEANUP_THUMBS`, chamar `final_reply_posted()`
automaticamente na primeira vez que o NIR acessar. Isso garante que o resultado
fica visível imediatamente.

Alternativa: chamar automaticamente nos submits do doctor e scheduler, mas isso
pode ser prematuro se o NIR ainda não viu o resultado intermediário.

**Decisão**: chamar nos submits. O caso é que o NIR já viu "Aguardando médico" ou
"Aguardando agendamento" — quando o resultado chega, podemos avançar direto.
Chamar no `doctor_submit` (deny) e no `scheduler_submit` (confirm/deny).

Para `FAILED`, chamar no `orchestrator` (pipeline) — mas isso é Phase 2 (já feito).
Verificar se o pipeline já transita para `FAILED`. Se não, adicionar lá.

### D4: Top Info com nome do paciente

O mock mostra "Maria Silva dos Santos" no topo. Atualmente o template mostra
`extracted_text|truncatechars:60`. Alinhar com o mock: extrair nome de
`structured_data["patient"]["name"]` e usar como título.

### D5: Eventos doctor/scheduler na timeline

Já existem labels para `DOCTOR_ACCEPT`, `DOCTOR_DENY`, `APPT_CONFIRMED`, `APPT_DENIED`.
Verificar se estão completos. Adicionar payload enrichment: mostrar suporte + fluxo
na decisão médica, data agendada na confirmação.

## Arquivos previstos

| Arquivo | Tipo |
|---------|------|
| `apps/intake/views.py` | modificado (resultado final + auto-transição) |
| `templates/intake/case_detail.html` | modificado (resultado final + nome paciente) |
| `apps/doctor/views.py` | modificado (final_reply_posted no deny) |
| `apps/scheduler/views.py` | modificado (final_reply_posted no confirm/deny) |
| `apps/intake/tests/test_case_detail.py` | modificado (testes resultado final) |

## Orçamento de testes

- Testes de resultado por tipo (scheduled/deny doctor/deny scheduler/failed): ~6
- Testes de auto-transição (doctor deny → WAIT_R1_CLEANUP, scheduler confirm → WAIT_R1_CLEANUP): ~3
- Testes de confirm receipt (todos os cenários): ~3
- Testes de nome do paciente no top info: ~1
- Total estimado: ~13 novos testes
