# Slice 1 Report: App dashboard + view + template + case detail admin

## Resumo

Criação do app `apps/dashboard/` com dashboard de monitoramento para supervisor/admin,
incluindo métricas, tabela de casos com filtros/paginação, case detail admin sem botão
de confirmação, e redirecionamento da home_view.

## Arquivos criados/modificados

### Criados (6)
- `apps/dashboard/__init__.py`
- `apps/dashboard/apps.py` — `DashboardConfig`
- `apps/dashboard/urls.py` — namespace `dashboard`, paths: `index`, `case_detail`
- `apps/dashboard/views.py` — `dashboard_index` + `dashboard_case_detail`
- `apps/dashboard/templatetags/__init__.py`
- `apps/dashboard/templatetags/dashboard_extras.py` — filtro `lookup` para templates
- `apps/dashboard/tests/__init__.py`
- `apps/dashboard/tests/test_dashboard.py` — 30 testes
- `templates/dashboard/index.html` — alinhado ao mock

### Modificados (4)
- `config/urls.py` — add `path("dashboard/", include("apps.dashboard.urls"))`
- `config/settings/base.py` — add `"apps.dashboard"` ao INSTALLED_APPS
- `apps/accounts/views.py` — home_view redireciona manager/admin para `dashboard:index`
- `pyproject.toml` — mypy overrides para `apps.dashboard.*`

## Funcionalidades

1. **Dashboard** (`GET /dashboard/`)
   - Summary cards: Total Hoje, Aceitos, Negados, Em Andamento
   - Sub-métricas: Aguardando por Etapa (Fila Médica, Agendamento, Confirmação)
   - Sub-métricas: Fluxo de Admissão (Agendamento, Vinda Imediata)
   - Sub-métricas: Tempo Médio (Upload→Decisão, Decisão→Agendamento, Ciclo Total)
   - Tabela de todos os casos (sem filtro de usuário) com filtros por status/data
   - Paginação (20 por página)
   - Nav pills: Dashboard (ativo) / Prompts / Usuários / Auditoria (placeholders)

2. **Case Detail Admin** (`GET /dashboard/<uuid>/`)
   - Reusa template `intake/case_detail.html`
   - Mostra qualquer caso (sem filtro `created_by=request.user`)
   - Sem botão "Confirmar Recebimento" (`can_confirm_receipt=False`)

3. **Home Redirect**
   - manager → `/dashboard/`
   - admin → `/dashboard/`
   - NIR não é redirecionado (mantém intake)

## Qualidade

- Ruff check: ✅ All checks passed
- Ruff format: ✅ 98 files already formatted
- Mypy: ✅ Success: no issues found in 104 source files
- Pytest: ✅ 398 passed (30 novos testes do dashboard)

## Testes (30)

### TestDashboardAccess (6)
- `test_dashboard_requires_login` — redirect para login
- `test_dashboard_accessible_for_manager` — 200
- `test_dashboard_accessible_for_admin` — 200
- `test_dashboard_blocked_for_nir` — 302
- `test_dashboard_blocked_for_doctor` — 302
- `test_dashboard_blocked_for_scheduler` — 302

### TestDashboardSummaryCards (3)
- `test_summary_cards_show_correct_counts`
- `test_summary_cards_include_today_total`
- `test_summary_cards_exclude_old_cases`

### TestDashboardSubMetrics (3)
- `test_shows_waiting_by_stage`
- `test_shows_admission_flow`
- `test_shows_average_times`

### TestDashboardCaseTable (5)
- `test_case_table_shows_all_cases` — sem filtro de usuário
- `test_case_table_has_status_filter`
- `test_case_table_has_pagination` — >20 casos
- `test_case_table_shows_patient_name`
- `test_case_table_has_action_links`

### TestDashboardNavPills (4)
- `test_has_dashboard_pill_active`
- `test_has_prompts_pill`
- `test_has_usuarios_pill`
- `test_has_auditoria_pill`

### TestDashboardCaseDetailAdmin (6)
- `test_case_detail_accessible_for_manager`
- `test_case_detail_accessible_for_admin`
- `test_case_detail_shows_any_case` — caso de outro NIR
- `test_case_detail_no_confirm_button` — WAIT_R1_CLEANUP_THUMBS sem "Confirmar"
- `test_case_detail_404_for_nonexistent`
- `test_case_detail_blocked_for_nir`

### TestHomeRedirect (3)
- `test_manager_redirects_to_dashboard`
- `test_admin_redirects_to_dashboard`
- `test_nir_not_redirected_to_dashboard`

## Critérios de Sucesso

- [x] App dashboard registrado e acessível
- [x] `/dashboard/` retorna 200 para manager/admin
- [x] `/dashboard/` redireciona para login se não autenticado
- [x] Summary cards com contagens corretas
- [x] Sub-métricas (por etapa, fluxo, tempo médio)
- [x] Tabela de casos com filtros (status, data) e paginação
- [x] `/dashboard/<uuid>/` mostra detalhe de qualquer caso
- [x] Case detail admin sem botão "Confirmar Recebimento"
- [x] `home_view` redireciona manager/admin para `/dashboard/`
- [x] Template estende `base.html` e alinha com mock
- [x] Testes: dashboard (30 no total, incluindo 6 detail + 3 redirect)
- [x] ruff + mypy + pytest clean
