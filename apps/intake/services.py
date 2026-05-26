"""Business logic for intake file processing.

Separates file validation and Case creation from the view layer,
keeping the view thin and the logic testable in isolation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.cases.models import Case

if TYPE_CHECKING:
    from apps.accounts.models import User as AccountsUser

logger = logging.getLogger(__name__)

# ── Validation ──────────────────────────────────────────────────────────


class FileValidationError(ValueError):
    """A single file failed validation (does not imply batch rejection)."""


class BatchValidationError(ValueError):
    """The entire batch is invalid (e.g. empty or exceeds batch limit)."""


def validate_single_file(file: UploadedFile) -> None:
    """Validate a single uploaded file.

    Raises ``FileValidationError`` if the file fails any check.

    Checks (in order):
    1. Extension must be ``.pdf``.
    2. File size must not exceed ``INTAKE_MAX_UPLOAD_BYTES_PER_FILE``.
    """
    file_name = file.name or ""
    file_size = file.size or 0

    # Extension check (belt-and-suspenders with form validator)
    if not file_name.lower().endswith(".pdf"):
        raise FileValidationError(f'"{file_name}" não é um arquivo PDF.')

    max_file_size = settings.INTAKE_MAX_UPLOAD_BYTES_PER_FILE
    if file_size > max_file_size:
        raise FileValidationError(
            f'"{file_name}" excede o limite de {max_file_size // (1024 * 1024)} MB '
            f"({file_size / (1024 * 1024):.1f} MB)."
        )


def validate_batch(files: list[UploadedFile]) -> None:
    """Validate the entire batch before per-file processing.

    Raises ``BatchValidationError`` if the batch is rejected outright.
    """
    if not files:
        raise BatchValidationError("Nenhum arquivo enviado.")

    max_files = settings.INTAKE_MAX_FILES_PER_BATCH
    if len(files) > max_files:
        raise BatchValidationError(f"Máximo de {max_files} arquivos por lote. Recebidos: {len(files)}.")

    total_bytes = sum(f.size or 0 for f in files)
    max_batch = settings.INTAKE_MAX_UPLOAD_BYTES_PER_BATCH
    if total_bytes > max_batch:
        raise BatchValidationError(
            f"Tamanho total do lote ({total_bytes / (1024 * 1024):.1f} MB) "
            f"excede o limite de {max_batch // (1024 * 1024)} MB."
        )


# ── Processing ──────────────────────────────────────────────────────────


def process_uploaded_files(
    files: list[UploadedFile],
    user: AccountsUser,
) -> tuple[list[Case], list[str]]:
    """Validate and process a batch of uploaded PDFs.

    For each valid file a new ``Case`` is created, the PDF saved, the
    FSM advanced to ``R1_ACK_PROCESSING``, and PDF extraction enqueued.

    Args:
        files: List of uploaded files from ``request.FILES.getlist(...)``.
        user: The authenticated NIR user creating the cases.

    Returns:
        A tuple ``(cases, errors)`` where ``cases`` is the list of
        successfully created ``Case`` instances and ``errors`` is a list
        of human-readable error messages for the files that were rejected.
    """
    cases: list[Case] = []
    errors: list[str] = []

    # Batch-level validation (empty, too many, too large total)
    try:
        validate_batch(files)
    except BatchValidationError as exc:
        return [], [str(exc)]

    # Per-file validation & processing
    for file in files:
        try:
            validate_single_file(file)
        except FileValidationError as exc:
            errors.append(str(exc))
            continue

        case = _create_case_from_file(file, user)
        cases.append(case)

    return cases, errors


def _create_case_from_file(file: UploadedFile, user: AccountsUser) -> Case:
    """Create a single Case from an uploaded PDF file.

    Steps:
    1. Create ``Case(created_by=user)``.
    2. Save ``pdf_file``.
    3. FSM transition ``NEW → R1_ACK_PROCESSING``.
    4. Enqueue async PDF extraction.

    The caller is responsible for calling ``case.save()`` on each
    transition step.
    """
    # 1. Create case
    case = Case.objects.create(created_by=user)

    # 2. Save PDF
    case.pdf_file = file
    case.save()

    # 3. FSM: NEW → R1_ACK_PROCESSING
    case.start_processing(user=user)
    case.save()

    # 4. Enqueue async PDF extraction (runs in background cluster "pdf")
    from apps.intake.tasks import enqueue_pdf_extraction

    enqueue_pdf_extraction(case.case_id)

    return case
