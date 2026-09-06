# Slice 001 — Página Histórico: sub-abas, janela, versão corrente, cards, tabela e busca

## Objetivo

Comportamento observável: com papel `manager`/`admin`, a aba Follow-up ganha sub-abas **Registrar** (atual `/dashboard/follow-ups/`, intacta) e **Histórico & Exportação** (`/dashboard/follow-ups/history/`), que exibe para uma janela de datas (default: últimos 7 dias incluindo hoje, local `America/Bahia`) os cards-resumo do período (casos com follow-up, taxa de realizado, causas com submotivos, internações) e a tabela paginada (1 linha por desfecho de procedimento) da **versão corrente** de cada caso, com busca `?q=` por ocorrência/paciente dentro da janela. Atores sem papel ficam bloqueados.

## Contexto necessário (ler antes de editar)

- `apps/cases/models.py` — `CaseFollowUp` (related_name `follow_ups`, campo `version`, `patient_admitted`, `recorded_by`, `recorded_at`) e `ProcedureFollowUp` (related_name `procedure_outcomes`; `performed`, `non_performance_reason`, `resource_shortage_detail`, `other_reason`), `CaseProcedure.procedure_type` com choices/labels.
- `apps/cases/followup.py` — service do domínio (aqui entra o helper novo; leia o módulo inteiro, é curto).
- `apps/dashboard/views.py` — `followup_list` (~L1450) e helpers `_followup_group_date` (~L1331, fonte única da data de grupo), `_current_follow_up_map` (~L1405), `_followup_patient_name` (~L1495, nome do paciente via `structured_data.patient.name`), `_followup_history` (padrão de `author_label`: `get_full_name() or username`, senão "—").
- `apps/dashboard/urls.py` — rotas existentes `follow-up`s.
- `templates/dashboard/followup_list.html` — página atual da aba (vai só ganhar o include das sub-abas).
- `apps/dashboard/tests/` — padrões de teste existentes (`test_followup_list_view.py` para fixtures/asserts de listagem; fixtures em `tests/shared_case_fixtures.py`: `user`, `case_factory`, `advance_to`).
- Design: seções **D1** (IA/sub-abas), **D2** (população/versão corrente), **D3** (data de grupo, janela 7d/31d, fallback, `q` dentro da janela), **D6** (SSR, partial de tabs, paginação 25), **D7** (guard), **D8** (Python-side) de `../design.md`.
- Tempo local: use `django.utils.timezone.localdate/localtime` (settings já configuram `America/Bahia`).

## Requisitos verificáveis

- **R1** — `current_follow_ups()` em `apps/cases/followup.py`: queryset de `CaseFollowUp` com exatamente a versão máxima por caso (1 row por caso com follow-up), `select_related("case", "recorded_by")` + `prefetch_related("procedure_outcomes__procedure")`.
- **R2** — `GET /dashboard/follow-ups/history/` com papel `manager` → 200; a página e a listagem atual exibem as sub-abas via partial `templates/dashboard/_followup_tabs.html` (ativa conforme a página; "Registrar" default em `/dashboard/follow-ups/`).
- **R3** — População: só casos com follow-up; cada caso 1x pela versão corrente (caso com v1+v2 aparece 1x com dados da v2; caso elegível sem follow-up não aparece).
- **R4** — Janela por data de grupo: default `hoje-6 .. hoje`; `?start=&end=` ISO válidos com `start ≤ end` e span ≤ 31 dias respeitados; inválido/invertido/acima do limite → default; header exibe a janela ativa (formato `dd/mm/yyyy`). O eixo é SEMPRE a data de grupo (`_followup_group_date`), nunca `recorded_at` — comprovado por teste com datas deliberadamente dissociadas (R4b na matriz).
- **R5** — `?q=` filtra por ocorrência (`agency_record_number`) ou nome do paciente (contains case-insensitive) dentro da janela; o termo persiste no input.
- **R6** — Cards do período (janela+busca): nº de casos, taxa de realizado por procedimento, causas de não realização com breakdown de submotivo para `resource_shortage`, nº de internações. Sem JS: Bootstrap + `progress` bars.
- **R7** — Tabela paginada (`Paginator`, 25/página): 1 linha por `ProcedureFollowUp` da versão corrente, colunas ocorrência, paciente, data do grupo (`dd/mm/yyyy`), procedimento (label), desfecho, causa/submotivo/texto (labels), internação (Sim/Não), versão, registrado por (`author_label`), registrado em (`dd/mm/yyyy hh:mm` local); ordenação por data de grupo desc e, dentro dela, paciente/horário (padrão da aba Registrar).
- **R8** — Guard: `@role_required("manager", "admin")`; usuários sem esses papéis (p.ex. `nir`, `scheduler`) e anônimos não acessam.

## Matriz requisito → arquivo(s) → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/cases/followup.py` | `pytest apps/cases/tests/test_followup_services.py -k current_follow_ups` (novo) |
| R2 | `templates/dashboard/_followup_tabs.html` (novo), `followup_list.html` (include), `followup_history.html` (novo), `apps/dashboard/{views,urls}.py` | `pytest apps/dashboard/tests/test_followup_history.py -k tabs` (novo) |
| R3 | `apps/dashboard/views.py` (população via R1) | `... -k "current_version or single_row"` (novo) |
| R4 | `apps/dashboard/views.py` (parse/fallback da janela) | `... -k "window"` (novo) |
| R4b | `apps/dashboard/views.py` (eixo = data de grupo, NÃO `recorded_at`) | `... -k window_group_date` (novo: caso com data de grupo dentro da janela e `recorded_at` fora aparece; caso com data de grupo fora e `recorded_at` dentro NÃO aparece) |
| R5 | `apps/dashboard/views.py` | `... -k search` (novo) |
| R6 | `apps/dashboard/views.py` + `followup_history.html` | `... -k cards` (novo; asserts no HTML) |
| R7 | idem | `... -k "table or pagination"` (novo) |
| R8 | `apps/dashboard/views.py` | `... -k "role or anonymous"` (novo) |

## Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/followup.py                          # + current_follow_ups()
  - apps/cases/tests/test_followup_services.py      # + testes do helper
  - apps/dashboard/views.py                         # + view followup_history + helpers privados
  - apps/dashboard/urls.py                          # +1 rota nomeada followup_history
  - templates/dashboard/_followup_tabs.html         # novo (partial de sub-abas)
  - templates/dashboard/followup_list.html          # include do partial (1 linha)
  - templates/dashboard/followup_history.html       # novo
  - apps/dashboard/tests/test_followup_history.py   # novo (testes R2–R8)

allowed_incidental_files: []

out_of_scope:
  - exportação CSV (Slice 002) e filtros performed/reason/admitted (Slice 003)
  - aba Registrar (comportamento/URL/queries inalterados, além do include)
  - FSM, models, migrations, JS, static, specs (parent cuida), manual do usuário
  - tasks.md / commit / push (parent)
```

Escale (não amplie o slice) se: precisar de migration/índice; alterar queries/modelos; quebrar testes existentes da aba Registrar por motivo que não seja o include.

## Plano de testes do slice

### RED

Ordem: ESCREVA os testes novos primeiro, DEPOIS execute os comandos RED (arquivo de teste novo inexistente faria pytest falhar por "file not found", não pelo comportamento-alvo).

Comandos focados (com os testes já escritos, devem falhar ANTES da implementação):

- `uv run pytest apps/cases/tests/test_followup_services.py -k current_follow_ups -q` → `AttributeError`/`ImportError` (helper inexistente).
- `uv run pytest apps/dashboard/tests/test_followup_history.py -q` → 404 na rota nova (view/URL inexistentes) e asserts de sub-aba falham.

### GREEN / verificação local

```bash
uv run pytest apps/cases/tests/test_followup_services.py -q            # exit 0
uv run pytest apps/dashboard/tests/test_followup_history.py -q         # exit 0
uv run pytest apps/dashboard/tests -q                                  # exit 0 (aba Registrar intacta)
uv run ruff check apps/cases/followup.py apps/dashboard && uv run ruff format --check apps/cases/followup.py apps/dashboard  # exit 0
```

Fixtures de teste podem reutilizar `record_case_follow_up` (service) para criar versões — evidencia R3.

## Critérios de aceitação

- [ ] R1–R8 verdes com os comandos acima; sem regressão em `apps/dashboard/tests`.
- [ ] Página renderiza sem JS novo; sub-aba Registrar funcionalmente intacta.
- [ ] Diff dentro do blast radius declarado.
