"""Case lock service — work queue lease management.

Provides atomic claim, assert, release, and expiry operations
for the Case model, using Django/PostgreSQL transactions.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.cases.models import Case, CaseAttachment, CaseStatus


@dataclass(frozen=True)
class CaseLockResult:
    """Result of a lock claim operation."""

    acquired: bool
    token: uuid.UUID | None = None
    reason: str = ""
    locked_by_display: str = ""
    locked_until: datetime | None = None


def _get_lease_seconds(override: int | None = None) -> int:
    """Return the lease duration in seconds."""
    if override is not None:
        return override
    return getattr(settings, "CASE_LOCK_LEASE_SECONDS", 300)


def _record_event(
    case: Case,
    event_type: str,
    user: Any,
    payload: dict[str, object] | None = None,
) -> None:
    """Create a CaseEvent for the given case."""
    from apps.cases.models import CaseEvent

    CaseEvent.objects.create(
        case=case,
        event_type=event_type,
        actor=user,
        actor_type="human",
        payload=payload or {},
    )


def claim_case_lock(
    *,
    case_id: uuid.UUID,
    user: Any,
    expected_status: CaseStatus,
    context: str,
    role: str,
    lease_seconds: int | None = None,
) -> CaseLockResult:
    """Atomically claim a lease on a Case.

    Acquisition rules (in order):
    1. Case must be in the expected status.
    2. No active lock (locked_by is None or locked_until <= now).
    3. If there is an expired lock, it can be taken over.

    When taking over an expired lock, a WORK_LOCK_EXPIRED event is recorded
    with the previous owner's information.

    Args:
        case_id: UUID of the case to lock.
        user: The user claiming the lock.
        expected_status: Required CaseStatus for the lock.
        context: Operational context (e.g. 'doctor_decision').
        role: Active role of the user at claim time.
        lease_seconds: Override the default lease duration.

    Returns:
        CaseLockResult with acquired flag and token if successful.
    """
    seconds = _get_lease_seconds(lease_seconds)
    now = timezone.now()
    token = uuid.uuid4()
    locked_until = now + timedelta(seconds=seconds)

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)

        # Status check
        if case.status != expected_status:
            return CaseLockResult(
                acquired=False,
                reason=f"Caso não está em {expected_status}",
            )

        # Lock check
        previous_locked_by = None
        if case.locked_by is not None and case.locked_until is not None:
            if case.locked_until > now:
                # Active lock belongs to someone else
                if case.locked_by_id != user.pk:
                    return CaseLockResult(
                        acquired=False,
                        reason="Caso está reservado por outro usuário",
                        locked_by_display=case.locked_by.display_name,
                        locked_until=case.locked_until,
                    )
                # Same user already holds the lock — renew it
                case.locked_at = now
                case.locked_until = locked_until
                case.lock_token = token
                case.lock_context = context
                case.lock_role = role
                case.save(
                    update_fields=[
                        "locked_at",
                        "locked_until",
                        "lock_token",
                        "lock_context",
                        "lock_role",
                    ]
                )

                _record_event(
                    case,
                    "WORK_LOCK_CLAIMED",
                    user,
                    {
                        "context": context,
                        "role": role,
                        "lease_seconds": seconds,
                    },
                )

                return CaseLockResult(
                    acquired=True,
                    token=token,
                    locked_by_display=user.display_name,
                    locked_until=locked_until,
                )
            # Lock is expired — record who had it
            previous_locked_by = {
                "id": str(case.locked_by_id),
                "display": case.locked_by.display_name if case.locked_by else "desconhecido",
                "locked_at": case.locked_at.isoformat() if case.locked_at else "",
                "locked_until": case.locked_until.isoformat(),
            }

        # Acquire lock
        case.locked_by = user
        case.locked_at = now
        case.locked_until = locked_until
        case.lock_token = token
        case.lock_context = context
        case.lock_role = role
        case.save(
            update_fields=[
                "locked_by",
                "locked_at",
                "locked_until",
                "lock_token",
                "lock_context",
                "lock_role",
            ]
        )

        # Record expiration event if we took over an expired lock
        if previous_locked_by:
            _record_event(
                case,
                "WORK_LOCK_EXPIRED",
                user,
                {
                    "context": context,
                    "role": role,
                    "expired_locked_by_id": previous_locked_by["id"],
                    "expired_locked_by_display": previous_locked_by["display"],
                    "expired_locked_at": previous_locked_by["locked_at"],
                    "expired_locked_until": previous_locked_by["locked_until"],
                },
            )

        # Record claim event
        _record_event(
            case,
            "WORK_LOCK_CLAIMED",
            user,
            {
                "context": context,
                "role": role,
                "lease_seconds": seconds,
            },
        )

    return CaseLockResult(
        acquired=True,
        token=token,
        locked_by_display=user.display_name,
        locked_until=locked_until,
    )


def assert_case_lock(
    *,
    case: Case,
    user: Any,
    token: uuid.UUID,
    context: str,
) -> None:
    """Validate that the current user holds a valid lock on the case.

    Raises PermissionError with a descriptive message if:
    - The case is not locked.
    - The lock belongs to a different user.
    - The lock token does not match.
    - The lock context does not match.
    - The lock has expired.
    """
    now = timezone.now()

    if case.locked_by is None:
        raise PermissionError("Caso não possui reserva ativa.")

    if case.locked_by_id != user.pk:
        raise PermissionError(f"Lock pertence a outro usuário: {case.locked_by.display_name}")

    if case.lock_token is None or case.lock_token != token:
        raise PermissionError("Token de lock inválido.")

    if case.lock_context != context:
        raise PermissionError(f"Contexto de lock inválido: esperado '{context}', obtido '{case.lock_context}'")

    if case.locked_until is None or case.locked_until <= now:
        raise PermissionError("Lock expirou.")


def release_case_lock(
    *,
    case_id: uuid.UUID,
    user: Any,
    token: uuid.UUID,
    context: str,
) -> bool:
    """Release a lock on a case.

    Clears all lock fields and records a WORK_LOCK_RELEASED event.
    Only succeeds if the caller holds a valid lock.
    """
    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)
        try:
            assert_case_lock(case=case, user=user, token=token, context=context)
        except PermissionError:
            return False

        _record_event(
            case,
            "WORK_LOCK_RELEASED",
            user,
            {
                "context": context,
            },
        )

        case.locked_by = None
        case.locked_at = None
        case.locked_until = None
        case.lock_token = None
        case.lock_context = ""
        case.lock_role = ""
        case.save(
            update_fields=[
                "locked_by",
                "locked_at",
                "locked_until",
                "lock_token",
                "lock_context",
                "lock_role",
            ]
        )

    return True


def renew_case_lock(
    *,
    case_id: uuid.UUID,
    user: Any,
    token: uuid.UUID,
    context: str,
    lease_seconds: int | None = None,
) -> CaseLockResult:
    """Renew an existing lock on a case (heartbeat).

    Only succeeds if:
    - The lock exists and is not expired.
    - The user matches the locked_by user.
    - The token matches the lock_token.
    - The context matches the lock_context.

    This is a heartbeat operation and does NOT create CaseEvent entries
    to avoid polluting the audit timeline.

    Returns:
        CaseLockResult with acquired=True and new locked_until if successful.
    """
    seconds = _get_lease_seconds(lease_seconds)
    now = timezone.now()
    locked_until = now + timedelta(seconds=seconds)

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)

        # Lock must exist and be active
        if case.locked_by is None or case.locked_until is None:
            return CaseLockResult(
                acquired=False,
                reason="Caso não possui reserva ativa para renovar.",
            )

        if case.locked_until <= now:
            return CaseLockResult(
                acquired=False,
                reason="Reserva expirou. Adquira uma nova reserva.",
            )

        if case.locked_by_id != user.pk:
            return CaseLockResult(
                acquired=False,
                reason="Reserva pertence a outro usuário.",
            )

        if case.lock_token is None or case.lock_token != token:
            return CaseLockResult(
                acquired=False,
                reason="Token de reserva inválido.",
            )

        if case.lock_context != context:
            return CaseLockResult(
                acquired=False,
                reason=f"Contexto de reserva inválido: esperado '{context}', obtido '{case.lock_context}'.",
            )

        # Renew: extend locked_until, update locked_at
        case.locked_at = now
        case.locked_until = locked_until
        case.save(update_fields=["locked_at", "locked_until"])

    return CaseLockResult(
        acquired=True,
        token=token,
        locked_by_display=user.display_name,
        locked_until=locked_until,
    )


def expire_stale_locks_for_statuses(
    *,
    statuses: Iterable[CaseStatus],
) -> int:
    """Clear all expired locks for cases in the given statuses.

    This is a lazy cleanup — called before building queue context
    to ensure expired locks don't block cases.

    Returns:
        Number of locks that were cleared.
    """
    now = timezone.now()
    qs: QuerySet[Case] = Case.objects.filter(
        status__in=list(statuses),
        locked_by__isnull=False,
        locked_until__isnull=False,
        locked_until__lte=now,
    )
    count = qs.count()
    if count == 0:
        return 0

    qs.update(
        locked_by=None,
        locked_at=None,
        locked_until=None,
        lock_token=None,
        lock_context="",
        lock_role="",
    )
    return count


# ── Post-schedule intercurrence constants ──────────────────────────────


POST_SCHEDULE_ISSUE_STATUS_NONE = ""
POST_SCHEDULE_ISSUE_STATUS_OPENED = "opened"
POST_SCHEDULE_ISSUE_STATUS_RESPONDED = "responded"


# Official NIR reasons
POST_SCHEDULE_ISSUE_REASONS: tuple[str, ...] = (
    "death",
    "clinical_condition",
    "transport_unavailable",
    "external_regulation",
    "reschedule_request",
    "other",
)

# Reasons where message is optional
POST_SCHEDULE_ISSUE_REASONS_MESSAGE_OPTIONAL: tuple[str, ...] = (
    "death",
    "external_regulation",
)

# Scheduler actions
POST_SCHEDULE_ISSUE_SCHEDULER_ACTIONS: tuple[str, ...] = (
    "cancel",
    "reschedule",
    "maintain",
    "deny",
)


# Labels em português para exibição na UI
POST_SCHEDULE_ISSUE_REASON_LABELS: dict[str, str] = {
    "death": "Paciente faleceu",
    "clinical_condition": "Paciente sem condição clínica de transporte",
    "transport_unavailable": "Transporte indisponível pela unidade de origem",
    "external_regulation": "Exame realizado pela regulação estadual em outro serviço",
    "reschedule_request": "Solicitação de reagendamento pela unidade de origem",
    "other": "Outro",
}


def get_post_schedule_issue_reason_label(reason: str) -> str:
    """Retorna label em português para um motivo de intercorrência.

    Se o motivo não for reconhecido, retorna o próprio código como fallback.
    """
    return POST_SCHEDULE_ISSUE_REASON_LABELS.get(reason, reason)


# ── Post-schedule intercurrence services ────────────────────────────────


def is_post_schedule_issue_eligible(case: Case) -> bool:
    """Check if a case is eligible for opening a post-schedule issue."""
    # Check active issue FIRST — status may have changed after opening
    if case.post_schedule_issue_status:
        return False
    return (
        case.status == CaseStatus.CLEANED
        and case.doctor_decision == "accept"
        and case.doctor_admission_flow == "scheduled"
        and case.appointment_status == "confirmed"
    )


def get_post_schedule_issue_ineligibility_reason(case: Case) -> str:
    """Return a human-readable reason why the case is not eligible."""
    # Check active issue FIRST so the status change after opening doesn't
    # mask the real reason
    if case.post_schedule_issue_status:
        return "Já existe uma intercorrência ativa neste caso."
    if case.status != CaseStatus.CLEANED:
        return "Caso não está encerrado (CLEANED)."
    if case.doctor_decision != "accept":
        return "Caso não foi aceito pelo médico."
    if case.doctor_admission_flow != "scheduled":
        return "Fluxo de admissão não é agendado."
    if case.appointment_status != "confirmed":
        return "Agendamento não está confirmado."
    return "Motivo desconhecido."


def open_post_schedule_issue(
    *,
    case: Case,
    user: Any,
    reason: str,
    message: str = "",
) -> Case:
    """Open a post-schedule intercurrence for an eligible case.

    Args:
        case: The case (must be CLEANED and eligible).
        user: The user opening the issue.
        reason: One of POST_SCHEDULE_ISSUE_REASONS.
        message: Optional/required message depending on reason.

    Returns:
        The case with updated fields, saved.

    Raises:
        ValueError: If the case is not eligible, reason is invalid,
                    or message is required but empty.
    """
    if reason not in POST_SCHEDULE_ISSUE_REASONS:
        raise ValueError(f"Motivo inválido: '{reason}'. Motivos válidos: {', '.join(POST_SCHEDULE_ISSUE_REASONS)}")

    if reason not in POST_SCHEDULE_ISSUE_REASONS_MESSAGE_OPTIONAL and not message.strip():
        raise ValueError(f"Mensagem é obrigatória para o motivo '{reason}'.")

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)

        if not is_post_schedule_issue_eligible(case):
            reason_text = get_post_schedule_issue_ineligibility_reason(case)
            raise ValueError(f"Caso não elegível para intercorrência: {reason_text}")

        # Take a snapshot of current appointment state
        appointment_snapshot = {
            "status": case.appointment_status,
            "appointment_at": case.appointment_at.isoformat() if case.appointment_at else None,
            "appointment_location": case.appointment_location or "",
            "appointment_instructions": case.appointment_instructions or "",
        }

        now = timezone.now()
        case.post_schedule_issue_status = POST_SCHEDULE_ISSUE_STATUS_OPENED
        case.post_schedule_issue_reason = reason
        case.post_schedule_issue_message = message
        case.post_schedule_issue_opened_by = user
        case.post_schedule_issue_opened_at = now
        case.post_schedule_issue_response_action = ""
        case.post_schedule_issue_response_message = ""
        case.post_schedule_issue_responded_by = None
        case.post_schedule_issue_responded_at = None

        # FSM transition CLEANED → WAIT_APPT
        case.open_post_schedule_issue(user=user)
        case.save()

        # Record the audit event with appointment snapshot
        _record_event(
            case,
            "POST_SCHEDULE_ISSUE_OPENED",
            user,
            {
                "reason": reason,
                "message": message,
                "appointment_snapshot": appointment_snapshot,
            },
        )

    return Case.objects.get(pk=case.pk)


def respond_post_schedule_issue(
    *,
    case: Case,
    user: Any,
    action: str,
    response_message: str = "",
    appointment_at: str | None = None,
    appointment_location: str = "",
    appointment_instructions: str = "",
) -> Case:
    """Respond to an opened post-schedule intercurrence.

    Args:
        case: The case with an opened issue.
        user: The scheduler user responding.
        action: One of POST_SCHEDULE_ISSUE_SCHEDULER_ACTIONS.
        response_message: Optional message from the scheduler.
        appointment_at: New appointment datetime (required for reschedule).
        appointment_location: New location (for reschedule).
        appointment_instructions: New instructions (for reschedule).

    Returns:
        The case with updated fields, saved.

    Raises:
        ValueError: If the case has no opened issue, action is invalid,
                    or reschedule is missing required fields.
    """
    if action not in POST_SCHEDULE_ISSUE_SCHEDULER_ACTIONS:
        raise ValueError(
            f"Ação inválida: '{action}'. Ações válidas: {', '.join(POST_SCHEDULE_ISSUE_SCHEDULER_ACTIONS)}"
        )

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)

        if case.post_schedule_issue_status != POST_SCHEDULE_ISSUE_STATUS_OPENED:
            raise ValueError("Caso não possui intercorrência aberta para responder.")

        now = timezone.now()

        if action == "cancel":
            case.appointment_status = "cancelled"
        elif action == "reschedule":
            case.appointment_status = "confirmed"
            if appointment_at:
                from datetime import datetime as dt_mod
                from zoneinfo import ZoneInfo

                try:
                    parsed = dt_mod.fromisoformat(appointment_at)
                except ValueError:
                    parsed = dt_mod.fromisoformat(appointment_at.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
                case.appointment_at = parsed
            case.appointment_location = appointment_location
            case.appointment_instructions = appointment_instructions
        elif action == "maintain":
            case.appointment_status = "confirmed"
        elif action == "deny":
            # Preserve appointment_status="confirmed" and current data
            case.appointment_status = "confirmed"

        case.post_schedule_issue_status = POST_SCHEDULE_ISSUE_STATUS_RESPONDED
        case.post_schedule_issue_response_action = action
        case.post_schedule_issue_response_message = response_message
        case.post_schedule_issue_responded_by = user
        case.post_schedule_issue_responded_at = now

        # FSM transition through final_reply_posted to WAIT_R1_CLEANUP_THUMBS
        case.final_reply_posted(user=user)
        case.save()

        # Record the audit event
        _record_event(
            case,
            "POST_SCHEDULE_ISSUE_RESPONDED",
            user,
            {
                "action": action,
                "response_message": response_message,
            },
        )

    return Case.objects.get(pk=case.pk)


def acknowledge_post_schedule_issue(
    *,
    case: Case,
    user: Any,
) -> Case:
    """Acknowledge a responded post-schedule intercurrence and close the cycle.

    Uses a direct FSM transition WAIT_R1_CLEANUP_THUMBS → CLEANED without
    passing through CLEANUP_RUNNING, since there is no real cleanup to perform.
    The POST_SCHEDULE_ISSUE_ACKNOWLEDGED event is created by the FSM transition.

    Args:
        case: The case with a responded issue.
        user: The NIR user acknowledging.

    Returns:
        The case with cleared issue fields, back to CLEANED.

    Raises:
        ValueError: If the case has no responded issue.
    """
    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)

        if case.post_schedule_issue_status != POST_SCHEDULE_ISSUE_STATUS_RESPONDED:
            raise ValueError("Caso não possui intercorrência respondida para confirmar ciência.")

        # Clear issue fields
        case.post_schedule_issue_status = POST_SCHEDULE_ISSUE_STATUS_NONE
        case.post_schedule_issue_reason = ""
        case.post_schedule_issue_message = ""
        case.post_schedule_issue_opened_by = None
        case.post_schedule_issue_opened_at = None
        case.post_schedule_issue_response_action = ""
        case.post_schedule_issue_response_message = ""
        case.post_schedule_issue_responded_by = None
        case.post_schedule_issue_responded_at = None

        # FSM transition WAIT_R1_CLEANUP_THUMBS → CLEANED (direct, no cleanup)
        case.post_schedule_issue_acknowledged(user=user)
        case.save()

    return Case.objects.get(pk=case.pk)


def compute_lock_display(case: Case, user: Any = None) -> dict[str, Any]:
    """Compute lock display info for a case card.

    Returns a dict with is_locked, is_locked_by_current_user,
    locked_by_display, locked_until, and lock_context.

    If the lock has expired, all fields indicate "not locked".
    """
    now = timezone.now()
    is_locked = case.locked_by is not None and case.locked_until is not None and case.locked_until > now
    return {
        "is_locked": is_locked,
        "is_locked_by_current_user": bool(is_locked and user is not None and case.locked_by_id == user.pk),
        "locked_by_display": case.locked_by.display_name if is_locked and case.locked_by else "",
        "locked_until": case.locked_until.isoformat() if is_locked and case.locked_until else "",
        "lock_context": case.lock_context if is_locked else "",
    }


# ── Administrative Closure ───────────────────────────────────────────────


ADMINISTRATIVE_CLOSURE_REASONS: dict[str, str] = {
    "processing_error": "Erro de processamento",
    "llm_failure": "Falha do LLM",
    "system_bug": "Bug do sistema",
    "stuck_lock": "Reserva/lock travado",
    "duplicate_reprocess": "Duplicado/reapresentação manual",
    "other": "Outro",
}

ADMINISTRATIVE_CLOSURE_REASON_CHOICES: list[tuple[str, str]] = [
    (k, v) for k, v in ADMINISTRATIVE_CLOSURE_REASONS.items()
]


def administratively_close_case(
    *,
    case: Case,
    user: Any,
    reason_code: str,
    reason_text: str,
    active_role: str,
) -> Case:
    """Encerra um caso administrativamente.

    Transição excepcional para CLEANED, disponível apenas para manager/admin.
    Registra evento CASE_ADMINISTRATIVELY_CLOSED com payload auditável.
    Limpa lock operacional e intercorrência pós-agendamento, se houver.

    Args:
        case: O caso a ser encerrado (não pode ser CLEANED).
        user: Usuário que está encerrando.
        reason_code: Código do motivo (chave em ADMINISTRATIVE_CLOSURE_REASONS).
        reason_text: Texto descritivo do motivo (obrigatório, não vazio).
        active_role: Papel ativo do usuário no momento.

    Returns:
        O caso recarregado, agora em CLEANED.

    Raises:
        ValueError: Se validações falharem.
    """
    if not reason_text.strip():
        raise ValueError("Motivo obrigatório: forneça uma descrição do encerramento.")

    if not reason_code:
        raise ValueError("Código de motivo obrigatório.")

    if reason_code not in ADMINISTRATIVE_CLOSURE_REASONS:
        raise ValueError(
            f"Código de motivo inválido: '{reason_code}'. "
            f"Códigos válidos: {', '.join(ADMINISTRATIVE_CLOSURE_REASONS.keys())}"
        )

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)

        if case.status == CaseStatus.CLEANED:
            raise ValueError("Caso já está encerrado (CLEANED).")

        previous_status = str(case.status)

        # Snapshot de lock
        had_lock = case.locked_by is not None
        previous_lock: dict[str, object] = {}
        if had_lock:
            previous_lock = {
                "locked_by_id": str(case.locked_by_id) if case.locked_by_id else None,
                "locked_by_display": case.locked_by.display_name if case.locked_by else "",
                "locked_at": case.locked_at.isoformat() if case.locked_at else None,
                "locked_until": case.locked_until.isoformat() if case.locked_until else None,
                "lock_token": str(case.lock_token) if case.lock_token else None,
                "lock_context": case.lock_context,
                "lock_role": case.lock_role,
            }

        # Snapshot de intercorrência pós-agendamento
        post_schedule_issue_snapshot = {
            "status": case.post_schedule_issue_status,
            "reason": case.post_schedule_issue_reason,
            "message": case.post_schedule_issue_message,
        }

        # Monta payload do evento
        payload: dict[str, object] = {
            "previous_status": previous_status,
            "reason_code": reason_code,
            "reason_text": reason_text.strip(),
            "active_role": active_role,
            "had_lock": had_lock,
            "previous_lock": previous_lock,
            "post_schedule_issue_status": case.post_schedule_issue_status,
        }

        # Limpa lock
        case.locked_by = None
        case.locked_at = None
        case.locked_until = None
        case.lock_token = None
        case.lock_context = ""
        case.lock_role = ""

        # Limpa intercorrência pós-agendamento
        if case.post_schedule_issue_status:
            payload["post_schedule_issue_snapshot"] = post_schedule_issue_snapshot
            case.post_schedule_issue_status = ""
            case.post_schedule_issue_reason = ""
            case.post_schedule_issue_message = ""
            case.post_schedule_issue_opened_by = None
            case.post_schedule_issue_opened_at = None
            case.post_schedule_issue_response_action = ""
            case.post_schedule_issue_response_message = ""
            case.post_schedule_issue_responded_by = None
            case.post_schedule_issue_responded_at = None

        # FSM transition CLEANED
        case.administratively_close(user=user, payload=payload)
        case.save()

    return Case.objects.get(pk=case.pk)


# ── Attachment suppression ────────────────────────────────────────────────


def suppress_case_attachment(
    *,
    attachment: CaseAttachment,
    user: Any,
    reason: str,
) -> CaseAttachment:
    """Suprime um anexo ativo de forma auditável.

    Operação transacional com select_for_update. Valida motivo obrigatório
    e idempotência (anexo já suprimido não pode ser suprimido novamente).

    Registra CASE_ATTACHMENT_SUPPRESSED em CaseEvent com payload contendo
    metadados mínimos (sem conteúdo clínico integral).

    Args:
        attachment: O anexo a ser suprimido (deve estar ativo).
        user: Usuário NIR que está suprimindo.
        reason: Motivo obrigatório da supressão.

    Returns:
        O anexo com campos de supressão preenchidos.

    Raises:
        ValueError: Se motivo vazio ou anexo já suprimido.
    """
    if not reason.strip():
        raise ValueError("Motivo obrigatório para supressão do anexo.")

    with transaction.atomic():
        # Lock the attachment row for update
        att = CaseAttachment.objects.select_for_update().get(pk=attachment.pk)

        if att.is_suppressed:
            raise ValueError(f"Anexo {att.attachment_id} já está suprimido.")

        now = timezone.now()
        att.is_suppressed = True
        att.suppressed_at = now
        att.suppressed_by = user
        att.suppression_reason = reason.strip()
        att.save(
            update_fields=[
                "is_suppressed",
                "suppressed_at",
                "suppressed_by",
                "suppression_reason",
            ]
        )

        # Record audit event with metadata only (no clinical content)
        _record_event(
            att.case,
            "CASE_ATTACHMENT_SUPPRESSED",
            user,
            payload={
                "attachment_id": str(att.attachment_id),
                "original_filename": att.original_filename,
                "content_type": att.content_type,
                "size_bytes": att.size_bytes,
                "sha256": att.sha256,
                "reason": reason.strip(),
            },
        )

    return CaseAttachment.objects.get(pk=att.pk)
