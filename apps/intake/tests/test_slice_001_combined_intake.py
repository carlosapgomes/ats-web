"""Slice 001 — intake combinado EDA + Colonoscopia (R4/R5/R6).

Cobre:
- R4: opção textual "EDA + Colonoscopia" sem default; flag falsa bloqueia
      Colonoscopia e combinado no backend/UI; EDA permanece; lote usa uma
      seleção para todos os PDFs.
- R5: cada PDF combinado cria UM Case e EXATAMENTE duas rows declaradas +
      evento CASE_PROCEDURES_DECLARED; nunca 2N casos; ausência/valor inválido
      não cria nada.
- R6: Meus Casos e detalhe exibem labels simples/combinado pela projeção,
      sem query por row no template.
- R7: atomicidade — falha não deixa caso/rows parciais.
"""

from __future__ import annotations

import re
from io import BytesIO
from unittest import mock

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseProcedure

pytestmark = pytest.mark.django_db

User = get_user_model()

_COMBINED_VALUE = "eda_colonoscopy"


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

    user = User.objects.create_user(username="nir-combined@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


# ── R5: 1 PDF → 1 Case → 2 rows ─────────────────────────────────────────


@pytest.mark.django_db
class TestCombinedIntake:
    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_one_pdf_combined_creates_one_case_and_two_rows(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": _COMBINED_VALUE},
            follow=True,
        )
        assert Case.objects.count() == 1
        case = Case.objects.get()
        assert case.exam_type == _COMBINED_VALUE
        rows = list(CaseProcedure.objects.filter(case=case).order_by("procedure_type"))
        assert len(rows) == 2
        assert {r.procedure_type for r in rows} == {"eda", "colonoscopy"}
        assert all(r.declared_by_nir for r in rows)
        assert all(r.detection_status == "pending" for r in rows)

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_batch_of_n_pdfs_creates_n_cases_never_2n(self, client) -> None:
        client, _ = _nir_client(client)
        files = [_simple_pdf() for _ in range(4)]
        client.post(
            reverse("intake:home"),
            {"pdf_files": files, "exam_type": _COMBINED_VALUE},
            follow=True,
        )
        assert Case.objects.count() == 4
        for case in Case.objects.all():
            assert CaseProcedure.objects.filter(case=case).count() == 2

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_combined_upload_records_ordered_declared_event(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": _COMBINED_VALUE},
            follow=True,
        )
        case = Case.objects.get()
        event = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURES_DECLARED")
        assert event.payload["procedures"] == ["eda", "colonoscopy"]
        assert "text" not in event.payload

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_combined_badge_on_my_cases_and_detail(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": _COMBINED_VALUE},
            follow=True,
        )
        case = Case.objects.get()

        response = client.get(reverse("intake:my_cases"))
        content = response.content.decode()
        assert "EDA + Colonoscopia" in content
        assert "exam-type-eda_colonoscopy" in content

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        content = response.content.decode()
        assert "EDA + Colonoscopia" in content
        assert "exam-type-eda_colonoscopy" in content

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_simple_cases_keep_simple_labels(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "eda"},
            follow=True,
        )
        response = client.get(reverse("intake:my_cases"))
        content = response.content.decode()
        assert "exam-type-eda" in content
        assert "EDA + Colonoscopia" not in content

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_absent_or_invalid_selection_creates_nothing(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(reverse("intake:home"), {"pdf_files": [_simple_pdf()]}, follow=True)
        assert Case.objects.count() == 0
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "cpre"},
            follow=True,
        )
        assert Case.objects.count() == 0

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_intake_failure_creates_no_partial_case_or_rows(self, client) -> None:
        client, _ = _nir_client(client)
        with mock.patch("apps.intake.services.set_declared_procedures", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                client.post(
                    reverse("intake:home"),
                    {"pdf_files": [_simple_pdf()], "exam_type": _COMBINED_VALUE},
                    follow=True,
                )
        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0


# ── R4: flag bloqueia colon/combinado somente no intake ──────────────────


@pytest.mark.django_db
class TestCombinedFlagEnforcement:
    def test_flag_off_rejects_combined(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": _COMBINED_VALUE},
            follow=True,
        )
        assert Case.objects.count() == 0

    def test_flag_off_rejects_colonoscopy(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "colonoscopy"},
            follow=True,
        )
        assert Case.objects.count() == 0

    def test_flag_off_accepts_eda(self, client) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse("intake:home"),
            {"pdf_files": [_simple_pdf()], "exam_type": "eda"},
            follow=True,
        )
        assert Case.objects.count() == 1

    def test_flag_on_shows_combined_option_without_default(self, client) -> None:
        client, _ = _nir_client(client)
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.get(reverse("intake:home"))
        content = response.content.decode()
        assert "EDA + Colonoscopia" in content
        radios = re.findall(r'<input[^>]*name=["\']exam_type["\'][^>]*>', content)
        assert len(radios) == 3
        for tag in radios:
            assert "checked" not in tag, f"Radio pré-marcado: {tag}"

    def test_flag_off_disables_colon_and_combined(self, client) -> None:
        client, _ = _nir_client(client)
        response = client.get(reverse("intake:home"))
        content = response.content.decode()
        assert content.count('value="colonoscopy"') == 1
        assert content.count('value="eda_colonoscopy"') == 1
        assert "indispon" in content.lower()
