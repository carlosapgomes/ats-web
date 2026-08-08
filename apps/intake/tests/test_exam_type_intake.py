"""Slice 002 — tipo explícito no intake NIR (R2/R3) e badges (R4).

Cobre:
- R2: backend exige tipo válido; lote homogêneo; sem opção pré-marcada.
- R3: COLONOSCOPY_INTAKE_ENABLED default false bloqueia só novos uploads;
      casos preexistentes continuam legíveis/processáveis.
- R4: badges EDA/Colonoscopia em casos recentes, Meus Casos, detalhe NIR
      e identificação da decisão médica; CASE_CREATED com exam_type.
"""

from __future__ import annotations

from io import BytesIO

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ExamType

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_pdf_bytes(text: str = "Paciente: João da Silva\nRegistro: 2026-0505-001") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _simple_pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("test.pdf", _create_test_pdf_bytes(), content_type="application/pdf")


def _nir_client(client):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir-exam@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc-exam@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


# ── R2: upload exige tipo válido ─────────────────────────────────────────


@pytest.mark.django_db
class TestUploadRequiresExamType:
    def test_post_without_exam_type_creates_no_case(self, client) -> None:
        """Form/POST sem tipo: nenhum caso criado e interface informa obrigatoriedade."""
        client, _ = _nir_client(client)
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()]},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "tipo" in content.lower()
        assert "exame" in content.lower()

    def test_post_with_invalid_exam_type_creates_no_case(self, client) -> None:
        """POST manipulado com tipo não suportado: nenhum caso criado."""
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "cpre"},
            follow=True,
        )
        assert Case.objects.count() == 0

    def test_post_with_eda_creates_eda_case(self, client) -> None:
        client, _ = _nir_client(client)
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "eda"},
            follow=True,
        )
        assert response.status_code == 200
        case = Case.objects.get()
        assert case.exam_type == ExamType.EDA


# ── R2: lote homogêneo ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestBatchHomogeneity:
    def test_eda_batch_creates_all_eda(self, client) -> None:
        """Um tipo se aplica a todos os PDFs do lote."""
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files, "exam_type": "eda"},
            follow=True,
        )
        assert Case.objects.count() == 3
        assert set(Case.objects.values_list("exam_type", flat=True)) == {ExamType.EDA}

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_colonoscopy_batch_creates_all_colonoscopy(self, client) -> None:
        """Com flag ativa, lote colonoscopia cria todos colonoscopia."""
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(3)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files, "exam_type": "colonoscopy"},
            follow=True,
        )
        assert Case.objects.count() == 3
        assert set(Case.objects.values_list("exam_type", flat=True)) == {ExamType.COLONOSCOPY}


# ── R3: flag global bloqueia somente intake ──────────────────────────────


@pytest.mark.django_db
class TestIntakeFlag:
    def test_flag_off_rejects_colonoscopy_post(self, client) -> None:
        """Default false: POST manual de colonoscopy é rejeitado sem criar caso."""
        client, _ = _nir_client(client)
        response = client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "colonoscopy"},
            follow=True,
        )
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "colonoscopia" in content.lower()

    def test_flag_off_eda_upload_still_works(self, client) -> None:
        """Flag desligada não afeta EDA."""
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "eda"},
            follow=True,
        )
        assert Case.objects.count() == 1
        # Slice 008 (R5): prova row declarada, não a coluna.
        assert CaseProcedure.objects.filter(
            case=Case.objects.get(), procedure_type=ExamType.EDA, declared_by_nir=True
        ).exists()

    def test_existing_colonoscopy_readable_and_processable_when_flag_off(self, client, user) -> None:
        """Caso colonoscopia preexistente segue legível/processável com flag off.

        A flag é consultada no intake, não no processamento downstream.
        """
        case = Case.objects.create(
            created_by=user,
            exam_type=ExamType.COLONOSCOPY,
            agency_record_number="2026-C1",
        )
        # Leitura por helper não-intake (consulta de fila) independe da flag
        fetched = Case.objects.filter(
            status=case.status,
            exam_type=ExamType.COLONOSCOPY,
        ).get(pk=case.pk)
        assert fetched.agency_record_number == "2026-C1"

        # Transição FSM downstream também não consulta a flag
        case.start_processing(user=user)
        case.save()
        assert Case.objects.get(pk=case.pk).status == CaseStatus.R1_ACK_PROCESSING


# ── R2: HTML do formulário ───────────────────────────────────────────────


@pytest.mark.django_db
class TestHtmlRadios:
    def _home_content(self, client) -> str:
        client, _ = _nir_client(client)
        response = client.get(reverse("intake:home"))
        assert response.status_code == 200
        return str(response.content.decode())

    def test_radio_fieldset_with_accessible_label(self, client) -> None:
        content = self._home_content(client)
        assert 'name="exam_type"' in content
        assert "Tipo de exame" in content
        assert "<fieldset" in content.lower() or 'role="radiogroup"' in content.lower()

    def test_no_option_checked_by_default(self, client) -> None:
        content = self._home_content(client)
        import re

        radios = re.findall(r"<input[^>]*name=[\"']exam_type[\"'][^>]*>", content)
        assert len(radios) >= 2, "Devem existir opções EDA e Colonoscopia"
        for tag in radios:
            assert "checked" not in tag, f"Radio pré-marcado: {tag}"

    def test_copy_requires_separate_batches_per_type(self, client) -> None:
        content = self._home_content(client)
        assert "mesmo tipo" in content.lower() or "lotes separados" in content.lower()

    def test_flag_off_explains_colonoscopy_unavailable(self, client) -> None:
        content = self._home_content(client)
        assert "Colonoscopia" in content
        assert "indispon" in content.lower() or "habilitad" in content.lower()


# ── R4: auditoria via upload ─────────────────────────────────────────────


@pytest.mark.django_db
class TestAuditViaUpload:
    def test_case_created_event_contains_exam_type(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "eda"},
            follow=True,
        )
        case = Case.objects.get()
        event = CaseEvent.objects.get(case=case, event_type="CASE_CREATED")
        assert event.payload.get("exam_type") == ExamType.EDA


# ── R4: badges iniciais ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestBadges:
    def _make_case(self, user, exam_type: str, record: str) -> Case:
        # Slice 008 review fix F4: fixture NIR explícita — rows declaradas
        # autorizam o badge (intake em modo estrito, sem fallback da ponte).
        case = Case.objects.create(
            created_by=user,
            exam_type=exam_type,
            agency_record_number=record,
        )
        for procedure_type in (ExamType.EDA, ExamType.COLONOSCOPY):
            if exam_type == procedure_type or exam_type == "eda_colonoscopy":
                CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
        return case

    def test_badge_on_intake_home_recent_cases(self, client) -> None:
        client, nir_user = _nir_client(client)
        self._make_case(nir_user, ExamType.EDA, "2026-E1")
        self._make_case(nir_user, ExamType.COLONOSCOPY, "2026-C1")
        response = client.get(reverse("intake:home"))
        content = response.content.decode()
        assert "2026-E1" in content and "2026-C1" in content
        assert "exam-type-badge" in content
        assert "exam-type-eda" in content
        assert "exam-type-colonoscopy" in content

    def test_badge_on_my_cases(self, client, user) -> None:
        client, _ = _nir_client(client)
        self._make_case(user, ExamType.COLONOSCOPY, "2026-C2")
        response = client.get(reverse("intake:my_cases"))
        content = response.content.decode()
        assert "2026-C2" in content
        assert "exam-type-badge" in content
        assert "exam-type-colonoscopy" in content

    def test_badge_on_nir_case_detail(self, client, user) -> None:
        client, _ = _nir_client(client)
        case = self._make_case(user, ExamType.EDA, "2026-E2")
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "exam-type-badge" in content
        assert "exam-type-eda" in content

    def test_badge_on_doctor_decision(self, client, user, advance_to) -> None:
        """Badge mínimo no topo/identificação da decisão médica (R4).

        Slice 009-A: o badge médico agora é projetado da dimensão detectada
        (strict), então a fixture declara a row detectada explicitamente.
        """
        client, _ = _doctor_client(client)
        case = Case.objects.create(
            created_by=user,
            exam_type=ExamType.COLONOSCOPY,
            structured_data={"patient": {"name": "Paciente Badge", "age": 60}},
        )
        case = advance_to(case, CaseStatus.WAIT_DOCTOR)
        assert case.status == CaseStatus.WAIT_DOCTOR
        CaseProcedure.objects.create(
            case=case,
            procedure_type=ExamType.COLONOSCOPY,
            declared_by_nir=True,
            detection_status="detected",
        )

        response = client.get(reverse("doctor:decision", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "exam-type-badge" in content
        assert "exam-type-colonoscopy" in content
