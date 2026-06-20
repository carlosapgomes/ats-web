"""Testes para o modelo CaseAttachment — Slice 001.

RED phase: testes falham antes da implementação.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    FileField,
    PositiveBigIntegerField,
    TextField,
    UUIDField,
)

from apps.cases.models import Case, CaseAttachment, CaseStatus

User = get_user_model()


@pytest.mark.django_db
class TestCaseAttachmentModelFields:
    """Verificação da estrutura do modelo CaseAttachment."""

    def test_model_exists(self) -> None:
        """CaseAttachment está definido em apps.cases.models."""
        assert hasattr(CaseAttachment, "__module__")
        assert CaseAttachment.__module__.startswith("apps.cases.models")

    def test_primary_key_is_uuid(self) -> None:
        """attachment_id é UUID primary_key."""
        field = CaseAttachment._meta.get_field("attachment_id")
        assert isinstance(field, UUIDField)
        assert field.primary_key is True

    def test_case_fk(self) -> None:
        """case é FK para Case com related_name='attachments'."""
        field = CaseAttachment._meta.get_field("case")
        assert isinstance(field, models.ForeignKey)
        assert field.remote_field.model == Case
        assert field.remote_field.related_name == "attachments"

    def test_file_field_exists(self) -> None:
        """file é FileField com upload_to function."""
        field = CaseAttachment._meta.get_field("file")
        assert isinstance(field, FileField)
        assert field.upload_to is not None
        assert callable(field.upload_to)

    def test_original_filename_field(self) -> None:
        """original_filename é CharField."""
        field = CaseAttachment._meta.get_field("original_filename")
        assert isinstance(field, CharField)

    def test_stored_filename_field(self) -> None:
        """stored_filename é CharField."""
        field = CaseAttachment._meta.get_field("stored_filename")
        assert isinstance(field, CharField)

    def test_content_type_field(self) -> None:
        """content_type é CharField."""
        field = CaseAttachment._meta.get_field("content_type")
        assert isinstance(field, CharField)

    def test_size_bytes_field(self) -> None:
        """size_bytes é PositiveBigIntegerField."""
        field = CaseAttachment._meta.get_field("size_bytes")
        assert isinstance(field, PositiveBigIntegerField)

    def test_sha256_field(self) -> None:
        """sha256 é CharField(64) com db_index."""
        field = CaseAttachment._meta.get_field("sha256")
        assert isinstance(field, CharField)
        assert field.max_length == 64
        assert field.db_index is True  # type: ignore[attr-defined]

    def test_uploaded_by_field(self) -> None:
        """uploaded_by é FK User com PROTECT."""
        field = CaseAttachment._meta.get_field("uploaded_by")
        assert isinstance(field, models.ForeignKey)
        assert field.remote_field.model == User
        assert field.remote_field.on_delete.__name__ == "PROTECT"  # type: ignore[union-attr]

    def test_created_at_field(self) -> None:
        """created_at é DateTimeField com auto_now_add."""
        field = CaseAttachment._meta.get_field("created_at")
        assert isinstance(field, DateTimeField)
        assert field.auto_now_add is True

    def test_suppression_fields(self) -> None:
        """Campos de supressão existem."""
        assert isinstance(CaseAttachment._meta.get_field("is_suppressed"), BooleanField)
        assert CaseAttachment._meta.get_field("is_suppressed").default is False
        assert isinstance(CaseAttachment._meta.get_field("suppressed_at"), DateTimeField)
        assert CaseAttachment._meta.get_field("suppressed_at").null is True

        sup_by = CaseAttachment._meta.get_field("suppressed_by")
        assert isinstance(sup_by, models.ForeignKey)
        assert sup_by.null is True
        assert sup_by.blank is True
        assert sup_by.remote_field.on_delete.__name__ == "PROTECT"  # type: ignore[union-attr]

        assert isinstance(CaseAttachment._meta.get_field("suppression_reason"), TextField)
        assert CaseAttachment._meta.get_field("suppression_reason").blank is True

    def test_upload_phase_fields(self) -> None:
        """Campos de fase de upload existem."""
        field = CaseAttachment._meta.get_field("upload_phase")
        assert isinstance(field, CharField)
        assert field.max_length == 20
        assert field.default == "initial"

        field2 = CaseAttachment._meta.get_field("uploaded_when_case_status")
        assert isinstance(field2, CharField)
        assert field2.blank is True

        field3 = CaseAttachment._meta.get_field("note")
        assert isinstance(field3, TextField)
        assert field3.blank is True


@pytest.mark.django_db
class TestCaseAttachmentUploadPath:
    """Testes do caminho de upload usando UUID."""

    def _create_attachment(self) -> tuple[CaseAttachment, Case]:
        user = User.objects.create_user(username="nir_attach_path@test.com", password="testpass123")
        case = Case.objects.create(created_by=user)
        attachment = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("original.pdf", b"%PDF-1.4 test content", content_type="application/pdf"),
            original_filename="original.pdf",
            stored_filename="stored.pdf",
            content_type="application/pdf",
            size_bytes=512,
            sha256="a" * 64,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        return attachment, case

    def test_upload_path_uses_case_and_attachment_uuid(self) -> None:
        """Caminho é case_attachments/<case_id>/<attachment_id>.<ext>."""
        attachment, case = self._create_attachment()
        path = attachment.file.name
        assert path is not None
        expected_dir = f"case_attachments/{case.case_id}"
        assert path.startswith(expected_dir)
        # Should contain the attachment UUID
        assert str(attachment.attachment_id) in path
        # Should end with .pdf
        assert path.endswith(".pdf")

    def test_original_filename_not_in_path(self) -> None:
        """Nome original não aparece no caminho do arquivo."""
        attachment, _ = self._create_attachment()
        path = attachment.file.name
        assert path is not None
        assert "original" not in path

    def test_path_has_expected_format(self) -> None:
        """Path format: case_attachments/<uuid>/<uuid>.ext"""
        attachment, case = self._create_attachment()
        path = attachment.file.name
        assert path is not None
        parts = path.split("/")
        assert len(parts) >= 3
        assert parts[0] == "case_attachments"
        # Second part is case UUID
        uuid.UUID(parts[1])  # will raise if not valid
        # Last part starts with attachment UUID
        filename = parts[-1]
        file_id = filename.split(".")[0]
        uuid.UUID(file_id)  # will raise if not valid


@pytest.mark.django_db
class TestCaseAttachmentMetadata:
    """Testes de metadados do anexo."""

    def test_preserves_original_filename(self) -> None:
        """original_filename preserva o nome original."""
        user = User.objects.create_user(username="nir_meta@test.com", password="testpass123")
        case = Case.objects.create(created_by=user)
        attachment = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("laudo_usg_hepatico.pdf", b"%PDF content", content_type="application/pdf"),
            original_filename="laudo_usg_hepatico.pdf",
            stored_filename="stored.pdf",
            content_type="application/pdf",
            size_bytes=256,
            sha256="b" * 64,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        assert attachment.original_filename == "laudo_usg_hepatico.pdf"

    def test_preserves_metadata(self) -> None:
        """Metadados são preservados corretamente."""
        user = User.objects.create_user(username="nir_meta2@test.com", password="testpass123")
        case = Case.objects.create(created_by=user)
        content = b"%PDF-1.4 some content"
        sha256 = hashlib.sha256(content).hexdigest()
        attachment = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("doc.pdf", content, content_type="application/pdf"),
            original_filename="doc.pdf",
            stored_filename="stored.pdf",
            content_type="application/pdf",
            size_bytes=len(content),
            sha256=sha256,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        assert attachment.content_type == "application/pdf"
        assert attachment.size_bytes == len(content)
        assert attachment.sha256 == sha256
        assert attachment.uploaded_by == user

    def test_defaults_to_active(self) -> None:
        """Novo anexo nasce com is_suppressed=False."""
        user = User.objects.create_user(username="nir_active@test.com", password="testpass123")
        case = Case.objects.create(created_by=user)
        attachment = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("doc.pdf", b"%PDF", content_type="application/pdf"),
            original_filename="doc.pdf",
            stored_filename="stored.pdf",
            content_type="application/pdf",
            size_bytes=8,
            sha256="c" * 64,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        assert attachment.is_suppressed is False
        assert attachment.suppressed_at is None
        assert attachment.suppressed_by is None
        assert attachment.suppression_reason == ""

    def test_initial_upload_phase(self) -> None:
        """Anexo inicial nasce com upload_phase='initial', status preenchido e note vazio."""
        user = User.objects.create_user(username="nir_phase@test.com", password="testpass123")
        case = Case.objects.create(created_by=user)
        attachment = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("doc.pdf", b"%PDF", content_type="application/pdf"),
            original_filename="doc.pdf",
            stored_filename="stored.pdf",
            content_type="application/pdf",
            size_bytes=8,
            sha256="d" * 64,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        assert attachment.upload_phase == "initial"
        assert attachment.uploaded_when_case_status == CaseStatus.NEW
        assert attachment.note == ""


@pytest.mark.django_db
class TestCaseAttachmentSuppressionFilter:
    """Testes de filtragem de anexos suprimidos."""

    def test_active_queryset_excludes_suppressed(self) -> None:
        """QuerySet filtrado não inclui anexos suprimidos."""
        user = User.objects.create_user(username="nir_supp@test.com", password="testpass123")
        case = Case.objects.create(created_by=user)

        active = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("active.pdf", b"%PDF", content_type="application/pdf"),
            original_filename="active.pdf",
            stored_filename="active_stored.pdf",
            content_type="application/pdf",
            size_bytes=8,
            sha256="e" * 64,
            uploaded_by=user,
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        suppressed = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("suppressed.pdf", b"%PDF", content_type="application/pdf"),
            original_filename="suppressed.pdf",
            stored_filename="suppressed_stored.pdf",
            content_type="application/pdf",
            size_bytes=8,
            sha256="f" * 64,
            uploaded_by=user,
            is_suppressed=True,
            suppressed_at="2026-06-01T00:00:00Z",
            suppression_reason="Enviado incorretamente",
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )

        active_qs = CaseAttachment.objects.filter(case=case, is_suppressed=False)
        assert active in active_qs
        assert suppressed not in active_qs
