"""Slice 003 — exposição de EDA + Cápsula e EDA + Dilatação no intake (R1).

Cobre:

- as duas identidades entram na lista explícita de exposição do intake sem
  flag nova e sem gate de Colonoscopia;
- cada pacote cria exatamente um ``Case`` com uma ``CaseProcedure`` declarada;
- o ``<select name="exam_type">`` SSR publica as duas opções habilitadas;
- a família Retossigmoidoscopia (Slice 005) continua fora do intake.
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
from apps.intake.services import ensure_exam_type_allowed, intake_selection_options

User = get_user_model()

HOME_URL = "intake:home"

# Identidades entregues neste slice (design D10): acrescentadas à lista
# explícita de exposição, na ordem do catálogo (após EDA).
NEW_SELECTION_KEYS = (ProcedureType.EDA_CAPSULE, ProcedureType.EDA_DILATION)

# Ordem canônica da família EDA no catálogo (Slice 004 acrescenta GTT).
EDA_FAMILY_CODES = (
    ProcedureType.EDA,
    ProcedureType.EDA_GASTROSTOMY,
    ProcedureType.EDA_CAPSULE,
    ProcedureType.EDA_DILATION,
)


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

    user = User.objects.create_user(username="nir-package@test.com", password="testpass123")
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


# ── R1: exposição das duas identidades ────────────────────────────────────


class TestPackageExposure:
    def test_both_packages_are_exposed_with_catalog_labels(self) -> None:
        options = {option.key: option for option in intake_selection_options()}
        for key in NEW_SELECTION_KEYS:
            assert key in options, key
            assert options[key].label == ProcedureType(key).label

    def test_packages_are_exposed_in_catalog_order_next_to_eda(self) -> None:
        """Ordem do catálogo na família EDA: EDA, GTT, Cápsula, Dilatação.

        O Slice 004 insere EDA + GTT entre EDA e Cápsula; a ordem relativa dos
        pacotes deste slice é preservada (nunca listas divergentes por slice).
        """
        keys = [option.key for option in intake_selection_options()]
        eda_family = [key for key in keys if key in set(EDA_FAMILY_CODES)]

        assert eda_family == list(EDA_FAMILY_CODES)
        assert keys.index(ProcedureType.EDA_CAPSULE) < keys.index(ProcedureType.EDA_DILATION)

    @override_settings(
        COLONOSCOPY_INTAKE_ENABLED=False,
        ECHOENDOSCOPY_INTAKE_ENABLED=False,
        CPRE_INTAKE_ENABLED=False,
    )
    def test_packages_need_no_new_flag(self) -> None:
        """R1: nenhuma flag nova medeia as variações no cutover (D14)."""
        enabled = {option.key for option in intake_selection_options() if option.enabled}
        for key in NEW_SELECTION_KEYS:
            assert key in enabled, key
            assert ensure_exam_type_allowed(key) == key

    def test_packages_are_never_aliases_of_the_colonoscopy_gate(self) -> None:
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            enabled = {option.key for option in intake_selection_options() if option.enabled}
        assert set(NEW_SELECTION_KEYS).issubset(enabled)

    def test_later_slices_stay_out_of_the_intake(self) -> None:
        keys = [option.key for option in intake_selection_options()]
        for key in ("rectosigmoidoscopy", "rectosigmoidoscopy_dilation", "rectosigmoidoscopy_argon"):
            assert key not in keys, key

    @pytest.mark.django_db
    def test_home_renders_both_options_enabled(self, client) -> None:
        client, _ = _nir_client(client)
        html = client.get(reverse(HOME_URL)).content.decode()
        for key in NEW_SELECTION_KEYS:
            assert "disabled" not in _option_tag(html, key), key


# ── R1: uma row por caso ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestPackageIntakeCreatesOneRow:
    @pytest.mark.parametrize("exam_type", NEW_SELECTION_KEYS)
    def test_package_upload_creates_one_case_with_one_declared_row(self, client, exam_type: str) -> None:
        _post_upload(client, exam_type)
        assert Case.objects.count() == 1
        case = Case.objects.get()
        rows = CaseProcedure.objects.filter(case=case)
        assert [(row.procedure_type, row.declared_by_nir) for row in rows] == [(exam_type, True)]

    @pytest.mark.parametrize("exam_type", NEW_SELECTION_KEYS)
    def test_declared_event_carries_the_exact_identity(self, client, exam_type: str) -> None:
        _post_upload(client, exam_type)
        case = Case.objects.get()
        assert case.events.filter(event_type="CASE_PROCEDURES_DECLARED").latest("timestamp").payload == {
            "procedures": [exam_type]
        }

    def test_label_alias_is_still_rejected_for_the_new_packages(self, client) -> None:
        _post_upload(client, ProcedureType.EDA_CAPSULE.label)
        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0
