# Slice 002 — Aplicação do guard no dashboard (views + nav)

## Objetivo

Tornar a restrição CHD observável end-to-end: as 4 rotas de follow-up passam a
exigir posse de `scheduler` para `manager` ativo (admin isento), e o pill
"Follow-up" some da navegação para quem não satisfaz.

## Contexto necessário

- `apps/dashboard/views.py` — views `followup_list` (~:1458), `followup_history`
  (~:1730), `followup_history_export` (~:1816), `followup_form` (~:1948); hoje
  `@login_required` + `@role_required("manager", "admin")`.
- `templates/dashboard/_nav.html:7` — pill "Follow-up" (único link de nav para
  a superfície; não há entrada em outros navs).
- `apps/dashboard/tests/test_followup_{list_view,form_view,history}.py` —
  helpers `_login_as(role)` criam usuários de papel único; classes
  `TestFollowUp*Access` com `test_manager_allowed`/`test_other_roles_redirected`.
- `apps/dashboard/tests/test_dashboard.py` — testes do index (nav renderizada).
- Slice 001 mergeado: `followup_access_required` + `can_access_followup` no
  contexto. Design: D3, D6 e D7 de `design.md` do change.
- Helpers `_login_as` dos 3 arquivos (linhas ~20-31/20-31/45-58): estratégia D6 —
  `_login_as("manager")` passa a criar `manager`+`scheduler` (supervisor do
  CHD); helper novo `_login_as_plain_manager` para os bloqueios.

## Requisitos verificáveis

- R1 As 4 views recebem `@followup_access_required` empilhado após
  `@role_required("manager", "admin")` (decorator que consome `can_access_followup`).
- R2 Matriz D6 coluna "4 rotas": manager sem CHD → 302 `/` + flash e sem
  conteúdo; manager com CHD → comportamento atual (200/render); admin sem CHD →
  200; admin+scheduler com ativo `manager` → 200 (teste explícito);
  scheduler ativo e demais papéis → como hoje.
- R3 Pill "Follow-up" ausente no HTML do dashboard para manager sem CHD e
  demais papéis sem acesso; presente para manager+CHD e admin.
- R4 Helpers conforme D6: `_login_as("manager")` cria `manager`+`scheduler`
  (testes de comportamento existentes seguem passando sem edição individual);
  `_login_as_plain_manager` novo para bloqueios; `test_manager_allowed`
  converte para o helper CHD e assere posse dos dois papéis.

## Matriz requisito -> arquivo -> teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `apps/dashboard/views.py` | `rg -n "followup_access_required" apps/dashboard/views.py` (4 views) + R2 |
| R2 | `apps/dashboard/views.py` | `test_manager_sem_chd_redirecionado_*`, `test_chd_manager_allowed`, `test_admin_sem_chd_allowed`, `test_admin_com_scheduler_ativo_manager` (nos 3 arquivos de teste) |
| R3 | `templates/dashboard/_nav.html` | `test_nav_pill_*` via `dashboard:index` (em `test_dashboard.py` ou arquivo de teste de followup) |
| R4 | 3 arquivos de teste | helpers + parametrizações atualizadas |

```yaml
expected_files:
  - apps/dashboard/views.py
  - templates/dashboard/_nav.html
  - apps/dashboard/tests/test_followup_list_view.py
  - apps/dashboard/tests/test_followup_form_view.py
  - apps/dashboard/tests/test_followup_history.py

allowed_incidental_files:
  - apps/dashboard/tests/test_dashboard.py   # apenas se o teste do pill (R3) ficar melhor aqui

out_of_scope:
  - apps/accounts (slice 001 já entregue)
  - templates de conteúdo (aba, form, histórico) — apenas _nav.html
  - manual, seeds, migrations
```

## Plano de testes do slice

### RED

- comando: `uv run pytest apps/dashboard/tests -k "chd" -q`
- falha esperada: `test_manager_sem_chd_redirecionado_*` falham com 200 em vez
  de 302 (views ainda liberam manager sem `scheduler`); testes do pill falham
  com "Follow-up" presente no HTML.

### GREEN / verificação local

- `uv run pytest apps/dashboard/tests -k "chd or followup" -q` — exit 0
- `uv run pytest apps/dashboard/tests -q` — exit 0 (matriz completa + todos os testes de comportamento existentes com helper CHD)
- `uv run pytest apps/accounts/tests -q` — exit 0 (política intacta)
- `uv run ruff check apps/dashboard && uv run ruff format --check apps/dashboard` — exit 0
- `uv run mypy apps/dashboard apps/accounts` — exit 0

## Critérios de aceitação

- [ ] Matriz D6 (colunas "Nav pill" e "4 rotas") integralmente demonstrada
- [ ] Nenhum conteúdo de follow-up renderizado para manager sem CHD
- [ ] Fluxo atual preservado para manager+CHD e admin (testes existentes convertidos, não deletados)
- [ ] Blast radius dentro do previsto; gates locais verdes
