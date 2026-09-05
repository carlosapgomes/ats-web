# Slice 002 — Aba de listagem Follow-up do supervisor

## Objetivo

Comportamento observável: `manager`/`admin` abrem `/dashboard/follow-ups/`, veem os casos elegíveis de hoje+ontem (ou de uma data escolhida, ou resultado de busca), ordenados por data e nome, cada um com badge pendente/registrado e link para o formulário (rota já reservada; o form em si é o Slice 003). Papéis demais são barrados.

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
- **R5** — Cada card exibe: ocorrência (`agency_record_number`), nome do paciente, data/hora agendada (ou label do fluxo de admissão p/ imediatos), badge "Follow-up registrado" (com versão/atualização) ou "Follow-up pendente", e link para `dashboard:followup_form`.
- **R6** — Pill "Follow-up" visível em `templates/dashboard/_nav.html` apontando para a rota.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/dashboard/views.py` | `pytest apps/dashboard/tests/test_followup_list_view.py -k role` |
| R2 | idem + `templates/dashboard/followup_list.html` | `pytest ... -k "default_today_yesterday or ordering"` |
| R3 | idem | `pytest ... -k specific_date` |
| R4 | idem | `pytest ... -k search` |
| R5 | template + view | `pytest ... -k card_badges` |
| R6 | `templates/dashboard/_nav.html` | `pytest ... -k nav` (assert contém url) |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/dashboard/views.py                # +followup_list view
  - apps/dashboard/urls.py                 # +rota followup_list
  - templates/dashboard/_nav.html          # +pill
  - templates/dashboard/followup_list.html # novo
  - apps/dashboard/tests/test_followup_list_view.py  # novo

allowed_incidental_files: []

out_of_scope:
  - formulário/POST (Slice 003), rota do form pode ser registrada mas sem view de POST
  - apps/cases (nada a mudar), FSM, signals
  - paginação, exportação, métricas
```

**Escalar** se: precisar de model/migration nova, middleware, ou alterar views existentes do dashboard além de adicionar.

## Plano de testes do slice

### RED

```bash
uv run pytest apps/dashboard/tests/test_followup_list_view.py -q
```

Falha esperada: 404/`ImportError` — rota/view não existem. Testes criam usuário+role (`Role.objects.get_or_create`), setam `client.session["active_role"]`, criam `Case` com `appointment_at=timezone.now()` (e variante ontem via `timezone.make_aware(datetime)`), `CaseProcedure` e follow-up via `record_case_follow_up` para o badge.

### GREEN

```bash
uv run pytest apps/dashboard/tests/test_followup_list_view.py -q
```

### Verificação do slice

```bash
uv run pytest apps/dashboard/tests apps/cases/tests -q   # regressão das duas áreas
uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard
uv run mypy apps/dashboard
```

## Critérios de aceitação

- [ ] R1–R6 verdes nos testes focados.
- [ ] Filtro de data usa `timezone.localdate` (sem `date.today()` — checar por `rg "date.today" apps/dashboard/views.py` → vazio no código novo).
- [ ] Nenhum arquivo fora do blast radius; suite de dashboard/cases sem regressão.
