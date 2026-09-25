"""Slice 002 — controle pesquisável de procedimento no upload NIR (R1–R6).

Cobre:
- R1: helper de opções da jornada composto por catálogo + flags e
  ``<select name="exam_type">`` SSR sem opção real pré-selecionada;
- R2/R3: markup do combobox e aliases pesquisáveis derivados do catálogo;
- R4: fallback SSR, preservação da seleção no re-render inválido e gating do
  submit no ``upload.js``;
- R5: backend aceita somente chave canônica — alias, label, texto livre e
  combinação indisponível são rejeitados sem criar caso;
- R6: nenhuma identidade nova exposta e nenhuma dependência frontend.

A cobertura canônica do combobox (contrato HTML/POST, re-render e validação
backend) é deste arquivo; o teste Node ``procedure_combobox.test.js`` é
complementar (teclado/normalização em isolamento).
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import Case, CaseProcedure, ProcedureType
from apps.intake.services import ensure_exam_type_allowed, intake_selection_options

User = get_user_model()

HOME_URL = "intake:home"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
APP_CSS = PROJECT_ROOT / "static" / "css" / "app.css"

# Ordem explícita de exposição no intake (design D10): as seleções publicadas.
# Slice 002 entregou cinco; o Slice 003 acrescentou os pacotes EDA + Cápsula e
# EDA + Dilatação e o Slice 004 acrescentou EDA + GTT, todos na ordem do
# catálogo (após EDA). A família Retossigmoidoscopia continua fora (Slice 005).
EXPOSED_SELECTION_KEYS = (
    "eda",
    "eda_gastrostomy",
    "eda_capsule",
    "eda_dilation",
    "colonoscopy",
    "eda_colonoscopy",
    "echoendoscopy",
    "cpre",
)

# Pacotes publicados sem gate de flag (Slices 003/004).
PACKAGE_SELECTION_KEYS = ("eda_gastrostomy", "eda_capsule", "eda_dilation")

# Vocabulário CSS exigido pelo componente (AGENTS.md §8: a fatia de UI inclui
# o vocabulário em app.css e o pina em teste de guarda).
COMBOBOX_CSS_SELECTORS = (
    ".procedure-combobox",
    ".procedure-combobox--enhanced",
    ".procedure-combobox__select",
    ".procedure-combobox__input",
    ".procedure-combobox__input:focus-visible",
    ".procedure-combobox__list",
    ".procedure-combobox__option",
    ".procedure-combobox__option--active",
    ".procedure-combobox__option--disabled",
    ".procedure-combobox__empty",
    ".procedure-combobox__error",
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


def _non_pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("relatorio.txt", b"nao e um pdf", content_type="text/plain")


def _nir_client(client):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir-combobox@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _exam_type_select_html(html: str) -> str:
    """Trecho ``<select name="exam_type">...</select>`` do controle canônico."""
    match = re.search(r'<select[^>]*name="exam_type"[^>]*>.*?</select>', html, re.DOTALL)
    assert match is not None, "select canônico de exam_type ausente"
    return match.group(0)


def _option_tags(html: str) -> list[str]:
    """Tags ``<option>`` do controle canônico (atributos em qualquer ordem)."""
    return re.findall(r"<option[^>]*>", _exam_type_select_html(html))


def _option_tag(html: str, value: str) -> str:
    """Tag ``<option>`` da seleção canônica ``value`` (falha se ausente)."""
    for tag in _option_tags(html):
        if f'value="{value}"' in tag:
            return tag
    raise AssertionError(f"Opção {value!r} ausente no HTML: {_option_tags(html)}")


def _select_tag(html: str) -> str:
    match = re.search(r"<select[^>]*>", _exam_type_select_html(html))
    assert match is not None, "select canônico de exam_type ausente"
    return match.group(0)


# ── R1/R6: helper de opções da jornada ───────────────────────────────────


class TestIntakeSelectionOptions:
    """O helper compõe catálogo + flags sobre a lista explícita de exposição."""

    def test_exposes_only_published_selections_in_explicit_order(self) -> None:
        keys = tuple(option.key for option in intake_selection_options())
        assert keys == EXPOSED_SELECTION_KEYS
        # Slices futuros ainda não aparecem no intake.
        assert "rectosigmoidoscopy" not in keys

    def test_labels_come_from_the_catalog(self) -> None:
        labels = {option.key: option.label for option in intake_selection_options()}
        assert labels["eda"] == ProcedureType.EDA.label
        assert labels["echoendoscopy"] == ProcedureType.ECHOENDOSCOPY.label
        assert labels["eda_colonoscopy"] == "EDA + Colonoscopia"

    def test_composite_selection_carries_component_search_aliases(self) -> None:
        aliases = {option.key: option.aliases for option in intake_selection_options()}
        assert aliases["eda_colonoscopy"] == (ProcedureType.EDA.label, ProcedureType.COLONOSCOPY.label)
        assert aliases["eda"] == ()

    @override_settings(
        COLONOSCOPY_INTAKE_ENABLED=False,
        ECHOENDOSCOPY_INTAKE_ENABLED=False,
        CPRE_INTAKE_ENABLED=False,
    )
    def test_all_flags_off_expose_only_eda_and_its_packages_as_enabled(self) -> None:
        enabled = {option.key for option in intake_selection_options() if option.enabled}
        assert enabled == {"eda", *PACKAGE_SELECTION_KEYS}

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True)
    def test_colonoscopy_flag_enables_the_pair_and_the_combined_selection(self) -> None:
        enabled = {option.key for option in intake_selection_options() if option.enabled}
        assert enabled == {"eda", *PACKAGE_SELECTION_KEYS, "colonoscopy", "eda_colonoscopy"}

    @override_settings(ECHOENDOSCOPY_INTAKE_ENABLED=True, CPRE_INTAKE_ENABLED=True)
    def test_specialized_flags_are_independent_from_colonoscopy(self) -> None:
        enabled = {option.key for option in intake_selection_options() if option.enabled}
        assert enabled == {"eda", *PACKAGE_SELECTION_KEYS, "echoendoscopy", "cpre"}

    @override_settings(
        COLONOSCOPY_INTAKE_ENABLED=True,
        ECHOENDOSCOPY_INTAKE_ENABLED=True,
        CPRE_INTAKE_ENABLED=True,
    )
    def test_enabled_flag_matches_the_backend_gate(self) -> None:
        for option in intake_selection_options():
            assert option.enabled is True, option.key
            assert ensure_exam_type_allowed(option.key) == option.key

    @override_settings(
        COLONOSCOPY_INTAKE_ENABLED=False,
        ECHOENDOSCOPY_INTAKE_ENABLED=False,
        CPRE_INTAKE_ENABLED=False,
    )
    def test_disabled_flag_matches_backend_rejection(self) -> None:
        for option in intake_selection_options():
            if option.enabled:
                continue
            with pytest.raises(ValueError):
                ensure_exam_type_allowed(option.key)


# ── R1: markup SSR do controle ───────────────────────────────────────────


@pytest.mark.django_db
class TestUploadControlMarkup:
    def _home_html(self, client) -> str:
        client, _ = _nir_client(client)
        response = client.get(reverse(HOME_URL))
        assert response.status_code == 200
        return str(response.content.decode())

    def test_select_is_the_only_canonical_control(self, client) -> None:
        html = self._home_html(client)
        select = _select_tag(html)
        assert 'name="exam_type"' in select
        assert "data-procedure-combobox" in select
        assert not re.search(r"<input[^>]*name=[\"']exam_type[\"']", html), "radios de exam_type ainda presentes"

    def test_no_real_option_is_preselected(self, client) -> None:
        html = self._home_html(client)
        tags = _option_tags(html)
        placeholders = [tag for tag in tags if 'value=""' in tag]
        assert placeholders, "placeholder de seleção ausente"
        assert "selected" in placeholders[0]

        real = [tag for tag in tags if 'value=""' not in tag]
        values = {re.search(r'value="([^"]*)"', tag).group(1) for tag in real}  # type: ignore[union-attr]
        assert values == set(EXPOSED_SELECTION_KEYS)
        for tag in real:
            assert "selected" not in tag, f"Opção real pré-selecionada: {tag}"

    def test_options_follow_current_flags(self, client) -> None:
        html = self._home_html(client)
        assert "disabled" not in _option_tag(html, "eda")
        for key in ("colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre"):
            assert "disabled" in _option_tag(html, key), key

    @override_settings(COLONOSCOPY_INTAKE_ENABLED=True, ECHOENDOSCOPY_INTAKE_ENABLED=True)
    def test_enabled_flags_remove_the_disabled_marker(self, client) -> None:
        html = self._home_html(client)
        for key in ("colonoscopy", "eda_colonoscopy", "echoendoscopy"):
            assert "disabled" not in _option_tag(html, key), key
        assert "disabled" in _option_tag(html, "cpre")

    def test_unavailable_options_are_explained_in_text(self, client) -> None:
        html = self._home_html(client)
        # Mensagem textual (não apenas cor/atributo) para o tipo indisponível.
        assert "indisponível para novos envios" in html

    def test_composite_option_carries_search_aliases(self, client) -> None:
        html = self._home_html(client)
        tag = _option_tag(html, "eda_colonoscopy")
        match = re.search(r'data-search-aliases="([^"]*)"', tag)
        assert match is not None, "data-search-aliases ausente na seleção combinada"
        assert ProcedureType.EDA.label in match.group(1)
        assert ProcedureType.COLONOSCOPY.label in match.group(1)

    def test_select_is_named_and_associated_with_label_guidance_and_script(self, client) -> None:
        html = self._home_html(client)
        select = _select_tag(html)
        assert 'aria-labelledby="exam-type-select-label"' in select
        assert 'aria-describedby="exam-type-guidance"' in select
        assert 'id="exam-type-select-label"' in html
        assert "js/procedure_combobox.js" in html, "combobox progressivo não carregado"


# ── R4: fallback SSR, re-render e gating do submit ────────────────────────


@pytest.mark.django_db
class TestFallbackAndRerender:
    def test_without_javascript_the_select_posts_the_canonical_value(self, client) -> None:
        client, _ = _nir_client(client)
        response = client.post(
            reverse(HOME_URL),
            {"pdf_files": [_simple_pdf()], "exam_type": "eda"},
            follow=True,
        )
        assert response.status_code == 200
        assert Case.objects.count() == 1
        assert CaseProcedure.objects.filter(
            case=Case.objects.get(), procedure_type=ProcedureType.EDA, declared_by_nir=True
        ).exists()

    def test_invalid_rerender_preserves_the_valid_selection(self, client) -> None:
        client, _ = _nir_client(client)
        response = client.post(
            reverse(HOME_URL),
            {"pdf_files": [_non_pdf()], "exam_type": "eda"},
        )
        assert response.status_code == 200
        assert Case.objects.count() == 0
        html = response.content.decode()
        assert "selected" in _option_tag(html, "eda"), "seleção válida perdida no re-render"
        assert "selected" not in _option_tag(html, "colonoscopy")

    def test_missing_selection_is_associated_with_the_control(self, client) -> None:
        client, _ = _nir_client(client)
        response = client.post(reverse(HOME_URL), {"pdf_files": [_simple_pdf()]})
        assert response.status_code == 200
        assert Case.objects.count() == 0
        html = response.content.decode()

        select = _select_tag(html)
        assert 'aria-invalid="true"' in select
        assert 'aria-describedby="exam-type-guidance exam-type-error"' in select
        assert "data-procedure-combobox" in select

        error = re.search(r"<[^>]*id=\"exam-type-error\"[^>]*>", html)
        assert error is not None, "erro textual do controle ausente"
        assert 'role="alert"' in error.group(0)
        assert "Selecione o tipo de exame" in html

    def test_submit_button_is_gated_by_the_select_in_upload_js(self) -> None:
        script = (PROJECT_ROOT / "static" / "js" / "upload.js").read_text()
        assert 'select[name="exam_type"]' in script
        assert 'input[name="exam_type"]' not in script


# ── R5: backend aceita somente a chave canônica ───────────────────────────


@pytest.mark.django_db
class TestBackendAcceptsOnlyCanonicalSelection:
    def _post(self, client, exam_type: str) -> None:
        client, _ = _nir_client(client)
        client.post(
            reverse(HOME_URL),
            {"pdf_files": [_simple_pdf()], "exam_type": exam_type},
            follow=True,
        )

    @pytest.mark.parametrize(
        "value",
        ["GTT", "gtt", "cápsula", "Cápsula", "EDA", "EDA + Cápsula", "EDA + Colonoscopia", "coloscopia"],
    )
    def test_alias_label_or_free_text_is_rejected_without_case(self, client, value: str) -> None:
        self._post(client, value)
        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0

    def test_unknown_selection_key_is_rejected_without_case(self, client) -> None:
        self._post(client, "eda_unknown")
        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0

    def test_unavailable_combination_is_rejected_without_case(self, client) -> None:
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=False):
            self._post(client, "eda_colonoscopy")
        assert Case.objects.count() == 0
        assert CaseProcedure.objects.count() == 0

    def test_canonical_selection_key_is_still_accepted(self, client) -> None:
        self._post(client, "eda")
        assert Case.objects.count() == 1
        assert CaseProcedure.objects.filter(procedure_type=ProcedureType.EDA, declared_by_nir=True).count() == 1


# ── R3/R6: vocabulário CSS e ausência de dependência frontend ─────────────


class TestComboboxAssets:
    def test_css_vocabulary_is_defined(self) -> None:
        css = APP_CSS.read_text()
        for selector in COMBOBOX_CSS_SELECTORS:
            assert selector in css, f"Seletor {selector} ausente em app.css"

    def test_visible_focus_is_not_color_only(self) -> None:
        css = APP_CSS.read_text()
        start = css.index(".procedure-combobox__input:focus-visible")
        block = css[start : css.index("}", start)]
        assert "outline" in block, "foco visível depende apenas de cor"

    def test_no_frontend_dependency_was_added(self) -> None:
        assert not (Path(settings.BASE_DIR) / "package.json").exists()
        assert not (Path(settings.BASE_DIR) / "node_modules").exists()

    def test_combobox_script_is_vanilla(self) -> None:
        script = (PROJECT_ROOT / "static" / "js" / "procedure_combobox.js").read_text()
        assert not re.search(r"^\s*import\s", script, re.MULTILINE)
        assert "require(" not in script
        assert "normalize('NFD')" in script, "normalização de busca ausente"
