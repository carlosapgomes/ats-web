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
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseProcedure, CaseStatus, ProcedureType
from apps.intake.services import create_corrected_resubmission

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

    def test_post_requires_confirmation(self, client) -> None:
        """POST sem checkbox de confirmação não cria caso (backend é fonte de verdade)."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        response = nir_client.post(
            url,
            {"correction_reason": "Laudo corrigido", "pdf_file": _simple_pdf()},
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
                    "confirmation": "on",
                    "exam_type": "eda",
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
                    "confirmation": "on",
                    "exam_type": "eda",
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
                {
                    "correction_reason": "Laudo corrigido",
                    "pdf_file": pdf,
                    "confirmation": "on",
                    "exam_type": "eda",
                },
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
                    "confirmation": "on",
                    "exam_type": "eda",
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
                {
                    "correction_reason": "Laudo corrigido",
                    "pdf_file": pdf,
                    "confirmation": "on",
                    "exam_type": "eda",
                },
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
                {
                    "correction_reason": "Documento corrigido",
                    "pdf_file": pdf,
                    "confirmation": "on",
                    "exam_type": "eda",
                },
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


# ── Closed cases search tests (Slice 002) ────────────────────────────────


@pytest.mark.django_db
class TestClosedCasesSearchCorrectionVisibility:
    """Testes para visibilidade de correção na busca de casos encerrados."""

    def test_closed_cases_search_shows_corrected_resubmission_action(self, client) -> None:
        """Caso CLEANED aparece na busca com link "Reenviar caso corrigido"."""
        nir_client, nir_user = _nir_client(client)
        Case.objects.create(
            created_by=nir_user,
            agency_record_number="CLOSED-001",
            status=CaseStatus.CLEANED,
        )
        url = reverse("intake:closed_cases_search")
        response = nir_client.get(url, {"q": "CLOSED-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reenviar caso corrigido" in content

    def test_closed_cases_search_shows_corrected_by_badge_when_applicable(self, client) -> None:
        """Caso encerrado com correção mostra badge "Corrigido por novo envio"."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(
            created_by=nir_user,
            agency_record_number="CLOSED-002-ORIG",
            status=CaseStatus.CLEANED,
        )
        # Criar novo caso que corrige o original
        Case.objects.create(
            created_by=nir_user,
            corrects_case=original,
            correction_reason="Laudo corrigido",
            correction_created_by=nir_user,
            correction_created_at=timezone.now(),
            agency_record_number="CLOSED-002-NEW",
            status=CaseStatus.WAIT_DOCTOR,
        )
        url = reverse("intake:closed_cases_search")
        response = nir_client.get(url, {"q": "CLOSED-002-ORIG"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "corrigido" in content.lower() or "Corrigido" in content


# ── Slice 007: reenvio corrigido exige tipo explícito (R3/R4) ────────────


@pytest.mark.django_db
class TestCorrectedResubmissionExamTypeFlag:
    """R3/R4 — o reenvio corrigido NÃO herda tipo: exige escolha explícita no
    novo caso. A escolha passa pela validação central (choice + flag de
    intake) antes de qualquer efeito colateral. O original permanece intacto.
    """

    # ── Tipo ausente/inválido rejeitado (RED R3) ─────────────────────

    def test_service_requires_exam_type(self) -> None:
        """Sem tipo explícito, o serviço levanta ValueError sem efeitos."""
        nir_user = _nir_user()
        original = Case.objects.create(created_by=nir_user)
        with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
            with pytest.raises(ValueError):
                create_corrected_resubmission(
                    original_case=original,
                    pdf_file=_simple_pdf(),
                    user=nir_user,
                    correction_reason="Laudo corrigido",
                )

        assert Case.objects.count() == 1
        mock_enqueue.assert_not_called()
        original = Case.objects.get(pk=original.pk)
        # Nada foi declarado no original (projeção intacta, sem coluna).
        assert CaseProcedure.objects.filter(case=original).count() == 0
        assert original.status == CaseStatus.NEW
        assert set(original.events.values_list("event_type", flat=True)) == {"CASE_CREATED"}

    def test_post_without_exam_type_creates_no_case(self, client) -> None:
        """View: POST sem tipo re-renderiza com warning; nada é criado."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
            response = nir_client.post(
                url,
                {
                    "correction_reason": "Laudo corrigido",
                    "pdf_file": _simple_pdf(),
                    "confirmation": "on",
                },
            )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Selecione o tipo de exame" in content
        assert Case.objects.count() == 1
        mock_enqueue.assert_not_called()

    def test_post_with_invalid_exam_type_creates_no_case(self, client) -> None:
        """Tipo inválido também é rejeitado pelo backend."""
        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
            response = nir_client.post(
                url,
                {
                    "correction_reason": "Laudo corrigido",
                    "pdf_file": _simple_pdf(),
                    "confirmation": "on",
                    "exam_type": "cpre",
                },
            )

        assert response.status_code == 200
        assert Case.objects.count() == 1
        mock_enqueue.assert_not_called()

    def test_form_has_no_prechecked_type(self, client) -> None:
        """Formulário sem opção pré-marcada (radios EDA/Colonoscopia)."""
        import re

        nir_client, nir_user = _nir_client(client)
        original = Case.objects.create(created_by=nir_user)
        url = reverse("intake:corrected_resubmission", args=[original.case_id])
        response = nir_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="exam_type"' in content
        assert "Tipo de exame" in content
        radios = re.findall(r"<input[^>]*name=[\"']exam_type[\"'][^>]*>", content)
        assert len(radios) >= 2
        for tag in radios:
            assert "checked" not in tag, f"Radio pré-marcado: {tag}"

    # ── Flag de intake vale para o novo caso (R3/F1) ──────────────────

    def test_service_rejects_explicit_colonoscopy_when_flag_off(self) -> None:
        """Flag false + tipo explícito colonoscopia → ValueError sem efeitos."""
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=False):
            nir_user = _nir_user()
            original = Case.objects.create(created_by=nir_user)
            with pytest.raises(ValueError):
                create_corrected_resubmission(
                    original_case=original,
                    pdf_file=_simple_pdf(),
                    user=nir_user,
                    correction_reason="Laudo corrigido",
                    exam_type="colonoscopy",
                )
        assert Case.objects.count() == 1

    def test_post_with_explicit_colonoscopy_flag_off_creates_no_case(self, client) -> None:
        """View: flag false + colonoscopia explícita → tela com indisponibilidade."""
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=False):
            nir_client, nir_user = _nir_client(client)
            original = Case.objects.create(
                created_by=nir_user,
                agency_record_number="2026-C1",
            )
            url = reverse("intake:corrected_resubmission", args=[original.case_id])
            with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
                response = nir_client.post(
                    url,
                    {
                        "correction_reason": "Laudo corrigido",
                        "pdf_file": _simple_pdf(),
                        "confirmation": "on",
                        "exam_type": "colonoscopy",
                    },
                )

        assert response.status_code == 200
        content = response.content.decode()
        assert "colonoscopia" in content.lower()
        assert "indispon" in content.lower() or "habilitad" in content.lower()

        assert Case.objects.count() == 1
        mock_enqueue.assert_not_called()
        original = Case.objects.get(pk=original.pk)
        # Nada foi declarado no original (projeção intacta, sem coluna).
        assert CaseProcedure.objects.filter(case=original).count() == 0
        assert original.status == CaseStatus.NEW
        assert original.agency_record_number == "2026-C1"
        event_types = set(original.events.values_list("event_type", flat=True))
        assert "CASE_MARKED_SUPERSEDED" not in event_types
        assert event_types == {"CASE_CREATED"}

    # ── Tipo explícito válido persiste no novo caso (R3) ──────────────

    def test_post_with_explicit_colonoscopy_flag_on_persists_type(self, client) -> None:
        """Flag true + colonoscopia explícita → novo caso colonoscopia."""
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            nir_client, nir_user = _nir_client(client)
            original = Case.objects.create(created_by=nir_user)
            url = reverse("intake:corrected_resubmission", args=[original.case_id])
            with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
                response = nir_client.post(
                    url,
                    {
                        "correction_reason": "Laudo corrigido",
                        "pdf_file": _simple_pdf(),
                        "confirmation": "on",
                        "exam_type": "colonoscopy",
                    },
                )

        assert response.status_code == 302
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None
        # Slice 008 (R5): prova row declarada, não a coluna.
        assert CaseProcedure.objects.filter(
            case=new_case, procedure_type=ProcedureType.COLONOSCOPY, declared_by_nir=True
        ).exists()
        mock_enqueue.assert_called_once_with(new_case.case_id)

    def test_post_with_explicit_eda_flag_off_persists_type(self, client) -> None:
        """Flag false + EDA explícito → novo caso EDA (EDA segue ok)."""
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=False):
            nir_client, nir_user = _nir_client(client)
            original = Case.objects.create(created_by=nir_user)
            url = reverse("intake:corrected_resubmission", args=[original.case_id])
            with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
                response = nir_client.post(
                    url,
                    {
                        "correction_reason": "Laudo corrigido",
                        "pdf_file": _simple_pdf(),
                        "confirmation": "on",
                        "exam_type": "eda",
                    },
                )

        assert response.status_code == 302
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None
        # Slice 008 (R5): prova row declarada, não a coluna.
        assert CaseProcedure.objects.filter(
            case=new_case, procedure_type=ProcedureType.EDA, declared_by_nir=True
        ).exists()
        mock_enqueue.assert_called_once_with(new_case.case_id)

    # ── R4: tipo pode divergir do original; original permanece intacto ──

    def test_post_eda_original_to_colonoscopy_new_with_flag_on(self, client) -> None:
        """Original EDA → novo Colonoscopia é válido com flag ativa."""
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            nir_client, nir_user = _nir_client(client)
            original = Case.objects.create(
                created_by=nir_user,
                agency_record_number="2026-EDA-ORIG",
            )
            url = reverse("intake:corrected_resubmission", args=[original.case_id])
            with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
                response = nir_client.post(
                    url,
                    {
                        "correction_reason": "Laudo corrigido",
                        "pdf_file": _simple_pdf(),
                        "confirmation": "on",
                        "exam_type": "colonoscopy",
                    },
                )

        assert response.status_code == 302
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None
        # Slice 008 (R5): prova row declarada, não a coluna.
        assert CaseProcedure.objects.filter(
            case=new_case, procedure_type=ProcedureType.COLONOSCOPY, declared_by_nir=True
        ).exists()
        mock_enqueue.assert_called_once_with(new_case.case_id)

        # Original permanece EDA e inalterado
        original = Case.objects.get(pk=original.pk)
        assert original.agency_record_number == "2026-EDA-ORIG"
        assert original.status == CaseStatus.NEW

    def test_correction_created_event_contains_exam_type(self, client) -> None:
        """Evento de correção inclui o tipo do novo caso (R4)."""
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            nir_client, nir_user = _nir_client(client)
            original = Case.objects.create(created_by=nir_user)
            url = reverse("intake:corrected_resubmission", args=[original.case_id])
            with patch("apps.intake.tasks.enqueue_pdf_extraction"):
                nir_client.post(
                    url,
                    {
                        "correction_reason": "Laudo corrigido",
                        "pdf_file": _simple_pdf(),
                        "confirmation": "on",
                        "exam_type": "colonoscopy",
                    },
                )

        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None
        event = CaseEvent.objects.get(case=new_case, event_type="CASE_CORRECTION_CREATED")
        # Contrato form→evento: a escolha explícita do reenvio (SSR) persiste
        # no payload do CASE_CORRECTION_CREATED (auditoria, sem coluna).
        assert event.payload.get("exam_type") == "colonoscopy"
        assert "pdf" not in event.payload and "extracted_text" not in event.payload


# ── Slice 007 — R2: filtro por tipo na busca de encerrados ───────────────


@pytest.mark.django_db
class TestClosedCasesSearchExamTypeFilter:
    """R2: busca de encerrados recebe filtro exam_type compondo com o termo."""

    SEARCH_URL = reverse("intake:closed_cases_search")

    def _cleaned(self, user, selection: str, record: str) -> Case:
        # Slice 008 (R5)/011-B: fixture NIR explícita — rows declaradas
        # autorizam o filtro por dimensão declarada (sem coluna).
        case = Case.objects.create(
            created_by=user,
            agency_record_number=record,
            status=CaseStatus.CLEANED,
        )
        for procedure_type in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
            if selection == procedure_type or selection == "eda_colonoscopy":
                CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
        return case

    def test_default_todos_shows_both_types(self, client) -> None:
        """Sem parâmetro, busca por termo mostra ambos os tipos."""
        nir_client, nir_user = _nir_client(client)
        self._cleaned(nir_user, "eda", "CLOSED-EDA-001")
        self._cleaned(nir_user, "colonoscopy", "CLOSED-COL-001")

        response = nir_client.get(self.SEARCH_URL, {"q": "CLOSED"})
        content = response.content.decode()
        assert "CLOSED-EDA-001" in content
        assert "CLOSED-COL-001" in content

    def test_filter_eda_composes_with_term(self, client) -> None:
        """exam_type=eda + termo → somente EDA."""
        nir_client, nir_user = _nir_client(client)
        self._cleaned(nir_user, "eda", "CLOSED-EDA-001")
        self._cleaned(nir_user, "colonoscopy", "CLOSED-COL-001")

        response = nir_client.get(self.SEARCH_URL, {"q": "CLOSED", "exam_type": "eda"})
        content = response.content.decode()
        assert "CLOSED-EDA-001" in content
        assert "CLOSED-COL-001" not in content

    def test_filter_colonoscopy_composes_with_term(self, client) -> None:
        """exam_type=colonoscopy + termo → somente Colonoscopia."""
        nir_client, nir_user = _nir_client(client)
        self._cleaned(nir_user, "eda", "CLOSED-EDA-001")
        self._cleaned(nir_user, "colonoscopy", "CLOSED-COL-001")

        response = nir_client.get(self.SEARCH_URL, {"q": "CLOSED", "exam_type": "colonoscopy"})
        content = response.content.decode()
        assert "CLOSED-COL-001" in content
        assert "CLOSED-EDA-001" not in content

    def test_specific_type_without_term_lists_recent_of_type(self, client) -> None:
        """Tipo específico sem termo lista recentes do tipo (comportamento
        definido no design D13, consistente com o histórico CHD)."""
        nir_client, nir_user = _nir_client(client)
        self._cleaned(nir_user, "eda", "CLOSED-EDA-001")
        self._cleaned(nir_user, "colonoscopy", "CLOSED-COL-001")

        response = nir_client.get(self.SEARCH_URL, {"exam_type": "eda"})
        content = response.content.decode()
        assert "CLOSED-EDA-001" in content
        assert "CLOSED-COL-001" not in content

    def test_invalid_type_falls_back_to_all(self, client) -> None:
        """Tipo inválido cai para Todos (default)."""
        nir_client, nir_user = _nir_client(client)
        self._cleaned(nir_user, "eda", "CLOSED-EDA-001")
        self._cleaned(nir_user, "colonoscopy", "CLOSED-COL-001")

        response = nir_client.get(self.SEARCH_URL, {"q": "CLOSED", "exam_type": "cpre"})
        content = response.content.decode()
        assert "CLOSED-EDA-001" in content
        assert "CLOSED-COL-001" in content

    def test_all_without_term_keeps_empty_state(self, client) -> None:
        """Todos sem termo mantém o estado vazio atual (tela de busca)."""
        nir_client, _ = _nir_client(client)
        response = nir_client.get(self.SEARCH_URL, {"exam_type": "all"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Faça uma busca" in content

    def test_cards_show_exam_type_badge(self, client) -> None:
        """Cards de encerrados exibem badge persistido do tipo."""
        nir_client, nir_user = _nir_client(client)
        self._cleaned(nir_user, "colonoscopy", "CLOSED-COL-BADGE")

        response = nir_client.get(self.SEARCH_URL, {"q": "CLOSED-COL-BADGE"})
        content = response.content.decode()
        assert "exam-type-colonoscopy" in content
        assert "Colonoscopia" in content

    def test_template_has_exam_type_select(self, client) -> None:
        """Formulário de encerrados possui controle de tipo com default Todos."""
        nir_client, _ = _nir_client(client)
        response = nir_client.get(self.SEARCH_URL)
        content = response.content.decode()
        assert 'name="exam_type"' in content
        assert "Todos os tipos" in content
        assert '<option value="all" selected' in content or 'value="all"' in content

    def test_clear_button_restores_all_filters(self, client) -> None:
        """Botão Limpar restaura Todos + sem termo."""
        nir_client, _ = _nir_client(client)
        response = nir_client.get(self.SEARCH_URL + "?exam_type=colonoscopy&q=0428")
        content = response.content.decode()
        assert f'href="{self.SEARCH_URL}"' in content
