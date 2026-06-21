"""Testes do fluxo NIR de reenvio corrigido explícito — Slice 001.

RED: testes falham pois campos/serviço/rota/template não existem ainda.
GREEN: implementação mínima faz todos passarem.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import fitz  # type: ignore[import-untyped]
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseStatus

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_pdf_bytes(text: str = "Paciente: Maria\nRegistro: 2026-1234") -> bytes:
    """Cria um PDF em memória com PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _simple_pdf(text: str = "Paciente: Maria\nRegistro: 2026-1234") -> SimpleUploadedFile:
    """Retorna um SimpleUploadedFile PDF válido."""
    pdf_bytes = _create_test_pdf_bytes(text)
    return SimpleUploadedFile("relatorio.pdf", pdf_bytes, content_type="application/pdf")


def _simple_txt() -> SimpleUploadedFile:
    """Retorna um SimpleUploadedFile .txt (inválido)."""
    return SimpleUploadedFile("test.txt", b"not a pdf", content_type="text/plain")


def _simple_image() -> SimpleUploadedFile:
    """Retorna um SimpleUploadedFile PNG válido para anexo."""
    # Minimal valid PNG (1x1 pixel)
    png_bytes = bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,  # PNG header
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,  # IHDR chunk
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,  # IDAT chunk
            0x54,
            0x08,
            0xD7,
            0x63,
            0x60,
            0x60,
            0x00,
            0x00,
            0x00,
            0x04,
            0x00,
            0x01,
            0x27,
            0x38,
            0x2F,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,  # IEND chunk
            0x42,
            0x60,
            0x82,
        ]
    )
    return SimpleUploadedFile("anexo.png", png_bytes, content_type="image/png")


def _nir_user():
    """Cria e retorna um usuário com papel NIR."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _nir_client(client):
    """Cria usuário NIR, faz login e retorna (cliente, usuário)."""
    user = _nir_user()
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_user():
    """Cria e retorna um usuário com papel doctor."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    return user


def _doctor_client(client):
    """Cria usuário doctor, faz login e retorna (cliente, usuário)."""
    user = _doctor_user()
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCorrectedResubmissionGet:
    """GET /cases/<case_id>/corrected-resubmission/"""

    def test_get_requires_nir_role(self, client) -> None:
        """Usuário sem papel NIR não acessa."""
        doc_client, _ = _doctor_client(client)
        original = Case.objects.create(created_by=_nir_user())
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        response = doc_client.get(url)
        # Deve redirecionar por falta de role (active_role=doctor, precisa=nir)
        assert response.status_code == 302

    def test_get_renders_original_case_context(self, client) -> None:
        """GET como NIR mostra dados do caso anterior e campo de motivo."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(
            created_by=nir_user,
            agency_record_number="2026-0505-001",
        )
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        response = nir_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Deve mostrar registro do caso anterior
        assert "2026-0505-001" in content
        # Deve conter o campo motivo
        assert "Motivo" in content or "motivo" in content
        # Deve ter input file para novo PDF
        assert "pdf" in content.lower() or "PDF" in content

    def test_get_404_for_nonexistent_case(self, client) -> None:
        """GET com case_id inexistente retorna 404."""
        nir_client, _ = _nir_client(client)
        url = reverse("intake:corrected_resubmission", args=["00000000-0000-0000-0000-000000000000"])
        response = nir_client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestCorrectedResubmissionPost:
    """POST /cases/<case_id>/corrected-resubmission/"""

    def test_post_requires_correction_reason(self, client) -> None:
        """POST sem motivo não cria caso."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()
        response = nir_client.post(url, {"pdf_file": pdf})
        # Deve re-renderizar com mensagem de warning (sem redirect)
        assert response.status_code == 200
        assert "Motivo" in response.content.decode()
        # Nenhum novo caso deve ter sido criado
        assert Case.objects.count() == 1  # apenas o original
        # Caso original não deve ter sido alterado
        original = Case.objects.get(pk=original.pk)
        assert original.status == CaseStatus.NEW

    def test_post_requires_single_pdf(self, client) -> None:
        """POST sem PDF não cria caso."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        response = nir_client.post(url, {"correction_reason": "Anexo errado enviado"})
        assert response.status_code == 200
        assert Case.objects.count() == 1

    def test_post_rejects_invalid_pdf(self, client) -> None:
        """POST com arquivo não-PDF rejeita."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        response = nir_client.post(
            url,
            {"correction_reason": "Anexo errado", "pdf_file": _simple_txt()},
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1

    def test_post_creates_new_case_linked_to_original(self, client) -> None:
        """POST válido cria novo caso vinculado ao original."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()

        with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
            response = nir_client.post(
                url,
                {
                    "correction_reason": "Documento incompleto. Enviando laudo corrigido.",
                    "pdf_file": pdf,
                },
            )

        # Deve redirecionar (success)
        assert response.status_code == 302

        # Novo caso criado
        assert Case.objects.count() == 2
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None

        # Vínculo
        assert new_case.corrects_case == original
        assert new_case.correction_reason == "Documento incompleto. Enviando laudo corrigido."
        assert new_case.correction_created_by == nir_user
        assert new_case.correction_created_at is not None

        # Novo caso em processamento
        assert new_case.status == CaseStatus.R1_ACK_PROCESSING

        # Extração enfileirada
        mock_enqueue.assert_called_once_with(new_case.case_id)

    def test_post_does_not_modify_original_status_or_decision_fields(self, client) -> None:
        """Status/decisão do caso anterior permanecem intactos."""
        nir_client, nir_user = _nir_client(client)

        # Criar caso anterior já decidido (negado pelo médico)
        original = Case.objects.create(created_by=nir_user)
        # Avançar manualmente para DOCTOR_DENIED
        original.start_processing(user=nir_user)
        original.save()
        original.start_extraction(user=None)
        original.save()
        original.extraction_complete(success=True, user=None)
        original.save()
        original.llm1_complete(success=True, user=None)
        original.save()
        original.llm2_complete(success=True, user=None)
        original.save()
        original.ready_for_doctor(user=None)
        original.save()
        # Definir campos de decisão antes da transição
        original.doctor_decision = "deny"
        original.doctor_reason = "Paciente sem critérios"
        original.doctor = User.objects.create_user(username="doctor@test.com", password="testpass123")
        original.save()
        original.doctor_decide(decision="deny", user=nir_user)
        original.save()
        original = Case.objects.get(pk=original.pk)
        assert original.status == CaseStatus.DOCTOR_DENIED

        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()

        with patch("apps.intake.tasks.enqueue_pdf_extraction"):
            nir_client.post(
                url,
                {
                    "correction_reason": "Laudo corrigido",
                    "pdf_file": pdf,
                },
            )

        original = Case.objects.get(pk=original.pk)
        assert original.status == CaseStatus.DOCTOR_DENIED
        assert original.doctor_decision == "deny"
        assert original.doctor_reason == "Paciente sem critérios"

    def test_post_does_not_copy_original_attachments(self, client) -> None:
        """Anexos do caso anterior não são copiados para o novo caso."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        # Criar anexo no caso original
        CaseAttachment.objects.create(
            case=original,
            file=_simple_pdf(),
            original_filename="original_anexo.pdf",
            stored_filename="original_anexo.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="abc123",
            uploaded_by=nir_user,
        )

        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()

        with patch("apps.intake.tasks.enqueue_pdf_extraction"):
            response = nir_client.post(
                url,
                {"correction_reason": "Laudo corrigido", "pdf_file": pdf},
            )

        assert response.status_code == 302
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None

        # Anexo do original não deve estar no novo caso
        assert new_case.attachments.count() == 0
        # Original ainda tem seu anexo
        assert original.attachments.count() == 1

    def test_post_saves_new_attachments_only_on_new_case(self, client) -> None:
        """Anexos enviados no reenvio aparecem só no novo caso."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        # Anexo original
        CaseAttachment.objects.create(
            case=original,
            file=_simple_pdf(),
            original_filename="original.pdf",
            stored_filename="original.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="abc",
            uploaded_by=nir_user,
        )

        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()
        new_att = _simple_image()

        with patch("apps.intake.tasks.enqueue_pdf_extraction"):
            response = nir_client.post(
                url,
                {
                    "correction_reason": "Laudo corrigido",
                    "pdf_file": pdf,
                    "attachment_files": [new_att],
                },
            )

        assert response.status_code == 302
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None

        # Novo caso tem o novo anexo
        new_attachments = list(new_case.attachments.all())
        assert len(new_attachments) == 1
        assert new_attachments[0].original_filename == "anexo.png"

        # Original ainda tem seu anexo
        assert original.attachments.count() == 1

    def test_post_records_correction_events_on_both_cases(self, client) -> None:
        """Eventos registrados nos dois casos."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()

        with patch("apps.intake.tasks.enqueue_pdf_extraction"):
            nir_client.post(
                url,
                {"correction_reason": "Laudo corrigido", "pdf_file": pdf},
            )

        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None

        # Novo caso tem CASE_CORRECTION_CREATED
        new_events = list(CaseEvent.objects.filter(case=new_case))
        event_types_new = [e.event_type for e in new_events]
        assert "CASE_CORRECTION_CREATED" in event_types_new

        # Caso original tem CASE_MARKED_SUPERSEDED
        original_events = list(CaseEvent.objects.filter(case=original))
        event_types_orig = [e.event_type for e in original_events]
        assert "CASE_MARKED_SUPERSEDED" in event_types_orig

    def test_new_case_enqueued_for_pdf_extraction(self, client) -> None:
        """Extraçao PDF enfileirada para o novo caso."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()

        with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
            nir_client.post(
                url,
                {"correction_reason": "Documento corrigido", "pdf_file": pdf},
            )

        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None
        mock_enqueue.assert_called_once_with(new_case.case_id)

    def test_post_strips_whitespace_correction_reason(self, client) -> None:
        """Motivo com apenas espaços é rejeitado."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        pdf = _simple_pdf()

        response = nir_client.post(
            url,
            {"correction_reason": "   ", "pdf_file": pdf},
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1
