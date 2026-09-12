# Slice 003 — Ecoendoscopia do médico ao CHD/NIR

## Objetivo

Entregar aprovação direta ou `trocar e aprovar como Ecoendoscopia`, sem reanálise, e projetar autorizado/transformação ao CHD, NIR e thread sistêmica.

## Contexto necessário

- `design.md`: D10–D12
- deltas de decisão médica e work queues
- doctor form/service, system notices e projeções scheduler/intake

## Requisitos verificáveis

- **R1:** singleton pode ser mantido, negado ou trocado/aprovado como Eco com uma justificativa.
- **R2:** origem denied + destino approved persistem atomicamente com matriz/lock/FSM/suporte/fluxo válidos.
- **R3:** troca não chama LLM, Q ou policy e não mostra sugestão/checklist do destino.
- **R4:** substituição integral de combinado por Eco é aceita; conjunto parcial incompatível é rejeitado sem write.
- **R5:** CHD agenda Eco uma vez, sem label casado ou validação de sala; fluxos existentes permanecem.
- **R6:** CHD/NIR mostram detectado→autorizado, razões e badge Eco; resposta final compara três dimensões.
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
  - rerun/repolicy
  - CPRE
  - filtros globais
  - split de caso/agenda
```

Escalar se qualquer callback da troca alcançar orchestrator/task/policy.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1–R4 | doctor/procedure service | POST válido/inválido + spies negativos |
| R5/R6 | scheduler/intake | card, confirmação, final reply e admission flows |
| R7 | case service/notices | evento único, idempotência e zero notification |

## RED

1. Criar/ajustar os quatro testes antes do comando.
2. Rodar `uv run pytest apps/doctor/tests/test_specialized_procedure_swap.py apps/cases/tests/test_system_notices.py apps/scheduler/tests/test_specialized_scheduler.py apps/intake/tests/test_specialized_final_response.py -q -k echoendoscopy`.
3. RED válido é falha de assertion; path ausente/collection error não vale.

## GREEN / verificação local

- Mesmo comando RED com exit code 0.
- `uv run pytest apps/doctor/tests/test_slice_003_procedure_decision.py apps/doctor/tests/test_operational_admission_flows.py apps/scheduler/tests/test_slice_004_paired_scheduler_appointment.py apps/intake/tests/test_slice_005_nir_correction_and_response.py -q`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Spies confirmam zero rerun/repolicy.
- [ ] Falha estrutural não deixa write parcial.
- [ ] Mensagem sistêmica não cria inbox.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-003-report.md` com snapshot da troca e contagem zero de automações. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 003**: decisão/troca médica de Ecoendoscopia e projeções CHD/NIR, garantindo persistência atômica, `trocar e aprovar`, zero rerun/repolicy, evento e mensagem idempotente sem `UserNotification`. Crie testes RED antes do código, alcance GREEN, refatore, rode os gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push e não implemente CPRE nem filas amplas; entregue o handoff ao parent e pare.
