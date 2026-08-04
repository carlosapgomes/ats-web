# Tasks: Aliases pt-BR para menções de papéis

## Slice vertical

- [x] Slice 001 — Parser, notificações e microcopy para aliases pt-BR (`slices/slice-001-mention-aliases.md`)

## Definition of Done

- [x] `@medico` normaliza para papel canônico `doctor`.
- [x] `@chd` normaliza para papel canônico `scheduler`.
- [x] `@supervisor` normaliza para papel canônico `manager`.
- [x] Menções canônicas existentes continuam funcionando.
- [x] Usernames não reservados continuam funcionando.
- [x] Notificações são criadas para usuários ativos com papéis canônicos resolvidos por alias.
- [x] Payload do evento usa `mentioned_roles` canônicos.
- [x] Thread de comunicação operacional mostra exemplos de aliases.
- [x] Sem migration.
- [x] Testes relevantes passam.
- [x] Quality gate executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado e `REPORT_PATH` informado.
- [x] Commit e push realizados.
