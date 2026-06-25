# Follow-up hardening Slice 002: não marcar notificações como lidas no detalhe contextual

## Prompt para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, and:
- openspec/changes/scheduler-historical-intercurrence-requests/proposal.md
- openspec/changes/scheduler-historical-intercurrence-requests/design.md
- openspec/changes/scheduler-historical-intercurrence-requests/tasks.md
- openspec/changes/scheduler-historical-intercurrence-requests/slices/slice-002-mentioned-scheduler-readonly-context.md

Implement ONLY a short hardening follow-up for Slice 002.

Problem:
apps/scheduler/views.py::scheduler_context_detail currently marks all unread UserNotification rows for request.user + case as read when the contextual detail is opened directly:

UserNotification.objects.filter(
    recipient=request.user,
    case=case,
    read_at__isnull=True,
).update(read_at=now)

This is redundant and subtly expands scope. Per Slice 002 R5, marking a notification as read is already the responsibility of accounts notification_open. The context detail should only validate access and render the read-only detail.

Required corrections:
1. Remove notification read-marking from scheduler_context_detail.
2. Remove redundant assert request.user.is_authenticated lines in scheduler_context_detail; @login_required already guarantees authentication.
3. Keep authorization unchanged: scheduler_context_detail must still require an existing UserNotification for request.user + case.
4. Keep notification_open behavior unchanged: opening via the notifications inbox should still mark the specific notification as read before redirect.

TDD required:
Add/adjust tests first so RED fails before implementation.

Suggested tests:

1. test_scheduler_context_detail_direct_access_does_not_mark_notification_read
   - Create scheduler user with active_role=scheduler.
   - Create a case outside WAIT_APPT that can be opened through context detail.
   - Create an unread UserNotification(recipient=scheduler, case=case).
   - Login as scheduler and GET reverse("scheduler:context_detail", kwargs={"case_id": case.case_id}).
   - Assert status_code == 200.
   - Refresh notification and assert read_at is still None.

2. test_notification_open_still_marks_scheduler_notification_read_and_redirects
   - Create scheduler user with active_role=scheduler.
   - Create case outside WAIT_APPT.
   - Create unread UserNotification(recipient=scheduler, case=case).
   - Login and GET/POST whatever the existing notification_open test uses for opening notification.
   - Assert notification.read_at is not None.
   - Assert redirect points to scheduler:context_detail for non-WAIT_APPT case.
   - If an equivalent existing test already covers this, update/keep it and mention in report.

3. Optional hardening:
   - Create two unread notifications for the same user/case if allowed by constraints via different communication_message or setup.
   - Direct GET context_detail must not mark either one as read.
   - Only add this if setup is cheap; do not expand scope.

Scope restrictions:
- Do not implement Slice 003.
- Do not change scheduler historical search.
- Do not change CHD → NIR historical message behavior.
- Do not change notification models/migrations.
- Do not change resolve_notification_redirect_url except if tests reveal a regression directly related to this hardening.
- Do not change FSM, locks, case statuses, communication service behavior, or templates unless strictly necessary.
- Do not alter WAIT_APPT notification redirect semantics.

Implementation hints:
- In apps/scheduler/views.py::scheduler_context_detail, remove the import of UserNotification inside the view if it becomes unused.
- Keep _scheduler_has_context_notification as the single authorization helper.
- Remove now = timezone.now() if it becomes unused in that function/file section.
- Ensure ruff removes unused imports.

Expected behavior after fix:
- Opening /scheduler/context/<case_id>/ directly with a valid notification authorizes and renders the read-only detail.
- Direct context detail access does not mark any notification as read.
- Opening through accounts notification_open still marks the opened notification as read.
- No workflow action, lock behavior, FSM state, or communication posting behavior changes.

Validation:
Run at minimum:
uv run pytest apps/scheduler/tests/test_views.py apps/accounts/tests/test_notifications.py -q
uv run ruff check apps/scheduler apps/accounts
uv run ruff format --check apps/scheduler apps/accounts
uv run mypy apps/scheduler apps/accounts

If feasible, run full quality gate:
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest

Create a temporary markdown report:
/tmp/scheduler-historical-intercurrence-requests-slice-002-hardening-notification-read-report.md

Report must include:
- summary;
- files changed;
- RED evidence;
- GREEN evidence;
- before/after snippet of scheduler_context_detail;
- validation commands/results;
- confirmation that notification_open still marks notifications as read;
- confirmation that direct context_detail does not mark notifications as read;
- confirmation that no FSM/model/migration/Slice 003 changes were made.

Update openspec/changes/scheduler-historical-intercurrence-requests/tasks.md only if the project convention requires recording hardening notes; do not mark Slice 003 as started.

Commit and push.

Return:
REPORT_PATH=/tmp/scheduler-historical-intercurrence-requests-slice-002-hardening-notification-read-report.md

Stop after this hardening. Do not start Slice 003.
```
