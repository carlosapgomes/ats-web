"""Business logic for intake file processing.

Separates file validation and Case creation from the view layer,
keeping the view thin and the logic testable in isolation.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.cases.models import (
    ACCEPTED_ATTACHMENT_CONTENT_TYPES,
    ACCEPTED_ATTACHMENT_EXTENSIONS,
    EDA_COLONOSCOPY,
    Case,
    CaseAttachment,
    CaseStatus,
    ProcedureType,
)
from apps.cases.procedures import (
    get_declared_procedure_types,
    reset_detection_and_doctor_statuses,
    set_declared_procedures,
    sync_declared_projection,
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


# Seleção declarada aceita no intake (Slice 001): EDA, Colonoscopia ou a
# combinação eda_colonoscopy. O valor combinado NÃO é membro de
# ProcedureType.values — é chave de seleção derivada da projeção, não field
# choice.
_DECLARED_SELECTION_VALUES: frozenset[str] = frozenset({ProcedureType.EDA, ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY})


def validate_exam_type(exam_type: str | None) -> str:
    """Valida e normaliza a seleção declarada (intake e correção NIR).

    Levanta ``ValueError`` se ausente/inválida. Aceita EDA, Colonoscopia ou a
    combinação ``eda_colonoscopy`` (chave de seleção derivada) — nunca
    inferência por texto (R1). Desde o Slice 005 a correção NIR aceita as
    TRÊS seleções, então esta validação é compartilhada por novos
    intakes/reenvios e pela correção; o gate de flag de intake fica em
    ``ensure_exam_type_allowed`` (não aqui).
    """
    value = (exam_type or "").strip()
    if value not in _DECLARED_SELECTION_VALUES:
        raise ValueError("Selecione o tipo de exame (EDA, Colonoscopia ou EDA + Colonoscopia).")
    return value


def ensure_exam_type_allowed(exam_type: str | None) -> str:
    """Validação central de choice + flag para criação de novo caso.

    - tipo ausente/inválido → ValueError;
    - colonoscopia ou combinação com flag de intake desligada → ValueError;
    - EDA sempre permitido.

    Backend é a fonte de verdade; templates/JS apenas melhoram a UX.
    """
    value = validate_exam_type(exam_type)
    if value in (ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY) and not is_colonoscopy_intake_enabled():
        raise ValueError(
            "Colonoscopia e EDA + Colonoscopia ainda não estão habilitadas para novos envios. "
            "Envie lotes apenas de EDA."
        )
    return value


def _procedure_types_for_selection(exam_type: str) -> tuple[str, ...]:
    """Mapeia a seleção declarada para o conjunto de procedimentos.

    ``eda_colonoscopy`` (chave derivada) → (eda, colonoscopy); tipos únicos →
    o próprio.
    """
    if exam_type == EDA_COLONOSCOPY:
        return (ProcedureType.EDA, ProcedureType.COLONOSCOPY)
    return (exam_type,)


# ── Correção de tipo e confirmação NIR serializadas (Slice 006) ───────────

# Reason codes do scope gate elegíveis para correção de tipo: o NIR vê
# declarado/detectado e corrige o tipo no MESMO caso (spec exam-type-correction).
# non_eda_request e invalid_regulation_report NÃO são elegíveis: não se
# resolvem trocando o tipo (fora do escopo EDA/colonoscopia e falha de gate
# de regulação, respectivamente).
EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES: frozenset[str] = frozenset(
    {"exam_type_mismatch", "mixed_exam_request", "unknown_exam_type"}
)

# Motivos de correção selecionáveis pelo NIR (payload de CASE_PROCEDURE_DECLARATION_CORRECTED).
EXAM_TYPE_CORRECTION_REASONS: dict[str, str] = {
    "nir_identified_exam": "Tipo identificado na revisão manual do NIR",
    "declared_type_incorrect": "Tipo declarado incorreto no envio original",
    "other": "Outro motivo",
}

# Reserva NIR exigida por correção e confirmação (mesmo protocolo, C1/C3).
NIR_RECEIPT_CONTEXT: str = "nir_receipt"
NIR_RECEIPT_ROLE: str = "nir"

# Atraso do retry automático (Schedule ONCE) quando o enqueue pós-commit falha.
RECOVERY_SCHEDULE_DELAY_SECONDS: int = 60


class EnqueueAfterCommitError(RuntimeError):
    """Falha pós-commit ao enfileirar o reprocessamento LLM.

    A correção já foi commitada (caso em ``LLM_STRUCT``). ``recovery_scheduled``
    indica se um retry automático foi programado via ``Schedule`` ONCE.
    """

    def __init__(self, *, recovery_scheduled: bool, original: Exception) -> None:
        super().__init__("Falha pós-commit ao enfileirar o reprocessamento LLM.")
        self.recovery_scheduled = recovery_scheduled
        self.original = original


# Campos de reserva limpos após conclusão (o estado saiu de
# WAIT_R1_CLEANUP_THUMBS; a reserva nir_receipt perdeu o objeto).
_LOCK_CLEAR_FIELDS: tuple[str, ...] = (
    "locked_by",
    "locked_at",
    "locked_until",
    "lock_token",
    "lock_context",
    "lock_role",
)


def _validate_nir_actor(*, user: AccountsUser, active_role: str) -> None:
    """Valida o ator NIR explicitamente (C2).

    Exige ator autenticado, papel ativo NIR passado pela sessão e papel NIR
    atribuído ao usuário. Nunca deriva o papel ativo de papéis existentes de
    um usuário multi-role.
    """
    if user is None or not user.is_authenticated:
        raise PermissionError("Ator não autenticado.")
    if active_role != NIR_RECEIPT_ROLE:
        raise PermissionError("Papel ativo não é NIR; operação recusada.")
    if not user.roles.filter(name=NIR_RECEIPT_ROLE).exists():
        raise PermissionError("Usuário não possui o papel NIR atribuído.")


def _assert_receipt_lease(*, case: Case, user: AccountsUser, token: uuid.UUID) -> None:
    """Valida a reserva nir_receipt completa na instância bloqueada (C3).

    Owner correto, token exato, contexto ``nir_receipt``, papel ``nir`` e
    lease não expirada. Rejeita também lock do mesmo usuário quando token,
    contexto ou papel forem incompatíveis.
    """
    from apps.cases.services import assert_case_lock

    assert_case_lock(case=case, user=user, token=token, context=NIR_RECEIPT_CONTEXT)
    if case.lock_role != NIR_RECEIPT_ROLE:
        raise PermissionError(f"Papel da reserva inválido: esperado '{NIR_RECEIPT_ROLE}', obtido '{case.lock_role}'.")


def _clear_receipt_lease(case: Case) -> None:
    """Limpa os campos de reserva nir_receipt após conclusão."""
    for field in _LOCK_CLEAR_FIELDS:
        setattr(case, field, None if field not in ("lock_context", "lock_role") else "")
    case.save(update_fields=list(_LOCK_CLEAR_FIELDS))


def _acquire_locked_case(
    *,
    case_id: uuid.UUID,
    user: AccountsUser,
    active_role: str,
) -> Case:
    """Valida o ator NIR (C2) e retorna a instância bloqueada e atualizada.

    A linha é travada com ``select_for_update`` DENTRO da transação aberta
    pelo serviço; a instância retornada é a fonte de verdade para validação
    e mutação — nenhuma instância lida fora do lock é usada para salvar
    (C1/C4).
    """
    _validate_nir_actor(user=user, active_role=active_role)
    return Case.objects.select_for_update().get(pk=case_id)


def is_exam_type_correction_eligible(case: Case) -> bool:
    """Elegibilidade server-side para correção de tipo (R1).

    Estado estável pré-médico explicitamente enumerado: WAIT_R1_CLEANUP_THUMBS
    com manual review de mismatch/mixed/unknown. Estados transitórios de
    worker (R1_ACK_PROCESSING/EXTRACTING/LLM_STRUCT/LLM_SUGGEST/R2_POST_WIDGET)
    e qualquer decisão pós-WAIT_DOCTOR são recusados — nunca comparação
    textual frouxa de status.
    """
    if case.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        return False
    if case.doctor_decision:
        return False
    suggested = case.suggested_action
    if not isinstance(suggested, dict):
        return False
    if suggested.get("decision") != "manual_review_required":
        return False
    return suggested.get("reason_code") in EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES


def correct_case_exam_type(
    *,
    case_id: uuid.UUID,
    new_exam_type: str,
    user: AccountsUser,
    active_role: str,
    lock_token: uuid.UUID,
    reason_code: str,
) -> Case:
    """Corrige o tipo de exame no mesmo caso e reprocessa (Slice 006).

    Transacional com ``select_for_update`` (R1): nenhuma atualização parcial.
    Ator NIR e reserva completa validados sob o row lock (C2/C3). Preserva
    fontes e limpa derivados (R3). Transição FSM nomeada de volta a
    LLM_STRUCT (R2) com eventos append-only (R5). Após commit, enfileira o
    pipeline LLM exatamente uma vez — nunca reextrai PDF (R4); em falha de
    enqueue, agenda retry automático e levanta ``EnqueueAfterCommitError`` (C5).

    Raises:
        ValueError: caso inelegível, tipo inválido/igual ou reason_code inválido.
        PermissionError: ator sem papel NIR, papel ativo incorreto ou reserva
            incompatível/ausente/expirada.
        EnqueueAfterCommitError: enqueue pós-commit falhou (correção commitada).
    """
    validated_exam_type = validate_exam_type(new_exam_type)
    if reason_code not in EXAM_TYPE_CORRECTION_REASONS:
        raise ValueError("Motivo da correção inválido.")
    if lock_token is None:
        raise PermissionError("Token de reserva não fornecido.")

    with transaction.atomic():
        case = _acquire_locked_case(case_id=case_id, user=user, active_role=active_role)
        if not is_exam_type_correction_eligible(case):
            raise ValueError("Caso não está em revisão manual elegível para correção de tipo.")
        # Slice 008 (R2): igualdade/old/new usam CONJUNTOS de CaseProcedure —
        # o conjunto declarado vem das rows (coluna ponte removida no 011-C).
        new_procedures = list(_procedure_types_for_selection(validated_exam_type))
        old_procedures = list(get_declared_procedure_types(case))
        if set(new_procedures) == set(old_procedures):
            raise ValueError("O novo conjunto de procedimentos deve ser diferente do declarado.")
        _assert_receipt_lease(case=case, user=user, token=lock_token)

        # R3 — invalida artefatos derivados do perfil anterior; fontes ficam.
        case.structured_data = None
        case.summary_text = ""
        case.suggested_action = None
        case.priority_signals = []

        # R2 — detecção e disposições médicas voltam a pending (correção só é
        # permitida antes de qualquer decisão; nunca deixa projeção residual).
        reset_detection_and_doctor_statuses(case)

        # Slice 008 (R2/R7): evento enxuto com conjuntos anterior/novo e
        # motivo codificado (sem texto/PDF). SEM chaves singulares
        # old_exam_type/new_exam_type — a coluna deixou de ser fonte NIR.
        # Slice 005: substitui EXAM_TYPE_CORRECTED (valor singular).
        case._record_event(
            "CASE_PROCEDURE_DECLARATION_CORRECTED",
            user=user,
            payload={
                "old_procedures": old_procedures,
                "new_procedures": new_procedures,
                "reason_code": reason_code,
            },
        )
        # R3 (Slice 001) — reroteamento pelo serviço único de declaração:
        # projeção CaseProcedure.declared_by_nir sob a MESMA transação/lock;
        # falha reverte tudo (incl. derivados/eventos/FSM).
        sync_declared_projection(case, new_procedures)
        case.save()

        # R2 — transição FSM nomeada; CASE_REPROCESSING_REQUESTED é persistido
        # no save() seguinte, após CASE_PROCEDURE_DECLARATION_CORRECTED (ordem
        # append-only, sem sobrescrever _pending_event).
        case.reprocess_after_exam_type_correction(
            user=user,
            payload={"reason_code": reason_code},
        )
        case.save()

        # A reserva nir_receipt perdeu o objeto (estado saiu de
        # WAIT_R1_CLEANUP_THUMBS): limpa para não vazar lock em LLM_STRUCT.
        _clear_receipt_lease(case)

    # R4/C5 — fora da transação: um único enqueue LLM pós-commit. Em falha,
    # agenda retry automático (Schedule ONCE) e levanta erro explícito.
    _enqueue_pipeline_or_schedule_recovery(case.case_id)
    return case


def confirm_case_receipt(
    *,
    case_id: uuid.UUID,
    user: AccountsUser,
    active_role: str,
    lock_token: uuid.UUID,
) -> Case:
    """Confirma recebimento do resultado final e conclui o caso (NIR).

    Mesmo protocolo de row lock da correção (C1): ``transaction.atomic`` +
    ``select_for_update`` no mesmo ``case_id``, ator NIR e reserva completa
    validados na instância bloqueada e atualizada, e somente então as
    transições FSM. Confirmação e correção nunca podem vencer juntas e
    nenhuma usa instância obsoleta para salvar.

    Preserva o fluxo legado: ciência de intercorrência pós-agendamento
    respondida (``acknowledge_scheduled_post_acceptance_issue``) ou limpeza
    comum (``cleanup_triggered`` → ``cleanup_completed``).

    Raises:
        ValueError: caso não está aguardando confirmação.
        PermissionError: ator ou reserva incompatíveis.
    """
    from apps.cases.services import (
        POST_SCHEDULE_ISSUE_STATUS_RESPONDED,
        acknowledge_scheduled_post_acceptance_issue,
    )

    if lock_token is None:
        raise PermissionError("Token de reserva não fornecido.")

    with transaction.atomic():
        case = _acquire_locked_case(case_id=case_id, user=user, active_role=active_role)
        if case.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
            raise ValueError("Este caso não está aguardando confirmação de recebimento.")
        _assert_receipt_lease(case=case, user=user, token=lock_token)

        if case.post_schedule_issue_status == POST_SCHEDULE_ISSUE_STATUS_RESPONDED:
            case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)
        else:
            case.cleanup_triggered(user=user)
            case.save()
            case.cleanup_completed(user=user)
            case.save()

        _clear_receipt_lease(case)

    return Case.objects.get(pk=case.case_id)


def _enqueue_pipeline_or_schedule_recovery(case_id: uuid.UUID) -> None:
    """R4/C5: um único enqueue LLM pós-commit; em falha agenda retry automático.

    O retry usa ``Schedule`` ONCE apontando para ``execute_pdf_extraction``:
    em ``LLM_STRUCT`` ela re-enfileira o pipeline sem reextrair o PDF
    (recovery idempotente existente). Nenhum enqueue de extração de PDF é
    feito aqui. Se a programação do retry também falhar, o caso permanece em
    ``LLM_STRUCT`` para recovery manual/documentado.
    """
    from apps.pipeline.tasks import enqueue_pipeline

    try:
        enqueue_pipeline(case_id)
    except Exception as exc:
        logger.exception("enqueue_pipeline falhou para %s — agendando retry", case_id)
        recovery_scheduled = False
        try:
            _schedule_pipeline_recovery(case_id)
            recovery_scheduled = True
        except Exception:
            logger.exception("Falha ao agendar retry automático para %s", case_id)
        raise EnqueueAfterCommitError(recovery_scheduled=recovery_scheduled, original=exc) from exc


def _schedule_pipeline_recovery(case_id: uuid.UUID) -> None:
    """Programa retry automático via django-q2 Schedule ONCE (C5/RR1/RR3).

    Direciona explicitamente ao cluster ``pdf`` — o único cluster implantado
    que executa ``execute_pdf_extraction`` (dev/prod rodam apenas
    ``Q_CLUSTER_NAME=llm`` e ``Q_CLUSTER_NAME=pdf``; schedules com cluster
    NULL só são consumidos pelo cluster default ``ats``, não implantado).

    Em ``LLM_STRUCT``, ``execute_pdf_extraction`` não reextrai PDF: reavalia
    o regulation gate e chama ``enqueue_pipeline``. ONCE usa o default
    ``repeats=-1``: o scheduler do django-q2 DELETA o Schedule após o
    dispatch, sem deixar nome residual determinístico por ``case_id`` que
    bloquearia um novo recovery do mesmo caso (IntegrityError).
    """
    from datetime import timedelta

    from django_q.models import Schedule
    from django_q.tasks import schedule as q_schedule

    q_schedule(
        "apps.intake.tasks.execute_pdf_extraction",
        str(case_id),
        schedule_type=Schedule.ONCE,
        next_run=timezone.now() + timedelta(seconds=RECOVERY_SCHEDULE_DELAY_SECONDS),
        name=f"slice006-recovery:{case_id}",
        cluster="pdf",
    )


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
    1. Create ``Case(created_by=user)`` (conjunto declarado via rows).
    2. Save ``pdf_file``.
    3. FSM transition ``NEW → R1_ACK_PROCESSING``.
    4. Enqueue async PDF extraction.

    The caller is responsible for calling ``case.save()`` on each
    transition step.
    """
    # 1. Create case
    with transaction.atomic():
        case = Case.objects.create(created_by=user)

        # 2. Save PDF
        case.pdf_file = file
        case.save()

        # Slice 001 (R5): projeção declarada no MESMO caso — um PDF combinado
        # vira UM Case com DUAS rows; falha aqui reverte o caso.
        set_declared_procedures(
            case=case,
            procedure_types=_procedure_types_for_selection(exam_type),
            actor=user,
        )

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

    ``exam_type`` é OBRIGATÓRIO (Slice 007): o novo caso exige escolha
    explícita do NIR — o tipo do original NÃO é herdado. O tipo informado
    passa sempre pela validação central (choice + flag de intake), pois o
    reenvio cria um NOVO Case — é novo intake (R3/F1): flag desligada
    impede novo colonoscopia mesmo quando o original é colonoscopia.

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

    # 0. Exam type OBRIGATÓRIO — validação central (choice + flag) ANTES
    #    de qualquer criação/evento/save/enqueue. Ausente/inválido levanta
    #    ValueError e nada é criado (R3).
    validated_exam_type = ensure_exam_type_allowed(exam_type)

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

    # 4/5/6. Create new Case (atomic): PDF, projeção declarada e FSM inicial.
    # Slice 001: reenvio é NOVO intake — a seleção declarada projeta rows
    # (combinação → duas rows); falha reverte o caso inteiro.
    with transaction.atomic():
        new_case = Case.objects.create(
            created_by=user,
            corrects_case=original_case,
            correction_reason=reason,
            correction_created_by=user,
            correction_created_at=tz.now(),
        )

        new_case.pdf_file = pdf_file
        new_case.save()

        set_declared_procedures(
            case=new_case,
            procedure_types=_procedure_types_for_selection(validated_exam_type),
            actor=user,
        )

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
            # R4: tipo do novo caso — divergência fica auditável sem mudar
            # semântica dos eventos existentes (sem PDF/texto clínico).
            "exam_type": validated_exam_type,
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
