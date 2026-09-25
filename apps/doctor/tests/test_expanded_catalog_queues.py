"""Slice 008 — fila médica pelo catálogo ampliado (R1, R2, R7).

- R1: Pendentes filtra pela dimensão DETECTADA e Decididos Hoje pela
  AUTORIZADA; as opções/contadores dos controles derivam do catálogo
  (``SELECTION_KEYS``) e continuam compostos com busca e polling.
- R2: cada pacote/Retossigmoidoscopia aparece como badge singleton com a label
  canônica; a transformação detectado → autorizado usa o texto existente e não
  cria ``UserNotification``.
- R7: o template itera ``procedure_filter_options`` e o script inicializa
  chaves/contagens pelos elementos renderizados (``data-*``), sem objeto
  literal fechado de tipos.

Sem runner JS, o comportamento do script é provado por inspeção estática dos
marcadores de inicialização dinâmica (matriz manual no relatório do slice).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Role, UserNotification
from apps.cases.models import (
    Case,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.cases.procedures import PROCEDURE_LABELS, SELECTION_KEYS, SUPPORTED_PROCEDURE_TYPES

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "doctor" / "queue.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "doctor_queue_filter.js"

# Universo do catálogo (design D12): `all` + cada chave de seleção válida, na
# ordem canônica do catálogo (o combinado é a chave derivada, por último), e
# `none` em Decididos Hoje.
CATALOG_FILTER_VALUES = ["all", *SELECTION_KEYS]
DECIDED_FILTER_VALUES = [*CATALOG_FILTER_VALUES, "none"]

# Label canônica de cada chave de seleção (chave derivada = labels dos
# componentes), derivada do catálogo — nunca redigitada no teste.
SELECTION_LABELS = {
    key: " + ".join(PROCEDURE_LABELS[part] for part in (("eda", "colonoscopy") if key == "eda_colonoscopy" else (key,)))
    for key in SELECTION_KEYS
}

# Identidades canônicas ATÔMICAS cuja label contém "+" — nunca podem acionar
# regra textual de combinado (R4).
PLUS_LABEL_CODES = tuple(code for code in SUPPORTED_PROCEDURE_TYPES if "+" in PROCEDURE_LABELS[code])


def _radio_values(html: str, name: str) -> list[str]:
    """Valores dos radios com `name` na ordem em que foram renderizados."""
    return re.findall(rf'name="{name}"[^>]*?value="([^"]+)"', html)


def _create_role(name: str) -> Any:
    role, _ = Role.objects.get_or_create(name=name)
    return role


def _login_as(client, role_name: str) -> Any:
    user = User.objects.create_user(username=f"{role_name}@catalog-queues.test", password="testpass123")
    user.roles.add(_create_role(role_name))
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _make_case(
    nir: Any,
    *,
    status: str = CaseStatus.WAIT_DOCTOR,
    declared: tuple[str, ...] = (),
    detected: tuple[str, ...] = (),
    approved: tuple[str, ...] = (),
    denied: tuple[str, ...] = (),
    doctor: Any = None,
    name: str = "Paciente Catálogo",
    record: str = "CAT-001",
) -> Case:
    """Caso com rows explícitas por dimensão (nunca inferidas de campo/JSON)."""
    case = Case.objects.create(
        created_by=nir,
        status=status,
        agency_record_number=record,
        doctor=doctor,
        doctor_decision="accept" if doctor is not None else "",
        doctor_decided_at=timezone.now() if doctor is not None else None,
        structured_data={"patient": {"name": name, "age": 55, "gender": "F"}},
    )
    for procedure_type in set(declared) | set(detected) | set(approved) | set(denied):
        CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=procedure_type in declared,
            detection_status=(DetectionStatus.DETECTED if procedure_type in detected else DetectionStatus.NOT_DETECTED),
            doctor_disposition=(
                DoctorDisposition.APPROVED
                if procedure_type in approved
                else DoctorDisposition.DENIED
                if procedure_type in denied
                else DoctorDisposition.PENDING
            ),
        )
    return case


# ── R1: universo de opções derivado do catálogo ───────────────────────────


@pytest.mark.django_db
class TestDoctorCatalogFilterUniverse:
    """Controles de Pendentes/Decididos Hoje derivados do catálogo (R1/D12)."""

    def test_pending_filter_universe_is_the_catalog(self, client) -> None:
        _login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        values = _radio_values(content, "doctor-queue-exam-type")
        assert values == CATALOG_FILTER_VALUES
        assert "none" not in values

    def test_decided_filter_universe_is_the_catalog_plus_none(self, client) -> None:
        _login_as(client, "doctor")
        content = client.get("/doctor/?tab=decided").content.decode()
        values = _radio_values(content, "doctor-decided-exam-type")
        assert values == DECIDED_FILTER_VALUES

    def test_pending_options_render_catalog_labels(self, client) -> None:
        _login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        for key, label in SELECTION_LABELS.items():
            assert f">{label} <span" in content, f"label ausente no filtro Pendentes: {key} → {label}"

    def test_every_option_exposes_count_and_label_markers(self, client) -> None:
        """R7: cada opção renderiza contador e label legíveis pelo script."""
        _login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        for key in CATALOG_FILTER_VALUES:
            assert f'data-exam-type-count="{key}"' in content
        assert content.count('data-exam-type-label="') == len(CATALOG_FILTER_VALUES)
        decided = client.get("/doctor/?tab=decided").content.decode()
        assert 'data-exam-type-count="none"' in decided
        assert 'data-exam-type-label="Nenhum autorizado"' in decided

    def test_filter_composes_with_search_and_polling(self, client) -> None:
        """R1: filtro e busca ficam fora do alvo do swap HTMX."""
        _login_as(client, "doctor")
        content = client.get("/doctor/?tab=pending").content.decode()
        assert "data-doctor-queue-search" in content
        assert 'id="doctor-queue-type-filter"' in content
        assert 'hx-get="/doctor/partials/queue/?tab=pending"' in content
        assert 'hx-trigger="every 20s"' in content


# ── R1/R2: dimensão projetada e badge singleton por identidade ────────────


@pytest.mark.django_db
class TestDoctorCatalogCardDimension:
    """Pendentes = detectado; Decididos Hoje = autorizado (R1/D12)."""

    def test_pending_package_card_is_singleton_with_catalog_label(self, client) -> None:
        nir = _login_as(client, "nir")
        case = _make_case(
            nir,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA_GASTROSTOMY,),
            name="Pacote GTT",
            record="PEND-GTT",
        )
        _login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        assert f'data-proc-selection="{ProcedureType.EDA_GASTROSTOMY}"' in content
        assert f'data-exam-type="{ProcedureType.EDA_GASTROSTOMY}"' in content
        assert f">{PROCEDURE_LABELS[ProcedureType.EDA_GASTROSTOMY]}</span>" in content
        # Identidade única: a EDA base não aparece como badge separado.
        assert ">EDA</span>" not in content
        assert str(case.case_id) in content

    def test_pending_retosigmoid_argon_card_is_one_identity(self, client) -> None:
        nir = _login_as(client, "nir")
        _make_case(
            nir,
            declared=(ProcedureType.RECTOSIGMOIDOSCOPY,),
            detected=(ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,),
            name="Argônio",
            record="PEND-ARG",
        )
        _login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        assert content.count(f'data-proc-selection="{ProcedureType.RECTOSIGMOIDOSCOPY_ARGON}"') == 1
        assert f">{PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_ARGON]}</span>" in content
        assert ">Retossigmoidoscopia</span>" not in content

    def test_decided_selection_uses_authorized_dimension(self, client) -> None:
        doctor = _login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-decided-catalog@test", password="testpass123")
        nir.roles.add(_create_role("nir"))
        _make_case(
            nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA,),
            approved=(ProcedureType.EDA_CAPSULE,),
            denied=(ProcedureType.EDA,),
            doctor=doctor,
            name="Troca Cápsula",
            record="DEC-CAP",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert f'data-proc-selection="{ProcedureType.EDA_CAPSULE}"' in content
        assert f">{PROCEDURE_LABELS[ProcedureType.EDA_CAPSULE]}</span>" in content
        assert (
            f"Detectado: {PROCEDURE_LABELS[ProcedureType.EDA]} · "
            f"Autorizado: {PROCEDURE_LABELS[ProcedureType.EDA_CAPSULE]}" in content
        )

    def test_decided_true_combined_keeps_exact_pair_key(self, client) -> None:
        doctor = _login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-combined-catalog@test", password="testpass123")
        nir.roles.add(_create_role("nir"))
        _make_case(
            nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            declared=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            detected=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            approved=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            doctor=doctor,
            name="Combinado",
            record="DEC-COMB",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert 'data-proc-selection="eda_colonoscopy"' in content
        assert "EDA + Colonoscopia" in content
        # Sem divergência detectado/autorizado não há texto de transformação.
        assert "Autorizado:" not in content

    def test_decided_combined_partially_approved_keeps_transformation(self, client) -> None:
        doctor = _login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-partial-catalog@test", password="testpass123")
        nir.roles.add(_create_role("nir"))
        _make_case(
            nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            declared=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            detected=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            approved=(ProcedureType.EDA,),
            denied=(ProcedureType.COLONOSCOPY,),
            doctor=doctor,
            name="Combinado Parcial",
            record="DEC-PART",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert 'data-proc-selection="eda"' in content
        assert "Detectado: EDA + Colonoscopia · Autorizado: EDA" in content

    def test_decided_package_singleton_has_no_transformation(self, client) -> None:
        doctor = _login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-pkg-catalog@test", password="testpass123")
        nir.roles.add(_create_role("nir"))
        _make_case(
            nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            declared=(ProcedureType.EDA_DILATION,),
            detected=(ProcedureType.EDA_DILATION,),
            approved=(ProcedureType.EDA_DILATION,),
            doctor=doctor,
            name="Dilatação Mantida",
            record="DEC-DIL",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert f'data-proc-selection="{ProcedureType.EDA_DILATION}"' in content
        assert f">{PROCEDURE_LABELS[ProcedureType.EDA_DILATION]}</span>" in content
        assert "Autorizado:" not in content


# ── R2: transformação textual sem inbox ───────────────────────────────────


@pytest.mark.django_db
class TestDoctorCatalogTransformationWithoutNotification:
    """A transformação textual usa o mecanismo existente e não cria inbox (R2)."""

    def test_transformation_is_textual_and_creates_no_user_notification(self, client) -> None:
        doctor = _login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-notify-catalog@test", password="testpass123")
        nir.roles.add(_create_role("nir"))
        _make_case(
            nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA,),
            approved=(ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,),
            denied=(ProcedureType.EDA,),
            doctor=doctor,
            name="Troca Argônio",
            record="DEC-ARG",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        label = PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_ARGON]
        assert f"Detectado: EDA · Autorizado: {label}" in content
        assert UserNotification.objects.count() == 0


# ── R7: template itera e script inicializa pelo DOM ───────────────────────


class TestDoctorCatalogQueueStatic:
    """Inspeção estática do template/script (R7) — sem runner JS."""

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_template_iterates_projected_options(self) -> None:
        html = self._read(QUEUE_HTML)
        assert html.count("{% for option in procedure_filter_options %}") == 2
        assert 'data-exam-type-count="{{ option.key }}"' in html
        assert 'data-exam-type-label="{{ option.label }}"' in html
        # Nenhuma opção/label literal permanece no template.
        for key in SELECTION_KEYS:
            assert f'value="{key}"' not in html, f"opção literal no template: {key}"
        assert 'value="none"' not in html
        assert "Nenhum autorizado" not in html
        assert ">EDA<" not in html

    def test_script_initializes_counts_from_rendered_elements(self) -> None:
        """R7: chaves/contagens vêm dos elementos renderizados, não de lista fixa."""
        js = self._read(QUEUE_FILTER_JS)
        literal = re.search(r"var counts = \{([^}]*)\}", js)
        assert literal is not None
        assert literal.group(1).strip() == "", "objeto literal fechado de tipos no script"
        assert "[data-exam-type-count]" in js
        assert 'getAttribute("data-exam-type-count")' in js
        assert "emptyCounts" in js

    def test_script_reads_scope_label_from_rendered_element(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert 'getAttribute("data-exam-type-label")' in js
        # Nenhuma lista fechada de labels no script.
        for label in ("Ecoendoscopia", "CPRE", "EDA + Colonoscopia", "Nenhum autorizado", "Colonoscopia"):
            assert f'return "{label}"' not in js
        assert "scopeLabel" in js

    def test_script_keeps_composed_filter_and_polling(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert 'card.getAttribute("data-proc-selection")' in js
        assert "data-doctor-exam-filter" in js
        assert "htmx:afterSwap" in js
        assert "clearFilter" in js
        assert 'searchInput.value = ""' in js
        assert "casos" in js

    def test_plus_labels_never_trigger_paired_reasoning(self) -> None:
        """R4: a fila médica não deriva identidade/casado de label com "+"."""
        assert PLUS_LABEL_CODES, "catálogo sem identidades com '+' na label"
        js = self._read(QUEUE_FILTER_JS)
        html = self._read(QUEUE_HTML)
        for source in (js, html):
            assert 'split("+")' not in source
            assert "Agendamento casado" not in source
