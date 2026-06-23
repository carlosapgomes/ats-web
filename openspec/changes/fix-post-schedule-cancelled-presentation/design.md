# Design: Corrigir apresentação de agendamento cancelado após intercorrência

## Estado atual

O fluxo de intercorrência pós-agendamento permite que um caso já `CLEANED`, aceito pelo médico e com agendamento confirmado, seja reaberto para `WAIT_APPT`. O scheduler responde a intercorrência com uma ação:

- `cancel` → define `appointment_status = "cancelled"`;
- `reschedule` → define `appointment_status = "confirmed"` e atualiza dados do agendamento;
- `maintain` → define `appointment_status = "confirmed"`;
- `deny` → preserva/define `appointment_status = "confirmed"`.

Depois o NIR confirma ciência e o caso volta para `CLEANED`.

A UI gerencial atual trata resultados principalmente por `doctor_decision`, `appointment_status="denied"`, `appointment_status="confirmed"` e estados terminais. Como `cancelled` não é tratado explicitamente, há dois bugs de apresentação:

1. `_compute_result()` no card da lista cai em `doctor_decision == "accept"` e mostra “Aguardando Agendamento”.
2. `dashboard_case_detail()` pode montar `result_info.type = "accepted_scheduled"` para caso terminal e o template mostra “Agendamento Confirmado”.

## Decisões

### D1. Corrigir apenas apresentação

Não alterar dados, FSM, serviços de intercorrência ou eventos. O estado persistido atual já representa corretamente o resultado operacional:

```text
appointment_status = "cancelled"
```

### D2. `cancelled` tem precedência sobre aceito/confirmado terminal

No dashboard, a ordem de decisão deve considerar `appointment_status == "cancelled"` antes de:

- `doctor_decision == "accept"` → “Aguardando Agendamento”;
- fallback terminal para `accepted_scheduled`.

### D3. Manter `confirmed` como agendamento confirmado

Casos pós-intercorrência respondidos com `reschedule`, `maintain` ou `deny` permanecem com `appointment_status="confirmed"`. Este change não cria distinção visual obrigatória entre esses subtipos, para manter o slice enxuto e evitar consulta extra a eventos quando o status atual já basta.

### D4. Novo tipo de resultado final no detalhe

Adicionar um `result_info.type` específico, por exemplo:

```python
{"type": "appt_cancelled", ...}
```

O template deve renderizar badge/descrição clara:

```text
Agendamento cancelado após intercorrência
```

Pode exibir data/hora e instruções originais/remanescentes se existirem, com rótulo neutro (“Agendamento anterior”), sem chamar de confirmado.

## Arquivos previstos

Slice único vertical e enxuto:

| Arquivo | Mudança |
| --- | --- |
| `openspec/changes/fix-post-schedule-cancelled-presentation/*` | artefatos do change |
| `apps/dashboard/tests/test_dashboard.py` | testes RED/GREEN de lista e detalhe |
| `apps/dashboard/views.py` | regra de apresentação do card e detalhe |
| `templates/intake/case_detail.html` | bloco visual do novo resultado |

## Testes recomendados

1. Card do dashboard para caso `CLEANED`, `doctor_decision="accept"`, `doctor_admission_flow="scheduled"`, `appointment_status="cancelled"` mostra cancelamento e não mostra “Aguardando Agendamento”.
2. Detalhe do mesmo caso mostra cancelamento e não mostra “Agendamento Confirmado”.
3. Caso equivalente com `appointment_status="confirmed"` continua mostrando “Agendamento Confirmado”.

## Rollback

Rollback simples via revert do commit. Como não há migração nem alteração de dados, o risco operacional é baixo.
