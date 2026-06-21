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

    # 3. LLM_STRUCT recovery path — re-evaluate regulation gate before enqueue.
    #    A previous attempt may have crashed after extraction_complete() but before
    #    the gate decision; never bypass the gate on django-q2 retry.
    if case.status == CaseStatus.LLM_STRUCT:
        logger.info(
            "Case %s already at LLM_STRUCT — re-evaluating regulation gate before pipeline enqueue",
            case_id,
        )
        from apps.intake.regulation_gate import evaluate_regulation_report_text

        gate_result = evaluate_regulation_report_text(case.extracted_text or "")
        if not gate_result.accepted:
            _handle_regulation_gate_failure(case, gate_result)
            return

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

    # 6. Regulation gate check — block LLM pipeline for non-regulation documents.
    from apps.intake.regulation_gate import evaluate_regulation_report_text

    gate_result = evaluate_regulation_report_text(case.extracted_text or "")
    if not gate_result.accepted:
        _handle_regulation_gate_failure(case, gate_result)
        return

    # 7. Enqueue pipeline AFTER successful extraction + gate pass, OUTSIDE
    #    try/except.  If this fails the exception propagates → django-q2
    #    retries → step 3 (LLM_STRUCT recovery) calls enqueue_pipeline again.
    from apps.pipeline.tasks import enqueue_pipeline

    enqueue_pipeline(case.case_id)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _do_extraction(case: Case) -> None:
    """Core extraction logic — extracted for clarity and testability.

    Transitions FSM: R1_ACK → EXTRACTING → LLM_STRUCT.
    Does **not** call ``enqueue_pipeline`` — that is the caller's
    responsibility, so that a failure there does not interfere with
    the FSM state.

    Sets ``case._explicit_record_number`` as a transient attribute
    (not persisted to DB) so the caller can determine whether the
    saved ``agency_record_number`` was extracted from an explicit
    pattern or is a timestamp fallback.
    """
    from apps.intake.pdf_utils import (
        extract_explicit_record_number,
        extract_pdf_text,
        extract_regulation_days_on_screen,
        strip_watermark_and_extract_record,
    )

    # Transition: R1_ACK_PROCESSING → EXTRACTING (if not already there)
    if case.status == CaseStatus.R1_ACK_PROCESSING:
        case.start_extraction(user=None)
        case.save()

    # Extract text from PDF file
    extracted = extract_pdf_text(case.pdf_file.path)
    cleaned_text, record_number = strip_watermark_and_extract_record(extracted)

    # Track whether record number was extracted from explicit pattern
    # (not a timestamp fallback) for regulation gate handling.
    case._explicit_record_number = extract_explicit_record_number(extracted)  # type: ignore[attr-defined]

    # Persist extracted data
    case.extracted_text = cleaned_text
    case.agency_record_number = record_number  # may be fallback; caller can clear
    case.agency_record_extracted_at = timezone.now()
    case.regulation_days_on_screen = extract_regulation_days_on_screen(cleaned_text)
    case.save()

    # Transition: EXTRACTING → LLM_STRUCT
    case.extraction_complete(success=True, user=None)
    case.save()


def _handle_regulation_gate_failure(case: Case, gate_result: object) -> None:
    """Handle regulation gate rejection: bypass LLM pipeline, route to manual review.

    The case is at ``LLM_STRUCT`` after a successful extraction.  This helper:
    1. Clears fallback (timestamp) record numbers to avoid false evidence.
    2. Sets ``suggested_action`` with ``manual_review_required``.
    3. Records ``REGULATION_REPORT_GATE_FAILED`` event with gate evidence.
    4. Calls ``scope_gate_bypass`` (LLM_STRUCT → WAIT_R1_CLEANUP_THUMBS).
    5. Records ``FINAL_REPLY_POSTED`` event (pattern from orchestrator.py).

    **Does not** call ``enqueue_pipeline`` — that is the caller's choice.

    Args:
        case: Case instance (must be at LLM_STRUCT).
        gate_result: ``RegulationReportGateResult`` from ``evaluate_regulation_report_text``.
    """
    gate = gate_result  # noqa: F841 — used via local name for brevity

    # 1. Clear fallback record number if not explicitly extracted
    if not getattr(case, "_explicit_record_number", ""):
        case.agency_record_number = ""
        case.agency_record_extracted_at = None

    # 2. Set suggested_action with manual_review_required
    if hasattr(gate, "reason_text"):
        reason_text = gate.reason_text
    elif isinstance(gate, dict):
        reason_text = gate.get("reason_text", "")
    else:
        reason_text = str(gate)

    case.suggested_action = {
        "schema_version": "1.1",
        "language": "pt-BR",
        "decision": "manual_review_required",
        "suggestion": "manual_review_required",
        "reason_code": "invalid_regulation_report",
        "reason_text": reason_text,
        "evidence": {
            "matched_header": getattr(gate, "matched_header", False),
            "matched_institutional_signals": getattr(gate, "matched_institutional_signals", []),
            "matched_operational_sections": getattr(gate, "matched_operational_sections", []),
            "text_length": getattr(gate, "text_length", 0),
        },
    }
    case.save()

    # 3. Record gate failure event
    case._record_event(
        "REGULATION_REPORT_GATE_FAILED",
        payload={
            "reason_code": "invalid_regulation_report",
            "reason_text": reason_text,
            "matched_header": getattr(gate, "matched_header", False),
            "matched_institutional_signals": getattr(gate, "matched_institutional_signals", []),
            "matched_operational_sections": getattr(gate, "matched_operational_sections", []),
            "text_length": getattr(gate, "text_length", 0),
        },
    )
    case.save()  # persist event BEFORE FSM transition overwrites _pending_event

    # 4. Scope gate bypass: LLM_STRUCT → WAIT_R1_CLEANUP_THUMBS
    case.scope_gate_bypass(reason_code="invalid_regulation_report")
    case.save()

    # 5. Record final reply posted (pattern from orchestrator.py)
    case._record_event("FINAL_REPLY_POSTED")
    case.save()

    logger.info(
        "Regulation gate blocked case %s: reason_code=%s, matched_header=%s, "
        "matched_signals=%d, matched_sections=%d, text_length=%d",
        case.case_id,
        "invalid_regulation_report",
        getattr(gate, "matched_header", False),
        len(getattr(gate, "matched_institutional_signals", [])),
        len(getattr(gate, "matched_operational_sections", [])),
        getattr(gate, "text_length", 0),
    )


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
