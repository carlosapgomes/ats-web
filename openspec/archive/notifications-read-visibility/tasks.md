<!-- markdownlint-disable MD013 -->

# Tasks: Ocultar notificações lidas há mais de 48h

## Slice vertical

- [x] Slice 001 — Janela de visibilidade de leitura end-to-end na lista do usuário (`slices/slice-001-hide-read-older-48h.md`)

## Definition of Done do change

- [x] `visible_for_list()` oculta notificações com `read_at < now - 48h` e preserva não lidas (NULL-safe).
- [x] A janela é medida por `read_at`, nunca por `created_at`.
- [x] `/accounts/notifications/` não renderiza notificações lidas há mais de 48h e mantém leituras recentes e não lidas.
- [x] Badge de não lidas, `notification_open`, `notification_mark_read`, `notifications_mark_all_read` e criação por menção permanecem inalterados.
- [x] Nenhuma deleção/update de `UserNotification`, `CaseCommunicationMessage` ou `CaseEvent`.
- [x] `NOTIFICATION_READ_RETENTION_HOURS = 48` definido em `config/settings/base.py` e consumido com fallback defensivo.
- [x] Nenhum template, URL, migration, permissão, task django-q2 ou arquivo funcional extra foi adicionado.
- [x] TDD RED → GREEN → REFACTOR comprovado no relatório.
- [x] Quality gate completo passou:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Pytest final registrou exit code 0, zero failures/errors e `passed_final >= passed_baseline` (3197 vs 3191).
- [x] Relatório `/tmp/notifications-read-visibility-slice-001-report.md` criado com RED/GREEN, snippets antes/depois, gates e rerun (consolidado pelo parent a partir do report inline do worker).
- [x] Commit rastreável criado pelo parent (loop parent-controlled); push da branch `change/notifications-read-visibility` pendente de instrução explícita do usuário.

> Loop parent-controlled concluído em 2026-09-05: reviewer `Merge verdict: OK with
> notes` (0 P0/P1; 1 P2 report-only: `get_queryset()` sem `hints=self._hints`,
> sem efeito hoje — nenhum db router no projeto).

## Regra de atualização

Marque o slice e cada item da Definition of Done somente depois que todos os critérios, inspeções e gates do arquivo do slice tiverem evidência. Qualquer falha mantém o change incompleto. Não marque parcialmente para representar intenção ou progresso.
