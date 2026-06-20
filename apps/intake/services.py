"""Business logic for intake file processing.

Separates file validation and Case creation from the view layer,
keeping the view thin and the logic testable in isolation.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.cases.models import (
    ACCEPTED_ATTACHMENT_CONTENT_TYPES,
    ACCEPTED_ATTACHMENT_EXTENSIONS,
    Case,
    CaseAttachment,
)

if TYPE_CHECKING:
    from apps.accounts.models import User as AccountsUser

logger = logging.getLogger(__name__)

# ── Validation ──────────────────────────────────────────────────────────


class FileValidationError(ValueError):
    """A single file failed validation (does not imply batch rejection)."""


class BatchValidationError(ValueError):
    """The entire batch is invalid (e.g. empty or exceeds batch limit)."""


class AttachmentValidationError(ValueError):
    """An attachment file failed validation (rejects the whole batch)."""


def validate_single_file(file: UploadedFile) -> None:
    """Validate a single uploaded PDF file.

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


# ── Attachment validation ────────────────────────────────────────────────


def validate_attachment_file(file: UploadedFile) -> None:
    """Validate a single attachment file.

    Raises ``AttachmentValidationError`` if the file fails any check.

    Checks:
    1. Extension must be .pdf, .jpg, .jpeg, or .png.
    2. Content-type must be one of the accepted types.
    3. File size must not exceed ``INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE``.
    """
    file_name = file.name or ""
    file_size = file.size or 0
    content_type = (file.content_type or "").lower()

    # Extension check
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in ACCEPTED_ATTACHMENT_EXTENSIONS:
        raise AttachmentValidationError(f'"{file_name}" formato não aceito. Use PDF, JPEG ou PNG.')

    # Content-type check (belt-and-suspenders)
    if content_type and content_type not in ACCEPTED_ATTACHMENT_CONTENT_TYPES:
        raise AttachmentValidationError(f'"{file_name}" tipo de conteúdo não aceito: {content_type}.')

    # Size check
    max_size = settings.INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE
    if file_size > max_size:
        raise AttachmentValidationError(
            f'"{file_name}" excede o limite de {max_size // (1024 * 1024)} MB ({file_size / (1024 * 1024):.1f} MB).'
        )


def validate_attachments(
    attachments: list[UploadedFile],
    pdf_count: int,
) -> None:
    """Validate the full set of attachments before processing.

    Raises ``AttachmentValidationError`` on first violation.

    Checks:
    1. Attachments are only allowed when there is exactly 1 PDF.
    2. Maximum 10 attachments.
    3. Total size of attachments does not exceed per-case limit.
    4. Per-file validation via ``validate_attachment_file``.
    """
    if not attachments:
        return

    # Only allowed with exactly 1 PDF
    if pdf_count != 1:
        raise AttachmentValidationError(
            "Anexos só são permitidos quando há exatamente 1 relatório principal. "
            "Remova os anexos ou envie apenas 1 PDF."
        )

    # Max count
    max_attachments = settings.INTAKE_MAX_ATTACHMENTS_PER_CASE
    if len(attachments) > max_attachments:
        raise AttachmentValidationError(f"Máximo de {max_attachments} anexos por caso. Recebidos: {len(attachments)}.")

    # Per-file validation
    for att in attachments:
        validate_attachment_file(att)

    # Total size
    total_bytes = sum(f.size or 0 for f in attachments)
    max_total = settings.INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE
    if total_bytes > max_total:
        raise AttachmentValidationError(
            f"Tamanho total dos anexos ({total_bytes / (1024 * 1024):.1f} MB) "
            f"excede o limite de {max_total // (1024 * 1024)} MB."
        )


# ── Attachment creation ─────────────────────────────────────────────────


def create_case_attachment(
    *,
    case: Case,
    uploaded_file: UploadedFile,
    user: AccountsUser,
    upload_phase: str = "initial",
) -> CaseAttachment:
    """Create a CaseAttachment from an uploaded file.

    Computes SHA256 hash, saves metadata, and creates the record.
    The file is already saved via the FileField on save().
    """
    file_content = uploaded_file.read()
    sha256 = hashlib.sha256(file_content).hexdigest()
    file_name = uploaded_file.name or ""
    content_type = uploaded_file.content_type or "application/octet-stream"
    file_size = uploaded_file.size or len(file_content)
    ext = os.path.splitext(file_name)[1].lower()

    # Rewind the file for Django's storage backend
    uploaded_file.seek(0)

    attachment = CaseAttachment(
        case=case,
        file=uploaded_file,
        original_filename=file_name,
        stored_filename=f"{case.case_id}{ext}",
        content_type=content_type,
        size_bytes=file_size,
        sha256=sha256,
        uploaded_by=user,
        upload_phase=upload_phase,
        uploaded_when_case_status=case.status,
    )
    attachment.save()
    return attachment


def record_attachment_event(attachment: CaseAttachment) -> None:
    """Record CASE_ATTACHMENT_ADDED audit event."""
    from apps.cases.models import CaseEvent

    CaseEvent.objects.create(
        case=attachment.case,
        event_type="CASE_ATTACHMENT_ADDED",
        actor=attachment.uploaded_by,
        actor_type="human",
        payload={
            "attachment_id": str(attachment.attachment_id),
            "original_filename": attachment.original_filename,
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
            "sha256": attachment.sha256,
        },
    )


# ── Processing ──────────────────────────────────────────────────────────


def process_uploaded_files(
    files: list[UploadedFile],
    user: AccountsUser,
    attachments: list[UploadedFile] | None = None,
) -> tuple[list[Case], list[str]]:
    """Validate and process a batch of uploaded PDFs with optional attachments.

    For each valid file a new ``Case`` is created, the PDF saved, the
    FSM advanced to ``R1_ACK_PROCESSING``, and PDF extraction enqueued.

    If attachments are provided and valid, they are saved as CaseAttachment
    records linked to the single case created.

    Args:
        files: List of uploaded files from ``request.FILES.getlist(...)``.
        user: The authenticated NIR user creating the cases.
        attachments: Optional list of attachment files.

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

    # Validate and process attachments
    att_list = attachments or []
    attachment_error: str | None = None
    if att_list:
        try:
            validate_attachments(att_list, pdf_count=len(files))
        except AttachmentValidationError as exc:
            attachment_error = str(exc)
            # If multi-PDF, we still create cases but reject attachments
            # If single PDF with invalid attachments, we don't create cases
            if len(files) == 1:
                errors.append(str(exc))
                return [], errors

    # Per-file validation & processing
    for file in files:
        try:
            validate_single_file(file)
        except FileValidationError as exc:
            errors.append(str(exc))
            continue

        case = _create_case_from_file(file, user)
        cases.append(case)

    # If there was a multi-PDF attachment error, report it after creating cases
    if attachment_error:
        errors.append(attachment_error)

    # If we have exactly 1 case and valid attachments, save them
    if cases and att_list and len(cases) == 1 and not attachment_error:
        case = cases[0]
        for att_file in att_list:
            try:
                attachment = create_case_attachment(
                    case=case,
                    uploaded_file=att_file,
                    user=user,
                    upload_phase="initial",
                )
                record_attachment_event(attachment)
            except Exception as exc:
                logger.exception("Failed to save attachment for case %s", case.case_id)
                errors.append(f"Erro ao salvar anexo: {exc}")

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
