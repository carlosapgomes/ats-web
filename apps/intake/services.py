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
    ExamType,
)

if TYPE_CHECKING:
    from apps.accounts.models import User as AccountsUser

logger = logging.getLogger(__name__)

# ── Exam type validation (centralized — R2/R3) ──────────────────────────


def is_colonoscopy_intake_enabled() -> bool:
    """Flag global de intake: permite novos uploads de colonoscopia.

    Consultada APENAS no intake (novos casos). Nenhum worker/pipeline/fila
    deve consultar esta flag para interromper casos existentes (R3).
    """
    return bool(getattr(settings, "COLONOSCOPY_INTAKE_ENABLED", False))


def validate_exam_type(exam_type: str | None) -> str:
    """Valida e normaliza o tipo de exame declarado.

    Levanta ``ValueError`` se ausente/inválido. Aceita somente valores do
    enum ``ExamType`` — nunca inferência por texto (R1).
    """
    value = (exam_type or "").strip()
    if value not in ExamType.values:
        raise ValueError("Selecione o tipo de exame (EDA ou Colonoscopia).")
    return value


def ensure_exam_type_allowed(exam_type: str | None) -> str:
    """Validação central de choice + flag para criação de novo caso.

    - tipo ausente/inválido → ValueError;
    - colonoscopia com flag de intake desligada → ValueError;
    - EDA sempre permitido.

    Backend é a fonte de verdade; templates/JS apenas melhoram a UX.
    """
    value = validate_exam_type(exam_type)
    if value == ExamType.COLONOSCOPY and not is_colonoscopy_intake_enabled():
        raise ValueError("Colonoscopia ainda não está habilitada para novos envios. Envie lotes apenas de EDA.")
    return value


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
    *,
    exam_type: str | None = None,
) -> tuple[list[Case], list[str]]:
    """Validate and process a batch of uploaded PDFs with optional attachments.

    For each valid file a new ``Case`` is created, the PDF saved, the
    FSM advanced to ``R1_ACK_PROCESSING``, and PDF extraction enqueued.

    ``exam_type`` é obrigatório (R2): um único tipo válido se aplica a TODOS
    os PDFs do lote. A validação ocorre ANTES de qualquer criação de caso;
    tipo ausente/inválido/bloqueado pela flag rejeita o request inteiro.

    Args:
        files: List of uploaded files from ``request.FILES.getlist(...)``.
        user: The authenticated NIR user creating the cases.
        attachments: Optional list of attachment files.
        exam_type: Tipo de exame declarado para o lote inteiro.

    Returns:
        A tuple ``(cases, errors)`` where ``cases`` is the list of
        successfully created ``Case`` instances and ``errors`` is a list
        of human-readable error messages for the files that were rejected.
    """
    cases: list[Case] = []
    errors: list[str] = []

    # Exam type gate FIRST — sem tipo válido, nenhum caso é criado (R2/R3)
    try:
        validated_exam_type = ensure_exam_type_allowed(exam_type)
    except ValueError as exc:
        return [], [str(exc)]

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

        case = _create_case_from_file(file, user, exam_type=validated_exam_type)
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


def _create_case_from_file(
    file: UploadedFile,
    user: AccountsUser,
    *,
    exam_type: str,
) -> Case:
    """Create a single Case from an uploaded PDF file.

    Steps:
    1. Create ``Case(created_by=user, exam_type=exam_type)``.
    2. Save ``pdf_file``.
    3. FSM transition ``NEW → R1_ACK_PROCESSING``.
    4. Enqueue async PDF extraction.

    The caller is responsible for calling ``case.save()`` on each
    transition step.
    """
    # 1. Create case
    case = Case.objects.create(created_by=user, exam_type=exam_type)

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


# ── Corrected resubmission ──────────────────────────────────────────────


def create_corrected_resubmission(
    *,
    original_case: Case,
    pdf_file: UploadedFile,
    user: AccountsUser,
    correction_reason: str,
    attachments: list[UploadedFile] | None = None,
    exam_type: str | None = None,
) -> Case:
    """Create a new Case that explicitly corrects a previous Case.

    ``exam_type`` é opcional neste slice: quando ausente, o novo caso
    preserva o tipo do caso original (herança temporária — a escolha livre
    será do Slice 007). Quando informado, passa pela mesma validação
    central (choice + flag de intake).

    Steps:
    1. Validate correction_reason (required, not blank).
    2. Validate pdf_file (must be a single valid PDF).
    3. Validate attachments per existing rules.
    4. Create new ``Case`` with correction metadata.
    5. Save PDF and advance FSM to ``R1_ACK_PROCESSING``.
    6. Enqueue PDF extraction.
    7. Save attachments on the new case (if provided).
    8. Record ``CASE_CORRECTION_CREATED`` on the new case.
    9. Record ``CASE_MARKED_SUPERSEDED`` on the original case.
    10. Return the new case.

    The original case is NOT modified in status, decision fields,
    attachments, or any other data.
    """
    from django.utils import timezone as tz

    # 0. Exam type — preserve original by default; explicit type validated
    if exam_type is None:
        exam_type = original_case.exam_type
    else:
        exam_type = ensure_exam_type_allowed(exam_type)

    # 1. Validate correction_reason
    reason = (correction_reason or "").strip()
    if not reason:
        raise ValueError("Motivo do reenvio corrigido é obrigatório.")

    # 2. Validate PDF
    validate_single_file(pdf_file)

    # 3. Validate attachments
    att_list = attachments or []
    if att_list:
        validate_attachments(att_list, pdf_count=1)

    # 4. Create new Case with correction metadata
    new_case = Case.objects.create(
        created_by=user,
        exam_type=exam_type,
        corrects_case=original_case,
        correction_reason=reason,
        correction_created_by=user,
        correction_created_at=tz.now(),
    )

    # 5. Save PDF and advance FSM: NEW → R1_ACK_PROCESSING
    new_case.pdf_file = pdf_file
    new_case.save()

    new_case.start_processing(user=user)
    new_case.save()

    # 6. Enqueue PDF extraction
    from apps.intake.tasks import enqueue_pdf_extraction

    enqueue_pdf_extraction(new_case.case_id)

    # 7. Save attachments on the new case (if provided)
    if att_list:
        for att_file in att_list:
            attachment = create_case_attachment(
                case=new_case,
                uploaded_file=att_file,
                user=user,
                upload_phase="initial",
            )
            record_attachment_event(attachment)

    # 8. Record CASE_CORRECTION_CREATED on new case
    new_case._record_event(
        "CASE_CORRECTION_CREATED",
        user=user,
        payload={
            "original_case_id": str(original_case.case_id),
            "original_agency_record_number": original_case.agency_record_number or "",
            "correction_reason": reason,
            "created_by_id": str(user.pk),
        },
    )
    new_case.save()

    # 9. Record CASE_MARKED_SUPERSEDED on original case
    original_case._record_event(
        "CASE_MARKED_SUPERSEDED",
        user=user,
        payload={
            "corrected_case_id": str(new_case.case_id),
            "corrected_agency_record_number": new_case.agency_record_number or "",
            "correction_reason": reason,
            "created_by_id": str(user.pk),
        },
    )
    original_case.save()

    return new_case
