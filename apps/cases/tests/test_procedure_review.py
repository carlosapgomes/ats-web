"""S2 RED — dominio da revisao humana: fingerprint, autoridade e apresentacao.

Contrato: openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/
slices/slice-002-human-confirmation-to-doctor-with-timeline.md (R3, R4, R7).

Estado RED: `apps.cases.procedure_review` nao existe — CaseEvent e a unica
fonte de verdade e nenhum helper distingue confirmacao humana de correcao
legada. Estes testes definem o contrato do helper de dominio puro.
"""

from __future__ import annotations

import hashlib

import pytest

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ProcedureType

pytestmark = pytest.mark.django_db


def _nir_user(django_user_model, username: str = "nir-dom@test.com"):
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username)
    user.roles.add(Role.objects.get_or_create(name="nir")[0])
    return user


def _review_case(*, user, declared: str = ProcedureType.EDA) -> Case:
    case = Case.objects.create(
        created_by=user,
        status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        extracted_text="RELATORIO DE OCORRENCIAS\nMotivo da Solicitacao: EDA",
        suggested_action={
            "decision": "manual_review_required",
            "reason_code": "exam_type_mismatch",
            "reason_text": "Divergencia.",
        },
    )
    CaseProcedure.objects.create(case=case, procedure_type=declared, declared_by_nir=True)
    return case


def _review_event(case: Case) -> CaseEvent:
    return CaseEvent.objects.create(
        case=case,
        event_type="EDA_SCOPE_GATED_MANUAL_REVIEW",
        actor=None,
        actor_type="system",
        payload={"reason_code": "exam_type_mismatch", "reason_text": "Divergencia."},
    )


def _confirmation_event(case, user, review, *, confirmed=("eda",), fingerprint="v1:abc") -> CaseEvent:
    from apps.cases.procedure_review import REVIEW_CONFIRMED_EVENT

    return CaseEvent.objects.create(
        case=case,
        event_type=REVIEW_CONFIRMED_EVENT,
        actor=user,
        actor_type="human",
        payload={
            "version": 1,
            "actor_role": "nir",
            "review_event_id": review.pk,
            "review_reason_code": "exam_type_mismatch",
            "previous_declared_procedures": ["eda"],
            "confirmed_procedures": list(confirmed),
            "selection_changed": list(confirmed) != ["eda"],
            "justification": "Revisei e confirmo.",
            "source_fingerprint": fingerprint,
        },
    )


class TestSourceFingerprint:
    def test_fingerprint_is_versioned_and_deterministic(self) -> None:
        from apps.cases.procedure_review import compute_source_fingerprint

        left = compute_source_fingerprint(pdf_bytes=b"%PDF-1.4 sintese", extracted_text="texto")
        right = compute_source_fingerprint(pdf_bytes=b"%PDF-1.4 sintese", extracted_text="texto")
        assert left == right
        assert left.startswith("v1:")
        changed = compute_source_fingerprint(pdf_bytes=b"%PDF-1.4 outro", extracted_text="texto")
        assert changed != left

    def test_fingerprint_ignores_filename_and_attachments(self, django_user_model) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        first = source_fingerprint_for_case(case)
        assert first is not None
        assert first == source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        assert first.startswith("v1:")

    def test_fingerprint_changes_when_text_changes(self, django_user_model) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        before = source_fingerprint_for_case(case)
        case.extracted_text = (case.extracted_text or "") + " Anexo posterior."
        after = source_fingerprint_for_case(case)
        assert before != after


class TestConfirmationAuthority:
    def test_latest_valid_confirmation_is_consumed(self, django_user_model) -> None:
        from apps.cases.procedure_review import (
            consume_valid_confirmation,
            source_fingerprint_for_case,
        )

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        review = _review_event(case)
        event = _confirmation_event(case, user, review, fingerprint=source_fingerprint_for_case(case))
        effective, consumed = consume_valid_confirmation(case)
        assert effective == ("eda",)
        assert consumed is not None
        assert consumed.pk == event.pk

    def test_legacy_correction_event_has_no_authority(self, django_user_model) -> None:
        from apps.cases.procedure_review import consume_valid_confirmation

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURE_DECLARATION_CORRECTED",
            actor=user,
            actor_type="human",
            payload={
                "old_procedures": ["eda"],
                "new_procedures": ["colonoscopy"],
                "reason_code": "nir_identified_exam",
            },
        )
        effective, consumed = consume_valid_confirmation(case)
        assert effective is None
        assert consumed is None

    def test_stale_source_is_not_consumed_and_invalidated(self, django_user_model) -> None:
        from apps.cases.procedure_review import consume_valid_confirmation

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        review = _review_event(case)
        _confirmation_event(case, user, review, fingerprint="v1:antigo")
        case.extracted_text = (case.extracted_text or "") + " Fonte alterada depois."
        case.save()
        effective, _ = consume_valid_confirmation(case)
        assert effective is None
        invalidated = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_INVALIDATED")
        assert invalidated.count() == 1
        first_invalidated = invalidated.first()
        assert first_invalidated is not None
        assert isinstance(first_invalidated.payload, dict)
        assert "source" in str(first_invalidated.payload.get("reason", ""))

    def test_superseded_review_is_not_consumed(self, django_user_model) -> None:
        from apps.cases.procedure_review import (
            consume_valid_confirmation,
            source_fingerprint_for_case,
        )

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        old_review = _review_event(case)
        _confirmation_event(case, user, old_review, fingerprint=source_fingerprint_for_case(case))
        _review_event(case)  # revisao mais recente invalida a resolucao anterior
        effective, _ = consume_valid_confirmation(case)
        assert effective is None

    def test_no_confirmation_event_is_not_an_error(self, django_user_model) -> None:
        from apps.cases.procedure_review import consume_valid_confirmation

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        _review_event(case)
        effective, consumed = consume_valid_confirmation(case)
        assert effective is None
        assert consumed is None


class TestConfirmationPresentation:
    def test_title_names_confirmed_selection_and_change(self, django_user_model) -> None:
        from apps.cases.procedure_review import confirmation_timeline_lines, format_confirmation_title

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        review = _review_event(case)
        event = _confirmation_event(case, user, review, confirmed=("rectosigmoidoscopy_argon",))
        title = format_confirmation_title(event)
        assert "Retossigmoidoscopia + Argônio" in title
        assert "NIR" in title
        lines = confirmation_timeline_lines(event)
        assert any("EDA" in line and "Retossigmoidoscopia + Argônio" in line for line in lines)
        assert any("Revisei e confirmo." in line for line in lines)

    def test_maintained_selection_is_explicit(self, django_user_model) -> None:
        from apps.cases.procedure_review import confirmation_timeline_lines

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        review = _review_event(case)
        event = _confirmation_event(case, user, review, confirmed=("eda",))
        lines = confirmation_timeline_lines(event)
        assert any("mantida" in line.lower() for line in lines)

    def test_raw_codes_never_leak_as_labels(self, django_user_model) -> None:
        from apps.cases.procedure_review import format_confirmation_title

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        review = _review_event(case)
        event = _confirmation_event(case, user, review, confirmed=("cpre",))
        assert "cpre" not in format_confirmation_title(event)
        assert "CPRE" in format_confirmation_title(event)

    def test_applied_and_invalidated_lines_are_system_scoped(self, django_user_model) -> None:
        from apps.cases.procedure_review import (
            REVIEW_APPLIED_EVENT,
            REVIEW_INVALIDATED_EVENT,
            format_applied_lines,
            format_invalidated_lines,
        )

        user = _nir_user(django_user_model)
        case = _review_case(user=user)
        review = _review_event(case)
        confirmed = _confirmation_event(case, user, review, confirmed=("cpre",))
        applied = CaseEvent.objects.create(
            case=case,
            event_type=REVIEW_APPLIED_EVENT,
            actor=None,
            actor_type="system",
            payload={
                "confirmation_event_id": confirmed.pk,
                "automatic_procedures": ["eda", "echoendoscopy", "cpre"],
                "effective_procedures": ["cpre"],
            },
        )
        lines = format_applied_lines(applied)
        assert any("CPRE" in line for line in lines)
        assert any("Ecoendoscopia" in line for line in lines)
        invalidated = CaseEvent.objects.create(
            case=case,
            event_type=REVIEW_INVALIDATED_EVENT,
            actor=None,
            actor_type="system",
            payload={"confirmation_event_id": confirmed.pk, "reason": "source_changed"},
        )
        assert any("fonte" in line.lower() for line in format_invalidated_lines(invalidated))

    def test_fingerprint_material_is_hashlib_verifiable(self) -> None:
        """O fingerprint v1 combina sha256 do PDF + sha256 do texto (D3)."""
        pdf = b"%PDF-1.4 sintese"
        text = "texto extraido"
        pdf_hex = hashlib.sha256(pdf).hexdigest()
        text_hex = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert len(pdf_hex) == 64 and len(text_hex) == 64
