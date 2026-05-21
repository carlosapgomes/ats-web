"""django-q2 task entry points for pipeline execution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from django_q.tasks import async_task

if TYPE_CHECKING:
    from apps.cases.models import SupervisorSummary


def enqueue_pipeline(case_id: uuid.UUID) -> None:
    """Enqueue the pipeline task via django-q2.

    Routes to cluster "llm" so the PDF extraction cluster is not blocked.
    Called synchronously from views; the actual work runs in a worker.
    """
    async_task(
        "apps.pipeline.tasks.execute_pipeline",
        str(case_id),
        q_options={"cluster": "llm", "task_name": f"llm:{case_id}"},
    )


def execute_pipeline(case_id_str: str) -> None:
    """Entry point for django-q2 worker.

    Loads the case and runs the full pipeline orchestrator.
    """
    from apps.pipeline.orchestrator import run_pipeline

    run_pipeline(uuid.UUID(case_id_str))


def generate_periodic_summary(now_utc: datetime | None = None) -> SupervisorSummary:
    """Generate a periodic supervisor summary for the last completed window.

    Resolves the summary window, aggregates metrics from cases created
    within that window, and persists the result via get_or_create for
    idempotency.

    Args:
        now_utc: Override current time (UTC) for testing. Defaults to now.

    Returns the SupervisorSummary instance (existing or newly created).
    """

    from django.conf import settings

    from apps.cases.models import Case, SupervisorSummary
    from apps.pipeline.summary import (
        aggregate_window_metrics,
        resolve_previous_summary_window,
    )

    if now_utc is None:
        now_utc = datetime.now(UTC)

    cutoff_hours = getattr(settings, "SUMMARY_CUTOFF_HOURS", "7,13,19,1")
    tz_name = getattr(settings, "SUMMARY_TIMEZONE", settings.TIME_ZONE)

    window_start, window_end = resolve_previous_summary_window(
        now_utc,
        tz_name,
        cutoff_hours,
    )

    cases_qs = Case.objects.filter(
        created_at__gte=window_start,
        created_at__lt=window_end,
    )
    metrics = aggregate_window_metrics(cases_qs)

    summary, _created = SupervisorSummary.objects.get_or_create(
        window_start=window_start,
        window_end=window_end,
        defaults={
            "patients_received": metrics["patients_received"],
            "reports_processed": metrics["reports_processed"],
            "cases_evaluated": metrics["cases_evaluated"],
            "accepted_scheduled": metrics["accepted_scheduled"],
            "immediate_admission": metrics["immediate_admission"],
            "refused": metrics["refused"],
            "in_progress": metrics["in_progress"],
            "status": "sent",
        },
    )
    return summary


def enqueue_periodic_summary() -> None:
    """Enqueue the periodic summary generation task via django-q2."""
    async_task("apps.pipeline.tasks.generate_periodic_summary")
