# Slice 007 — Filas, analytics e follow-up especializados

## Objetivo

Fechar todas as superfícies operacionais para Ecoendoscopia/CPRE e remover pressupostos binários residuais, mantendo métricas case-level e agendamento casado exclusivamente EDA + Colonoscopia.

## Contexto necessário

- `design.md`: D12–D15
- deltas `exam-type-work-queues`, `exam-type-analytics`, `exam-type-correction`
- views/templates/JS de filas médico, CHD, NIR e dashboard
- `apps/dashboard/procedure_analytics.py`
- fluxo de follow-up por `CaseProcedure`

## Requisitos verificáveis

- **R1:** filtros válidos em cada papel incluem Eco/CPRE e usam dimensão correta.
- **R2:** singleton especializado não aparece como combinado, EDA nem `none`.
- **R3:** breakdown exclusivo fecha com casos; volume por componente inclui quatro tipos sem dupla contagem.
- **R4:** somente conjunto exato EDA+Colon incrementa agendamento casado.
- **R5:** follow-up permite registrar/exibir desfecho próprio para Eco/CPRE.
- **R6:** busca, polling, paginação e params continuam compondo.
- **R7:** inventário classifica ou remove todos os pressupostos binários executáveis.

## Escopo e blast radius

```yaml
expected_files:
  - apps/doctor/views.py
  - templates/doctor/_queue_content.html
  - apps/scheduler/views.py
  - templates/scheduler/_queue_content.html
  - apps/intake/views.py
  - templates/intake/_my_cases_content.html
  - apps/dashboard/procedure_analytics.py
  - apps/dashboard/views.py
  - templates/dashboard/index.html
  - apps/dashboard/tests/test_procedure_analytics.py
  - apps/doctor/tests/test_queue_exam_type_filters.py
  - apps/scheduler/tests/test_exam_type_filters.py
  - apps/intake/tests/test_my_cases.py
  - apps/dashboard/tests/test_followup_form_view.py
allowed_incidental_files:
  - static/js/doctor-queue.js
  - static/js/scheduler-queue.js
  - templates/dashboard/followup_form.html
file_cap: 17
out_of_scope:
  - nova métrica clínica
  - matriz de conversão visual não solicitada
  - alteração de follow-up model
  - sala/turno
```

Cap elevado decorre de quatro superfícies independentes. Se o inventário exceder o cap, parar e propor desmembramento vertical por ator antes de editar extras.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R2/R6 | views/templates/JS por papel | filtros/polling/busca parametrizados |
| R3/R4 | `procedure_analytics.py` | categorias, soma, componentes, paired exact |
| R5 | dashboard follow-up | form/registro/history para cada tipo |
| R7 | todos | inventário `rg` classificado no relatório |

## RED

- `uv run pytest apps/doctor/tests/test_queue_exam_type_filters.py apps/scheduler/tests/test_exam_type_filters.py apps/intake/tests/test_my_cases.py apps/dashboard/tests/test_procedure_analytics.py apps/dashboard/tests/test_followup_form_view.py -q -k 'echoendoscopy or cpre or specialized'`
- Falha esperada: opções/predicados/analytics ainda enumeram dois tipos.

## GREEN / verificação local

- Rodar os cinco módulos RED sem `-k`.
- `uv run pytest apps/dashboard/tests/test_dashboard.py apps/dashboard/tests/test_followup_history.py -q`
- `rg -n "ProcedureType\.(EDA|COLONOSCOPY)|len\([^)]*proced|_PROCEDURE_ORDER|_PROCEDURE_TYPES|eda_colonoscopy" apps templates static`
- Ruff check/format nos arquivos Python alterados.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Resultado do inventário está classificado no relatório, sem ocorrência executável inexplicada.
- [ ] Cards combinados existentes continuam corretos.
- [ ] Não houve alteração do modelo de follow-up.

## Handoff

Gerar `REPORT_PATH=/tmp/support-independent-echoendoscopy-cpre-slice-007-report.md` com tabela de filtros/dimensões e inventário. Parar antes do gate operacional.
