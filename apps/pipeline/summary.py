"""Summary aggregation and window resolution for periodic supervisor summaries."""

from __future__ import annotations

import zoneinfo
from datetime import UTC, datetime, timedelta
from typing import Any

from django.db.models import Count, Q
from django.db.models.query import QuerySet

from apps.cases.models import Case, CaseStatus

# Statuses considered "in progress" (not terminal)
IN_PROGRESS_STATUSES = [
    CaseStatus.NEW,
    CaseStatus.R1_ACK_PROCESSING,
    CaseStatus.EXTRACTING,
    CaseStatus.LLM_STRUCT,
    CaseStatus.LLM_SUGGEST,
    CaseStatus.R2_POST_WIDGET,
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.WAIT_APPT,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    CaseStatus.CLEANUP_RUNNING,
]

# Statuses where the LLM/reports pipeline has completed (LLM_SUGGEST and beyond)
_REPORTS_PROCESSED_STATUSES = [
    CaseStatus.LLM_SUGGEST,
    CaseStatus.R2_POST_WIDGET,
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.DOCTOR_DENIED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.WAIT_APPT,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.APPT_DENIED,
    CaseStatus.FAILED,
    CaseStatus.R1_FINAL_REPLY_POSTED,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    CaseStatus.CLEANUP_RUNNING,
    CaseStatus.CLEANED,
]

# Statuses that reached the doctor evaluation stage (WAIT_DOCTOR and beyond)
_EVALUATED_STATUSES = [
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.DOCTOR_DENIED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.WAIT_APPT,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.APPT_DENIED,
    CaseStatus.R1_FINAL_REPLY_POSTED,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    CaseStatus.CLEANUP_RUNNING,
    CaseStatus.CLEANED,
]


def resolve_previous_summary_window(
    run_at_utc: datetime,
    timezone_name: str,
    cutoff_hours: str,
) -> tuple[datetime, datetime]:
    """Resolve the most recently completed summary window.

    Given a run time in UTC, a timezone name, and a comma-separated list of
    cutoff hours (in that timezone), returns ``(window_start_utc,
    window_end_utc)`` representing the most recently completed window.

    Example:
        cutoffs ``"7,13,19,1"`` mean summaries are generated at 01:00, 07:00,
        13:00 and 19:00 in the target timezone. If ``run_at_utc`` corresponds
        to 11:30 BRT, the window is 01:00–07:00 BRT.
    """
    tz = zoneinfo.ZoneInfo(timezone_name)
    run_at_local = run_at_utc.astimezone(tz)

    cutoffs = sorted(int(h) for h in cutoff_hours.split(","))

    # Find the most recent cutoff <= current local hour
    current_hour = run_at_local.hour
    past_cutoffs = [h for h in cutoffs if h <= current_hour]

    if past_cutoffs:
        window_end_hour = past_cutoffs[-1]
        window_end_local = run_at_local.replace(
            hour=window_end_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        # No cutoff in past today — use last cutoff of previous day
        window_end_hour = cutoffs[-1]
        window_end_local = (run_at_local - timedelta(days=1)).replace(
            hour=window_end_hour,
            minute=0,
            second=0,
            microsecond=0,
        )

    # Find the previous cutoff
    idx = cutoffs.index(window_end_hour)
    if idx == 0:
        # Wrap around to previous day
        prev_hour = cutoffs[-1]
        window_start_local = (window_end_local - timedelta(days=1)).replace(
            hour=prev_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        prev_hour = cutoffs[idx - 1]
        window_start_local = window_end_local.replace(
            hour=prev_hour,
            minute=0,
            second=0,
            microsecond=0,
        )

    # Convert to UTC
    window_start_utc = window_start_local.astimezone(UTC)
    window_end_utc = window_end_local.astimezone(UTC)

    return (window_start_utc, window_end_utc)


def aggregate_window_metrics(cases_qs: QuerySet[Case]) -> dict[str, Any]:
    """Compute summary metrics from a case queryset.

    Returns a dict with keys matching ``SupervisorSummary`` fields:
        - patients_received
        - reports_processed
        - cases_evaluated
        - accepted_scheduled
        - immediate_admission
        - refused
        - in_progress
    """
    metrics = cases_qs.aggregate(
        patients_received=Count("pk"),
        reports_processed=Count(
            "pk",
            filter=Q(status__in=_REPORTS_PROCESSED_STATUSES),
        ),
        cases_evaluated=Count(
            "pk",
            filter=Q(status__in=_EVALUATED_STATUSES),
        ),
        accepted_scheduled=Count(
            "pk",
            filter=Q(status=CaseStatus.APPT_CONFIRMED),
        ),
        immediate_admission=Count(
            "pk",
            filter=Q(doctor_admission_flow="immediate"),
        ),
        refused=Count(
            "pk",
            filter=Q(status__in=[CaseStatus.DOCTOR_DENIED, CaseStatus.APPT_DENIED]),
        ),
        in_progress=Count(
            "pk",
            filter=Q(status__in=IN_PROGRESS_STATUSES),
        ),
    )
    return metrics
