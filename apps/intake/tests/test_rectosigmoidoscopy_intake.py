"""Slice 005 — família Retossigmoidoscopia no intake (R1).

Cobre:

- as três identidades entram na lista explícita de exposição do intake sem
  flag nova e sem gate de Colonoscopia;
- cada upload cria exatamente um ``Case`` com uma ``CaseProcedure`` declarada
  com o código selecionado;
- o ``<select name="exam_type">`` SSR publica as três opções habilitadas com o
  código canônico como valor (label/alias nunca é valor válido);
- nenhuma sigla operacional nova é aceita.
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

# Identidades entregues neste slice (design D10), na ordem do catálogo: depois
# de Colonoscopia e do combinado derivado.
NEW_SELECTION_KEYS = (
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
)

# Ordem canônica da família Colonoscopia no catálogo (Slice 005 acrescenta as
# três Retossigmoidoscopias).
COLONOSCOPY_FAMILY_CODES = (ProcedureType.COLONOSCOPY, *NEW_SELECTION_KEYS)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_pdf_bytes(text: str = "Paciente: Ana Souza\nRegistro: 2026-0905-001") -> bytes:
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

    user = User.objects.create_user(username="nir-recto@test.com", password="testpass123")
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
    return re.findall(r"<option[^>]*>[^<]*</option>", match.group(0))


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


# ── R1: exposição das três identidades ────────────────────────────────────


class TestRectosigmoidoscopyExposure:
    def test_identities_are_exposed_with_catalog_labels(self) -> None:
        options = {option.key: option for option in intake_selection_options()}
        for key in NEW_SELECTION_KEYS:
            assert key in options, key
            assert options[key].label == ProcedureType(key).label

    def test_identities_are_exposed_in_catalog_order_within_the_family(self) -> None:
        keys = [option.key for option in intake_selection_options()]
        colon_family = [key for key in keys if key in set(COLONOSCOPY_FAMILY_CODES)]

        assert colon_family == list(COLONOSCOPY_FAMILY_CODES)

    @override_settings(
        COLONOSCOPY_INTAKE_ENABLED=False,
        ECHOENDOSCOPY_INTAKE_ENABLED=False,
        CPRE_INTAKE_ENABLED=False,
    )
    def test_identities_need_no_new_flag_and_no_colonoscopy_gate(self) -> None:
        """R1: nenhuma flag nova medeia as Retossigmoidoscopias (D10/D14)."""
        enabled = {option.key for option in intake_selection_options() if option.enabled}
        for key in NEW_SELECTION_KEYS:
            assert key in enabled, key
            assert ensure_exam_type_allowed(key) == key

    def test_options_never_carry_invented_abbreviations_or_aliases(self) -> None:
        """A identidade atômica usa somente a própria label canônica (D1)."""
        options = {option.key: option for option in intake_selection_options()}
        for key in NEW_SELECTION_KEYS:
            assert options[key].aliases == ()

    def test_free_text_abbreviation_is_rejected(self) -> None:
        for value in ("rsc", "retossigmoido", "Retossigmoidoscopia + Dilatacao"):
            with pytest.raises(ValueError):
                ensure_exam_type_allowed(value)

    @pytest.mark.django_db
    def test_home_renders_the_three_options_enabled(self, client) -> None:
        client, _ = _nir_client(client)
        html = client.get(reverse(HOME_URL)).content.decode()
        for key in NEW_SELECTION_KEYS:
            tag = _option_tag(html, key)
            assert "disabled" not in tag, key
            assert ProcedureType(key).label in tag, key


# ── R1: uma row por caso ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestRectosigmoidoscopyIntakeCreatesOneRow:
    @pytest.mark.parametrize("exam_type", NEW_SELECTION_KEYS)
    def test_upload_creates_one_case_with_one_declared_row(self, client, exam_type: str) -> None:
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

    @pytest.mark.parametrize("exam_type", NEW_SELECTION_KEYS)
    def test_upload_never_creates_the_base_row_alongside_the_identity(self, client, exam_type: str) -> None:
        _post_upload(client, exam_type)
        case = Case.objects.get()
        assert CaseProcedure.objects.filter(case=case).count() == 1

    @pytest.mark.parametrize("exam_type", NEW_SELECTION_KEYS)
    def test_label_alias_is_rejected(self, client, exam_type: str) -> None:
        _post_upload(client, ProcedureType(exam_type).label)
        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0
