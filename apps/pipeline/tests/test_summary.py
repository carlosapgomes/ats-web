"""Tests for SupervisorSummary model, aggregation, window resolution and task."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone as tz_utils

from apps.cases.models import Case, CaseStatus, SupervisorSummary
from apps.pipeline.summary import (
    aggregate_window_metrics,
    resolve_previous_summary_window,
)

User = get_user_model()

# ────────────────────────────────────────────────────────────────────────────
# resolve_previous_summary_window tests (8)
# ────────────────────────────────────────────────────────────────────────────


class TestResolveWindow:
    """resolve_previous_summary_window determines the last completed window."""

    CUTOFFS = "7,13,19,1"
    TZ = "America/Bahia"  # UTC-3

    def make_utc(self, year, month, day, hour, minute=0):
        return datetime(year, month, day, hour, minute, tzinfo=UTC)

    def test_returns_datetime_tuple(self):
        """Returns a tuple of two aware datetimes."""
        run_at = self.make_utc(2026, 5, 9, 14, 30)  # 11:30 BRT
        result = resolve_previous_summary_window(run_at, self.TZ, self.CUTOFFS)
        assert isinstance(result, tuple)
        assert len(result) == 2
        start, end = result
        assert start.tzinfo is not None
        assert end.tzinfo is not None
        assert start < end

    def test_morning_window(self):
        """Run at 11:30 BRT (14:30 UTC) -> window 01:00-07:00 BRT."""
        run_at = self.make_utc(2026, 5, 9, 14, 30)  # 11:30 BRT
        start, end = resolve_previous_summary_window(run_at, self.TZ, self.CUTOFFS)
        # Window: 01:00-07:00 BRT = 04:00-10:00 UTC
        assert start == self.make_utc(2026, 5, 9, 4, 0)
        assert end == self.make_utc(2026, 5, 9, 10, 0)

    def test_afternoon_window(self):
        """Run at 15:00 BRT (18:00 UTC) -> window 07:00-13:00 BRT."""
        run_at = self.make_utc(2026, 5, 9, 18, 0)  # 15:00 BRT
        start, end = resolve_previous_summary_window(run_at, self.TZ, self.CUTOFFS)
        # Window: 07:00-13:00 BRT = 10:00-16:00 UTC
        assert start == self.make_utc(2026, 5, 9, 10, 0)
        assert end == self.make_utc(2026, 5, 9, 16, 0)

    def test_evening_window(self):
        """Run at 23:00 BRT (02:00+1 UTC) -> window 13:00-19:00 BRT."""
        run_at = self.make_utc(2026, 5, 10, 2, 0)  # 23:00 BRT on May 9
        start, end = resolve_previous_summary_window(run_at, self.TZ, self.CUTOFFS)
        # Window: 13:00-19:00 BRT = 16:00-22:00 UTC on May 9
        assert start == self.make_utc(2026, 5, 9, 16, 0)
        assert end == self.make_utc(2026, 5, 9, 22, 0)

    def test_after_midnight_window(self):
        """Run at 00:30 BRT (03:30 UTC) -> window 13:00-19:00 BRT (prev day).

        At 00:30 BRT the 01:00 cutoff hasn't fired yet, so the last
        completed window is 13:00-19:00.
        """
        run_at = self.make_utc(2026, 5, 10, 3, 30)  # 00:30 BRT on May 10
        start, end = resolve_previous_summary_window(run_at, self.TZ, self.CUTOFFS)
        # Window: May 9 13:00 -> 19:00 BRT = May 9 16:00 -> 22:00 UTC
        assert start == self.make_utc(2026, 5, 9, 16, 0)
        assert end == self.make_utc(2026, 5, 9, 22, 0)

    def test_early_morning_window(self):
        """Run at 04:05 BRT (07:05 UTC) -> window 19:00(prev)-01:00 BRT.

        At 04:05 BRT the last cutoff was 01:00, so the last completed
        window is 19:00(prev day) -> 01:00.
        """
        run_at = self.make_utc(2026, 5, 9, 7, 5)  # 04:05 BRT
        start, end = resolve_previous_summary_window(run_at, self.TZ, self.CUTOFFS)
        # Window: May 8 19:00 -> May 9 01:00 BRT = May 8 22:00 -> May 9 04:00 UTC
        assert start == self.make_utc(2026, 5, 8, 22, 0)
        assert end == self.make_utc(2026, 5, 9, 4, 0)

    def test_window_respects_timezone(self):
        """Different timezone yields different window boundaries."""
        run_at = self.make_utc(2026, 5, 9, 14, 30)
        # America/Sao Paulo is also UTC-3, so same result
        start_sp, end_sp = resolve_previous_summary_window(run_at, "America/Sao_Paulo", self.CUTOFFS)
        assert start_sp == self.make_utc(2026, 5, 9, 4, 0)
        assert end_sp == self.make_utc(2026, 5, 9, 10, 0)

        # Europe/Lisbon is UTC+1 (or UTC+0), so different window
        start_lis, end_lis = resolve_previous_summary_window(run_at, "Europe/Lisbon", self.CUTOFFS)
        # 14:30 UTC = 15:30 Lisbon (UTC+1 in summer)
        # Past cutoffs ≤ 15: 1,7,13 → last=13
        # Window: 07:00-13:00 Lisbon = 06:00-12:00 UTC
        assert start_lis == self.make_utc(2026, 5, 9, 6, 0)
        assert end_lis == self.make_utc(2026, 5, 9, 12, 0)

    def test_custom_cutoffs(self):
        """Custom cutoff hours are respected."""
        run_at = self.make_utc(2026, 5, 9, 18, 0)  # 15:00 BRT
        cutoffs = "8,20"
        start, end = resolve_previous_summary_window(run_at, self.TZ, cutoffs)
        # 15:00 BRT, past cutoffs ≤ 15: [8]
        # Window: 08:00(prev... wait) -> 08:00 ... hmm
        # Last past cutoff: 8 (08:00 BRT)
        # Previous cutoff before 8: none (index 0), so wrap to 20 (previous day)
        # Window: 20:00(prev day) -> 08:00 BRT = 23:00(prev day) -> 11:00 UTC
        assert start == self.make_utc(2026, 5, 8, 23, 0)
        assert end == self.make_utc(2026, 5, 9, 11, 0)


# ────────────────────────────────────────────────────────────────────────────
# aggregate_window_metrics tests (6)
# ────────────────────────────────────────────────────────────────────────────


class TestAggregateWindowMetrics:
    """aggregate_window_metrics computes summary from a case queryset."""

    @pytest.fixture
    def supervisor_user(self, db):
        return User.objects.create_user(username="supervisor", password="testpass")

    @pytest.fixture
    def window_start(self):
        return tz_utils.make_aware(datetime(2026, 5, 9, 10, 0))

    @pytest.fixture
    def window_end(self):
        return tz_utils.make_aware(datetime(2026, 5, 9, 16, 0))

    @pytest.fixture
    def cases_in_window(self, supervisor_user, window_start, window_end):
        """Create cases with various statuses within the window."""
        cases = {}
        mid = window_start + (window_end - window_start) / 2

        # Create cases normally (auto_now_add sets created_at)
        # then override created_at via update()
        def _make(**kw):
            c = Case.objects.create(created_by=supervisor_user, **kw)
            Case.objects.filter(pk=c.pk).update(created_at=mid)
            return Case.objects.get(pk=c.pk)

        # NEW (in progress, not processed, not evaluated)
        cases["new"] = _make(status=CaseStatus.NEW)
        # LLM_SUGGEST (reports_processed, not evaluated)
        cases["llm_suggest"] = _make(status=CaseStatus.LLM_SUGGEST)
        # WAIT_DOCTOR (reports_processed + cases_evaluated, in_progress)
        cases["wait_doctor"] = _make(status=CaseStatus.WAIT_DOCTOR)
        # APPT_CONFIRMED (reports_processed + cases_evaluated + accepted_scheduled)
        cases["appt_confirmed"] = _make(status=CaseStatus.APPT_CONFIRMED)
        # APPT_CONFIRMED with immediate admission
        cases["immediate"] = _make(
            status=CaseStatus.APPT_CONFIRMED,
            doctor_admission_flow="immediate",
        )
        # DOCTOR_DENIED (refused)
        cases["denied"] = _make(status=CaseStatus.DOCTOR_DENIED)
        # APPT_DENIED (refused)
        cases["appt_denied"] = _make(status=CaseStatus.APPT_DENIED)
        return cases

    @pytest.fixture
    def case_outside_window(self, supervisor_user, window_start):
        """Create a case outside the window."""
        before = window_start - timedelta(hours=1)
        c = Case.objects.create(created_by=supervisor_user, status=CaseStatus.NEW)
        Case.objects.filter(pk=c.pk).update(created_at=before)
        return Case.objects.get(pk=c.pk)

    def test_empty_queryset(self):
        """Empty queryset yields zeroes."""
        metrics = aggregate_window_metrics(Case.objects.none())
        expected = {
            "patients_received": 0,
            "reports_processed": 0,
            "cases_evaluated": 0,
            "accepted_scheduled": 0,
            "immediate_admission": 0,
            "refused": 0,
            "in_progress": 0,
        }
        assert metrics == expected

    def test_counts_patients_received(self, cases_in_window, case_outside_window, window_start, window_end):
        """patients_received counts all cases in window."""
        qs = Case.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        metrics = aggregate_window_metrics(qs)
        assert metrics["patients_received"] == 7

    def test_counts_reports_processed(self, cases_in_window, window_start, window_end):
        """reports_processed counts cases that passed LLM pipeline."""
        qs = Case.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        metrics = aggregate_window_metrics(qs)
        # LLM_SUGGEST, WAIT_DOCTOR, APPT_CONFIRMED(x2), DOCTOR_DENIED, APPT_DENIED = 6
        # NEW is not processed
        assert metrics["reports_processed"] == 6

    def test_counts_accepted_scheduled(self, cases_in_window, window_start, window_end):
        """accepted_scheduled counts only APPT_CONFIRMED."""
        qs = Case.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        metrics = aggregate_window_metrics(qs)
        # APPT_CONFIRMED + APPT_CONFIRMED(immediate) = 2
        assert metrics["accepted_scheduled"] == 2

    def test_counts_refused(self, cases_in_window, window_start, window_end):
        """refused counts DOCTOR_DENIED + APPT_DENIED."""
        qs = Case.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        metrics = aggregate_window_metrics(qs)
        assert metrics["refused"] == 2

    def test_counts_in_progress(self, cases_in_window, window_start, window_end):
        """in_progress counts active (non-terminal) cases.

        APPT_CONFIRMED is still in progress (not yet cleaned).
        Terminal statuses like DOCTOR_DENIED and APPT_DENIED are excluded.
        """
        qs = Case.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        metrics = aggregate_window_metrics(qs)
        # NEW + LLM_SUGGEST + WAIT_DOCTOR + APPT_CONFIRMED + APPT_CONFIRMED(immediate) = 5
        # DOCTOR_DENIED and APPT_DENIED are terminal, excluded
        assert metrics["in_progress"] == 5


# ────────────────────────────────────────────────────────────────────────────
# Task tests (3)
# ────────────────────────────────────────────────────────────────────────────


class TestGeneratePeriodicSummary:
    """generate_periodic_summary and enqueue_periodic_summary."""

    @pytest.fixture
    def supervisor_user(self, db):
        return User.objects.create_user(username="supervisor2", password="testpass")

    @pytest.fixture
    def cases(self, supervisor_user):
        """Create a batch of cases for summary testing.

        Cases are created with created_at set to 08:00 BRT (11:00 UTC) so
        they fall within the 07:00-13:00 BRT window when the task runs
        at 13:30 BRT (16:30 UTC).
        """
        # Fixed UTC timestamp: 2026-05-09 11:00 UTC = 08:00 BRT
        ts = datetime(2026, 5, 9, 11, 0, tzinfo=UTC)
        for status in [
            CaseStatus.NEW,
            CaseStatus.LLM_SUGGEST,
            CaseStatus.WAIT_DOCTOR,
            CaseStatus.APPT_CONFIRMED,
            CaseStatus.DOCTOR_DENIED,
        ]:
            c = Case.objects.create(created_by=supervisor_user, status=status)
            Case.objects.filter(pk=c.pk).update(created_at=ts)

    def test_generate_periodic_summary_creates_summary(self, cases):
        """generate_periodic_summary creates a SupervisorSummary record.

        Pass now_utc=16:30 UTC (13:30 BRT) so the resolved window is
        07:00-13:00 BRT = 10:00-16:00 UTC, which includes the test
        cases created at 11:00 UTC.
        """
        from apps.pipeline.tasks import generate_periodic_summary

        frozen_now = datetime(2026, 5, 9, 16, 30, tzinfo=UTC)
        summary = generate_periodic_summary(now_utc=frozen_now)

        assert isinstance(summary, SupervisorSummary)
        assert summary.pk is not None
        assert summary.patients_received == 5
        assert summary.status == "sent"

    def test_generate_periodic_summary_idempotent(self, cases):
        """Same window does not create duplicate summaries."""
        from apps.pipeline.tasks import generate_periodic_summary

        frozen_now = datetime(2026, 5, 9, 16, 30, tzinfo=UTC)
        s1 = generate_periodic_summary(now_utc=frozen_now)
        s2 = generate_periodic_summary(now_utc=frozen_now)
        assert s1.pk == s2.pk  # same record, get_or_create

    def test_enqueue_periodic_summary(self, monkeypatch):
        """enqueue_periodic_summary calls async_task."""
        from apps.pipeline.tasks import enqueue_periodic_summary

        called_args = []

        def mock_async_task(*args, **kwargs):
            called_args.append(args)

        monkeypatch.setattr("apps.pipeline.tasks.async_task", mock_async_task)
        enqueue_periodic_summary()
        assert called_args == [("apps.pipeline.tasks.generate_periodic_summary",)]
