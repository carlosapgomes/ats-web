# Relatório — Follow-up Hardening Slice 002: não marcar notificações como lidas no detalhe contextual

## Resumo

Removeu-se a marcação redundante de notificações como lidas dentro da view `scheduler_context_detail`. A responsabilidade de marcar como lida é exclusiva do `notification_open` em `apps/accounts/views.py`. A view contextual apenas valida autorização e renderiza o detalhe read-only.

## Arquivos alterados

| Arquivo | Mudança |
|---------|---------|
| `apps/scheduler/views.py` | Removeu bloco de `.update(read_at=...)`, import de `UserNotification` dentro da view, e asserts `request.user.is_authenticated` redundantes |
| `apps/scheduler/tests/test_views.py` | Adicionou 2 testes de hardening: acesso direto não marca como lida (single + múltiplas notificações) |
| `apps/accounts/tests/test_notifications.py` | Adicionou 1 teste: `notification_open` ainda marca como lida e redireciona para `context_detail`; + reformat automático via ruff |

## Evidência do RED

```bash
uv run pytest apps/scheduler/tests/test_views.py::TestSchedulerContextDetail::test_scheduler_context_detail_direct_access_does_not_mark_notification_read -x --no-header -q
```

Falha esperada: `assert notif.read_at is None` — a view marcava a notificação como lida.

```
AssertionError: Direct context detail access must NOT mark the notification as read
assert datetime.datetime(2026, 6, 25, 12, 0, 3, ...) is None
```

## Evidência do GREEN

```bash
uv run pytest apps/scheduler/tests/ apps/accounts/tests/test_notifications.py -q --no-header
```

Resultado: **205 passed**

## Snippet antes/depois — `scheduler_context_detail`

**Antes:**
```python
    from apps.accounts.models import UserNotification
    from apps.intake.views import (
        EVENT_DOT_CSS, EVENT_LABELS, STATUS_CSS_CLASS,
        STATUS_LABELS, STEP_STATUS_INDEX, STEPS,
    )

    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )

    # Autorização: deve existir UserNotification para o usuário + caso
    assert request.user.is_authenticated
    if not _scheduler_has_context_notification(request.user, case):
        raise Http404("Nenhuma notificação encontrada para este caso.")

    # ── Mark notification as read ────────────────────────────────────────
    now = timezone.now()
    assert request.user.is_authenticated
    UserNotification.objects.filter(
        recipient=request.user,
        case=case,
        read_at__isnull=True,
    ).update(read_at=now)

    # ── Build context ────────────────────────────────────────────────────
```

**Depois:**
```python
    from apps.intake.views import (
        EVENT_DOT_CSS, EVENT_LABELS, STATUS_CSS_CLASS,
        STATUS_LABELS, STEP_STATUS_INDEX, STEPS,
    )

    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )

    # Autorização: deve existir UserNotification para o usuário + caso
    # A marcação como lida é feita exclusivamente por notification_open em accounts.
    if not _scheduler_has_context_notification(request.user, case):
        raise Http404("Nenhuma notificação encontrada para este caso.")

    # ── Build context ────────────────────────────────────────────────────
```

## Validação completa

```text
uv run ruff check .         → All checks passed!
uv run ruff format --check . → 166 files already formatted
uv run mypy .               → Success: no issues found in 185 source files
uv run pytest               → 1539 passed
```

## Confirmações

- ✅ `notification_open` ainda marca notificações como lidas (teste `test_notification_open_still_marks_and_redirects_scheduler_non_wait_appt`)
- ✅ Acesso direto ao `context_detail` não marca notificações como lidas (testes `test_scheduler_context_detail_direct_access_does_not_mark_notification_read` + `_does_not_mark_notification_read_with_multiple_unread`)
- ✅ Nenhuma mudança em FSM, models, migrations, comunicação ou Slice 003
- ✅ Autorização continua exigindo `UserNotification` para o par usuário+caso
