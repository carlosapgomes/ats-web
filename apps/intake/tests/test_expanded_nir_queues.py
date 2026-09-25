"""Slice 007 — filas/cards/resposta NIR pelo catálogo (R4–R6).

Cobre:

- R4: cards, detalhe e resposta final projetam labels e
  declarado/detectado/autorizado/razões para as dez identidades, com uma
  linha semântica por pacote e duas somente em EDA + Colonoscopia;
- R5: filas operacionais/encerradas filtram pelo CÓDIGO ATÔMICO EXATO (ou
  ``eda_colonoscopy``); EDA simples nunca entra no filtro de variação; o
  polling preserva os parâmetros da busca;
- R6: as flags preexistentes continuam limitando SOMENTE seus intakes e
  nenhuma flag nova é criada.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.cases.procedures import procedure_types_for_selection
from apps.intake.services import (
    _INTAKE_SELECTION_FLAG_GATES,
    ensure_exam_type_allowed,
    intake_selection_options,
    is_intake_selection_enabled,
)
from apps.intake.views import _procedure_comparison

pytestmark = pytest.mark.django_db

User = get_user_model()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVICES_SOURCE = PROJECT_ROOT / "apps" / "intake" / "services.py"

MY_CASES_URL = "intake:my_cases"
CLOSED_SEARCH_URL = "intake:closed_cases_search"

ALL_FLAGS_OFF = {
    "COLONOSCOPY_INTAKE_ENABLED": False,
    "ECHOENDOSCOPY_INTAKE_ENABLED": False,
    "CPRE_INTAKE_ENABLED": False,
}

ALL_FLAGS_ON = {
    "COLONOSCOPY_INTAKE_ENABLED": True,
    "ECHOENDOSCOPY_INTAKE_ENABLED": True,
    "CPRE_INTAKE_ENABLED": True,
}

PUBLISHED_SELECTION_KEYS = tuple(option.key for option in intake_selection_options())

# Identidades atômicas sem gate de flag no intake.
FLAGLESS_SELECTION_KEYS = (
    ProcedureType.EDA,
    ProcedureType.EDA_GASTROSTOMY,
    ProcedureType.EDA_CAPSULE,
    ProcedureType.EDA_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client, username: str = "nir-queues@test.com"):
    from apps.accounts.models import Role

    user = User.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _make_case(user, *, declared: str, record: str, status: str = CaseStatus.NEW) -> Case:
    """Caso com a projeção declarada exata para a chave de seleção informada."""
    case = Case.objects.create(created_by=user, agency_record_number=record, status=status)
    for procedure_type in procedure_types_for_selection(declared):
        CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
    return case


def _select_block(html: str) -> str:
    match = re.search(r"<select[^>]*name=\"exam_type\"[^>]*>.*?</select>", html, re.DOTALL)
    assert match is not None, "select canônico de exam_type ausente"
    return match.group(0)


def _option_tags(block: str) -> list[str]:
    return re.findall(r"<option[^>]*>", block)


def _option_values(block: str) -> list[str]:
    values: list[str] = []
    for tag in _option_tags(block):
        match = re.search(r'value="([^"]*)"', tag)
        if match and match.group(1):
            values.append(match.group(1))
    return values


def _option_tag(block: str, value: str) -> str:
    for tag in _option_tags(block):
        if f'value="{value}"' in tag:
            return tag
    raise AssertionError(f"Opção {value!r} ausente: {_option_tags(block)}")


# ═══════════════════════════════════════════════════════════════════════════
# R5 — filtros exatos e opções derivadas do catálogo
# ═══════════════════════════════════════════════════════════════════════════


class TestFilterOptions:
    def test_my_cases_select_lists_every_selection_key_with_all_default(self, client) -> None:
        client, _ = _nir_client(client, "nir-filter-options@test.com")
        block = _select_block(client.get(reverse(MY_CASES_URL)).content.decode())

        assert _option_values(block) == ["all", *PUBLISHED_SELECTION_KEYS]
        assert "selected" in _option_tag(block, "all")

    def test_closed_search_select_lists_every_selection_key_with_all_default(self, client) -> None:
        client, _ = _nir_client(client, "nir-filter-options-closed@test.com")
        block = _select_block(client.get(reverse(CLOSED_SEARCH_URL)).content.decode())

        assert _option_values(block) == ["all", *PUBLISHED_SELECTION_KEYS]
        assert "selected" in _option_tag(block, "all")

    def test_filter_options_ignore_intake_flags_for_existing_cases(self, client) -> None:
        """R6: flags limitam intakes, não a consulta de casos já existentes."""
        with override_settings(**ALL_FLAGS_OFF):
            client, user = _nir_client(client, "nir-filter-flags@test.com")
            cpre_case = _make_case(user, declared=ProcedureType.CPRE, record="FILTER-CPRE-001")

            block = _select_block(client.get(reverse(MY_CASES_URL)).content.decode())
            assert _option_values(block) == ["all", *PUBLISHED_SELECTION_KEYS]

            content = client.get(reverse(MY_CASES_URL) + "?exam_type=cpre").content.decode()
            assert str(cpre_case.case_id) in content

    @pytest.mark.parametrize(
        "dimension",
        [
            ProcedureType.EDA,
            ProcedureType.EDA_GASTROSTOMY,
            ProcedureType.EDA_CAPSULE,
            ProcedureType.EDA_DILATION,
            ProcedureType.RECTOSIGMOIDOSCOPY,
            ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
            ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
            EDA_COLONOSCOPY,
        ],
    )
    def test_operational_filters_match_only_the_exact_declared_identity(self, client, dimension: str) -> None:
        client, user = _nir_client(client, f"nir-filter-exact-{dimension}@test.com")
        cases = {
            key: _make_case(user, declared=key, record=f"E{index}")
            for index, key in enumerate(
                (
                    ProcedureType.EDA,
                    ProcedureType.EDA_GASTROSTOMY,
                    ProcedureType.EDA_CAPSULE,
                    ProcedureType.EDA_DILATION,
                    EDA_COLONOSCOPY,
                    ProcedureType.RECTOSIGMOIDOSCOPY,
                    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
                    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
                )
            )
        }
        target = cases[dimension]

        content = client.get(reverse(MY_CASES_URL) + f"?exam_type={dimension}").content.decode()
        assert str(target.case_id) in content
        for key, case in cases.items():
            if key == dimension:
                continue
            assert str(case.case_id) not in content, f"{key} vazou para o filtro {dimension}"

    @pytest.mark.parametrize(
        "dimension",
        [
            ProcedureType.EDA_GASTROSTOMY,
            ProcedureType.EDA_CAPSULE,
            ProcedureType.EDA_DILATION,
            ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
        ],
    )
    def test_plain_eda_never_matches_variation_filters(self, client, dimension: str) -> None:
        client, user = _nir_client(client, f"nir-filter-plain-{dimension}@test.com")
        plain = _make_case(user, declared=ProcedureType.EDA, record="PLAIN-EDA")
        variation = _make_case(user, declared=dimension, record="VARIATION")

        variation_content = client.get(reverse(MY_CASES_URL) + f"?exam_type={dimension}").content.decode()
        assert str(variation.case_id) in variation_content
        assert str(plain.case_id) not in variation_content

        eda_content = client.get(reverse(MY_CASES_URL) + "?exam_type=eda").content.decode()
        assert str(plain.case_id) in eda_content
        assert str(variation.case_id) not in eda_content

    def test_closed_search_filters_match_only_the_exact_declared_identity(self, client) -> None:
        client, user = _nir_client(client, "nir-filter-closed@test.com")
        gastrostomy = _make_case(user, declared=ProcedureType.EDA_GASTROSTOMY, record="CLOSED-GTT", status="CLEANED")
        capsule = _make_case(user, declared=ProcedureType.EDA_CAPSULE, record="CLOSED-CAP", status="CLEANED")
        combined = _make_case(user, declared=EDA_COLONOSCOPY, record="CLOSED-COMB", status="CLEANED")

        content = client.get(reverse(CLOSED_SEARCH_URL) + "?exam_type=eda_gastrostomy").content.decode()
        assert str(gastrostomy.case_id) in content
        assert str(capsule.case_id) not in content
        assert str(combined.case_id) not in content

        content = client.get(reverse(CLOSED_SEARCH_URL) + "?exam_type=eda_colonoscopy").content.decode()
        assert str(combined.case_id) in content
        assert str(gastrostomy.case_id) not in content

    def test_polling_preserves_variation_filter_parameters(self, client) -> None:
        client, _ = _nir_client(client, "nir-filter-poll@test.com")
        content = client.get(
            reverse(MY_CASES_URL) + "?exam_type=eda_dilation&q=0428&status=WAIT_DOCTOR"
        ).content.decode()

        assert 'hx-get="/cases/my-cases/partial/?exam_type=eda_dilation&amp;q=0428&amp;status=WAIT_DOCTOR"' in content
        assert 'hx-trigger="every 20s"' in content

    def test_invalid_filter_falls_back_to_all(self, client) -> None:
        client, user = _nir_client(client, "nir-filter-bogus@test.com")
        case = _make_case(user, declared=ProcedureType.EDA_DILATION, record="BOGUS-VISIBLE")

        content = client.get(reverse(MY_CASES_URL) + "?exam_type=bogus").content.decode()
        assert str(case.case_id) in content


# ═══════════════════════════════════════════════════════════════════════════
# R4 — cards, detalhe e resposta final pelo catálogo
# ═══════════════════════════════════════════════════════════════════════════


class TestCatalogProjection:
    @pytest.mark.parametrize(
        "declared",
        [
            ProcedureType.EDA,
            ProcedureType.EDA_GASTROSTOMY,
            ProcedureType.EDA_CAPSULE,
            ProcedureType.EDA_DILATION,
            ProcedureType.COLONOSCOPY,
            ProcedureType.RECTOSIGMOIDOSCOPY,
            ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
            ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
            ProcedureType.ECHOENDOSCOPY,
            ProcedureType.CPRE,
            EDA_COLONOSCOPY,
        ],
    )
    def test_card_projects_catalog_label_and_key_for_every_identity(self, client, declared: str) -> None:
        client, user = _nir_client(client, f"nir-card-{declared}@test.com")
        _make_case(user, declared=declared, record="CARD")
        label = " + ".join(ProcedureType(code).label for code in procedure_types_for_selection(declared))

        content = client.get(reverse(MY_CASES_URL)).content.decode()
        assert f'exam-type-{declared}">{label}</span>' in content

    def test_package_card_is_a_single_identity_without_base_eda(self, client) -> None:
        client, user = _nir_client(client, "nir-card-package@test.com")
        _make_case(user, declared=ProcedureType.EDA_DILATION, record="CARD-PACKAGE")

        content = client.get(reverse(MY_CASES_URL)).content.decode()
        assert content.count('exam-type-eda_dilation"') == 1
        assert 'exam-type-eda"' not in content

    def test_comparison_projects_one_row_per_package_and_two_only_for_combined(self) -> None:
        user = User.objects.create_user(username="nir-comparison@test.com")

        package = _make_case(user, declared=ProcedureType.EDA_CAPSULE, record="COMP-PACKAGE")
        CaseProcedure.objects.filter(case=package).update(detection_status=DetectionStatus.DETECTED)
        CaseProcedure.objects.filter(case=package, procedure_type=ProcedureType.EDA_CAPSULE).update(
            doctor_disposition=DoctorDisposition.APPROVED,
            doctor_reason="Indicada por sangramento obscuro.",
        )
        package_comparison = _procedure_comparison(Case.objects.get(pk=package.pk))

        assert package_comparison["declared_label"] == ProcedureType.EDA_CAPSULE.label
        assert package_comparison["detected_label"] == ProcedureType.EDA_CAPSULE.label
        assert package_comparison["authorized_label"] == ProcedureType.EDA_CAPSULE.label
        assert len(package_comparison["per_procedure"]) == 1
        package_row = package_comparison["per_procedure"][0]
        assert package_row["label"] == ProcedureType.EDA_CAPSULE.label
        assert package_row["status"] == "Aprovado"
        assert package_row["reason"] == "Indicada por sangramento obscuro."

        combined = _make_case(user, declared=EDA_COLONOSCOPY, record="COMP-COMBINED")
        CaseProcedure.objects.filter(case=combined).update(detection_status=DetectionStatus.DETECTED)
        CaseProcedure.objects.filter(case=combined, procedure_type=ProcedureType.EDA).update(
            doctor_disposition=DoctorDisposition.APPROVED,
        )
        CaseProcedure.objects.filter(case=combined, procedure_type=ProcedureType.COLONOSCOPY).update(
            doctor_disposition=DoctorDisposition.DENIED,
            doctor_reason="Sem indicação no momento.",
        )
        combined_comparison = _procedure_comparison(Case.objects.get(pk=combined.pk))

        assert [row["label"] for row in combined_comparison["per_procedure"]] == ["EDA", "Colonoscopia"]
        assert combined_comparison["per_procedure"][1]["status"] == "Negado"
        assert combined_comparison["per_procedure"][1]["reason"] == "Sem indicação no momento."

    def test_final_response_in_closed_detail_shows_three_dimensions_for_package(self, client) -> None:
        client, user = _nir_client(client, "nir-closed-package@test.com")
        case = _make_case(
            user,
            declared=ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
            record="CLOSED-ARGON",
            status=CaseStatus.CLEANED,
        )
        CaseProcedure.objects.filter(case=case).update(detection_status=DetectionStatus.DETECTED)
        CaseProcedure.objects.filter(case=case, procedure_type=ProcedureType.RECTOSIGMOIDOSCOPY_ARGON).update(
            doctor_disposition=DoctorDisposition.APPROVED,
            doctor_reason="Angiodisplasia residual.",
        )

        content = client.get(reverse("intake:closed_case_detail", args=[case.case_id])).content.decode()

        assert "Solicitado pelo NIR" in content
        assert "Detectado na análise" in content
        assert "Decisão médica" in content
        assert ProcedureType.RECTOSIGMOIDOSCOPY_ARGON.label in content
        assert "Angiodisplasia residual." in content


# ═══════════════════════════════════════════════════════════════════════════
# R6 — flags preexistentes limitam somente seus intakes
# ═══════════════════════════════════════════════════════════════════════════


class TestExistingFlagsOnly:
    def test_all_flags_off_keep_new_identities_available(self) -> None:
        with override_settings(**ALL_FLAGS_OFF):
            enabled = {option.key for option in intake_selection_options() if option.enabled}
            assert enabled == {*FLAGLESS_SELECTION_KEYS}
            for key in FLAGLESS_SELECTION_KEYS:
                assert ensure_exam_type_allowed(key) == key
                assert is_intake_selection_enabled(key) is True

    @pytest.mark.parametrize(
        "key",
        [ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY, ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE],
    )
    def test_all_flags_off_block_only_the_gated_intakes(self, key: str) -> None:
        with override_settings(**ALL_FLAGS_OFF), pytest.raises(ValueError):
            ensure_exam_type_allowed(key)

    def test_no_new_intake_flag_was_created(self) -> None:
        """R6: a tabela de gates continua exatamente a dos três intakes preexistentes."""
        assert set(_INTAKE_SELECTION_FLAG_GATES) == {
            ProcedureType.COLONOSCOPY,
            EDA_COLONOSCOPY,
            ProcedureType.ECHOENDOSCOPY,
            ProcedureType.CPRE,
        }
        flag_names = set(re.findall(r"\b([A-Z_]+_INTAKE_ENABLED)\b", SERVICES_SOURCE.read_text()))
        assert flag_names == {
            "COLONOSCOPY_INTAKE_ENABLED",
            "ECHOENDOSCOPY_INTAKE_ENABLED",
            "CPRE_INTAKE_ENABLED",
        }
