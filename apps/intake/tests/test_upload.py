"""Testes de upload de PDF e criação de caso — Slice 3."""

from __future__ import annotations

import os
from io import BytesIO

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
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
    """POST /cases/ — criação de caso via upload."""

    def test_upload_creates_case(self, client) -> None:
        """POST com PDF e registro cria Case no banco."""
        client, _ = _nir_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        response = client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1
        case = Case.objects.first()
        assert case is not None
        assert case.agency_record_number == "2026-0505-001"

    def test_upload_sets_created_by(self, client) -> None:
        """case.created_by deve ser o usuário logado."""
        client, user = _nir_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.created_by == user

    def test_upload_saves_pdf_file(self, client) -> None:
        """case.pdf_file deve existir no MEDIA_ROOT."""
        client, _ = _nir_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.pdf_file is not None
        assert os.path.exists(case.pdf_file.path)

    def test_upload_transitions_to_llm_struct(self, client) -> None:
        """Após upload e extração, status deve ser LLM_STRUCT."""
        client, _ = _nir_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.status == CaseStatus.LLM_STRUCT

    def test_upload_extracts_text(self, client) -> None:
        """case.extracted_text deve conter o texto do PDF."""
        client, _ = _nir_client(client)
        pdf_text = "Paciente: João da Silva\nRegistro: 2026-0505-001"
        pdf_bytes = _create_test_pdf_bytes(text=pdf_text)
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert "João da Silva" in case.extracted_text
        assert case.agency_record_extracted_at is not None

    def test_upload_sets_agency_record_number(self, client) -> None:
        """agency_record_number deve vir do formulário, não do PDF."""
        client, _ = _nir_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "MY-CUSTOM-123"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        assert case.agency_record_number == "MY-CUSTOM-123"

    def test_upload_rejects_non_pdf(self, client) -> None:
        """POST com arquivo .txt deve falhar validação."""
        client, _ = _nir_client(client)
        txt_file = SimpleUploadedFile("test.txt", b"not a pdf", content_type="text/plain")
        response = client.post(
            reverse("intake:home"),
            {"pdf_file": txt_file, "agency_record_number": "2026-0505-001"},
        )
        assert response.status_code == 200  # form re-rendered with errors
        assert Case.objects.count() == 0

    def test_upload_requires_nir_role(self, client) -> None:
        """Usuário doctor não pode fazer upload."""
        client, _ = _doctor_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        response = client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
        )
        # Redirected away because role_required blocks
        assert response.status_code == 302
        assert Case.objects.count() == 0

    def test_upload_requires_login(self, client) -> None:
        """Sem login, POST deve redirecionar para /login/."""
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        response = client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
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
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        events = CaseEvent.objects.filter(case=case)
        event_types = set(e.event_type for e in events)
        assert "CASE_CREATED" in event_types

    def test_upload_generates_processing_events(self, client) -> None:
        """Deve gerar CASE_START_PROCESSING, CASE_START_EXTRACTION, CASE_EXTRACTION_OK."""
        client, _ = _nir_client(client)
        pdf_bytes = _create_test_pdf_bytes()
        pdf_file = SimpleUploadedFile("test.pdf", pdf_bytes, content_type="application/pdf")
        client.post(
            reverse("intake:home"),
            {"pdf_file": pdf_file, "agency_record_number": "2026-0505-001"},
            follow=True,
        )
        case = Case.objects.first()
        assert case is not None
        events = CaseEvent.objects.filter(case=case)
        event_types = set(e.event_type for e in events)
        assert "CASE_START_PROCESSING" in event_types
        assert "CASE_START_EXTRACTION" in event_types
        assert "CASE_EXTRACTION_OK" in event_types
