<!-- markdownlint-disable MD013 -->

# Tasks: Ocultar notificações lidas há mais de 48h

## Slice vertical

- [ ] Slice 001 — Janela de visibilidade de leitura end-to-end na lista do usuário (`slices/slice-001-hide-read-older-48h.md`)

## Definition of Done do change

- [ ] `visible_for_list()` oculta notificações com `read_at < now - 48h` e preserva não lidas (NULL-safe).
- [ ] A janela é medida por `read_at`, nunca por `created_at`.
- [ ] `/accounts/notifications/` não renderiza notificações lidas há mais de 48h e mantém leituras recentes e não lidas.
- [ ] Badge de não lidas, `notification_open`, `notification_mark_read`, `notifications_mark_all_read` e criação por menção permanecem inalterados.
- [ ] Nenhuma deleção/update de `UserNotification`, `CaseCommunicationMessage` ou `CaseEvent`.
- [ ] `NOTIFICATION_READ_RETENTION_HOURS = 48` definido em `config/settings/base.py` e consumido com fallback defensivo.
- [ ] Nenhum template, URL, migration, permissão, task django-q2 ou arquivo funcional extra foi adicionado.
- [ ] TDD RED → GREEN → REFACTOR comprovado no relatório.
- [ ] Quality gate completo passou:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
- [ ] Relatório `/tmp/notifications-read-visibility-slice-001-report.md` criado com RED/GREEN, snippets antes/depois, gates e rerun.
- [ ] Commit rastreável e push da branch `change/notifications-read-visibility` realizados.

## Regra de atualização

Marque o slice e cada item da Definition of Done somente depois que todos os critérios, inspeções e gates do arquivo do slice tiverem evidência. Qualquer falha mantém o change incompleto. Não marque parcialmente para representar intenção ou progresso.
