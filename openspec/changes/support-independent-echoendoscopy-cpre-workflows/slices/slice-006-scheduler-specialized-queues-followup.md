# Slice 006 — Jornada CHD e pós-procedimento especializados

## Objetivo

Permitir que o CHD filtre/agende/consulte Ecoendoscopia e CPRE e registre seu pós-procedimento, mantendo uma agenda simples e o pareamento exclusivo EDA+Colonoscopia.

## Contexto necessário

- deltas `exam-type-work-queues` e specs canônicas de follow-up
- `design.md`: D12–D13
- scheduler queue/history e dashboard follow-up por `CaseProcedure`

## Requisitos verificáveis

- **R1:** Pendentes/Processados/Histórico CHD filtram por autorizado incluindo Eco/CPRE.
- **R2:** especializado confirmado tem um `appointment_at` e nunca label/contador casado.
- **R3:** todos os grupos CHD usam o mesmo universo do contador.
- **R4:** follow-up lista e grava desfecho por row especializada com label correto, sem mudar seu modelo.
- **R5:** busca/limite/ordering e fluxos sem agendamento continuam.
- **R6:** lógica de par binário residual é removida; igualdade exata define combinado.

## Escopo e blast radius

```yaml
expected_files:
  - apps/scheduler/views.py
  - templates/scheduler/_queue_content.html
  - templates/scheduler/historical_search.html
  - static/js/scheduler-queue.js
  - apps/dashboard/views.py
  - templates/dashboard/followup_form.html
  - apps/scheduler/tests/test_exam_type_filters.py
  - apps/scheduler/tests/test_specialized_scheduler.py
  - apps/dashboard/tests/test_followup_form_view.py
allowed_incidental_files:
  - apps/dashboard/tests/test_followup_history.py
file_cap: 10
out_of_scope:
  - NIR/doctor/analytics summary
  - mudança no modelo de follow-up
  - sala específica
```

Escalar antes de alterar migrations de follow-up ou cruzar o cap.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1–R3/R5/R6 | scheduler view/templates/JS | filtros/grupos/history/paired exact |
| R4 | dashboard follow-up | form/registro/histórico por Eco e CPRE |

## RED

1. Criar/ampliar testes de scheduler/follow-up antes do comando.
2. `uv run pytest apps/scheduler/tests/test_exam_type_filters.py apps/scheduler/tests/test_specialized_scheduler.py apps/dashboard/tests/test_followup_form_view.py -q`
3. RED deve falhar em assertions especializadas; path/collection não vale.

## GREEN / verificação local

- Mesmo comando RED com exit code 0.
- `uv run pytest apps/scheduler/tests/test_slice_004_paired_scheduler_appointment.py apps/dashboard/tests/test_followup_history.py -q`
- Ruff check/format nos Python alterados.

## Critérios de aceitação

- [ ] R1–R6 provados.
- [ ] Especializados nunca contam como casado.
- [ ] Follow-up model permaneceu inalterado.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-006-report.md`. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 006**: filas/histórico CHD, igualdade exata do agendamento casado e follow-up especializado, sem alterar o modelo de follow-up. Crie testes RED primeiro, alcance GREEN, refatore, rode gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push nem implemente superfícies NIR/manager; entregue o handoff ao parent e pare.
