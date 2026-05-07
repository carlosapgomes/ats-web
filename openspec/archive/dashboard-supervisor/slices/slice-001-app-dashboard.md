# Slice 1: App dashboard + view + template + case detail admin

## Objetivo

Criar o app `apps/dashboard/` com a view de dashboard (métricas + tabela de casos),
template alinhado ao mock, case detail admin, e redirecionamento de home_view.

## Arquivos a criar

### 1. `apps/dashboard/` (app scaffold)
- `__init__.py`
- `apps.py` (`DashboardConfig`)
- `urls.py` — namespace `dashboard`
- `views.py` — `dashboard_index` + `dashboard_case_detail`

### 2. `config/urls.py`
Adicionar `path("dashboard/", include("apps.dashboard.urls"))`

### 3. `config/settings/base.py`
Adicionar `"apps.dashboard"` em `INSTALLED_APPS`

### 4. `templates/dashboard/index.html`
Alinhar com `demo-reference/admin/dashboard.html`:
- `{% extends "base.html" %}`
- Summary cards: Total Hoje, Aceitos, Negados, Em Andamento
- Sub-métricas: aguardando por etapa, fluxo de admissão, tempo médio
- Tabela de todos os casos com filtros (status dropdown + date pickers) e paginação
- Nav pills: Dashboard / Prompts / Usuários / Auditoria (links placeholder)

### 5. Case detail admin

Reutilizar `templates/intake/case_detail.html` mas sem `can_confirm_receipt`.
Na view `dashboard_case_detail`, carregar mesmo contexto da `case_detail` do intake
mas sem filtro `created_by=request.user` e com `can_confirm_receipt=False`.

### 6. `apps/accounts/views.py`
Atualizar `home_view`: manager → `redirect("dashboard:index")`, admin → `redirect("dashboard:index")`

## Queries do dashboard

```python
today = date.today()

# Summary cards
total_today = Case.objects.filter(created_at__date=today).count()
accepted = Case.objects.filter(
    created_at__date=today,
    doctor_decision="accept",
).exclude(status__in=[DOCTOR_DENIED, FAILED]).count()
denied = Case.objects.filter(
    created_at__date=today,
    status__in=[DOCTOR_DENIED, APPT_DENIED],
).count()
in_progress = total_today - accepted - denied

# Por etapa
waiting_doctor = Case.objects.filter(status=WAIT_DOCTOR).count()
waiting_appt = Case.objects.filter(status=WAIT_APPT).count()
waiting_confirm = Case.objects.filter(status=WAIT_R1_CLEANUP_THUMBS).count()

# Fluxo
scheduled_count = Case.objects.filter(
    created_at__date=today, doctor_admission_flow="scheduled",
    doctor_decision="accept",
).count()
immediate_count = Case.objects.filter(
    created_at__date=today, doctor_admission_flow="immediate",
    doctor_decision="accept",
).count()
```

## Critérios de sucesso

- [ ] App dashboard registrado e acessível
- [ ] `/dashboard/` retorna 200 para manager/admin
- [ ] `/dashboard/` redireciona para login se não autenticado
- [ ] Summary cards com contagens corretas
- [ ] Sub-métricas (por etapa, fluxo, tempo médio)
- [ ] Tabela de casos com filtros (status, data) e paginação
- [ ] `/dashboard/<uuid>/` mostra detalhe de qualquer caso
- [ ] Case detail admin sem botão "Confirmar Recebimento"
- [ ] `home_view` redireciona manager/admin para `/dashboard/`
- [ ] Template estende `base.html` e alinha com mock
- [ ] Testes: dashboard (8), case detail admin (3), redirect (2)
- [ ] ruff + mypy + pytest clean

## Arquivos: ideal ≤ 8
