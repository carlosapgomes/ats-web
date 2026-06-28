# Tasks: Separar identidade do app do título de página

## Slices

- [ ] Slice 0 — Infraestrutura: remover `{% block subtitle %}` do header, adicionar `{% block page_title %}` + `<h1 class="page-title">` no `<main>`, classe CSS `.page-title` (`slices/slice-000-infrastructure.md`)
- [x] Slice 1 — Migrar módulo `accounts` (`notifications.html`, `manual.html`) (`slices/slice-001-accounts.md`)
- [x] Slice 2 — Migrar módulo `intake` (7 templates) (`slices/slice-002-intake.md`)
- [x] Slice 3 — Migrar módulo `scheduler` (6 templates) (`slices/slice-003-scheduler.md`)
- [x] Slice 4 — Migrar módulos `doctor`, `dashboard`, `admin_ui` (7 templates) (`slices/slice-004-doctor-dashboard-admin.md`)

## Definition of Done

- [ ] Header tem altura constante em todas as páginas (não varia com o título).
- [ ] Ícones de notificação/avatar/toggler não são mais empurrados por texto longo.
- [ ] Cada uma das 23 páginas com override tem `<h1 class="page-title">` no `<main>`.
- [ ] `navbar-brand` exibe só nome + tagline fixa.
- [ ] Sem `<h1>` duplicado por página.
- [ ] Sem alteração de FSM/models/migrations.
- [ ] Quality gate: ruff, ruff format, mypy, pytest.
- [ ] Relatório temporário + REPORT_PATH informado por slice.
- [ ] Commit + push por slice.
