"""Tests for the Case lock service (work queue lease)."""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


def _create_role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _advance_to(case: Case, target: str) -> Case:
    """Advance a Case through FSM transitions to reach a target status."""
    path: dict[str, list[str]] = {
        str(CaseStatus.WAIT_DOCTOR): [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
        ],
    }
    steps = path.get(target, [])
    for step in steps:
        if "(" in step:
            method_name, args_str = step.split("(", 1)
            args_str = args_str.rstrip(")")
            kwargs = {}
            if "=" in args_str:
                for pair in args_str.split(","):
                    k, v = pair.split("=")
                    k = k.strip()
                    v = v.strip().strip("'")
                    if v == "True":
                        v = True
                    elif v == "False":
                        v = False
                    kwargs[k] = v
                getattr(case, method_name)(**kwargs)
            else:
                getattr(case, method_name)()
        else:
            getattr(case, step)()
        case.save()
    return Case.objects.get(pk=case.pk)


@pytest.mark.django_db
class TestClaimCaseLock:
    """Tests for claim_case_lock service function."""

    def _doctor_user(self):
        user = User.objects.create_user(username="doctor_claim@test.com", password="testpass123")
        user.roles.add(_create_role("doctor"))
        return user

    def _make_case_wait_doctor(self, user) -> Case:
        case = Case.objects.create(created_by=user)
        return _advance_to(case, CaseStatus.WAIT_DOCTOR)

    def test_claim_acquires_lock_for_available_case(self):
        """claim_case_lock acquires a lock on a WAIT_DOCTOR case without active lock."""
        from apps.cases.services import claim_case_lock

        user = self._doctor_user()
        case = self._make_case_wait_doctor(user)

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        assert result.acquired is True
        assert result.token is not None
        assert result.locked_by_display == user.display_name
        assert result.locked_until is not None
        assert result.locked_until > timezone.now()

        # Verify DB
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == user
        assert case.lock_token == result.token
        assert case.lock_context == "doctor_decision"
        assert case.lock_role == "doctor"
        assert case.locked_at is not None
        assert case.locked_until is not None

        # Must have created WORK_LOCK_CLAIMED event
        assert CaseEvent.objects.filter(
            case=case,
            event_type="WORK_LOCK_CLAIMED",
        ).exists()

    def test_second_user_cannot_claim_locked_case(self):
        """Second user cannot claim a case locked by another user."""
        from apps.cases.services import claim_case_lock

        doctor_a = self._doctor_user()
        doctor_b = User.objects.create_user(username="doctor_b@test.com", password="testpass123")
        doctor_b.roles.add(_create_role("doctor"))

        case = self._make_case_wait_doctor(doctor_a)

        # First claim succeeds
        result_a = claim_case_lock(
            case_id=case.case_id,
            user=doctor_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result_a.acquired is True

        # Second claim from different user fails
        result_b = claim_case_lock(
            case_id=case.case_id,
            user=doctor_b,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result_b.acquired is False
        assert result_b.token is None

    def test_expired_lock_can_be_assumed_by_another_user(self):
        """If a lock is expired, another user can claim it."""
        from apps.cases.services import claim_case_lock

        doctor_a = self._doctor_user()
        doctor_b = User.objects.create_user(username="doctor_c@test.com", password="testpass123")
        doctor_b.roles.add(_create_role("doctor"))
        doctor_b.first_name = "Dra. B"
        doctor_b.save()

        case = self._make_case_wait_doctor(doctor_a)

        # Claim with very short lease
        result_a = claim_case_lock(
            case_id=case.case_id,
            user=doctor_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=0,  # force immediate expiration
        )
        assert result_a.acquired is True

        # Expire the lock manually (set locked_until in the past)
        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        # Now doctor_b can claim
        result_b = claim_case_lock(
            case_id=case.case_id,
            user=doctor_b,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result_b.acquired is True
        assert result_b.token is not None

        # Verify case now belongs to doctor_b
        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == doctor_b
        assert case.lock_token == result_b.token

    def test_claim_on_expired_lock_creates_expired_event(self):
        """Claiming an expired lock creates WORK_LOCK_EXPIRED event with previous user info."""
        from apps.cases.services import claim_case_lock

        doctor_a = self._doctor_user()
        doctor_a.first_name = "Dr. A Old"
        doctor_a.professional_council = "CRM"
        doctor_a.professional_council_number = "12345"
        doctor_a.save()

        doctor_b = User.objects.create_user(username="doctor_d@test.com", password="testpass123")
        doctor_b.roles.add(_create_role("doctor"))
        doctor_b.first_name = "Dra. B New"
        doctor_b.save()

        case = self._make_case_wait_doctor(doctor_a)

        # First claim
        result_a = claim_case_lock(
            case_id=case.case_id,
            user=doctor_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=0,
        )
        assert result_a.acquired is True

        # Expire
        case = Case.objects.get(pk=case.case_id)
        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        # Second user claims expired lock
        claim_case_lock(
            case_id=case.case_id,
            user=doctor_b,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        # Check WORK_LOCK_EXPIRED event
        expired_event = CaseEvent.objects.filter(
            case=case,
            event_type="WORK_LOCK_EXPIRED",
        ).last()
        assert expired_event is not None

        payload = expired_event.payload
        assert payload.get("expired_locked_by_id") == str(doctor_a.pk)
        assert payload.get("expired_locked_by_display") == doctor_a.display_name
        assert payload.get("expired_locked_at") is not None
        assert payload.get("expired_locked_until") is not None
        assert payload.get("context") == "doctor_decision"


@pytest.mark.django_db
class TestAssertCaseLock:
    """Tests for assert_case_lock service function."""

    def _doctor_user(self):
        user = User.objects.create_user(username="doc_assert@test.com", password="testpass123")
        user.roles.add(_create_role("doctor"))
        return user

    def _make_case_wait_doctor(self, user) -> Case:
        case = Case.objects.create(created_by=user)
        return _advance_to(case, CaseStatus.WAIT_DOCTOR)

    def test_assert_valid_lock_passes(self):
        """assert_case_lock passes for valid user, token, and context."""
        from apps.cases.services import assert_case_lock, claim_case_lock

        user = self._doctor_user()
        case = self._make_case_wait_doctor(user)

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        assert result.token is not None

        # Should not raise
        case = Case.objects.get(pk=case.case_id)
        assert_case_lock(
            case=case,
            user=user,
            token=result.token,
            context="doctor_decision",
        )

    def test_assert_fails_for_wrong_user(self):
        """assert_case_lock raises for a different user."""
        from apps.cases.services import assert_case_lock, claim_case_lock

        doc_a = self._doctor_user()
        doc_b = User.objects.create_user(username="doc_assert_b@test.com", password="testpass123")
        doc_b.roles.add(_create_role("doctor"))

        case = self._make_case_wait_doctor(doc_a)

        result = claim_case_lock(
            case_id=case.case_id,
            user=doc_a,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        assert result.token is not None
        with pytest.raises(PermissionError, match="Lock pertence a outro usuário"):
            case = Case.objects.get(pk=case.case_id)
            assert_case_lock(
                case=case,
                user=doc_b,
                token=result.token,
                context="doctor_decision",
            )

    def test_assert_fails_for_wrong_token(self):
        """assert_case_lock raises for an incorrect token."""
        from apps.cases.services import assert_case_lock, claim_case_lock

        user = self._doctor_user()
        case = self._make_case_wait_doctor(user)

        claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        with pytest.raises(PermissionError, match="Token de lock inválido"):
            case = Case.objects.get(pk=case.case_id)
            assert_case_lock(
                case=case,
                user=user,
                token=uuid.uuid4(),
                context="doctor_decision",
            )

    def test_assert_fails_for_wrong_context(self):
        """assert_case_lock raises for a different context."""
        from apps.cases.services import assert_case_lock, claim_case_lock

        user = self._doctor_user()
        case = self._make_case_wait_doctor(user)

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        assert result.token is not None
        with pytest.raises(PermissionError, match="Contexto de lock inválido"):
            case = Case.objects.get(pk=case.case_id)
            assert_case_lock(
                case=case,
                user=user,
                token=result.token,
                context="scheduler_confirm",
            )

    def test_assert_fails_for_expired_lock(self):
        """assert_case_lock raises for an expired lock."""
        from apps.cases.services import assert_case_lock, claim_case_lock

        user = self._doctor_user()
        case = self._make_case_wait_doctor(user)

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=0,
        )

        # Manually expire
        Case.objects.filter(case_id=case.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        assert result.token is not None
        with pytest.raises(PermissionError, match="Lock expirou"):
            case = Case.objects.get(pk=case.case_id)
            assert_case_lock(
                case=case,
                user=user,
                token=result.token,
                context="doctor_decision",
            )


@pytest.mark.django_db
class TestReleaseCaseLock:
    """Tests for release_case_lock service function."""

    def _doctor_user(self):
        user = User.objects.create_user(username="doc_release@test.com", password="testpass123")
        user.roles.add(_create_role("doctor"))
        return user

    def _make_case_wait_doctor(self, user) -> Case:
        case = Case.objects.create(created_by=user)
        return _advance_to(case, CaseStatus.WAIT_DOCTOR)

    def test_release_clears_lock_fields(self):
        """release_case_lock clears lock fields and creates RELEASED event."""
        from apps.cases.services import claim_case_lock, release_case_lock

        user = self._doctor_user()
        case = self._make_case_wait_doctor(user)

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )

        assert result.token is not None
        case = Case.objects.get(pk=case.case_id)
        released = release_case_lock(
            case_id=case.case_id,
            user=user,
            token=result.token,
            context="doctor_decision",
        )

        assert released is True

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by is None
        assert case.locked_at is None
        assert case.locked_until is None
        assert case.lock_token is None
        assert case.lock_context == ""
        assert case.lock_role == ""

        assert CaseEvent.objects.filter(
            case=case,
            event_type="WORK_LOCK_RELEASED",
        ).exists()


@pytest.mark.django_db
class TestExpireStaleLocks:
    """Tests for expire_stale_locks_for_statuses service function."""

    def _doctor_user(self):
        user = User.objects.create_user(username="doc_stale@test.com", password="testpass123")
        user.roles.add(_create_role("doctor"))
        return user

    def _make_case(self, user, status: str) -> Case:
        case = Case.objects.create(created_by=user)
        return _advance_to(case, status)

    def test_expires_stale_locks_for_given_statuses(self):
        """Expired locks in specified statuses are cleared."""
        from apps.cases.services import claim_case_lock, expire_stale_locks_for_statuses

        user = self._doctor_user()

        case1 = self._make_case(user, CaseStatus.WAIT_DOCTOR)
        result1 = claim_case_lock(
            case_id=case1.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=0,
        )
        assert result1.acquired is True
        # Force expiration
        Case.objects.filter(case_id=case1.case_id).update(locked_until=timezone.now() - timedelta(seconds=1))

        expired_count = expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])
        assert expired_count >= 1

        case1 = Case.objects.get(pk=case1.case_id)
        assert case1.locked_by is None

    def test_does_not_affect_current_locks(self):
        """Non-expired locks are not affected."""
        from apps.cases.services import claim_case_lock, expire_stale_locks_for_statuses

        user = self._doctor_user()
        case = self._make_case(user, CaseStatus.WAIT_DOCTOR)

        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        expired_count = expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])
        assert expired_count == 0

        case = Case.objects.get(pk=case.case_id)
        assert case.locked_by == user
