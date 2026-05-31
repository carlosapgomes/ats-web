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

from apps.cases.models import Case, CaseStatus


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
