# Slice 003 — EDA + Cápsula e EDA + Dilatação até o médico

## Objetivo

Entregar EDA + Cápsula e EDA + Dilatação como pacotes atômicos do upload NIR ao relatório médico: seleção pesquisável, detecção/reconciliação conservadora, policy EDA sob código original e local anatômico informativo da dilatação. EDA + GTT permanece fora do intake até o Slice 004.

## Contexto necessário

- `design.md`: D2–D6, D10 e D13;
- specs `procedure-combination-policy`, `exam-type-intake-routing`, `procedure-neutral-analysis` e `per-procedure-medical-decision`;
- catálogo/schema 4.0 entregues no Slice 001 e combobox do Slice 002;
- `apps/pipeline/scope_detection.py`, `procedure_reconciliation.py`, `orchestrator.py`, `prior_case.py`;
- `apps/cases/exam_profiles.py`, `priority_signals.py`;
- `apps/doctor/presenters.py`, `templates/doctor/decision.html`;
- testes de scope/reconciliation/policy/presenter existentes.

## Requisitos verificáveis

- **R1:** intake oferece exatamente `eda_capsule` e `eda_dilation` adicionais, sem flag nova, e persiste uma row por caso.
- **R2:** solicitação atual local de EDA + cápsula/dilatação reconcilia somente o pacote; história, negação, procedimento realizado, termo solto e dilatação de colédoco não criam pacote.
- **R3:** duas variações atuais ou variação + Colonoscopia seguem fail-closed à revisão NIR; nenhum valor é descartado.
- **R4:** ambas usam o profile EDA, mas recommendation/history/eventos mantêm o código exato; não emitem sinais legados equivalentes em writes 4.0.
- **R5:** `eda_dilation` extrai/ancora `esophagus|pylorus|duodenum|anastomosis|jejunum|other|unknown`; local ausente/inventado resulta `unknown` e nunca muda policy.
- **R6:** relatório médico mostra uma seção por pacote e o local traduzido apenas para EDA + Dilatação; EDA + Colonoscopia continua com duas rows. Badges das novas identidades usam o agrupamento CSS por família (edição única em `app.css` cobrindo os dez códigos de uma vez, sem cores por variação — os Slices 004/005 não voltam a tocar CSS).

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/intake/views.py
  - apps/intake/services.py
  - apps/pipeline/scope_detection.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/cases/exam_profiles.py
  - apps/cases/priority_signals.py
  - apps/doctor/presenters.py
  - templates/doctor/decision.html
  - static/css/app.css
  - apps/intake/tests/test_eda_package_intake.py
  - apps/pipeline/tests/test_eda_package_pipeline_v4.py
  - apps/doctor/tests/test_eda_package_report.py
allowed_incidental_files:
  - schema 4.0 se validator/detalhe previsto no Slice 001 precisar de ajuste mínimo
  - fixture/helper de teste compartilhado
out_of_scope:
  - EDA + GTT e revisão infecciosa
  - Retossigmoidoscopia
  - troca médica/correção NIR/filas/analytics
  - submit da decisão médica das novas identidades (deliberadamente postergado ao Slice 006; a branch só é implantável completa)
```

Cap esperado: até 15 arquivos pela travessia intake → pipeline → médico (inclui o agrupamento CSS por família). Se for necessária coluna nova, threshold, alias não aprovado ou mudança de FSM, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | intake/catalog options | `test_eda_package_intake.py` |
| R2–R3 | scope/reconciliation | `test_eda_package_pipeline_v4.py` |
| R4–R5 | profiles/orchestrator/schema/signals | testes pipeline 4.0 |
| R6 | presenter/template | `test_eda_package_report.py` |

## RED

Criar testes antes da implementação e executar:

```bash
uv run pytest \
  apps/intake/tests/test_eda_package_intake.py \
  apps/pipeline/tests/test_eda_package_pipeline_v4.py \
  apps/doctor/tests/test_eda_package_report.py -q
```

Falha esperada: opções ainda ausentes, detector/reconciliação não produzem pacotes, profile não resolve códigos e local não é projetado.

Casos RED mínimos: solicitação atual positiva de cada pacote; histórico/negação; “dilatação de colédoco”; pacote + Colonoscopia; piloro explícito; local ausente; excerpt inventado.

## GREEN / verificação local

```bash
uv run pytest \
  apps/intake/tests/test_eda_package_intake.py \
  apps/pipeline/tests/test_eda_package_pipeline_v4.py \
  apps/doctor/tests/test_eda_package_report.py \
  apps/pipeline/tests/test_scope_detection.py \
  apps/pipeline/tests/test_eda_preop_policy.py \
  apps/doctor/tests/test_presenter.py -q
uv run ruff check apps/intake apps/pipeline apps/cases apps/doctor
uv run ruff format --check apps/intake apps/pipeline apps/cases apps/doctor
```

## Critérios de aceitação

- [ ] R1: cada pacote cria uma row e nenhuma flag nova.
- [ ] R2/R3: detecção é local/conservadora e matriz falha fechada.
- [ ] R4: profile é reutilizado sem identidade/histórico/sinal duplicado.
- [ ] R5/R6: local ancorado é informativo e o relatório não muda policy.

## Handoff

Worker entrega somente Cápsula/Dilatação ponta a ponta, com relatório e comandos. Não habilitar GTT, não tocar filas/analytics e não iniciar Slice 004. Reviewer confere especialmente os negativos de dilatação e a ausência de segunda row.
