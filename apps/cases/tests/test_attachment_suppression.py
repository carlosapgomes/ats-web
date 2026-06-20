"""Testes do serviço de supressão de anexo — Slice 003.

RED phase: testes falham antes da implementação.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseStatus

User = get_user_model()


@pytest.mark.django_db
class TestSuppressAttachmentService:
    """Testes do serviço suppress_case_attachment."""

    def _create_attachment(self) -> tuple[CaseAttachment, Any]:
        """Cria um anexo ativo para testes."""
        user = User.objects.create_user(username="nir_supp_serv@test.com", password="testpass123")
        case = Case.objects.create(created_by=user, status=CaseStatus.WAIT_DOCTOR)
        attachment = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("doc.pdf", b"%PDF content", content_type="application/pdf"),
            original_filename="doc.pdf",
            stored_filename="stored.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="a" * 64,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        return attachment, user

    def test_suppress_attachment_sets_suppression_fields(self) -> None:
        """Chamar serviço seta is_suppressed=True, suppressed_at, suppressed_by, suppression_reason."""
        from apps.cases.services import suppress_case_attachment

        attachment, user = self._create_attachment()
        reason = "Anexo enviado por engano — pertence a outro paciente."

        result = suppress_case_attachment(
            attachment=attachment,
            user=user,
            reason=reason,
        )

        assert result.is_suppressed is True
        assert result.suppressed_at is not None
        assert result.suppressed_by == user
        assert result.suppression_reason == reason

    def test_suppress_attachment_requires_reason(self) -> None:
        """Motivo vazio deve falhar."""
        from apps.cases.services import suppress_case_attachment

        attachment, user = self._create_attachment()

        with pytest.raises(ValueError, match="Motivo obrigatório"):
            suppress_case_attachment(
                attachment=attachment,
                user=user,
                reason="",
            )

        # Verifica que o anexo não foi alterado
        attachment.refresh_from_db()
        assert attachment.is_suppressed is False

    def test_suppress_attachment_is_idempotency_guarded(self) -> None:
        """Segunda supressão deve falhar."""
        from apps.cases.services import suppress_case_attachment

        attachment, user = self._create_attachment()
        reason = "Enviado incorretamente."

        # Primeira supressão — deve funcionar
        suppress_case_attachment(attachment=attachment, user=user, reason=reason)

        # Segunda supressão — deve falhar
        with pytest.raises(ValueError, match="já está suprimido"):
            suppress_case_attachment(
                attachment=attachment,
                user=user,
                reason="Outro motivo.",
            )

    def test_suppress_attachment_records_case_event(self) -> None:
        """Supressão registra CASE_ATTACHMENT_SUPPRESSED com payload mínimo."""
        from apps.cases.services import suppress_case_attachment

        attachment, user = self._create_attachment()
        reason = "Documento de outro paciente."

        suppress_case_attachment(attachment=attachment, user=user, reason=reason)

        # Verificar evento
        event = CaseEvent.objects.filter(
            case=attachment.case,
            event_type="CASE_ATTACHMENT_SUPPRESSED",
        ).first()

        assert event is not None
        assert event.actor == user
        assert event.actor_type == "human"
        payload = event.payload or {}
        assert payload.get("attachment_id") == str(attachment.attachment_id)
        assert payload.get("original_filename") == "doc.pdf"
        assert payload.get("reason") == reason
        # Não deve expor conteúdo clínico integral
        assert "content" not in payload

    def test_suppress_attachment_is_transactional(self) -> None:
        """Operação usa select_for_update e é transacional."""
        from apps.cases.services import suppress_case_attachment

        attachment, user = self._create_attachment()
        reason = "Motivo válido."

        # A operação deve funcionar dentro de uma transação
        with transaction.atomic():
            result = suppress_case_attachment(
                attachment=attachment,
                user=user,
                reason=reason,
            )

        assert result.is_suppressed is True


@pytest.mark.django_db
class TestCaseAttachmentSuppressedTimelineLabel:
    """Testa que o label de timeline existe para CASE_ATTACHMENT_SUPPRESSED."""

    def test_attachment_suppressed_event_has_timeline_label(self) -> None:
        """Label 'Anexo suprimido pelo NIR' deve existir no mapa de labels."""
        from apps.intake.views import EVENT_LABELS

        assert "CASE_ATTACHMENT_SUPPRESSED" in EVENT_LABELS
        assert EVENT_LABELS["CASE_ATTACHMENT_SUPPRESSED"] == "Anexo suprimido pelo NIR"
