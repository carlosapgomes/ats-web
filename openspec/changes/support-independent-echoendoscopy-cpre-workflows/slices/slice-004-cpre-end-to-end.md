# Slice 004 — CPRE de ponta a ponta

## Objetivo

Entregar CPRE em uma jornada completa NIR → pipeline → médico → CHD/NIR, incluindo aprovação direta e troca médica, reutilizando as fronteiras já aprovadas para Ecoendoscopia.

## Contexto necessário

- `design.md`: D3–D14
- todos os deltas relacionados a CPRE
- implementação aprovada dos Slices 001–003

## Requisitos verificáveis

- **R1:** flag CPRE false oculta/rejeita; true permite upload/correção/reenvio singleton, independentemente da flag Eco.
- **R2:** detector qualifica `CPRE`/nome completo; histórico/negação não detectam; `EDA com/e CPRE` colapsa somente quando a ocorrência prova vínculo.
- **R3:** policy aceita US/TC/RM/MRCP somente após verificação determinística: contexto único, aliases coerentes e predicado/heading estrito. Sem sítio/achado, solicitação com/sem `laudo`, agendamento, menção, conflito, duplicidade, contexto amplo, mismatch, excerpt inventado, `tracked_exams`-only ou anexo-only falham. Data antiga é preservada e não expira.
- **R4:** pendências agregadas forçam sugestão deny sem bloquear médico.
- **R5:** médico aprova diretamente ou troca/aprova CPRE sem rerun/repolicy; matriz bloqueia conjunto incompatível.
- **R6:** CHD/NIR mostram CPRE/transformação/razões/evento/thread e agenda simples.
- **R7:** fluxo Eco não regride.

## Escopo e blast radius

```yaml
expected_files:
  - config/settings/base.py
  - apps/intake/services.py
  - templates/intake/intake_home.html
  - templates/intake/corrected_resubmission.html
  - apps/pipeline/scope_detection.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/llm1_service_v3.py
  - apps/cases/exam_profiles.py
  - apps/pipeline/policy/eda_preop_policy.py
  - apps/doctor/forms.py
  - templates/doctor/decision.html
  - apps/intake/tests/test_specialized_procedure_intake.py
  - apps/pipeline/tests/test_cpre_pipeline_v3.py
  - apps/doctor/tests/test_specialized_procedure_swap.py
  - apps/scheduler/tests/test_specialized_scheduler.py
  - apps/intake/tests/test_specialized_final_response.py
allowed_incidental_files:
  - apps/llm/management/commands/seed_prompts.py
file_cap: 17
out_of_scope:
  - policy clínica não aprovada
  - validade temporal
  - sala específica
  - anexos no LLM
```

Escalar se CPRE exigir branch fora do catálogo/profile, nova FSM ou ampliação clínica.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1 | settings/intake | matriz das flags e POST manipulado |
| R2 | scope/reconciliation/prompt | vínculo, histórico, negação e independentes |
| R3/R4 | pipeline/policy/verificador | modalidade×sítio×achado, heading/predicado positivo e table-driven de solicitação, `solicita laudo`, agendado, menção, conflito de aliases, duplicidade, contexto amplo, mismatch, excerpt inventado, `tracked_exams`-only e anexo-only; data antiga e múltiplas falhas |
| R5/R6 | doctor/scheduler/intake | troca + spies zero + downstream |
| R7 | testes Eco | regressão ponta a ponta |

## RED

1. Criar `test_cpre_pipeline_v3.py` e ampliar os testes compartilhados antes do comando.
2. Rodar `uv run pytest apps/pipeline/tests/test_cpre_pipeline_v3.py apps/intake/tests/test_specialized_procedure_intake.py apps/doctor/tests/test_specialized_procedure_swap.py apps/scheduler/tests/test_specialized_scheduler.py apps/intake/tests/test_specialized_final_response.py -q -k cpre`.
3. RED deve falhar em assertions de CPRE, nunca por arquivo inexistente.

## GREEN / verificação local

- Mesmo comando RED com exit code 0.
- `uv run pytest apps/pipeline/tests/test_specialized_preop_policy.py apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py apps/doctor/tests/test_echoendoscopy_workflow.py -q`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] US hepatobiliar e CPRM positivos; ausência, intenção/menção, conflito/ambiguidade, mismatch e sem âncora negativos.
- [ ] Imagem qualificante com data antiga permanece aceita e conserva a data.
- [ ] Zero rerun/repolicy na troca.
- [ ] Eco continua funcional.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-004-report.md` com tabela clínica e evidência end-to-end. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 004**: CPRE ponta a ponta sob flag própria, reutilizando contratos aprovados de Eco e cobrindo matriz clínica US/TC/RM/CPRM, verificação determinística, decisão direta/troca e downstream. Crie testes RED primeiro, incluindo todos os negativos R3 e data antiga sem expiração; alcance GREEN, refatore, rode gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push, preserve Eco e não avance às filas; entregue o handoff ao parent e pare.
