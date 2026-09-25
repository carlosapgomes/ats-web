"""Slice 004 — EDA + GTT no intake (R1).

Cobre:

- ``eda_gastrostomy`` entra na lista explícita de exposição do intake sem flag
  nova, na ordem canônica do catálogo (imediatamente após EDA);
- o upload do pacote cria exatamente um ``Case`` com uma ``CaseProcedure``
  declarada e o evento enxuto da declaração;
- alias/label/texto livre continuam rejeitados pelo backend;
- a família Retossigmoidoscopia (Slice 005) entra depois deste slice, na sequência do catálogo.
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
from apps.intake.services import INTAKE_EXPOSED_SELECTION_KEYS, ensure_exam_type_allowed, intake_selection_options

User = get_user_model()

HOME_URL = "intake:home"

PACKAGE_KEY = ProcedureType.EDA_GASTROSTOMY


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

    user = User.objects.create_user(username="nir-gtt@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _option_tags(html: str) -> list[str]:
    match = re.search(r'<select[^>]*name="exam_type"[^>]*>.*?</select>', html, re.DOTALL)
    assert match is not None, "select canônico de exam_type ausente"
    return re.findall(r"<option[^>]*>", match.group(0))


def _option_tag(html: str, value: str) -> str:
    for tag in _option_tags(html):
        if f'value="{value}"' in tag:
            return tag
    raise AssertionError(f"Opção {value!r} ausente no HTML: {_option_tags(html)}")


def _post_upload(client, exam_type: str) -> None:
    client, _ = _nir_client(client)
    client.post(
        reverse(HOME_URL),
        {"pdf_files": [_simple_pdf()], "exam_type": exam_type},
        follow=True,
    )


# ── R1: exposição do pacote ───────────────────────────────────────────────


class TestGastrostomyExposure:
    def test_package_is_exposed_with_the_catalog_label(self) -> None:
        options = {option.key: option for option in intake_selection_options()}

        assert PACKAGE_KEY in options
        assert options[PACKAGE_KEY].label == ProcedureType(PACKAGE_KEY).label == "EDA + Gastrostomia (GTT)"

    def test_package_is_exposed_in_catalog_order_right_after_eda(self) -> None:
        keys = [option.key for option in intake_selection_options()]

        assert keys.index(PACKAGE_KEY) == keys.index(ProcedureType.EDA) + 1

    def test_exposed_order_follows_the_catalog(self) -> None:
        from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES

        exposed = [key for key in INTAKE_EXPOSED_SELECTION_KEYS if key in SUPPORTED_PROCEDURE_TYPES]
        expected = [code for code in SUPPORTED_PROCEDURE_TYPES if code in set(exposed)]

        assert exposed == expected

    @override_settings(
        COLONOSCOPY_INTAKE_ENABLED=False,
        ECHOENDOSCOPY_INTAKE_ENABLED=False,
        CPRE_INTAKE_ENABLED=False,
    )
    def test_package_needs_no_new_flag(self) -> None:
        """R1/D14: nenhuma flag nova medeia o pacote no cutover."""
        enabled = {option.key for option in intake_selection_options() if option.enabled}

        assert PACKAGE_KEY in enabled
        assert ensure_exam_type_allowed(PACKAGE_KEY) == PACKAGE_KEY

    def test_package_is_never_gated_by_the_colonoscopy_flag(self) -> None:
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            enabled = {option.key for option in intake_selection_options() if option.enabled}

        assert PACKAGE_KEY in enabled

    def test_later_family_is_exposed_after_the_slice_005_delivery(self) -> None:
        """O Slice 005 publica a família Retossigmoidoscopia depois deste slice."""
        keys = [option.key for option in intake_selection_options()]

        for key in (
            "rectosigmoidoscopy",
            "rectosigmoidoscopy_dilation",
            "rectosigmoidoscopy_argon",
        ):
            assert key in keys, key
        assert keys.index("eda_gastrostomy") < keys.index("rectosigmoidoscopy")

    @pytest.mark.django_db
    def test_home_renders_the_option_enabled(self, client) -> None:
        client, _ = _nir_client(client)
        html = client.get(reverse(HOME_URL)).content.decode()

        assert "disabled" not in _option_tag(html, PACKAGE_KEY)


# ── R1: uma row por caso ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestGastrostomyIntakeCreatesOneRow:
    def test_upload_creates_one_case_with_one_declared_row(self, client) -> None:
        _post_upload(client, PACKAGE_KEY)

        assert Case.objects.count() == 1
        case = Case.objects.get()
        rows = CaseProcedure.objects.filter(case=case)
        assert [(row.procedure_type, row.declared_by_nir) for row in rows] == [(PACKAGE_KEY, True)]

    def test_declared_event_carries_the_exact_identity(self, client) -> None:
        _post_upload(client, PACKAGE_KEY)

        case = Case.objects.get()
        assert case.events.filter(event_type="CASE_PROCEDURES_DECLARED").latest("timestamp").payload == {
            "procedures": [PACKAGE_KEY]
        }

    @pytest.mark.parametrize("value", ["GTT", "gtt", "Gastrostomia", "EDA + Gastrostomia (GTT)", "gastrostomia"])
    def test_alias_label_or_free_text_is_rejected_without_case(self, client, value: str) -> None:
        _post_upload(client, value)

        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0
