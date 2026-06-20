"""Testes de upload NIR com anexos — Slice 001.

RED phase: testes falham antes da implementação.
"""

from __future__ import annotations

import hashlib
import io

import fitz
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseStatus

User = get_user_model()


def _create_pdf_bytes(text: str = "Paciente: João\nRegistro: 2026-0001") -> bytes:
    """Cria um PDF em memória."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _nir_client(client):
    """Cria usuário NIR logado."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir_attach@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    """Cria usuário doctor logado."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc_attach@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _pdf_file(name: str = "report.pdf") -> SimpleUploadedFile:
    """SimpleUploadedFile PDF válido."""
    return SimpleUploadedFile(name, _create_pdf_bytes(), content_type="application/pdf")


def _jpeg_file(name: str = "photo.jpg") -> SimpleUploadedFile:
    """SimpleUploadedFile JPEG (bytes mínimos de imagem)."""
    # Mínimo JPEG válido (SOI + EOI markers)
    jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100 + bytes([0xFF, 0xD9])
    return SimpleUploadedFile(name, jpeg_bytes, content_type="image/jpeg")


def _png_file(name: str = "image.png") -> SimpleUploadedFile:
    """SimpleUploadedFile PNG (bytes mínimos)."""
    png_bytes = bytes([0x89, 0x50, 0x4E, 0x47]) + b"\x00" * 100 + bytes([0x49, 0x45, 0x4E, 0x44])
    return SimpleUploadedFile(name, png_bytes, content_type="image/png")


def _txt_file(name: str = "notes.txt") -> SimpleUploadedFile:
    """SimpleUploadedFile .txt (inválido como anexo)."""
    return SimpleUploadedFile(name, b"not an image or pdf", content_type="text/plain")


# ── Attachment Upload Tests ──────────────────────────────────────────────


@pytest.mark.django_db
class TestAttachmentUpload:
    """Testes de upload NIR com anexos."""

    def test_single_pdf_accepts_pdf_jpeg_png_attachments(self, client) -> None:
        """Upload de 1 PDF + 3 anexos válidos: cria 1 case + 3 attachments."""
        client, user = _nir_client(client)
        pdf = _pdf_file()
        att1 = _pdf_file("attachment1.pdf")
        att2 = _jpeg_file()
        att3 = _png_file()

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [att1, att2, att3]},
            follow=True,
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1, "Deveria criar 1 case"
        case = Case.objects.first()
        attachments = CaseAttachment.objects.filter(case=case)
        assert attachments.count() == 3, f"Deveria criar 3 attachments, criou {attachments.count()}"
        assert response.status_code == 200

    def test_attachment_count_matches_uploaded(self, client) -> None:
        """Contagem de anexos corresponde aos arquivos enviados."""
        client, user = _nir_client(client)
        pdf = _pdf_file()
        attachments = [_pdf_file(f"att_{i}.pdf") for i in range(3)]

        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": attachments},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert CaseAttachment.objects.filter(case=case).count() == 3

    def test_attachment_upload_records_case_event(self, client) -> None:
        """Cada anexo gera CASE_ATTACHMENT_ADDED."""
        client, user = _nir_client(client)
        pdf = _pdf_file()
        att = _jpeg_file()

        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [att]},
            follow=True,
        )
        case = Case.objects.first()
        events = CaseEvent.objects.filter(case=case, event_type="CASE_ATTACHMENT_ADDED")
        assert events.count() == 1

        event = events.first()
        assert event is not None
        payload = event.payload or {}
        assert "attachment_id" in payload
        assert "original_filename" in payload
        assert "content_type" in payload
        assert "size_bytes" in payload
        assert "sha256" in payload

    def test_bulk_pdf_upload_rejects_attachments(self, client) -> None:
        """Upload com 2 PDFs + anexo: rejeita anexos, não associa ambiguamente."""
        client, _ = _nir_client(client)
        pdf1 = _pdf_file()
        pdf2 = _pdf_file()
        att = _jpeg_file()

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf1, pdf2], "attachment_files": [att]},
            follow=True,
        )
        content = response.content.decode()
        assert "anexos" in content.lower() and (
            "apenas" in content.lower() or "permitido" in content.lower() or "1" in content
        )

        # Nenhum attachment deve ser criado
        assert CaseAttachment.objects.count() == 0
        # Casos ainda devem ser criados (2 PDFs)
        assert Case.objects.count() == 2

    def test_attachment_rejects_invalid_extension(self, client) -> None:
        """Anexo .txt rejeitado."""
        client, _ = _nir_client(client)
        pdf = _pdf_file()
        txt = _txt_file()

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [txt]},
            follow=True,
        )
        content = response.content.decode()
        assert "formato" in content.lower() or "inválido" in content.lower() or "aceito" in content.lower()
        # Não deve criar caso com anexo inválido
        assert Case.objects.count() == 0
        assert CaseAttachment.objects.count() == 0

    def test_attachment_rejects_more_than_ten_files(self, client) -> None:
        """11 anexos rejeitados."""
        client, _ = _nir_client(client)
        pdf = _pdf_file()
        many_attachments = [_jpeg_file(f"img_{i}.jpg") for i in range(11)]

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": many_attachments},
            follow=True,
        )
        content = response.content.decode()
        assert "10" in content or "máximo" in content.lower() or "limite" in content.lower()
        assert Case.objects.count() == 0
        assert CaseAttachment.objects.count() == 0

    def test_attachment_rejects_file_over_20mb(self, client, monkeypatch) -> None:
        """Anexo acima do limite é rejeitado."""
        import django.conf

        client, _ = _nir_client(client)
        pdf = _pdf_file()

        # Reduzir limite temporariamente para 100 bytes
        monkeypatch.setattr(django.conf.settings, "INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE", 100)

        big_att = SimpleUploadedFile("big.jpg", b"x" * 200, content_type="image/jpeg")

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [big_att]},
            follow=True,
        )
        content = response.content.decode()
        assert "excede" in content.lower() or "limite" in content.lower()
        assert Case.objects.count() == 0
        assert CaseAttachment.objects.count() == 0

    def test_attachment_total_size_limit_message(self, client, monkeypatch) -> None:
        """Anexo total acima de 200 MB exibe mensagem clara."""
        import django.conf

        client, _ = _nir_client(client)
        pdf = _pdf_file()

        # Reduzir limite total para 150 bytes
        monkeypatch.setattr(django.conf.settings, "INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE", 150)

        att1 = SimpleUploadedFile("img1.jpg", b"x" * 100, content_type="image/jpeg")
        att2 = SimpleUploadedFile("img2.jpg", b"x" * 100, content_type="image/jpeg")

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [att1, att2]},
            follow=True,
        )
        content = response.content.decode()
        assert "excede" in content.lower() or "limite" in content.lower() or "tamanho total" in content.lower()
        assert Case.objects.count() == 0
        assert CaseAttachment.objects.count() == 0

    def test_bulk_upload_with_attachments_shows_clear_error_message(self, client) -> None:
        """Upload com 2 PDFs + anexo mostra mensagem clara sobre anexos."""
        client, _ = _nir_client(client)
        pdf1 = _pdf_file("report1.pdf")
        pdf2 = _pdf_file("report2.pdf")
        att = _jpeg_file()

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf1, pdf2], "attachment_files": [att]},
            follow=True,
        )
        content = response.content.decode()
        # Mensagem deve ser clara sobre anexos com múltiplos PDFs
        assert any(word in content.lower() for word in ["anexos", "apenas", "permitido", "relatório principal"])
        # Casos devem ser criados (2 PDFs válidos)
        assert Case.objects.count() == 2
        assert CaseAttachment.objects.count() == 0

    def test_case_attachment_added_event_has_timeline_label(self, client) -> None:
        """CASE_ATTACHMENT_ADDED tem label 'Anexo adicionado'."""
        # Verificar que o mapa EVENT_LABELS contém o label
        from apps.intake.views import EVENT_LABELS

        assert "CASE_ATTACHMENT_ADDED" in EVENT_LABELS
        assert EVENT_LABELS["CASE_ATTACHMENT_ADDED"] == "Anexo adicionado"

    def test_upload_without_attachments_still_works(self, client) -> None:
        """Upload sem anexos continua funcionando."""

        client, _ = _nir_client(client)
        pdf = _pdf_file()

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf]},
            follow=True,
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1
        assert CaseAttachment.objects.count() == 0

    def test_attachment_sha256_correct(self, client) -> None:
        """SHA256 do anexo é calculado corretamente."""
        client, user = _nir_client(client)
        pdf = _pdf_file()
        jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100 + bytes([0xFF, 0xD9])
        expected_sha = hashlib.sha256(jpeg_bytes).hexdigest()
        att = SimpleUploadedFile("test.jpg", jpeg_bytes, content_type="image/jpeg")

        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [att]},
            follow=True,
        )
        attachment = CaseAttachment.objects.first()
        assert attachment is not None
        assert attachment.sha256 == expected_sha

    def test_attachment_uploaded_when_case_status_recorded(self, client) -> None:
        """uploaded_when_case_status é preenchido com status atual (após FSM)."""
        client, user = _nir_client(client)
        pdf = _pdf_file()
        att = _jpeg_file()

        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [att]},
            follow=True,
        )
        attachment = CaseAttachment.objects.first()
        assert attachment is not None
        # Status é R1_ACK_PROCESSING pois o anexo é salvo após FSM transition
        assert attachment.uploaded_when_case_status == CaseStatus.R1_ACK_PROCESSING
        assert attachment.upload_phase == "initial"

    def test_upload_with_attachments_redirects_to_my_cases(self, client) -> None:
        """Upload com anexos redireciona para my_cases."""
        client, _ = _nir_client(client)
        pdf = _pdf_file()
        att = _jpeg_file()

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf], "attachment_files": [att]},
        )
        assert response.status_code == 302
        assert response.url == reverse("intake:my_cases")
