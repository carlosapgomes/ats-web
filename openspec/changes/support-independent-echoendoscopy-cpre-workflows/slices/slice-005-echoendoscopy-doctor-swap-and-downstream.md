# Slice 005 — Troca para Ecoendoscopia e comunicação downstream

## Objetivo

Entregar `trocar e aprovar como Ecoendoscopia` sem reanálise e projetar o autorizado/transformação ao CHD, NIR e thread sistêmica.

## Contexto necessário

- `design.md`: D10–D12
- deltas `per-procedure-medical-decision` e `exam-type-work-queues`
- `apps/doctor/forms.py`, `views.py`, `apps/cases/procedures.py`
- infraestrutura de system notices em `apps/cases/services.py`/signals
- cards/detalhes scheduler e resposta final intake

## Requisitos verificáveis

- **R1:** médico pode manter, negar ou trocar singleton para Eco e aprovar com uma justificativa.
- **R2:** troca persiste origem denied + destino approved atomicamente e valida matriz/lock/FSM/suporte/fluxo.
- **R3:** nenhum LLM, Q job ou policy é chamado; sugestão do destino não é exibida.
- **R4:** combinado pode ser integralmente substituído por Eco, mas combinação parcial incompatível é rejeitada sem write.
- **R5:** CHD agenda Eco uma vez, sem label casado nem regra de sala; todos os fluxos de admissão existentes continuam.
- **R6:** CHD/NIR veem detectado→autorizado, razões e badge principal Eco; resposta final compara três dimensões.
- **R7:** mudança cria evento dedicado e mensagem sistêmica idempotente sem `UserNotification`.

## Escopo e blast radius

```yaml
expected_files:
  - apps/doctor/forms.py
  - apps/doctor/views.py
  - templates/doctor/decision.html
  - apps/cases/procedures.py
  - apps/cases/services.py
  - apps/scheduler/views.py
  - templates/scheduler/_queue_content.html
  - apps/intake/views.py
  - templates/intake/case_detail.html
  - apps/doctor/tests/test_specialized_procedure_swap.py
  - apps/cases/tests/test_system_notices.py
  - apps/scheduler/tests/test_specialized_scheduler.py
  - apps/intake/tests/test_specialized_final_response.py
allowed_incidental_files:
  - templates/scheduler/confirm.html
file_cap: 14
out_of_scope:
  - rerun/repolicy do destino
  - CPRE
  - filtros/analytics completos
  - split de caso/agenda
```

Escalar imediatamente se qualquer callback da troca alcançar orchestrator, task queue ou policy.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1–R4 | doctor + procedure service | POST válido/inválido e spies negativos de LLM/policy/Q |
| R5/R6 | scheduler/intake | card, confirmação, final reply e fluxos admissionais |
| R7 | case service/system notices | evento único, mensagem idempotente, zero notification |

## RED

- `uv run pytest apps/doctor/tests/test_specialized_procedure_swap.py apps/cases/tests/test_system_notices.py apps/scheduler/tests/test_specialized_scheduler.py apps/intake/tests/test_specialized_final_response.py -q`
- Falha esperada: campos/validação/evento/projeções Eco ainda não existem.

## GREEN / verificação local

- Mesmo comando RED deve passar.
- `uv run pytest apps/doctor/tests/test_slice_003_procedure_decision.py apps/doctor/tests/test_operational_admission_flows.py apps/scheduler/tests/test_slice_004_paired_scheduler_appointment.py apps/intake/tests/test_slice_005_nir_correction_and_response.py -q`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Spy confirma zero rerun e zero avaliação de policy do destino.
- [ ] Operação inválida não deixa rows/eventos/FSM parciais.
- [ ] Mensagem é de sistema e não cria inbox global.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-005-report.md`, incluindo snapshot antes/depois da troca e contagem de chamadas automáticas igual a zero. Parar.
