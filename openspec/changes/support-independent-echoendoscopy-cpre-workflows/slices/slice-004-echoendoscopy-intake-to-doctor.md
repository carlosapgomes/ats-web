# Slice 004 — Ecoendoscopia do intake à avaliação médica

## Objetivo

Permitir que o NIR declare Ecoendoscopia sob flag, que o pipeline aplique precedência/policy 3.0 e que o médico receba badge, sugestão e pendências agregadas próprias do procedimento.

## Contexto necessário

- `design.md`: D3–D9 e D14
- deltas `exam-type-intake-routing` e `procedure-neutral-analysis`
- intake services/views/templates e correction/resubmission atuais
- scope detection, priority signals e presenter/relatório médico

## Requisitos verificáveis

- **R1:** flag false oculta/rejeita Eco; true permite upload/correção/reenvio com uma row declarada.
- **R2:** aliases e frases `EDA com/e ecoendoscopia` detectam somente Eco atual; histórico/negação não detectam.
- **R3:** declaração=detecção segue ao médico; mismatch retorna ao NIR sem auto-upgrade especializado.
- **R4:** policy mostra todas as pendências e sugere deny quando TC/RM qualificante falta.
- **R5:** relatório médico identifica Eco como procedimento, não como EDA+sinal duplicado, e avisa que anexos não participaram.
- **R6:** schema 1.1/2.0 com sinal/subtipo Eco continua legível sem backfill.

## Escopo e blast radius

```yaml
expected_files:
  - config/settings/base.py
  - apps/intake/services.py
  - apps/intake/views.py
  - templates/intake/intake_home.html
  - templates/intake/corrected_resubmission.html
  - apps/pipeline/scope_detection.py
  - apps/cases/priority_signals.py
  - apps/doctor/presenters.py
  - templates/doctor/decision.html
  - apps/intake/tests/test_specialized_procedure_intake.py
  - apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py
  - apps/doctor/tests/test_echoendoscopy_workflow.py
allowed_incidental_files:
  - config/settings/test.py
  - apps/pipeline/orchestrator.py
file_cap: 14
out_of_scope:
  - troca médica para Eco
  - CHD/final reply especializados
  - filtros/analytics globais
  - CPRE no intake
```

O cap maior é justificado pela primeira entrega vertical NIR→pipeline→médico. Escalar antes de excedê-lo ou tocar anexos/FSM.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1 | settings/intake | GET/POST flag off/on, correção e reenvio |
| R2/R3 | scope/reconciliation/orchestrator | frases positivas, históricas e mismatch |
| R4 | policy já criada + pipeline | sugestão deny/accept e lista completa |
| R5/R6 | priority signals/presenter/template | sem badge duplicado em 3.0; legado renderiza |

## RED

- `uv run pytest apps/intake/tests/test_specialized_procedure_intake.py apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py apps/doctor/tests/test_echoendoscopy_workflow.py -q`
- Falha esperada: flag/radio/detector/presenter Eco independente ainda não existem.

## GREEN / verificação local

- Mesmo comando RED deve passar.
- `uv run pytest apps/intake/tests/test_exam_type_intake.py apps/intake/tests/test_exam_type_correction.py apps/pipeline/tests/test_scope_detection.py apps/doctor/tests/test_presenter.py -q`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R6 provados.
- [ ] Eco chega a `WAIT_DOCTOR` como singleton.
- [ ] Falta de imagem nega só a sugestão, não remove ação médica.
- [ ] Nenhum anexo é enviado ao pipeline.
- [ ] CPRE permanece oculta.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-004-report.md` com evidência flag off/on e dois casos de policy. Parar antes do downstream.
