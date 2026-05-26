"""django-q2 task entry points for PDF extraction.

Routes to cluster "pdf" so the LLM cluster is not blocked by slow or
I/O-heavy PDF extraction.  Tasks are idempotent: they check FSM status
before acting and skip if extraction was already completed.
"""

from __future__ import annotations

import logging
import uuid

from django.utils import timezone
from django_q.tasks import async_task

from apps.cases.models import Case, CaseStatus

logger = logging.getLogger(__name__)


def enqueue_pdf_extraction(case_id: uuid.UUID) -> None:
    """Enqueue the PDF extraction task via django-q2.

    Routes to cluster "pdf" so extraction runs in a dedicated worker
    pool without blocking the LLM pipeline or the web request.
    """
    async_task(
        "apps.intake.tasks.execute_pdf_extraction",
        str(case_id),
        q_options={"cluster": "pdf", "task_name": f"pdf:{case_id}"},
    )


def execute_pdf_extraction(case_id_str: str) -> None:
    """Entry point for django-q2 pdf_worker.

    Loads the ``Case`` and:

    - If status is ``LLM_STRUCT``: re-enqueues the LLM pipeline **without**
      re-extracting the PDF (recovery path for when ``enqueue_pipeline``
      failed on a previous run).
    - If status is ``R1_ACK_PROCESSING`` or ``EXTRACTING``: extracts text
      from the PDF, persists data, advances FSM to ``LLM_STRUCT``, then
      enqueues the LLM pipeline **outside** the extraction try/except so
      that an ``enqueue_pipeline`` failure does **not** attempt an invalid
      FSM transition (the extraction was already successful).
    - If status is ``FAILED`` or beyond: skips (idempotency).

    The ``enqueue_pipeline`` call is deliberately *outside* the extraction
    error handler so that:

    - A failure *during* extraction correctly transitions to ``FAILED``.
    - A failure *after* extraction (enqueue) propagates to django-q2 for
      retry, and on retry the ``LLM_STRUCT`` recovery path re-enqueues
      the pipeline without re-extracting.

    Args:
        case_id_str: String representation of the case UUID.

    Raises:
        ValueError: If no ``Case`` with the given id exists.
    """
    case_id = uuid.UUID(case_id_str)

    # 1. Resolve Case
    try:
        case = Case.objects.get(case_id=case_id)
    except Case.DoesNotExist:
        logger.error("execute_pdf_extraction: Case %s not found", case_id)
        raise ValueError(f"Case {case_id} not found")

    # 2. Idempotency guard — FAILED or beyond → skip
    if case.status not in (
        CaseStatus.R1_ACK_PROCESSING,
        CaseStatus.EXTRACTING,
        CaseStatus.LLM_STRUCT,
    ):
        logger.info(
            "Case %s already processed (status=%s), skipping",
            case_id,
            case.status,
        )
        return

    # 3. LLM_STRUCT recovery path — enqueue pipeline without re-extracting
    if case.status == CaseStatus.LLM_STRUCT:
        logger.info(
            "Case %s already at LLM_STRUCT — re-enqueuing pipeline",
            case_id,
        )
        from apps.pipeline.tasks import enqueue_pipeline

        enqueue_pipeline(case.case_id)
        return

    # 4. Validate pdf_file presence
    if not case.pdf_file:
        logger.warning("Case %s has no pdf_file, marking as failed", case_id)
        _fail_extraction(case)
        return

    # 5. Perform extraction (FSM: R1_ACK → EXTRACTING → LLM_STRUCT)
    try:
        _do_extraction(case)
    except Exception:
        logger.exception("PDF extraction failed for case %s", case_id)
        _fail_extraction(case)
        return

    # 6. Enqueue pipeline AFTER successful extraction, OUTSIDE try/except.
    #    If this fails the exception propagates → django-q2 retries →
    #    step 3 (LLM_STRUCT recovery) calls enqueue_pipeline again.
    from apps.pipeline.tasks import enqueue_pipeline

    enqueue_pipeline(case.case_id)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _do_extraction(case: Case) -> None:
    """Core extraction logic — extracted for clarity and testability.

    Transitions FSM: R1_ACK → EXTRACTING → LLM_STRUCT.
    Does **not** call ``enqueue_pipeline`` — that is the caller's
    responsibility, so that a failure there does not interfere with
    the FSM state.
    """
    from apps.intake.pdf_utils import extract_pdf_text, strip_watermark_and_extract_record

    # Transition: R1_ACK_PROCESSING → EXTRACTING (if not already there)
    if case.status == CaseStatus.R1_ACK_PROCESSING:
        case.start_extraction(user=None)
        case.save()

    # Extract text from PDF file
    extracted = extract_pdf_text(case.pdf_file.path)
    cleaned_text, record_number = strip_watermark_and_extract_record(extracted)

    # Persist extracted data
    case.extracted_text = cleaned_text
    case.agency_record_number = record_number
    case.agency_record_extracted_at = timezone.now()
    case.save()

    # Transition: EXTRACTING → LLM_STRUCT
    case.extraction_complete(success=True, user=None)
    case.save()


def _fail_extraction(case: Case) -> None:
    """Transition case through EXTRACTING to FAILED.

    Handles the FSM path: R1_ACK_PROCESSING → EXTRACTING → FAILED.
    If the case is already at EXTRACTING, skips the first transition.

    **Safe guard:** only intended for cases at ``R1_ACK_PROCESSING``
    or ``EXTRACTING``.  Callers must ensure this precondition.
    """
    if case.status == CaseStatus.R1_ACK_PROCESSING:
        case.start_extraction(user=None)
        case.save()

    case.extraction_complete(success=False, user=None)
    case.save()
