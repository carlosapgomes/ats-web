# Tasks: Localizar motivos de intercorrência pós-agendamento

## Status

Change em andamento. Slice 001 concluído e validado.

## Slices

- [X] Slice 001 — Exibir labels em português para motivos de intercorrência
  (`slices/slice-001-localize-reason-labels.md`)

## Definition of Done

- [X] Fonte única de labels de motivos criada ou consolidada.
- [X] Scheduler queue exibe labels em português, não códigos crus.
- [X] Scheduler confirm exibe labels em português, não códigos crus.
- [X] Detalhe NIR continua exibindo labels em português.
- [X] Testes cobrem regressão para `death` e pelo menos um outro motivo.
- [X] Quality gate relevante executado.
- [X] Relatório temporário gerado com `REPORT_PATH`.
- [X] Commit e push realizados.

## Validação recomendada

```bash
uv run pytest apps/scheduler/tests/test_post_schedule_issue.py apps/scheduler/tests/test_views.py apps/intake/tests/test_post_schedule_issue_ack.py apps/intake/tests/test_post_schedule_issue_hardening.py -q
uv run ruff check apps/cases apps/scheduler apps/intake
uv run ruff format --check apps/cases apps/scheduler apps/intake
uv run mypy apps/cases apps/scheduler apps/intake
```

Quality gate completo, se viável:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```
