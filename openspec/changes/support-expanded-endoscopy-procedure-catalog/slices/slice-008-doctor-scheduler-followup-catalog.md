# Slice 008 — Filas médica/CHD e follow-up pelo catálogo

## Objetivo

Completar as jornadas operacionais de médico e CHD: filtros/badges/contadores de todos os tipos, Processados/Histórico, transformação textual e follow-up por identidade autorizada. Somente EDA + Colonoscopia recebe semântica de agendamento casado.

## Contexto necessário

- `design.md`: D11–D12;
- `specs/exam-type-work-queues/spec.md` e requisitos de decisão/analytics relacionados;
- `apps/doctor/views.py`, `templates/doctor/queue.html`, `static/js/doctor_queue_filter.js`;
- `apps/scheduler/views.py`, templates scheduler e `static/js/scheduler_queue_filter.js`;
- follow-up em `apps/cases`/`apps/dashboard` e ADR-0007;
- testes de filtros especializados, scheduler e follow-up existentes.

## Requisitos verificáveis

- **R1:** Pendentes usa dimensão detectada; Decididos Hoje/CHD usam autorizada; opções/contadores são derivados do catálogo e compõem com busca/polling.
- **R2:** cada pacote/Retossigmoidoscopia aparece como badge singleton; transformação declarado/detectado/autorizado usa texto e mensagem existente sem `UserNotification`.
- **R3:** CHD Pendentes/Processados/Histórico filtram exatamente por código; EDA não entra no filtro `eda_*`; query/count usam o mesmo universo.
- **R4:** `Agendamento casado` e contador paired aparecem somente para conjunto autorizado exato `{eda, colonoscopy}`; labels com `+` não acionam regra.
- **R5:** agendamento mantém uma data/hora/local e FSM/forms/locks atuais para qualquer identidade.
- **R6:** follow-up continua restrito a procedures autorizados e cria/mostra row sob código/label exatos para identidades novas.
- **R7:** scripts inicializam chaves/contagens pelos elementos renderizados, sem objeto literal fechado em quatro tipos.

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/doctor/views.py
  - templates/doctor/queue.html
  - static/js/doctor_queue_filter.js
  - apps/scheduler/views.py
  - templates/scheduler/queue.html
  - templates/scheduler/historical_search.html
  - static/js/scheduler_queue_filter.js
  - apps/cases/services.py
  - apps/dashboard/views.py
  - apps/doctor/tests/test_expanded_catalog_queues.py
  - apps/scheduler/tests/test_expanded_catalog_scheduler.py
  - apps/dashboard/tests/test_expanded_catalog_followup.py
allowed_incidental_files:
  - templates follow-up diretamente afetados
  - CSS de badge já previsto pelo catálogo
out_of_scope:
  - métricas/dashboard gerencial do Slice 009
  - segundo appointment ou regra de sala
  - nova notificação/evento/FSM
```

Cap esperado maior por duas jornadas e follow-up, mas cada alteração deve depender dos mesmos metadados do catálogo. Se surgir query por opção/N+1 ou regra `len == 2`, parar e corrigir o desenho antes de seguir.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1–R2, R7 | doctor view/template/JS | `test_expanded_catalog_queues.py` |
| R3–R5, R7 | scheduler view/templates/JS | `test_expanded_catalog_scheduler.py` |
| R6 | cases/dashboard follow-up | `test_expanded_catalog_followup.py` |
| R4 | shared paired helper | casos pacote vs combinado nos três testes |

## RED

```bash
uv run pytest \
  apps/doctor/tests/test_expanded_catalog_queues.py \
  apps/scheduler/tests/test_expanded_catalog_scheduler.py \
  apps/dashboard/tests/test_expanded_catalog_followup.py -q
```

Criar testes antes. Falha esperada: listas/JS/templates atuais omitem tipos novos ou contam pacotes como EDA/paired. Cobrir pelo menos EDA + GTT, EDA + Dilatação, Retossigmoidoscopia + Argônio e combinado verdadeiro.

## GREEN / verificação local

```bash
uv run pytest \
  apps/doctor/tests/test_expanded_catalog_queues.py \
  apps/scheduler/tests/test_expanded_catalog_scheduler.py \
  apps/dashboard/tests/test_expanded_catalog_followup.py \
  apps/doctor/tests/test_queue_exam_type_filters.py \
  apps/scheduler/tests/test_exam_type_filters.py \
  apps/scheduler/tests/test_specialized_scheduler.py \
  apps/cases/tests/test_followup_eligibility.py \
  apps/cases/tests/test_followup_services.py -q
uv run ruff check apps/doctor apps/scheduler apps/cases apps/dashboard
uv run ruff format --check apps/doctor apps/scheduler apps/cases apps/dashboard
```

Inventário focado:

```bash
rg -n "var counts = \{|len\([^)]*proced|Agendamento casado|eda_colonoscopy" \
  apps/doctor apps/scheduler templates/doctor templates/scheduler static/js
```

Classificar cada ocorrência restante; nenhuma regra paired pode depender de label, `+` ou cardinalidade.

## Critérios de aceitação

- [ ] R1/R7: opções e contadores são catálogo-driven nas filas.
- [ ] R2/R3: badges/transformações/filtros preservam código exato.
- [ ] R4/R5: paired é igualdade exata e operação/FSM permanecem.
- [ ] R6: follow-up cobre somente identidade autorizada exata.

## Handoff

Worker entrega estas jornadas e para antes do dashboard analítico. Reviewer verifica universos de contador/filtro, ausência de N+1 e que labels com `+` nunca acionam agendamento casado.
