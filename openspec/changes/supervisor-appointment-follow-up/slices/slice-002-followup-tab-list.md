# Slice 002 — Aba de listagem Follow-up do supervisor

## Objetivo

Comportamento observável: `manager`/`admin` abrem `/dashboard/follow-ups/`, veem os casos elegíveis de hoje+ontem (ou de uma data escolhida, ou resultado de busca), ordenados por data e nome, cada um com badge pendente/registrado. **Os cards NÃO linkam para o formulário neste slice** — rota `followup_form` e link do card chegam no Slice 003 (evita navegação quebrada entre slices). Papéis demais são barrados.

## Contexto necessário (ler antes de editar)

- `apps/dashboard/views.py` — padrão de view: `@login_required @role_required("manager", "admin")`, montagem de cards/dicts para o template (ex.: `case_list` ~L800+).
- `apps/dashboard/urls.py` — namespace `dashboard:`; `templates/dashboard/_nav.html` — pills.
- `apps/intake/views.py::closed_cases_search` (~L1455-1485) — padrão de busca `Q(agency_record_number__icontains) | Q(structured_data__patient__name__icontains)` limitada a 50.
- `apps/cases/admission.py` — `OPERATIONAL_NOTICE_FLOWS` (grupo vinda imediata).
- `apps/cases/followup.py::get_current_follow_up` — badge registrado/pendente (Slice 001).
- `openspec/changes/supervisor-appointment-follow-up/design.md` — D4 (query/listagem), D5 (rotas/permissions), D7 (timezone).

## Requisitos verificáveis

- **R1** — `GET /dashboard/follow-ups/` exige login + papel ativo `manager`/`admin`; outro papel → redirect com `messages.error` (padrão `role_required`).
- **R2** — Default: casos com `appointment_status="confirmed"`, `appointment_at` não nulo e `localdate(appointment_at)` ∈ {hoje, ontem} **mais** casos com `doctor_admission_flow ∈ OPERATIONAL_NOTICE_FLOWS`, `doctor_decided_at` não nulo e `localdate(doctor_decided_at)` ∈ {hoje, ontem}; agrupados por data ascendente; dentro da data, ordenados por nome do paciente e depois horário.
- **R3** — `?date=YYYY-MM-DD` válido lista só aquela data; ausente/inválida → default hoje+ontem.
- **R4** — `?q=` busca (icontains ocorrência OU nome) sobre elegíveis de **qualquer** data, limite 50, ignorando `?date` quando preenchida.
- **R5** — Cada card exibe: ocorrência (`agency_record_number`), nome do paciente, data/hora agendada (ou label do fluxo de admissão p/ imediatos), badge "Follow-up registrado" (com versão/atualização) ou "Follow-up pendente". **Sem link para o formulário neste slice** (a rota só passa a existir no Slice 003, que adiciona o link).
- **R6** — Pill "Follow-up" visível em `templates/dashboard/_nav.html` apontando para a rota.
- **R7** — Predicado de elegibilidade `is_followup_eligible(case)` em `apps/cases/followup.py` (agendado confirmado com `appointment_at`, ou fluxo operacional com `doctor_decided_at` — sem fallback), com testes unitários; a listagem o consome.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/dashboard/views.py` | `pytest apps/dashboard/tests/test_followup_list_view.py -k role` |
| R2 | idem + `templates/dashboard/followup_list.html` | `pytest ... -k "default_today_yesterday or ordering"` |
| R3 | idem | `pytest ... -k specific_date` |
| R4 | idem | `pytest ... -k search` |
| R5 | template + view | `pytest ... -k card_badges` |
| R6 | `templates/dashboard/_nav.html` | `pytest ... -k nav` (assert contém url) |
| R7 | `apps/cases/followup.py` + `apps/cases/tests/test_followup_eligibility.py` | `pytest apps/cases/tests/test_followup_eligibility.py` |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/views.py                # +followup_list view
  - apps/dashboard/urls.py                 # +rota followup_list
  - templates/dashboard/_nav.html          # +pill
  - templates/dashboard/followup_list.html # novo
  - apps/dashboard/tests/test_followup_list_view.py  # novo
  - apps/cases/followup.py                 # +is_followup_eligible
  - apps/cases/tests/test_followup_eligibility.py    # novo

allowed_incidental_files: []

out_of_scope:
  - formulário/POST e rota followup_form (Slice 003; a listagem NÃO linka para ela)
  - FSM, signals
  - paginação, exportação, métricas
```

**Escalar** se: precisar de model/migration nova, middleware, ou alterar views existentes do dashboard além de adicionar.

## Plano de testes do slice

### RED

Escreva primeiro `apps/cases/tests/test_followup_eligibility.py` e `apps/dashboard/tests/test_followup_list_view.py` (importando a view/rota novas). Depois:

```bash
uv run pytest apps/cases/tests/test_followup_eligibility.py apps/dashboard/tests/test_followup_list_view.py -q
```

Falha esperada: erro de coleção/import — `is_followup_eligible`, view e rota não existem. Testes criam usuário+role (`Role.objects.get_or_create`), setam `client.session["active_role"]`, criam `Case` com `appointment_at=timezone.now()` (e variante ontem via `timezone.make_aware(datetime)`), `CaseProcedure` e follow-up via `record_case_follow_up` para o badge.

### GREEN

```bash
uv run pytest apps/cases/tests/test_followup_eligibility.py apps/dashboard/tests/test_followup_list_view.py -q
```

### Verificação do slice

```bash
uv run pytest apps/dashboard/tests apps/cases/tests -q   # regressão das duas áreas
uv run ruff check apps/dashboard apps/cases && uv run ruff format --check apps/dashboard apps/cases
uv run mypy apps/dashboard apps/cases
```

## Critérios de aceitação

- [x] R1–R7 verdes nos testes focados.
- [x] Filtro de data usa `timezone.localdate` (sem `date.today()` — checar por `rg "date.today" apps/dashboard/views.py` → vazio no código novo).
- [x] Card NÃO renderiza link para `dashboard:followup_form` (`rg "followup_form" templates/dashboard/followup_list.html` → vazio).
- [x] Nenhum arquivo fora do blast radius; suite de dashboard/cases sem regressão.

## Registro de execução

- 2 rodadas de review. Rodada 1: BLOCK com 1×P1 (caso híbrido elegível sumia da lista — agrupamento priorizava ramo operacional divergindo de `is_followup_eligible`); corrigido com precedência unificada (ramo agendado válido vence) + `TestFollowUpListHybridCase` (3 testes). Rodada 2: **OK with notes**.
- P2s diferidos (não bloqueiam; report-only): (a) card híbrido confirmado exibe coluna de decisão do fluxo operacional (`is_immediate` só olha o fluxo — precedência de apresentação diverge da de agrupamento); (b) `agency_record_number` truncado em 12 chars (convenção herdada do dashboard); (c) pill Follow-up sem estado ativo (`_nav.html` do dashboard não gerencia aba ativa).
- Validação focada: 37 passed (testes do slice), 920 passed (apps/dashboard + apps/cases), ruff/format/mypy verdes.
