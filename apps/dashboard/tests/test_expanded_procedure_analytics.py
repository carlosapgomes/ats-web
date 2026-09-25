"""Slice 009 — analytics gerencial do catálogo ampliado (R1–R6).

Cobre o breakdown/tabela gerencial para as dez identidades atômicas e o
combinado, provando:

- R1: resumo `declared|detected|approved` com categorias exclusivas por caso,
  fechando com o universo aplicável;
- R2: filtro de tabela compõe dimensão + selection key + busca/status/datas/
  atenção/paginação com igualdade EXATA de conjunto (EDA simples nunca aparece
  sob ``eda_gastrostomy``);
- R3: volume por componente conta cada código atômico — pacote é UM
  componente, combinado são dois componentes de UM caso e família/profile
  nunca agrega volumes;
- R4: `paired_confirmed` conta uma única vez somente o autorizado exato
  ``{eda, colonoscopy}`` (nenhuma label com ``+`` conta);
- R5: conjunto persistido fora da matriz aparece no bucket explícito
  ``invalid``, nunca somado a categoria válida e nunca omitido;
- R6: opções/labels/ordem da tabela derivam do catálogo, compartilhando o
  mesmo universo com os chips do card gerencial (chips e select concordam).

Os helpers ``_expected_breakdown``/``_expected_volume`` são reutilizados do
teste de analytics existente (uma única grafia para o universo derivado).
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import (
    Case,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
)
from apps.cases.procedures import (
    PROCEDURE_LABELS,
    SELECTION_KEYS,
    SUPPORTED_PROCEDURE_TYPES,
    record_doctor_procedure_decisions,
    set_declared_procedures,
    set_detected_procedures,
)
from apps.dashboard import procedure_analytics
from apps.dashboard.procedure_analytics import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    DIMENSIONS,
    SELECTIONS,
    compute_procedure_analytics,
)
from apps.dashboard.tests.test_procedure_analytics import _expected_breakdown, _expected_volume

pytestmark = pytest.mark.django_db

User = get_user_model()

# Identidades atômicas cuja label contém ``+``: nenhuma delas pode compor o
# contador de agendamentos casados (R4) — o critério é conjunto, nunca texto.
PLUS_LABEL_CODES = tuple(code for code in SUPPORTED_PROCEDURE_TYPES if "+" in PROCEDURE_LABELS[code])

# Registro determinístico por identidade. Os tokens não são prefixo um do outro
# para permitir asserção por substring sem colisão entre fixtures.
ARN: dict[str, str] = {
    "eda": "X-EDA",
    "eda_gastrostomy": "X-GTT",
    "eda_capsule": "X-CAP",
    "eda_dilation": "X-DIL",
    "colonoscopy": "X-COL",
    "rectosigmoidoscopy": "X-RSC",
    "rectosigmoidoscopy_dilation": "X-RDL",
    "rectosigmoidoscopy_argon": "X-RAR",
    "echoendoscopy": "X-ECO",
    "cpre": "X-CPR",
    "eda_colonoscopy": "X-CMB",
    "none": "X-NON",
}

UNIVERSE_CASES = 12  # dez identidades + combinado + negativa integral

_SELECT_OPTION_RE = re.compile(r'<option value="([^"]+)"[^>]*>([^<]*)</option>')


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client: Any, role_name: str = "manager") -> Any:
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"slice009-{role_name}@test", password="testpass123")
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _make_case(
    user: Any,
    arn: str,
    *,
    declared: tuple[str, ...] = (),
    detected: tuple[str, ...] = (),
    approved: tuple[str, ...] = (),
    status: str = CaseStatus.NEW,
    appointment_status: str = "",
    patient_name: str = "",
) -> Case:
    """Caso com projeções escritas pelos serviços centrais (matriz fechada)."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        status=status,
        appointment_status=appointment_status,
        structured_data={"patient": {"name": patient_name}} if patient_name else None,
    )
    if declared:
        set_declared_procedures(case=case, procedure_types=list(declared), actor=user)
    if detected:
        set_detected_procedures(case=case, detected_types=list(detected), actor=user)
    if approved:
        record_doctor_procedure_decisions(
            case=case,
            decisions=[
                {"procedure_type": code, "disposition": "approved", "reason": "ok", "added_by_doctor": False}
                for code in approved
            ],
            actor=user,
        )
    return Case.objects.get(pk=case.pk)


def _make_off_matrix_case(user: Any, arn: str, *, codes: tuple[str, ...], appointment_status: str = "") -> Case:
    """Caso com conjunto persistido FORA da matriz (rows gravadas direto).

    Os serviços centrais recusam o conjunto (fail-closed), então a inconsistência
    só é alcançável por escrita direta — exatamente o cenário do bucket
    ``invalid`` (R5/design D12).
    """
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        status=CaseStatus.WAIT_DOCTOR,
        appointment_status=appointment_status,
    )
    for code in codes:
        CaseProcedure.objects.create(
            case=case,
            procedure_type=code,
            declared_by_nir=True,
            detection_status=DetectionStatus.DETECTED,
            doctor_disposition=DoctorDisposition.APPROVED,
        )
    return case


def _seed_expanded_universe(user: Any) -> dict[str, Case]:
    """Um caso por identidade atômica + combinado + negativa integral.

    A negativa integral (``X-NON``) declara Ecoendoscopia e não recebe nenhuma
    aprovação: ela existe para provar que ``none`` não vira identidade no
    autorizado, e compartilha de propósito a categoria ``echoendoscopy`` no
    declarado/detectado com ``X-ECO``.
    """
    Case.objects.all().delete()
    cases: dict[str, Case] = {}
    for code in SUPPORTED_PROCEDURE_TYPES:
        cases[code] = _make_case(
            user,
            ARN[code],
            declared=(code,),
            detected=(code,),
            approved=(code,),
        )
    cases["eda_colonoscopy"] = _make_case(
        user,
        ARN["eda_colonoscopy"],
        declared=("eda", "colonoscopy"),
        detected=("eda", "colonoscopy"),
        approved=("eda", "colonoscopy"),
        appointment_status="confirmed",
        status=CaseStatus.WAIT_APPT,
    )
    cases["none"] = _make_case(
        user,
        ARN["none"],
        declared=("echoendoscopy",),
        detected=("echoendoscopy",),
    )
    return cases


def _expected_declared_arns(code: str) -> tuple[str, ...]:
    """ARNs cujo conjunto DECLARADO é exatamente a identidade ``code``.

    ``X-NON`` (negativa integral) declara a mesma identidade Ecoendoscopia de
    ``X-ECO``: dois casos compartilham a categoria ``echoendoscopy``.
    """
    if code == "echoendoscopy":
        return (ARN["echoendoscopy"], ARN["none"])
    return (ARN[code],)


def _atomic_components(volume_for_dimension: dict[str, int]) -> int:
    """Soma os componentes atômicos da dimensão (exclui o contador derivado ``combined``)."""
    return sum(count for key, count in volume_for_dimension.items() if key != "combined")


def _summary_card_block(content: str) -> str:
    """Isola o HTML do card gerencial (marcador até a seção Sub-metrics)."""
    start = content.find('class="procedure-summary-card')
    assert start != -1, "Card deve ter marcador .procedure-summary-card"
    end = content.find("<!-- Sub-metrics -->", start)
    assert end != -1, "Card deve terminar antes da seção Sub-metrics"
    return content[start:end]


def _chip_count(card: str, label: str) -> int:
    """Conta renderizada do chip de categoria ``label`` no card gerencial."""
    match = re.search(re.escape(label) + r"</div>\s*<div[^>]*>(\d+)</div>", card)
    assert match is not None, f"Chip {label!r} deve existir no card"
    return int(match.group(1))


def _rendered_selection_options(content: str) -> list[tuple[str, str]]:
    """Pares (key, label) do select de procedimento da tabela."""
    start = content.find('id="procedure-selection"')
    assert start != -1, "Select de procedimento deve existir na página"
    end = content.find("</select>", start)
    assert end != -1, "Select de procedimento deve fechar"
    return _SELECT_OPTION_RE.findall(content[start:end])


def _index_url(**params: str) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{reverse('dashboard:index')}?{query}"


# ── R6: universo derivado do catálogo (chips e select concordam) ─────────


class TestCatalogDerivedSelectionUniverse:
    """R6 — opções/labels/ordem derivam do catálogo, sem lista local fechada."""

    def test_selections_derive_from_catalog_selection_keys(self) -> None:
        """``SELECTIONS`` = ``all`` + cada chave do catálogo + ``none``.

        O bucket ``invalid`` não é uma identidade filtrável: conjunto fora da
        matriz não casa seleção válida nenhuma (aparece apenas em ``all``),
        espelhando o bucket fail-closed do resumo (R5).
        """
        assert SELECTIONS == ("all", *SELECTION_KEYS, "none")
        assert set(SELECTIONS) - {"all", "none"} == set(SELECTION_KEYS)

    def test_breakdown_identity_categories_match_the_selection_universe(self) -> None:
        """Chips do card e select compartilham o mesmo universo de identidades."""
        identities = tuple(category for category in CATEGORY_ORDER if category not in ("none", "invalid"))
        assert identities == SELECTION_KEYS
        assert CATEGORY_ORDER[-2:] == ("none", "invalid")

    def test_catalog_labels_are_single_sourced(self) -> None:
        """Rótulos usados pelo card e pelo select vêm do catálogo/projeção única."""
        for code in SUPPORTED_PROCEDURE_TYPES:
            assert CATEGORY_LABELS[code] == PROCEDURE_LABELS[code]
        assert CATEGORY_LABELS["eda_colonoscopy"] == "EDA + Colonoscopia"
        assert CATEGORY_LABELS["none"] == "Nenhum"
        assert CATEGORY_LABELS["invalid"] == "Conjunto inválido"

    def test_selection_options_project_catalog_keys_and_labels(self) -> None:
        options = procedure_analytics.procedure_selection_options()
        assert [option["key"] for option in options] == list(SELECTIONS)
        assert options[0] == {"key": "all", "label": "Todos"}
        assert options[-1] == {"key": "none", "label": "Nenhum"}
        for option in options[1:]:
            assert option["label"] == CATEGORY_LABELS[option["key"]]
        # Ordem canônica do catálogo preservada nas identidades.
        assert [option["key"] for option in options if option["key"] not in ("all", "none")] == list(SELECTION_KEYS)

    def test_template_select_renders_catalog_options(self, client) -> None:
        _login_as(client)
        content = client.get(reverse("dashboard:index")).content.decode()
        rendered = _rendered_selection_options(content)
        assert [key for key, _ in rendered] == list(SELECTIONS)
        labels = dict(rendered)
        assert labels["all"] == "Todos"
        assert labels["none"] == "Nenhum"
        for code in SELECTION_KEYS:
            assert labels[code] == CATEGORY_LABELS[code]

    def test_template_source_has_no_closed_option_list(self) -> None:
        source = (Path(__file__).resolve().parents[3] / "templates" / "dashboard" / "index.html").read_text()
        assert "{% for option in procedure_selection_options %}" in source, "Select deve iterar as opções projetadas"
        for code in SELECTION_KEYS:
            assert f'<option value="{code}"' not in source, f"Opção {code!r} não pode ser lista local no template"


# ── R1: categorias exclusivas fecham com o universo ─────────────────────


class TestExclusiveCategoriesCloseTheUniverse:
    """R1 — cada caso em exatamente uma categoria, por dimensão."""

    def test_each_dimension_closes_with_the_universe(self, client) -> None:
        user = _login_as(client)
        _seed_expanded_universe(user)

        breakdown = compute_procedure_analytics(Case.objects.all())["breakdown"]

        for dimension in DIMENSIONS:
            total = sum(breakdown[dimension].values())
            assert total == UNIVERSE_CASES, (
                f"Breakdown {dimension} deve fechar com {UNIVERSE_CASES} casos, obteve {total}"
            )

        identity_counts = {
            "eda": 1,
            "eda_gastrostomy": 1,
            "eda_capsule": 1,
            "eda_dilation": 1,
            "colonoscopy": 1,
            "rectosigmoidoscopy": 1,
            "rectosigmoidoscopy_dilation": 1,
            "rectosigmoidoscopy_argon": 1,
            "echoendoscopy": 2,
            "cpre": 1,
            "eda_colonoscopy": 1,
        }
        assert breakdown["declared"] == _expected_breakdown(**identity_counts)
        assert breakdown["detected"] == _expected_breakdown(**identity_counts)
        # Autorizado: X-NON (sem aprovação) cai em ``none`` sem virar identidade.
        assert breakdown["approved"] == _expected_breakdown(
            **{code: 1 for code in SUPPORTED_PROCEDURE_TYPES},
            eda_colonoscopy=1,
            none=1,
        )

    def test_eda_family_identities_are_not_counted_as_eda(self, client) -> None:
        """Nenhuma identidade da família EDA é contada como EDA (nem por família)."""
        user = _login_as(client)
        _seed_expanded_universe(user)

        breakdown = compute_procedure_analytics(Case.objects.all())["breakdown"]["approved"]

        assert breakdown["eda"] == 1, "Somente o caso EDA simples conta como EDA"
        for code in ("eda_gastrostomy", "eda_capsule", "eda_dilation"):
            assert breakdown[code] == 1, f"{code} deve ter bucket próprio"
        assert breakdown["eda_colonoscopy"] == 1, "Combinado é categoria própria, não EDA"


# ── R3: volume por componente do catálogo ───────────────────────────────


class TestComponentVolumeIsPerAtomicCode:
    """R3 — pacote é um componente, combinado dois componentes de um caso."""

    @pytest.mark.parametrize("code", ("eda_gastrostomy", "eda_capsule", "eda_dilation"))
    def test_eda_package_is_one_component_and_never_inflates_base(self, client, code: str) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, ARN[code], declared=(code,), detected=(code,), approved=(code,))

        analytics = compute_procedure_analytics(Case.objects.all())

        for dimension in DIMENSIONS:
            assert analytics["breakdown"][dimension][code] == 1
            assert analytics["breakdown"][dimension]["eda"] == 0, "Pacote não desmembra a base EDA"
            assert analytics["volume"][dimension][code] == 1
            assert analytics["volume"][dimension]["eda"] == 0, "Pacote não infla o volume de EDA"
        assert _atomic_components(analytics["volume"]["declared"]) == 1, "Pacote é UM componente"

    @pytest.mark.parametrize(
        "code",
        ("rectosigmoidoscopy", "rectosigmoidoscopy_dilation", "rectosigmoidoscopy_argon"),
    )
    def test_rectosigmoidoscopy_family_never_aggregates_volumes(self, client, code: str) -> None:
        """Profile Colonoscopia compartilhado não soma identidades (R3)."""
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, ARN[code], declared=(code,), detected=(code,), approved=(code,))

        analytics = compute_procedure_analytics(Case.objects.all())

        for dimension in DIMENSIONS:
            assert analytics["volume"][dimension][code] == 1
            assert analytics["breakdown"][dimension][code] == 1
            for other in (
                "colonoscopy",
                "rectosigmoidoscopy",
                "rectosigmoidoscopy_dilation",
                "rectosigmoidoscopy_argon",
            ):
                if other == code:
                    continue
                assert analytics["volume"][dimension][other] == 0, f"{other} não pode receber o volume de {code}"

    def test_combined_keeps_two_components_of_a_single_case(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            ARN["eda_colonoscopy"],
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
        )

        analytics = compute_procedure_analytics(Case.objects.all())

        for dimension in DIMENSIONS:
            assert analytics["breakdown"][dimension]["eda_colonoscopy"] == 1
            assert sum(analytics["breakdown"][dimension].values()) == 1, "Combinado é UM caso"
            assert analytics["volume"][dimension]["eda"] == 1
            assert analytics["volume"][dimension]["colonoscopy"] == 1
            assert _atomic_components(analytics["volume"][dimension]) == 2, "Combinado são DOIS componentes"
            assert analytics["volume"][dimension]["combined"] == 1, (
                "Contador derivado do par exato, fora dos componentes"
            )

    def test_volume_buckets_are_exactly_the_catalog_codes(self, client) -> None:
        user = _login_as(client)
        _seed_expanded_universe(user)

        analytics = compute_procedure_analytics(Case.objects.all())

        for dimension in DIMENSIONS:
            assert set(analytics["volume"][dimension]) == set(SUPPORTED_PROCEDURE_TYPES) | {"combined"}

    def test_universe_components_close_with_cases_plus_combined(self, client) -> None:
        """Componentes = casos + 1 por combinado (combinado duplica uma vez)."""
        user = _login_as(client)
        _seed_expanded_universe(user)

        volume = compute_procedure_analytics(Case.objects.all())["volume"]

        # Declarado: X-CMB soma um componente de EDA e um de Colonoscopia; X-NON
        # soma um componente de Ecoendoscopia (a negativa integral não autoriza).
        declared_counts = {code: 1 for code in SUPPORTED_PROCEDURE_TYPES}
        declared_counts.update({"eda": 2, "colonoscopy": 2, "echoendoscopy": 2})
        assert volume["declared"] == _expected_volume(**declared_counts, combined=1)

        # Autorizado: X-NON não contribui nenhum componente; X-CMB continua dois.
        approved_counts = {code: 1 for code in SUPPORTED_PROCEDURE_TYPES}
        approved_counts.update({"eda": 2, "colonoscopy": 2})
        assert volume["approved"] == _expected_volume(**approved_counts, combined=1)
        assert _atomic_components(volume["declared"]) == UNIVERSE_CASES + 1
        assert _atomic_components(volume["approved"]) == UNIVERSE_CASES
        assert volume["declared"]["combined"] == 1
        assert volume["approved"]["combined"] == 1


# ── R4: paired confirmado é o conjunto exato ────────────────────────────


class TestPairedConfirmedIsTheExactSet:
    """R4 — só ``{eda, colonoscopy}`` autorizado e confirmado conta, uma vez."""

    @pytest.mark.parametrize("code", PLUS_LABEL_CODES)
    def test_plus_label_identity_never_counts_as_paired(self, client, code: str) -> None:
        """Label com ``+`` não é critério: pacote confirmado não é agendamento casado."""
        assert "+" in PROCEDURE_LABELS[code], "Fixture precisa de label com '+'"
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            ARN[code],
            declared=(code,),
            detected=(code,),
            approved=(code,),
            appointment_status="confirmed",
            status=CaseStatus.WAIT_APPT,
        )

        analytics = compute_procedure_analytics(Case.objects.all())

        assert analytics["paired_confirmed"] == 0, f"{code} tem '+' na label mas não é o par exato"
        assert analytics["volume"]["approved"][code] == 1, "A identidade continua mensurada em components"

    def test_exact_pair_confirmed_counts_once(self, client) -> None:
        user = _login_as(client)
        _seed_expanded_universe(user)

        analytics = compute_procedure_analytics(Case.objects.all())

        assert analytics["paired_confirmed"] == 1, "Somente o combinado confirmado conta, uma única vez"
        assert analytics["volume"]["approved"]["combined"] == 1

    def test_pair_approved_without_confirmation_does_not_count(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            ARN["eda_colonoscopy"],
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
            appointment_status="denied",
        )

        assert compute_procedure_analytics(Case.objects.all())["paired_confirmed"] == 0

    def test_off_matrix_confirmed_set_is_not_paired(self, client) -> None:
        """Dois códigos confirmados fora da matriz não compõem casados nem viram categoria."""
        user = _login_as(client)
        Case.objects.all().delete()
        _make_off_matrix_case(
            user,
            "OFF-PAIR",
            codes=("eda_gastrostomy", "colonoscopy"),
            appointment_status="confirmed",
        )

        analytics = compute_procedure_analytics(Case.objects.all())

        assert analytics["paired_confirmed"] == 0
        assert analytics["breakdown"]["approved"]["invalid"] == 1


# ── R5: conjunto inválido é explícito e nunca reduzido ──────────────────


class TestInvalidPersistedSetIsExplicit:
    """R5 — sentinela ``invalid`` tem bucket próprio, nunca categoria válida."""

    def test_off_matrix_set_lands_in_the_invalid_bucket_in_every_dimension(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_off_matrix_case(user, "OFF-DIM", codes=("eda_dilation", "colonoscopy"))

        analytics = compute_procedure_analytics(Case.objects.all())

        for dimension in DIMENSIONS:
            assert analytics["breakdown"][dimension]["invalid"] == 1
            assert sum(analytics["breakdown"][dimension].values()) == 1, "O caso não pode sumir nem duplicar"

    def test_off_matrix_set_is_never_merged_into_a_valid_category(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_off_matrix_case(user, "OFF-MERGE", codes=("eda_dilation", "colonoscopy"))

        breakdown = compute_procedure_analytics(Case.objects.all())["breakdown"]["approved"]

        assert breakdown["invalid"] == 1
        for category in CATEGORY_ORDER:
            if category == "invalid":
                continue
            assert breakdown[category] == 0, f"Conjunto fora da matriz nunca é somado a {category!r}"

    def test_manager_card_surfaces_the_invalid_bucket(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_off_matrix_case(user, "OFF-CARD", codes=("eda_dilation", "colonoscopy"))

        content = client.get(_index_url(procedure_dimension="approved")).content.decode()
        card = _summary_card_block(content)

        assert _chip_count(card, CATEGORY_LABELS["invalid"]) == 1, "Inconsistência precisa aparecer no card"
        assert _chip_count(card, CATEGORY_LABELS["eda_dilation"]) == 0, "Nunca reduzido a um singleton válido"
        assert _chip_count(card, CATEGORY_LABELS["eda_colonoscopy"]) == 0, "Nunca reinterpretado como o par"

    def test_off_matrix_set_matches_only_the_all_selection(self, client) -> None:
        """Fail-closed: a inconsistência não é alcançável por seleção de identidade."""
        user = _login_as(client)
        Case.objects.all().delete()
        _make_off_matrix_case(user, "OFF-FILTER", codes=("eda_gastrostomy", "colonoscopy"))

        all_content = client.get(_index_url(procedure_dimension="declared", procedure_selection="all")).content.decode()
        assert "OFF-FILTER" in all_content, "Conjunto inválido permanece visível em all"

        for selection in ("eda_gastrostomy", "colonoscopy", "eda_colonoscopy"):
            url = _index_url(procedure_dimension="declared", procedure_selection=selection, case_scope="all")
            assert "OFF-FILTER" not in client.get(url).content.decode(), (
                f"Conjunto fora da matriz não pode casar {selection!r}"
            )


# ── R2: tabela compõe dimensão + selection key exata ────────────────────


class TestTableFilterIsExactPerCatalogIdentity:
    """R2 — igualdade exata do conjunto da dimensão, composta com os filtros."""

    @pytest.mark.parametrize("code", SELECTION_KEYS)
    def test_selection_matches_only_its_exact_identity(self, client, code: str) -> None:
        user = _login_as(client)
        _seed_expanded_universe(user)

        url = _index_url(procedure_dimension="declared", procedure_selection=code, case_scope="all")
        content = client.get(url).content.decode()

        expected = _expected_declared_arns(code)
        for arn in expected:
            assert arn in content, f"{arn} deve casar a seleção {code}"
        for other_code, arn in ARN.items():
            if arn in expected:
                continue
            assert arn not in content, f"{arn} ({other_code}) não pode casar com a seleção {code}"

    def test_eda_gastrostomy_excludes_plain_eda(self, client) -> None:
        """R2 — EDA simples não aparece sob ``eda_gastrostomy`` (nem irmãs)."""
        user = _login_as(client)
        _seed_expanded_universe(user)

        content = client.get(
            _index_url(procedure_dimension="declared", procedure_selection="eda_gastrostomy", case_scope="all")
        ).content.decode()

        assert ARN["eda_gastrostomy"] in content
        assert ARN["eda"] not in content, "EDA simples não compartilha família na tabela"
        assert ARN["eda_dilation"] not in content
        assert ARN["eda_capsule"] not in content
        assert ARN["eda_colonoscopy"] not in content

    def test_none_authorization_stays_its_own_category(self, client) -> None:
        user = _login_as(client)
        _seed_expanded_universe(user)

        content = client.get(
            _index_url(procedure_dimension="approved", procedure_selection="none", case_scope="all")
        ).content.decode()

        assert ARN["none"] in content
        assert ARN["echoendoscopy"] not in content, "Ausência de aprovação não vira a identidade declarada"
        assert ARN["eda"] not in content

    def test_selection_composes_with_search_and_status(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "AND-DIL-1",
            declared=("eda_dilation",),
            detected=("eda_dilation",),
            status=CaseStatus.WAIT_DOCTOR,
            patient_name="Dora Dilata",
        )
        _make_case(
            user,
            "AND-DIL-2",
            declared=("eda_dilation",),
            detected=("eda_dilation",),
            status=CaseStatus.NEW,
            patient_name="Dora Dilata",
        )
        _make_case(
            user,
            "AND-CAP-1",
            declared=("eda_capsule",),
            detected=("eda_capsule",),
            status=CaseStatus.WAIT_DOCTOR,
            patient_name="Dora Capsula",
        )

        content = client.get(
            _index_url(
                procedure_dimension="declared",
                procedure_selection="eda_dilation",
                search="dora",
                status=CaseStatus.WAIT_DOCTOR,
                case_scope="all",
            )
        ).content.decode()

        assert "AND-DIL-1" in content, "Seleção + busca + status compõem por AND"
        assert "AND-DIL-2" not in content, "Status diferente não pode casar"
        assert "AND-CAP-1" not in content, "Identidade diferente não pode casar"

    def test_selection_composes_with_dates(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        today = timezone.localdate()
        five_days_ago = today - timedelta(days=5)
        _make_case(user, "DT-CAP-1", declared=("eda_capsule",), detected=("eda_capsule",))
        older = _make_case(user, "DT-CAP-2", declared=("eda_capsule",), detected=("eda_capsule",))
        older_start = timezone.make_aware(
            datetime.combine(five_days_ago, time(9, 0)),
            timezone.get_current_timezone(),
        )
        Case.objects.filter(pk=older.pk).update(created_at=older_start)

        today_content = client.get(
            _index_url(
                procedure_dimension="declared",
                procedure_selection="eda_capsule",
                date_from=today.isoformat(),
                date_to=today.isoformat(),
                case_scope="all",
            )
        ).content.decode()
        assert "DT-CAP-1" in today_content
        assert "DT-CAP-2" not in today_content, "Data fora da janela não pode casar"

        range_content = client.get(
            _index_url(
                procedure_dimension="declared",
                procedure_selection="eda_capsule",
                date_from=five_days_ago.isoformat(),
                date_to=today.isoformat(),
                case_scope="all",
            )
        ).content.decode()
        assert "DT-CAP-1" in range_content
        assert "DT-CAP-2" in range_content, "Janela ampliada inclui o caso antigo"

    def test_selection_composes_with_attention(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "AT-DIL-1",
            declared=("eda_dilation",),
            detected=("eda_dilation",),
            status=CaseStatus.FAILED,
        )
        _make_case(
            user,
            "AT-DIL-2",
            declared=("eda_dilation",),
            detected=("eda_dilation",),
            status=CaseStatus.NEW,
        )

        content = client.get(
            _index_url(
                procedure_dimension="declared",
                procedure_selection="eda_dilation",
                attention="1",
                case_scope="active",
            )
        ).content.decode()

        assert "AT-DIL-1" in content, "Atenção compõe com a seleção"
        assert "AT-DIL-2" not in content, "Caso sem critério de atenção não pode casar"

    def test_partial_pagination_preserves_expanded_selection(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        for index in range(25):
            _make_case(
                user,
                f"PG-GTT-{index:03d}",
                declared=("eda_gastrostomy",),
                detected=("eda_gastrostomy",),
            )

        url = _index_url(
            procedure_dimension="detected",
            procedure_selection="eda_gastrostomy",
            case_scope="all",
        )
        partial = client.get(url, headers={"X-ATS-Partial": "case-list"}).content.decode()

        assert "procedure_dimension=detected" in partial, "Paginação do partial preserva a dimensão"
        assert "procedure_selection=eda_gastrostomy" in partial, "Paginação do partial preserva a identidade"

        full = client.get(url).content.decode()
        assert 'name="procedure_selection" value="eda_gastrostomy"' in full, "Filtros preservam a seleção ativa"

    def test_unknown_selection_still_falls_back_to_all(self, client) -> None:
        """Valor fora do catálogo cai no default seguro (``all``), nunca em filtro parcial."""
        user = _login_as(client)
        _seed_expanded_universe(user)

        content = client.get(
            _index_url(procedure_dimension="declared", procedure_selection="bogus", case_scope="all")
        ).content.decode()

        assert ARN["eda"] in content and ARN["eda_gastrostomy"] in content


# ── R6/no-N+1: higiene de queries com o catálogo ampliado ───────────────


class TestExpandedCatalogQueryHygiene:
    """R6 — filtro composto sem N+1 e analytics com queries limitadas."""

    def test_analytics_queries_stay_bounded_with_expanded_catalog(self, client) -> None:
        user = _login_as(client)
        _seed_expanded_universe(user)

        with CaptureQueriesContext(connection) as captured:
            analytics = compute_procedure_analytics(Case.objects.all())

        assert sum(analytics["breakdown"]["declared"].values()) == UNIVERSE_CASES
        assert len(captured.captured_queries) <= 4, (
            f"Analytics deve usar <=4 queries, obteve {len(captured.captured_queries)}"
        )

    def test_expanded_selection_does_not_add_query_per_identity(self, client) -> None:
        """Filtro exato usa subqueries correlacionadas: nenhuma query por identidade."""
        user = _login_as(client)
        _seed_expanded_universe(user)

        with CaptureQueriesContext(connection) as baseline:
            client.get(_index_url(procedure_dimension="declared", procedure_selection="all", case_scope="all"))
        with CaptureQueriesContext(connection) as filtered:
            client.get(
                _index_url(procedure_dimension="declared", procedure_selection="eda_gastrostomy", case_scope="all")
            )

        assert len(filtered.captured_queries) <= len(baseline.captured_queries) + 1, (
            f"Filtro exato não deve introduzir queries por identidade: "
            f"{len(filtered.captured_queries)} vs {len(baseline.captured_queries)}"
        )
