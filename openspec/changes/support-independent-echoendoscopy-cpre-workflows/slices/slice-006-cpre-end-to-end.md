# Slice 006 — CPRE de ponta a ponta

## Objetivo

Adicionar CPRE ao fluxo já generalizado: seleção sob flag própria, detecção/policy, avaliação direta ou troca médica e projeção CHD/NIR, sem alterar o comportamento entregue para Ecoendoscopia.

## Contexto necessário

- `design.md`: D3–D13
- todos os deltas do change relacionados a CPRE
- implementação aprovada dos Slices 001–005
- tests/prompt/schema/policy já genéricos de Eco

## Requisitos verificáveis

- **R1:** CPRE flag false oculta/rejeita; true permite upload/correção/reenvio singleton.
- **R2:** `CPRE` e nome completo em solicitação atual detectam; histórico/negação não; `EDA com/e CPRE` colapsa para CPRE.
- **R3:** policy aceita US abdominal/abdome superior/hepatobiliar, CT/RM abdominal/abdome superior ou MRCP com achado; demais evidências falham.
- **R4:** pendências agregadas forçam sugestão deny, mas médico pode aprovar.
- **R5:** médico pode trocar e aprovar CPRE sem rerun/repolicy; matriz bloqueia combinação incompatível.
- **R6:** CHD/NIR mostram CPRE, transformação, razões, evento/thread e agenda simples.
- **R7:** flags Eco e CPRE funcionam independentemente.

## Escopo e blast radius

```yaml
expected_files:
  - config/settings/base.py
  - apps/intake/services.py
  - templates/intake/intake_home.html
  - templates/intake/corrected_resubmission.html
  - apps/pipeline/scope_detection.py
  - apps/pipeline/llm1_service_v3.py
  - apps/doctor/forms.py
  - templates/doctor/decision.html
  - apps/intake/tests/test_specialized_procedure_intake.py
  - apps/pipeline/tests/test_cpre_pipeline_v3.py
  - apps/doctor/tests/test_specialized_procedure_swap.py
  - apps/scheduler/tests/test_specialized_scheduler.py
  - apps/intake/tests/test_specialized_final_response.py
allowed_incidental_files:
  - apps/llm/management/commands/seed_prompts.py
file_cap: 14
out_of_scope:
  - nova regra clínica além do rulebook aprovado
  - validade temporal
  - sala/agenda específica
  - processamento de anexos
```

Escalar se CPRE exigir branch exclusiva fora de profiles/catalog ou qualquer nova FSM.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R7 | settings/intake/templates | matriz das duas flags e POST manipulado |
| R2 | scope/prompt | aliases, precedência, histórico e negação |
| R3/R4 | contract/policy já existentes | integração do payload ao resultado LLM2 |
| R5 | doctor | troca + spies zero |
| R6 | scheduler/intake/system notice | cards, final reply, agenda e thread |

## RED

- `uv run pytest apps/pipeline/tests/test_cpre_pipeline_v3.py apps/intake/tests/test_specialized_procedure_intake.py apps/doctor/tests/test_specialized_procedure_swap.py -q -k cpre`
- Falha esperada: CPRE ainda não está exposta/detectada nas integrações.

## GREEN / verificação local

- Mesmo comando RED deve passar.
- `uv run pytest apps/pipeline/tests/test_specialized_preop_policy.py apps/scheduler/tests/test_specialized_scheduler.py apps/intake/tests/test_specialized_final_response.py -q`
- `uv run pytest apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py apps/doctor/tests/test_echoendoscopy_workflow.py -q`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Casos positivos cobrem US hepatobiliar e CPRM.
- [ ] Casos negativos cobrem sem sítio, sem achado e mera solicitação.
- [ ] Eco continua funcional com CPRE off/on.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-006-report.md` com tabela de modalidades e resultados. Parar antes dos filtros/analytics globais.
