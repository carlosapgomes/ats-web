# Slice 002 — Ecoendoscopia do NIR à avaliação médica

## Objetivo

Permitir seleção de Ecoendoscopia sob flag e entregar o caso como singleton detectado, analisado e visível na fila/relatório médico, com proveniência suficiente para a precedência EDA+Eco.

## Contexto necessário

- `design.md`: D3–D9 e D14
- deltas de intake, combinação e análise neutra
- implementação aprovada do Slice 001
- intake/correction/resubmission, scope detection, priority signals e presenter médico

## Requisitos verificáveis

- **R1:** flag false oculta/rejeita Eco; true cria exatamente uma row declarada, inclusive em correção/reenvio.
- **R2:** detector produz ocorrências qualificadas com tipo, contexto atual/histórico/negação, evidence id/trecho e vínculo `com/e EDA`.
- **R3:** `EDA com/e ecoendoscopia` colapsa para Eco; duas solicitações independentes incompatíveis não são colapsadas só pelo conjunto.
- **R4:** declaração=detecção segue ao médico; mismatch retorna ao NIR sem auto-upgrade especializado.
- **R5:** TC/RM só qualifica com contexto único ancorado, modalidade/anatomia rederivadas e predicado/heading estrito de resultado. Solicitação com/sem `laudo`, agendamento, mera menção, mismatch, aliases conflitantes, contexto duplicado/amplo, excerpt inventado, `tracked_exams`-only ou anexo-only forçam deny.
- **R6:** relatório identifica Eco, avisa que anexos não participaram e não duplica sinal `echoendoscopy` em 3.0.
- **R7:** payload legado 1.1/2.0 continua legível sem nova row/backfill.

## Escopo e blast radius

```yaml
expected_files:
  - config/settings/base.py
  - apps/intake/services.py
  - apps/intake/views.py
  - templates/intake/intake_home.html
  - templates/intake/corrected_resubmission.html
  - apps/pipeline/scope_detection.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/pipeline/llm1_service_v3.py
  - apps/pipeline/imaging_evidence.py
  - apps/cases/exam_profiles.py
  - apps/pipeline/policy/eda_preop_policy.py
  - apps/cases/priority_signals.py
  - apps/doctor/presenters.py
  - templates/doctor/decision.html
  - apps/intake/tests/test_specialized_procedure_intake.py
  - apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py
  - apps/pipeline/tests/test_specialized_preop_policy.py
  - apps/doctor/tests/test_echoendoscopy_workflow.py
allowed_incidental_files:
  - config/settings/test.py
file_cap: 20
out_of_scope:
  - troca médica especializada
  - CHD/resposta final especializada
  - CPRE no intake
  - processamento de anexos
```

Escalar se proveniência não puder ser transportada sem mudar o contrato desenhado, ou antes de tocar FSM/anexos.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1 | settings/intake/templates | GET/POST flag off/on, correction e resubmission |
| R2–R4 | scope/reconciliation/orchestrator | expressão vinculada, solicitações independentes, histórico, negação e mismatch |
| R5 | `imaging_evidence.py`/pipeline/policy | resultado real por heading/predicado; table-driven de solicitação, `solicita laudo`, agendado, menção, mismatch, aliases conflitantes, ocorrência duplicada, contexto amplo, excerpt inventado, `tracked_exams`-only e anexo-only |
| R6/R7 | signal/presenter/template | sem duplicação 3.0; legado renderiza sem row nova |

## RED

1. Criar os quatro testes novos esperados antes de executá-los.
2. Rodar `uv run pytest apps/intake/tests/test_specialized_procedure_intake.py apps/pipeline/tests/test_echoendoscopy_pipeline_v3.py apps/pipeline/tests/test_specialized_preop_policy.py apps/doctor/tests/test_echoendoscopy_workflow.py -q -k 'echoendoscopy or legacy'`.
3. RED válido: assertions de flag/proveniência/precedência/relatório falham. Erro de caminho ou collection não vale.

## GREEN / verificação local

- Mesmo comando RED com exit code 0.
- `uv run pytest apps/intake/tests/test_exam_type_intake.py apps/intake/tests/test_exam_type_correction.py apps/pipeline/tests/test_scope_detection.py apps/doctor/tests/test_presenter.py -q`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Precedência usa ocorrência/vínculo, não somente set.
- [ ] Eco chega a `WAIT_DOCTOR` como singleton.
- [ ] Falta, intenção/agendamento/menção, conflito/ambiguidade, mismatch ou excerpt sem âncora negam apenas sugestão.
- [ ] Policy recebe somente evidência aprovada pelo verificador determinístico.
- [ ] Testes provam que texto de anexo não é consultado/enviado.
- [ ] CPRE permanece oculta.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-002-report.md` com evidência da proveniência e flag. Parar.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 002**: Ecoendoscopia do intake NIR até `WAIT_DOCTOR`, incluindo flag, aliases, precedência com proveniência por ocorrência e verificação determinística de imagem no relatório principal. Crie primeiro os testes RED, incluindo todos os negativos R5; alcance GREEN, refatore, rode os gates e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push e não implemente troca/downstream nem CPRE; entregue o handoff ao parent e pare.
