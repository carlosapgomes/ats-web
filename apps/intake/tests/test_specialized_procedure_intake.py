"""Slice 002 (R1) e Slice 004 (R1) — procedimentos especializados no intake NIR.

Cobre:

- flag ``ECHOENDOSCOPY_INTAKE_ENABLED`` false (default): opção indisponível no
  formulário e POST rejeitado (nenhum caso criado);
- flag true: cria exatamente UMA row declarada ``echoendoscopy`` por caso;
- flag ``CPRE_INTAKE_ENABLED`` (Slice 004) é INDEPENDENTE da flag acima: false
  oculta/rejeita CPRE, true cria exatamente UMA row declarada ``cpre``;
- reenvio corrigido e correção de tipo respeitam as mesmas flags;
- casos existentes não são interrompidos/apagados pelas flags (web-only).
"""

from __future__ import annotations

import re
from io import BytesIO

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import Case, CaseProcedure, ProcedureType
from apps.cases.procedures import get_declared_procedure_types
from apps.intake.services import ensure_exam_type_allowed, validate_exam_type

User = get_user_model()


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Paciente: Joao da Silva\nRegistro: 2026-0505-001", fontsize=12)
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("test.pdf", _pdf_bytes(), content_type="application/pdf")


def _nir_client(client):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir-echo@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


# ── R1: validação de choice + flag ──────────────────────────────────────────


class TestEchoendoscopyFlagValidation:
    def test_validate_exam_type_accepts_echoendoscopy(self) -> None:
        assert validate_exam_type("echoendoscopy") == ProcedureType.ECHOENDOSCOPY

    def test_validate_exam_type_accepts_cpre(self) -> None:
        assert validate_exam_type("cpre") == ProcedureType.CPRE

    def test_ensure_allowed_rejects_echoendoscopy_when_flag_off(self) -> None:
        with override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=False), pytest.raises(ValueError):
            ensure_exam_type_allowed("echoendoscopy")

    @override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=True)
    def test_ensure_allowed_accepts_echoendoscopy_when_flag_on(self) -> None:
        assert ensure_exam_type_allowed("echoendoscopy") == ProcedureType.ECHOENDOSCOPY


# ── R1: intake web ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEchoendoscopyIntake:
    def test_flag_off_hides_option_and_rejects_post(self, client) -> None:
        nir, _ = _nir_client(client)
        with override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=False):
            get_response = nir.get(reverse("intake:home"))
            assert "ecoendoscopia" in get_response.content.decode().lower()
            assert "disabled" in get_response.content.decode().lower()

            nir.post(
                reverse("intake:home"),
                {"pdf_files": [_pdf()], "exam_type": "echoendoscopy"},
                follow=True,
            )
        assert Case.objects.count() == 0

    @override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=True)
    def test_flag_on_creates_exactly_one_declared_row(self, client) -> None:
        nir, _ = _nir_client(client)
        nir.post(
            reverse("intake:home"),
            {"pdf_files": [_pdf()], "exam_type": "echoendoscopy"},
            follow=True,
        )
        case = Case.objects.get()
        assert get_declared_procedure_types(case) == (ProcedureType.ECHOENDOSCOPY,)
        rows = CaseProcedure.objects.filter(case=case, declared_by_nir=True)
        assert rows.count() == 1
        assert rows.get().procedure_type == ProcedureType.ECHOENDOSCOPY

    def test_cpre_flag_off_hides_option_and_rejects_post(self, client) -> None:
        nir, _ = _nir_client(client)
        with override_settings(CPRE_INTAKE_ENABLED=False):
            response = nir.get(reverse("intake:home"))
            html = response.content.decode()
            assert "CPRE" in html
            cpre_input = re.search(r'<input[^>]*id="exam-type-cpre"[^>]*>', html)
            assert cpre_input is not None, "opção CPRE ausente no formulário de intake"
            assert "disabled" in cpre_input.group(0)

            nir.post(
                reverse("intake:home"),
                {"pdf_files": [_pdf()], "exam_type": "cpre"},
                follow=True,
            )
        assert Case.objects.count() == 0

    @override_settings(CPRE_INTAKE_ENABLED=True)
    def test_cpre_flag_on_shows_option_and_creates_single_declared_row(self, client) -> None:
        nir, _ = _nir_client(client)
        response = nir.get(reverse("intake:home"))
        html = response.content.decode()
        cpre_input = re.search(r'<input[^>]*id="exam-type-cpre"[^>]*>', html)
        assert cpre_input is not None, "opção CPRE ausente no formulário de intake"
        assert "disabled" not in cpre_input.group(0)

        nir.post(
            reverse("intake:home"),
            {"pdf_files": [_pdf()], "exam_type": "cpre"},
            follow=True,
        )
        case = Case.objects.get()
        assert get_declared_procedure_types(case) == (ProcedureType.CPRE,)
        rows = CaseProcedure.objects.filter(case=case, declared_by_nir=True)
        assert rows.count() == 1
        assert rows.get().procedure_type == ProcedureType.CPRE

    def test_cpre_flag_is_independent_from_echoendoscopy_flag(self) -> None:
        with override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=False, CPRE_INTAKE_ENABLED=True):
            assert ensure_exam_type_allowed("cpre") == ProcedureType.CPRE
            with pytest.raises(ValueError):
                ensure_exam_type_allowed("echoendoscopy")

        with override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=True, CPRE_INTAKE_ENABLED=False):
            assert ensure_exam_type_allowed("echoendoscopy") == ProcedureType.ECHOENDOSCOPY
            with pytest.raises(ValueError):
                ensure_exam_type_allowed("cpre")

    @override_settings(CPRE_INTAKE_ENABLED=False)
    def test_cpre_flag_off_does_not_touch_existing_specialized_case(self, client, django_user_model) -> None:
        """Flag é web-only: nenhum caso existente é removido/alterado."""
        from apps.cases.procedures import set_declared_procedures

        user = django_user_model.objects.create_user(username="nir-existing-cpre")
        case = Case.objects.create(created_by=user, agency_record_number="55557", extracted_text="Solicito CPRE.")
        set_declared_procedures(case=case, procedure_types=[ProcedureType.CPRE], actor=user)

        assert get_declared_procedure_types(Case.objects.get(case_id=case.case_id)) == (ProcedureType.CPRE,)

    def test_flag_off_does_not_touch_existing_specialized_case(self, client, django_user_model) -> None:
        """Flag é web-only: nenhum caso existente é removido/alterado."""
        user = django_user_model.objects.create_user(username="nir-existing")
        case = Case.objects.create(
            created_by=user, agency_record_number="55555", extracted_text="Solicito ecoendoscopia."
        )
        from apps.cases.procedures import set_declared_procedures

        set_declared_procedures(case=case, procedure_types=[ProcedureType.ECHOENDOSCOPY], actor=user)

        with override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=False):
            assert Case.objects.filter(case_id=case.case_id).exists()
            assert get_declared_procedure_types(Case.objects.get(case_id=case.case_id)) == (
                ProcedureType.ECHOENDOSCOPY,
            )


# ── R1: reenvio corrigido ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestCorrectedResubmissionEchoendoscopy:
    def _original_case(self, user) -> Case:
        case = Case.objects.create(
            created_by=user,
            agency_record_number="99999",
            extracted_text="Solicito EDA.",
        )
        from apps.cases.procedures import set_declared_procedures

        set_declared_procedures(case=case, procedure_types=[ProcedureType.EDA], actor=user)
        return Case.objects.get(case_id=case.case_id)

    def test_flag_off_rejects_resubmission_as_echoendoscopy(self, client, django_user_model) -> None:
        nir, _ = _nir_client(client)
        original = self._original_case(django_user_model.objects.create_user(username="owner-off"))

        with override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=False):
            before = Case.objects.count()
            client.post(
                reverse("intake:corrected_resubmission", args=[original.case_id]),
                {
                    "correction_reason": "Tipo incorreto no envio anterior.",
                    "pdf_file": _pdf(),
                    "exam_type": "echoendoscopy",
                    "confirmation": "on",
                },
                follow=True,
            )
            assert Case.objects.count() == before

    @override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=True)
    def test_flag_on_accepts_resubmission_as_echoendoscopy(self, client, django_user_model) -> None:
        nir, _ = _nir_client(client)
        original = self._original_case(django_user_model.objects.create_user(username="owner-on"))

        client.post(
            reverse("intake:corrected_resubmission", args=[original.case_id]),
            {
                "correction_reason": "Tipo incorreto no envio anterior.",
                "pdf_file": _pdf(),
                "exam_type": "echoendoscopy",
                "confirmation": "on",
            },
            follow=True,
        )
        new_case = Case.objects.exclude(case_id=original.case_id).get()
        assert get_declared_procedure_types(new_case) == (ProcedureType.ECHOENDOSCOPY,)

    def test_flag_off_rejects_resubmission_as_cpre(self, client, django_user_model) -> None:
        nir, _ = _nir_client(client)
        original = self._original_case(django_user_model.objects.create_user(username="owner-cpre-off"))

        with override_settings(CPRE_INTAKE_ENABLED=False):
            before = Case.objects.count()
            client.post(
                reverse("intake:corrected_resubmission", args=[original.case_id]),
                {
                    "correction_reason": "Tipo incorreto no envio anterior.",
                    "pdf_file": _pdf(),
                    "exam_type": "cpre",
                    "confirmation": "on",
                },
                follow=True,
            )
            assert Case.objects.count() == before

    @override_settings(CPRE_INTAKE_ENABLED=True)
    def test_flag_on_accepts_resubmission_as_cpre(self, client, django_user_model) -> None:
        nir, _ = _nir_client(client)
        original = self._original_case(django_user_model.objects.create_user(username="owner-cpre-on"))

        client.post(
            reverse("intake:corrected_resubmission", args=[original.case_id]),
            {
                "correction_reason": "Tipo incorreto no envio anterior.",
                "pdf_file": _pdf(),
                "exam_type": "cpre",
                "confirmation": "on",
            },
            follow=True,
        )
        new_case = Case.objects.exclude(case_id=original.case_id).get()
        assert get_declared_procedure_types(new_case) == (ProcedureType.CPRE,)
