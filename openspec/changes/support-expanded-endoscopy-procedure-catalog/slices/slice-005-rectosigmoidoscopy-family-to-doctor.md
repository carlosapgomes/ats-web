# Slice 005 — Família Retossigmoidoscopia até o médico

## Objetivo

Entregar Retossigmoidoscopia, Retossigmoidoscopia + Dilatação e Retossigmoidoscopia + Argônio como três identidades singleton do upload à avaliação médica, reutilizando exatamente o profile de Colonoscopia sem transformar identidade, histórico ou volume.

## Contexto necessário

- `design.md`: D2–D5, D10–D13;
- specs de catálogo, intake, análise e decisão;
- padrão de pacote/precedência do Slice 003;
- `apps/cases/exam_profiles.py`, `procedures.py`;
- `apps/pipeline/scope_detection.py`, `procedure_reconciliation.py`, `orchestrator.py`, policy procedure-neutral;
- templates/presenters médicos e testes de Colonoscopia existentes.

## Requisitos verificáveis

- **R1:** as três opções aparecem no combobox sem flag nova e cada upload cria exatamente uma row com o código selecionado.
- **R2:** nome canônico atual detecta a identidade exata; dilatação/argônio exigem vínculo local com Retossigmoidoscopia e contexto de solicitação atual; histórico/negação/achado isolado não contam.
- **R3:** variação suprime a base da mesma expressão; duas variações, qualquer Retossigmoidoscopia + Colonoscopia ou outro par seguem fail-closed.
- **R4:** as três executam os requisitos/thresholds/condicionais do profile Colonoscopia e retornam pendências/recomendação sob o código original.
- **R5:** o relatório médico apresenta uma única seção/decisão por identidade e não usa label Colonoscopia.
- **R6:** EDA + Colonoscopia permanece a única combinação e o fluxo Colonoscopia existente continua verde.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/intake/views.py
  - apps/intake/services.py
  - apps/cases/exam_profiles.py
  - apps/pipeline/scope_detection.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/orchestrator.py
  - apps/doctor/presenters.py
  - templates/doctor/decision.html
  - apps/intake/tests/test_rectosigmoidoscopy_intake.py
  - apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py
  - apps/doctor/tests/test_rectosigmoidoscopy_report.py
allowed_incidental_files:
  - schemas 4.0 somente para validator já previsto
  - fixtures/helpers de teste
out_of_scope:
  - detalhe anatômico novo para Retossigmoidoscopia + Dilatação
  - regra clínica adicional de argônio/dilatação
  - troca médica, filas e analytics
  - submit da decisão médica das novas identidades (deliberadamente postergado ao Slice 006; a branch só é implantável completa)
```

Não inventar siglas/aliases. Se surgir requisito clínico diferente de Colonoscopia ou persistência de detalhe adicional, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | intake/catalog | `test_rectosigmoidoscopy_intake.py` |
| R2–R3 | scope/reconciliation | testes positivos/negativos pipeline |
| R4 | profile/orchestrator/policy | comparação parametrizada com Colonoscopia |
| R5–R6 | presenter/template + regressão | `test_rectosigmoidoscopy_report.py` e testes combinados |

## RED

```bash
uv run pytest \
  apps/intake/tests/test_rectosigmoidoscopy_intake.py \
  apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py \
  apps/doctor/tests/test_rectosigmoidoscopy_report.py -q
```

Criar os testes antes. Falha esperada: opções/detecção/profiles/presenter ainda ausentes. Incluir RED para base, duas variações, história/negação, variação+Colonoscopia, duas variações e igualdade de resultado clínico com Colonoscopia.

## GREEN / verificação local

```bash
uv run pytest \
  apps/intake/tests/test_rectosigmoidoscopy_intake.py \
  apps/pipeline/tests/test_rectosigmoidoscopy_pipeline_v4.py \
  apps/doctor/tests/test_rectosigmoidoscopy_report.py \
  apps/pipeline/tests/test_colonoscopy_pipeline.py \
  apps/pipeline/tests/test_scope_detection.py \
  apps/doctor/tests/test_colonoscopy_doctor.py -q
uv run ruff check apps/intake apps/cases apps/pipeline apps/doctor
uv run ruff format --check apps/intake apps/cases apps/pipeline apps/doctor
```

## Critérios de aceitação

- [ ] R1: três singletons selecionáveis e persistidos sem flag.
- [ ] R2/R3: vínculo local/precedência/matriz são conservadores.
- [ ] R4: profile Colonoscopia é reutilizado sob identidade exata.
- [ ] R5/R6: relatório singleton e combinado existente preservado.

## Handoff

Worker implementa somente a família Retossigmoidoscopia até o médico e para. Reviewer verifica particularmente que compartilhar profile não transforma código/label e que nenhum `len == 2` novo foi introduzido.
