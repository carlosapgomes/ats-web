# Tasks: Header de notificações e badges operacionais

## Slices verticais

- [x] Slice 001 — Header com sino, sem `queue_count` no perfil, inbox com voltar (`slices/slice-001-header-notifications-inbox.md`)
- [x] Slice 002 — Badges semânticos nas abas médico/agendador (`slices/slice-002-operational-tab-badges.md`)

## Definition of Done do change

- [ ] Header autenticado usa sino para notificações.
- [ ] Sino preserva `id="notification-badge"`, `data-notifications-badge`, `data-unread-count-url`, `data-count` e `aria-label`.
- [ ] Header não mostra mais `queue_count` ao lado do nome/avatar.
- [ ] Página `Minhas Notificações` tem botão `Voltar ao início` sempre visível.
- [x] `Pendentes` do médico mantém contador de ação.
- [x] `Decididos Hoje` do médico mantém contador com classe/cor neutra.
- [x] `Pendentes` do agendador mantém contador de ação.
- [x] `Processados Hoje` do agendador exibe `processed_today_count` com classe/cor neutra.
- [x] Abas NIR permanecem sem novos contadores.
- [x] `.notif-badge` deixa de ser usada para abas operacionais.
- [x] Testes relevantes adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [ ] Relatório markdown temporário gerado para cada slice, com snippets antes/depois e evidências RED/GREEN.
- [ ] Commit e push realizados após cada slice implementado.
