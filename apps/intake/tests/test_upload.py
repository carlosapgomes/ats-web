"""Testes de upload de PDF e criação de caso — Slice 003.

Upload múltiplo com extração assíncrona.
"""

from __future__ import annotations

import os
from io import BytesIO

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_pdf_bytes(text: str = "Paciente: João da Silva\nRegistro: 2026-0505-001") -> bytes:
    """Cria um PDF em memória com PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _nir_client(client):
    """Cria usuário NIR, faz login e retorna o cliente."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    """Cria usuário doctor, faz login e retorna o cliente."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _simple_pdf() -> SimpleUploadedFile:
    """Retorna um SimpleUploadedFile PDF válido."""
    pdf_bytes = _create_test_pdf_bytes()
    return SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")


def _simple_txt() -> SimpleUploadedFile:
    """Retorna um SimpleUploadedFile .txt (inválido)."""
    return SimpleUploadedFile("test.txt", b"not a pdf", content_type="text/plain")


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUploadPage:
    """GET /cases/ — renderização da página de upload."""

    def test_upload_page_renders(self, client) -> None:
        """GET com usuário NIR autenticado retorna 200 com form."""
        client, _ = _nir_client(client)
        response = client.get(reverse("intake:home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "encaminhamento" in content.lower() or "pdf" in content.lower()

    def test_upload_page_shows_recent_cases(self, client) -> None:
        """GET mostra lista de casos recentes do usuário."""
        client, user = _nir_client(client)
        Case.objects.create(created_by=user, agency_record_number="2026-0001")
        Case.objects.create(created_by=user, agency_record_number="2026-0002")
        response = client.get(reverse("intake:home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "2026-0001" in content
        assert "2026-0002" in content


@pytest.mark.django_db
class TestUploadPost:
    """POST /cases/ — criação de caso via upload único (compatibilidade)."""

    def test_upload_creates_case(self, client) -> None:
        """POST com PDF cria Case no banco."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1

    def test_upload_sets_created_by(self, client) -> None:
        """case.created_by deve ser o usuário logado."""
        client, user = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.created_by == user

    def test_upload_saves_pdf_file(self, client) -> None:
        """case.pdf_file deve existir no MEDIA_ROOT."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.pdf_file is not None
        assert os.path.exists(case.pdf_file.path)

    def test_upload_transitions_to_r1_ack_processing(self, client) -> None:
        """Após upload, status deve ser R1_ACK_PROCESSING (extração assíncrona)."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.status == CaseStatus.R1_ACK_PROCESSING

    def test_upload_does_not_extract_text(self, client) -> None:
        """case.extracted_text deve estar vazio (extração é assíncrona)."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.extracted_text == ""
        assert case.agency_record_number == ""
        assert case.agency_record_extracted_at is None

    def test_upload_rejects_non_pdf(self, client) -> None:
        """POST com arquivo .txt deve falhar validação e não criar Case."""
        client, _ = _nir_client(client)
        txt_file = _simple_txt()
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [txt_file]},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "não é um arquivo PDF" in content

    def test_upload_requires_nir_role(self, client) -> None:
        """Usuário doctor não pode fazer upload."""
        client, _ = _doctor_client(client)
        pdf_file = _simple_pdf()
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
        )
        assert response.status_code == 302
        assert Case.objects.count() == 0

    def test_upload_requires_login(self, client) -> None:
        """Sem login, POST deve redirecionar para /login/."""
        pdf_file = _simple_pdf()
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
        )
        assert response.status_code == 302
        assert "/login/" in response.url.lower()
        assert Case.objects.count() == 0


@pytest.mark.django_db
class TestUploadAuditEvents:
    """Verificação de eventos de auditoria (CaseEvent)."""

    def test_upload_generates_case_created_event(self, client) -> None:
        """Deve gerar CaseEvent CASE_CREATED."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        events = CaseEvent.objects.filter(case=case)
        event_types = set(e.event_type for e in events)
        assert "CASE_CREATED" in event_types

    def test_upload_generates_start_processing_event(self, client) -> None:
        """Deve gerar CASE_START_PROCESSING."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        events = CaseEvent.objects.filter(case=case)
        event_types = set(e.event_type for e in events)
        assert "CASE_START_PROCESSING" in event_types

    def test_upload_does_not_generate_extraction_events(self, client) -> None:
        """Não deve gerar CASE_START_EXTRACTION ou CASE_EXTRACTION_OK (assíncrono)."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        events = CaseEvent.objects.filter(case=case)
        event_types = set(e.event_type for e in events)
        assert "CASE_START_EXTRACTION" not in event_types
        assert "CASE_EXTRACTION_OK" not in event_types


# ── Multi-upload Tests ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestMultiUploadPost:
    """POST /cases/ com múltiplos PDFs."""

    def test_three_pdfs_create_three_cases(self, client) -> None:
        """POST com 3 PDFs cria 3 Cases."""
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        assert response.status_code == 200
        assert Case.objects.count() == 3

    def test_three_pdfs_all_at_r1_ack(self, client) -> None:
        """Todos os casos criados ficam em R1_ACK_PROCESSING."""
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        for case in Case.objects.all():
            assert case.status == CaseStatus.R1_ACK_PROCESSING

    def test_three_pdfs_all_have_created_by(self, client) -> None:
        """Todos os casos têm created_by = usuário logado."""
        client, user = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        for case in Case.objects.all():
            assert case.created_by == user

    def test_three_pdfs_all_have_pdf_file(self, client) -> None:
        """Todos os casos têm pdf_file salvo."""
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        for case in Case.objects.all():
            assert case.pdf_file is not None
            assert os.path.exists(case.pdf_file.path)

    def test_mixed_valid_and_invalid(self, client) -> None:
        """Mistura de PDFs válidos e .txt inválido: válidos processados, inválido reportado."""
        client, _ = _nir_client(client)
        valid1 = _simple_pdf()
        invalid = _simple_txt()
        valid2 = _simple_pdf()
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [valid1, invalid, valid2]},
            follow=True,
        )
        # Verificar mensagens
        content = response.content.decode()
        assert "2 encaminhamentos recebidos" in content
        assert "não é um arquivo PDF" in content
        assert Case.objects.count() == 2
        for case in Case.objects.all():
            assert case.status == CaseStatus.R1_ACK_PROCESSING

    def test_all_invalid_no_cases(self, client) -> None:
        """Todos arquivos inválidos → nenhum Case criado."""
        client, _ = _nir_client(client)
        files = [_simple_txt() for _ in range(3)]
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        # Cada arquivo deve gerar um erro
        for i in range(3):
            assert "não é um arquivo PDF" in content

    def test_empty_batch_rejected(self, client) -> None:
        """Nenhum arquivo → mensagem de erro e nenhum Case."""
        client, _ = _nir_client(client)
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": []},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "Nenhum arquivo" in content

    def test_redirects_to_my_cases(self, client) -> None:
        """Após upload bem-sucedido, redireciona para my_cases."""
        client, _ = _nir_client(client)
        pdf_file = _simple_pdf()
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [pdf_file]},
        )
        assert response.status_code == 302
        assert response.url == reverse("intake:my_cases")

    def test_enqueue_pdf_extraction_called_per_case(self, client, monkeypatch) -> None:
        """Para cada PDF, enqueue_pdf_extraction deve ser chamado."""
        from apps.intake import tasks

        calls: list[str] = []

        def _fake_enqueue(case_id: object) -> None:
            calls.append(str(case_id))

        monkeypatch.setattr(tasks, "enqueue_pdf_extraction", _fake_enqueue)

        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )

        assert len(calls) == 3
        # Verificar que os case_ids chamados correspondem aos criados
        case_ids = {str(c.case_id) for c in Case.objects.all()}
        assert set(calls) == case_ids

    def test_enqueue_not_called_for_invalid_files(self, client, monkeypatch) -> None:
        """Arquivo inválido não chama enqueue_pdf_extraction."""
        from apps.intake import tasks

        calls: list[str] = []

        def _fake_enqueue(case_id: object) -> None:
            calls.append(str(case_id))

        monkeypatch.setattr(tasks, "enqueue_pdf_extraction", _fake_enqueue)

        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_txt()]},
            follow=True,
        )

        assert len(calls) == 0
        assert Case.objects.count() == 0


@pytest.mark.django_db
class TestMultiUploadBatchLimits:
    """Testes de limites do lote."""

    def test_exceeds_max_files(self, client) -> None:
        """Acima de INTAKE_MAX_FILES_PER_BATCH → batch rejeitado."""
        client, _ = _nir_client(client)
        max_files = settings.INTAKE_MAX_FILES_PER_BATCH
        files = [_simple_pdf() for _ in range(max_files + 1)]
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "Máximo" in content or "excede" in content

    def test_exceeds_max_file_size(self, client, monkeypatch) -> None:
        """Arquivo acima de INTAKE_MAX_UPLOAD_BYTES_PER_FILE → rejeitado."""
        import django.conf

        client, _ = _nir_client(client)

        # Reduzir limite temporariamente para um valor pequeno
        monkeypatch.setattr(django.conf.settings, "INTAKE_MAX_UPLOAD_BYTES_PER_FILE", 100)

        pdf_bytes = _create_test_pdf_bytes()
        # Forçar size grande via SimpleUploadedFile com conteúdo grande
        big_file = SimpleUploadedFile("big.pdf", pdf_bytes + b"x" * 200, content_type="application/pdf")

        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [big_file]},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "excede o limite" in content


@pytest.mark.django_db
class TestMultiUploadEvents:
    """Eventos de auditoria para upload múltiplo."""

    def test_each_case_gets_case_created_event(self, client) -> None:
        """Cada Case deve ter seu próprio CASE_CREATED."""
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(2)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files},
            follow=True,
        )
        for case in Case.objects.all():
            events = CaseEvent.objects.filter(case=case)
            event_types = set(e.event_type for e in events)
            assert "CASE_CREATED" in event_types
