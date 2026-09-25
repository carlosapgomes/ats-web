# Slice 006 — Decisão, troca e histórico médico pelo catálogo

## Objetivo

Permitir ao médico aprovar/negar qualquer identidade, incluir ou substituir por destino canônico via combobox e consultar histórico por código exato. Operações permanecem atômicas, sem rerun/repolicy, e EDA + Colonoscopia mantém duas decisões independentes.

## Contexto necessário

- `design.md`: D2, D9–D11;
- specs `per-procedure-medical-decision`, `searchable-procedure-selection` e matriz do catálogo;
- `apps/doctor/forms.py`, `views.py`, `presenters.py`, `templates/doctor/decision.html`;
- `apps/pipeline/prior_case.py` e `apps/pipeline/tests/test_prior_case.py`;
- `apps/cases/procedures.py` e serviço transacional de decisões;
- testes `test_specialized_procedure_swap.py`, `test_slice_003_procedure_decision.py` e lock/FSM.

## Requisitos verificáveis

- **R1:** médico decide uma row por pacote/singleton e duas rows somente para EDA + Colonoscopia.
- **R2:** inclusão/substituição oferece todos os destinos canônicos em combobox pesquisável; alias/texto livre/`eda_colonoscopy` como `ProcedureType` são rejeitados.
- **R3:** troca válida nega origem/aprova destino com razões, evento/mensagem existentes e zero chamadas a LLM, fila, orchestrator ou policy do destino.
- **R4:** conjunto final aceita singleton ou par EDA+Colonoscopia; manter qualquer componente e adicionar variação falha sem row/evento/FSM parcial.
- **R5:** histórico consulta igualdade do código; EDA não conta para `eda_gastrostomy`, `eda_dilation` não conta para `rectosigmoidoscopy_dilation` e profiles compartilhados não contaminam contadores.
- **R6:** destino não analisado não recebe painel GTT/local de dilatação sintetizado; detalhes permanecem somente na origem analisada.
- **R7:** lock, permission, fluxos de admissão e banner de erro existentes permanecem.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/doctor/forms.py
  - apps/doctor/views.py
  - apps/doctor/presenters.py
  - templates/doctor/decision.html
  - apps/pipeline/prior_case.py
  - apps/cases/procedures.py
  - static/js/procedure_combobox.js
  - apps/doctor/tests/test_expanded_procedure_decision.py
  - apps/doctor/tests/test_exact_procedure_history.py
  - static/js/tests/procedure_combobox.test.js
allowed_incidental_files:
  - serviço de cases já responsável por decisão/evento, se necessário
  - helper/template do combobox já criado
out_of_scope:
  - recalcular detalhe/policy no destino
  - alterar FSM/locks/permissions/event taxonomy
  - filas do médico/CHD ou correção NIR
```

Se a implementação precisar rerun, nova ação FSM, evento novo ou equivalência por família, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1–R4 | form/view/service/template | `test_expanded_procedure_decision.py` |
| R2 | combobox/template | teste HTML/POST (canônico) + teste JS complementar |
| R5 | projections/presenter | `test_exact_procedure_history.py` |
| R6–R7 | view/presenter | spies de no-rerun + regressões lock/FSM |

## RED

```bash
uv run pytest \
  apps/doctor/tests/test_expanded_procedure_decision.py \
  apps/doctor/tests/test_exact_procedure_history.py -q
node --test static/js/tests/procedure_combobox.test.js
```

Criar testes primeiro. Falha esperada: formulário fechado em quatro tipos/campos, histórico não cobre códigos novos e combobox de destino não existe. RED deve incluir spies que falham se LLM/policy/fila forem chamados.

## GREEN / verificação local

```bash
uv run pytest \
  apps/doctor/tests/test_expanded_procedure_decision.py \
  apps/doctor/tests/test_exact_procedure_history.py \
  apps/doctor/tests/test_specialized_procedure_swap.py \
  apps/doctor/tests/test_slice_003_procedure_decision.py \
  apps/doctor/tests/test_operational_admission_flows.py \
  apps/cases/tests/test_lock_service.py \
  apps/cases/tests/test_fsm.py -q
node --test static/js/tests/procedure_combobox.test.js
uv run ruff check apps/doctor apps/pipeline apps/cases
uv run ruff format --check apps/doctor apps/pipeline apps/cases
```

## Critérios de aceitação

- [ ] R1/R2: todas as identidades são decidíveis/selecionáveis por código canônico.
- [ ] R3/R4: troca é atômica, matricial e sem rerun/repolicy.
- [ ] R5: histórico exato está provado entre famílias e variações.
- [ ] R6/R7: detalhes não são inventados e guards/FSM permanecem.

## Handoff

Worker entrega somente a jornada médica de decisão/histórico e para. Reviewer deve inspecionar transação, conjunto final e spies de ausência de automação; qualquer contaminação de histórico é bloqueante.
