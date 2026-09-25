# Slice 004 — EDA + GTT e revisão infecciosa consultiva

## Objetivo

Entregar EDA + GTT como pacote atômico do upload ao médico e exibir painel ancorado de revisão infecciosa. Todo resultado presente — inclusive normal/negativo — aparece; alerta visual exige preocupação explícita e nenhuma evidência altera policy, recomendação, decisão ou FSM.

## Contexto necessário

- `design.md`: D3–D8 e D13;
- `specs/gastrostomy-infection-review/spec.md` completo;
- requisitos GTT nas specs de catálogo/intake/análise/decisão;
- implementação 4.0 e padrão de ancoragem de imagem/dilatação;
- `apps/pipeline/orchestrator.py`, `projections.py`, schemas 4.0;
- `apps/cases/exam_profiles.py`, `priority_signals.py`;
- `apps/doctor/presenters.py`, `templates/doctor/decision.html`.

## Requisitos verificáveis

- **R1:** `eda_gastrostomy` é oferecido sem flag nova, cria uma row e reconcilia somente com ocorrência atual de EDA + GTT; GTT histórica/em uso prévio/negada não cria pacote.
- **R2:** schema/extrator aceita apenas oito categorias fechadas, com assessment, temporalidade, valor textual e excerpt; unidades/valores/classificações não são inventados.
- **R3:** verificador ancora trecho único, rederiva categoria e só aceita normal/alterado/positivo/negativo/febril/status de antibiótico com marcador local explícito; histórico domina.
- **R4:** painel mostra leucócitos/PCR/procalcitonina/lactato/culturas/temperatura-infectologia-antibióticos encontrados, inclusive normais/negativos e valores `unclassified`.
- **R5:** alerta aparece para preocupação atual ou não histórica explicitamente documentada, infectologia atual ou antibiótico atual/iniciado/escalado; normais, negativos, valor sem interpretação e histórico isolados não alertam.
- **R6:** com e sem alerta, policy evaluation, `failed_requirements`, recomendação LLM2, suporte, campos/form validation, transição FSM e destino permanecem idênticos.
- **R7:** writes 4.0 não persistem sinal legado `gastrostomy`; histórico antigo continua legível.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/intake/views.py
  - apps/pipeline/scope_detection.py
  - apps/pipeline/procedure_reconciliation.py
  - apps/pipeline/schemas/llm1_v4.py
  - apps/pipeline/infection_review.py
  - apps/pipeline/orchestrator.py
  - apps/cases/exam_profiles.py
  - apps/cases/priority_signals.py
  - apps/doctor/presenters.py
  - templates/doctor/decision.html
  - apps/intake/tests/test_gastrostomy_intake.py
  - apps/pipeline/tests/test_gastrostomy_infection_review.py
  - apps/doctor/tests/test_gastrostomy_infection_panel.py
allowed_incidental_files:
  - CSS existente para alerta/painel, somente se nenhuma classe Bootstrap suficiente atender
  - fixtures/helpers de teste
out_of_scope:
  - thresholds/reference ranges, diagnóstico ou score
  - hard rule/failed requirement de infecção
  - anexos como fonte
  - notificações, nova pendência, FSM ou campo persistente
```

Se qualquer implementação propuser threshold, inferir unidade, consultar anexo ou passar o DTO ao motor de policy como requisito, parar e escalar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1, R7 | intake/scope/reconciliation/profile/signals | `test_gastrostomy_intake.py` + negativos pipeline |
| R2–R3 | schema + `infection_review.py` | `test_gastrostomy_infection_review.py` |
| R4–R5 | presenter/template | `test_gastrostomy_infection_panel.py` |
| R6 | orchestrator/policy boundary | teste parametrizado de invariância |

## RED

Criar os testes e executar:

```bash
uv run pytest \
  apps/intake/tests/test_gastrostomy_intake.py \
  apps/pipeline/tests/test_gastrostomy_infection_review.py \
  apps/doctor/tests/test_gastrostomy_infection_panel.py -q
```

Falha esperada: GTT ainda não selecionável/detectável, coleção/verificador/presenter ausentes.

Fixtures RED obrigatórias:

- leucócitos explicitamente normais + cultura negativa → ambos visíveis, sem alerta;
- PCR numérica sem interpretação → visível `unclassified`, sem alerta;
- febre ou cultura positiva atual → alerta;
- antibiótico em uso/iniciado/escalado → alerta, sem diagnóstico;
- marcador somente histórico → sem alerta;
- excerpt inventado/duplicado → não confirmado;
- mesmos dados clínicos com revisão vazia/preocupante → policy/recomendação/FSM iguais.

## GREEN / verificação local

```bash
uv run pytest \
  apps/intake/tests/test_gastrostomy_intake.py \
  apps/pipeline/tests/test_gastrostomy_infection_review.py \
  apps/doctor/tests/test_gastrostomy_infection_panel.py \
  apps/pipeline/tests/test_eda_preop_policy.py \
  apps/pipeline/tests/test_v4_existing_workflow.py \
  apps/doctor/tests/test_views.py -q
uv run ruff check apps/intake apps/pipeline apps/cases apps/doctor
uv run ruff format --check apps/intake apps/pipeline apps/cases apps/doctor
```

Inspecionar no diff que `infection_review` não é importado por módulos em `apps/pipeline/policy/` e que nenhum código novo de `failed_requirements`/priority signal foi criado.

## Critérios de aceitação

- [ ] R1/R7: pacote único, detecção conservadora e sem sinal duplicado.
- [ ] R2/R3: evidências são fechadas, ancoradas e sem thresholds.
- [ ] R4/R5: normais aparecem e só preocupação explícita alerta.
- [ ] R6: testes provam invariância da policy/recomendação/FSM.

## Handoff

Entregar relatório com exemplos normal/preocupante e comparação de invariância antes/depois. Não tocar outras identidades, filas ou analytics. Reviewer deve tratar qualquer efeito bloqueante do painel como P0.
