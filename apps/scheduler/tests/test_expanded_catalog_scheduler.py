"""Slice 008 — filas CHD pelo catálogo ampliado (R1, R3, R4, R5, R7).

- R1/R3: opções e contadores de Pendentes/Processados Hoje derivam do catálogo e
  usam o MESMO universo do predicado de consulta; o Histórico filtra por
  igualdade exata de código (EDA não entra no filtro de um pacote e vice-versa)
  e REJEITA dimensão desconhecida em vez de reclassificá-la para ``all``
  (fallback que permanece exclusivo dos filtros NIR).
- R4: ``Agendamento casado`` e o contador paired existem SOMENTE para o
  conjunto autorizado exatamente ``{eda, colonoscopy}``; labels com ``+`` nunca
  acionam a regra (igualdade de conjunto, nunca cardinalidade/texto).
- R5: agendar qualquer identidade mantém uma data/hora/local e o FSM/locks
  atuais.
- R7: templates iteram as opções projetadas e o script inicializa
  chaves/contagens pelos elementos renderizados, sem objeto literal fechado.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.cases.procedures import (
    PROCEDURE_LABELS,
    SELECTION_KEYS,
    SUPPORTED_PROCEDURE_TYPES,
    is_paired_appointment_set,
)
from apps.scheduler.views import (
    _HISTORICAL_DIMENSION_CHOICES,
    _empty_approved_selection_buckets,
)

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "scheduler" / "queue.html"
HISTORICAL_HTML = REPO_ROOT / "templates" / "scheduler" / "historical_search.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "scheduler_queue_filter.js"

# Universo derivado do catálogo: ``all`` + cada chave de seleção válida. A
# ORDEM dos controles CHD é a mesma dos buckets de contagem (o combinado fica
# ao lado de Colonoscopia) — predicado, contador e opção no mesmo universo.
CATALOG_FILTER_VALUES = ["all", *SELECTION_KEYS]
BUCKET_FILTER_VALUES = list(_empty_approved_selection_buckets().keys())

SELECTION_LABELS = {
    key: " + ".join(PROCEDURE_LABELS[part] for part in (("eda", "colonoscopy") if key == "eda_colonoscopy" else (key,)))
    for key in SELECTION_KEYS
}

# Identidades ATÔMICAS cujo label contém "+" (pacotes) — nunca podem acionar a
# regra textual do agendamento casado (R4).
PLUS_LABEL_CODES = tuple(code for code in SUPPORTED_PROCEDURE_TYPES if "+" in PROCEDURE_LABELS[code])


def _radio_values(html: str, name: str) -> list[str]:
    return re.findall(rf'name="{name}"[^>]*?value="([^"]+)"', html)


def _create_role(name: str) -> Any:
    role, _ = Role.objects.get_or_create(name=name)
    return role


def _login_as(client, role_name: str) -> Any:
    user = User.objects.create_user(
        username=f"{role_name}@catalog-scheduler-{uuid.uuid4().hex[:8]}@test", password="testpass123"
    )
    user.roles.add(_create_role(role_name))
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _make_case(
    nir: Any,
    *,
    status: str = CaseStatus.WAIT_APPT,
    approved: tuple[str, ...] = (),
    detected: tuple[str, ...] = (),
    scheduler: Any = None,
    appointment_status: str = "",
    name: str = "Paciente CHD",
    record: str = "CHD-001",
    admission_flow: str = "scheduled",
) -> Case:
    """Caso com rows por dimensão (fonte única) — nunca inferidas do campo."""
    case = Case.objects.create(
        created_by=nir,
        status=status,
        agency_record_number=record,
        doctor_decision="accept",
        doctor_admission_flow=admission_flow,
        doctor_support_flag="none",
        scheduler=scheduler,
        appointment_status=appointment_status,
        appointment_decided_at=timezone.now() if appointment_status else None,
        structured_data={"patient": {"name": name, "age": 58, "gender": "F"}},
    )
    for procedure_type in tuple(dict.fromkeys((*detected, *approved))):
        row = CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=procedure_type in detected,
        )
        fields: list[str] = []
        if procedure_type in detected:
            row.detection_status = DetectionStatus.DETECTED
            fields.append("detection_status")
        if procedure_type in approved:
            row.doctor_disposition = DoctorDisposition.APPROVED
            fields.append("doctor_disposition")
        if fields:
            row.save(update_fields=fields)
    return case


def _claim_lock(case_id, scheduler: Any) -> str:
    from apps.cases.services import claim_case_lock

    result = claim_case_lock(
        case_id=case_id,
        user=scheduler,
        expected_status=CaseStatus.WAIT_APPT,
        context="scheduler_confirm",
        role="scheduler",
    )
    assert result.acquired is True
    return str(result.token)


def _confirm_appointment(client, case: Case, *, token: str, date: str = "2026-10-05", hour: str = "09:15") -> Any:
    return client.post(
        f"/scheduler/{case.case_id}/submit/",
        data={
            "decision": "confirm",
            "appointment_date": date,
            "appointment_time": hour,
            "appointment_location": "Hospital Central - Sala de Endoscopia",
            "notes": "",
            "reason": "",
            "lock_token": token,
        },
    )


# ── R1/R3: opções e contadores derivados do catálogo ──────────────────────


@pytest.mark.django_db
class TestSchedulerCatalogQueueUniverse:
    def test_pending_options_match_the_counted_universe(self, client) -> None:
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        values = _radio_values(content, "scheduler-queue-exam-type")
        assert values == BUCKET_FILTER_VALUES
        assert set(values) == set(CATALOG_FILTER_VALUES)

    def test_processed_options_match_the_counted_universe(self, client) -> None:
        _login_as(client, "scheduler")
        content = client.get("/scheduler/?tab=processed").content.decode()
        values = _radio_values(content, "scheduler-processed-exam-type")
        assert values == BUCKET_FILTER_VALUES
        assert set(values) == set(CATALOG_FILTER_VALUES)

    def test_all_catalog_buckets_render_zero_when_empty(self, client) -> None:
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        for key in CATALOG_FILTER_VALUES:
            assert f'data-exam-type-count="{key}"' in content
        assert 'data-exam-type-count="eda_gastrostomy">0<' in content
        assert 'data-exam-type-count="rectosigmoidoscopy_argon">0<' in content
        assert 'data-exam-type-count="eda_colonoscopy">0<' in content

    def test_package_is_counted_as_its_own_identity(self, client) -> None:
        nir = _login_as(client, "nir")
        _make_case(
            nir,
            approved=(ProcedureType.EDA_DILATION,),
            detected=(ProcedureType.EDA_DILATION,),
            name="Pacote Dilatação",
            record="CHD-DIL",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert 'data-exam-type-count="eda_dilation">1<' in content
        assert 'data-exam-type-count="eda">0<' in content
        assert 'data-exam-type-count="eda_colonoscopy">0<' in content
        assert f'data-approved-selection="{ProcedureType.EDA_DILATION}"' in content
        assert f">{PROCEDURE_LABELS[ProcedureType.EDA_DILATION]}</span>" in content
        assert "Agendamento casado" not in content

    def test_retosigmoid_argon_counts_once_and_is_not_paired(self, client) -> None:
        nir = _login_as(client, "nir")
        _make_case(
            nir,
            approved=(ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,),
            detected=(ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,),
            name="Argônio CHD",
            record="CHD-ARG",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert 'data-exam-type-count="rectosigmoidoscopy_argon">1<' in content
        assert 'data-exam-type-count="rectosigmoidoscopy">0<' in content
        assert 'data-exam-type-count="eda_colonoscopy">0<' in content
        assert content.count(f'data-approved-selection="{ProcedureType.RECTOSIGMOIDOSCOPY_ARGON}"') == 1
        assert f">{PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_ARGON]}</span>" in content
        assert ">Retossigmoidoscopia</span>" not in content
        assert "Agendamento casado" not in content

    def test_true_combined_counts_once_as_paired(self, client) -> None:
        nir = _login_as(client, "nir")
        _make_case(
            nir,
            approved=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            detected=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            name="Combinado CHD",
            record="CHD-COMB",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert 'data-exam-type-count="eda_colonoscopy">1<' in content
        assert 'data-exam-type-count="eda">0<' in content
        assert 'data-exam-type-count="colonoscopy">0<' in content
        assert content.count('data-approved-selection="eda_colonoscopy"') == 1
        assert "EDA + Colonoscopia · Agendamento casado" in content

    def test_package_swap_shows_textual_transformation(self, client) -> None:
        """R2: CHD vê a comparação textual para as novas identidades (sem inbox)."""
        from apps.accounts.models import UserNotification

        nir = _login_as(client, "nir")
        _make_case(
            nir,
            approved=(ProcedureType.EDA_GASTROSTOMY,),
            detected=(ProcedureType.EDA,),
            name="Troca GTT",
            record="CHD-TRANS",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert (
            f"Detectado: {PROCEDURE_LABELS[ProcedureType.EDA]} · "
            f"Autorizado: {PROCEDURE_LABELS[ProcedureType.EDA_GASTROSTOMY]}" in content
        )
        assert UserNotification.objects.count() == 0

    def test_filter_remains_outside_polling_target_with_actions_intact(self, client) -> None:
        nir = _login_as(client, "nir")
        case = _make_case(
            nir,
            approved=(ProcedureType.EDA_GASTROSTOMY,),
            detected=(ProcedureType.EDA_GASTROSTOMY,),
            name="GTT Fila",
            record="CHD-GTT",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert 'id="scheduler-queue-type-filter"' in content
        assert 'hx-get="/scheduler/partials/queue/?tab=pending"' in content
        assert 'hx-trigger="every 20s"' in content
        assert f"/scheduler/{case.case_id}/immediate-ack/" not in content  # não é fluxo operacional
        assert f"/scheduler/{case.case_id}/" in content  # CTA de agendamento preservado


# ── R3: Histórico por código exato e rejeição de dimensão desconhecida ────


@pytest.mark.django_db
class TestSchedulerHistoricalCatalogExactness:
    def _historical(self, nir: Any, *, approved: tuple[str, ...], record: str, name: str = "Paciente") -> Case:
        return _make_case(
            nir,
            status=CaseStatus.CLEANED,
            approved=approved,
            detected=approved,
            appointment_status="confirmed",
            name=name,
            record=record,
        )

    def test_eda_filter_never_matches_a_package(self, client) -> None:
        nir = _login_as(client, "nir")
        self._historical(nir, approved=(ProcedureType.EDA,), record="HX-EDA-S")
        self._historical(nir, approved=(ProcedureType.EDA_DILATION,), record="HX-EDA-DIL")
        self._historical(nir, approved=(ProcedureType.EDA_GASTROSTOMY,), record="HX-EDA-GTT")
        _login_as(client, "scheduler")

        content = client.get("/scheduler/historical/?exam_type=eda").content.decode()
        assert "HX-EDA-S" in content
        assert "HX-EDA-DIL" not in content
        assert "HX-EDA-GTT" not in content

        content = client.get("/scheduler/historical/?exam_type=eda_dilation").content.decode()
        assert "HX-EDA-DIL" in content
        assert "HX-EDA-S" not in content
        assert "HX-EDA-GTT" not in content

    def test_package_filter_is_exact_code_not_family(self, client) -> None:
        nir = _login_as(client, "nir")
        self._historical(nir, approved=(ProcedureType.RECTOSIGMOIDOSCOPY,), record="HX-RECTO")
        self._historical(nir, approved=(ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,), record="HX-ARGON")
        _login_as(client, "scheduler")

        content = client.get("/scheduler/historical/?exam_type=rectosigmoidoscopy_argon").content.decode()
        assert "HX-ARGON" in content
        assert "HX-RECTO" not in content
        assert f">{PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_ARGON]}</span>" in content

        content = client.get("/scheduler/historical/?exam_type=rectosigmoidoscopy").content.decode()
        assert "HX-RECTO" in content
        assert "HX-ARGON" not in content

    def test_unknown_dimension_is_rejected_not_reclassified(self, client) -> None:
        """R3: dimensão desconhecida não vira ``all`` (fallback é só do NIR)."""
        nir = _login_as(client, "nir")
        self._historical(
            nir,
            approved=(ProcedureType.EDA,),
            record="HX-REJ-01",
            name="Paciente Rejeitado",
        )
        _login_as(client, "scheduler")

        content = client.get("/scheduler/historical/?exam_type=bogus&q=Paciente").content.decode()
        assert "HX-REJ-01" not in content
        assert "Nenhum caso encontrado" in content
        assert '<option value="bogus"' not in content

        # Sem termo: continua rejeitando em vez de listar todos os tipos.
        content = client.get("/scheduler/historical/?exam_type=eda_bogus").content.decode()
        assert "HX-REJ-01" not in content
        assert "Nenhum caso encontrado" in content

    def test_known_dimensions_still_list_results(self, client) -> None:
        nir = _login_as(client, "nir")
        self._historical(nir, approved=(ProcedureType.CPRE,), record="HX-CPRE")
        _login_as(client, "scheduler")
        content = client.get("/scheduler/historical/?exam_type=cpre").content.decode()
        assert "HX-CPRE" in content

    def test_nir_filter_keeps_all_fallback_while_chd_rejects(self, client) -> None:
        """R3: a assimetria é intencional — NIR cai para ``all``; CHD rejeita.

        O spec delta do change declara a rejeição do CHD como comportamento
        DELIBERADAMENTE distinto do fallback para ``all`` mantido nos filtros
        NIR (que permanece inalterado); este teste prova os dois lados.
        """
        nir = _login_as(client, "nir")
        nir_case = _make_case(
            nir,
            status=CaseStatus.NEW,
            approved=(),
            name="Paciente NIR Fallback",
            record="NIR-FB-01",
        )
        chd_case = self._historical(nir, approved=(ProcedureType.EDA,), record="HX-ASYM-01")

        nir_content = client.get(reverse("intake:my_cases") + "?exam_type=bogus").content.decode()
        assert str(nir_case.case_id) in nir_content  # NIR: valor inválido → Todos

        _login_as(client, "scheduler")
        chd_content = client.get("/scheduler/historical/?exam_type=bogus").content.decode()
        assert str(chd_case.case_id) not in chd_content  # CHD: rejeitado
        assert "Nenhum caso encontrado" in chd_content

    def test_select_options_cover_the_catalog_universe(self, client) -> None:
        _login_as(client, "scheduler")
        content = client.get("/scheduler/historical/").content.decode()
        select_html = content[content.index('id="exam-type-select"') : content.index("</select>")]
        assert re.findall(r'<option value="([^"]+)"', select_html) == BUCKET_FILTER_VALUES
        assert set(_HISTORICAL_DIMENSION_CHOICES) == set(CATALOG_FILTER_VALUES)


# ── R4: paired é igualdade exata de conjunto ──────────────────────────────


@pytest.mark.django_db
class TestSchedulerPairedRuleExactness:
    @pytest.mark.parametrize("code", PLUS_LABEL_CODES)
    def test_plus_label_identity_is_never_paired(self, client, code: str) -> None:
        """R4: identidade cuja label contém ``+`` nunca é agendamento casado."""
        assert is_paired_appointment_set((code,)) is False
        nir = _login_as(client, "nir")
        _make_case(
            nir,
            approved=(code,),
            detected=(code,),
            name=f"Pacote {code}",
            record=f"PAIR-{code[:10]}",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert "Agendamento casado" not in content
        assert f">{SELECTION_LABELS[code]}</span>" in content

    def test_only_exact_pair_is_paired(self) -> None:
        assert is_paired_appointment_set((ProcedureType.EDA, ProcedureType.COLONOSCOPY)) is True
        assert is_paired_appointment_set((ProcedureType.COLONOSCOPY, ProcedureType.EDA)) is True
        assert is_paired_appointment_set((ProcedureType.EDA_GASTROSTOMY, ProcedureType.COLONOSCOPY)) is False
        assert is_paired_appointment_set((ProcedureType.EDA, ProcedureType.EDA_CAPSULE)) is False

    def test_paired_predicate_never_uses_labels_or_cardinality(self) -> None:
        """R4: predicado é igualdade de conjunto — sem label, ``+`` ou ``len``."""
        import inspect

        from apps.cases.procedures import is_paired_appointment_set as predicate

        source = inspect.getsource(predicate)
        assert "PAIRED_APPOINTMENT_SET" in source
        assert "len(" not in source
        assert '"+"' not in source
        assert ".label" not in source

    def test_paired_suffix_only_for_the_exact_pair(self, client) -> None:
        nir = _login_as(client, "nir")
        _make_case(
            nir,
            approved=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            detected=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            name="Casado Real",
            record="PAIR-OK",
        )
        _make_case(
            nir,
            approved=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,),
            detected=(ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,),
            name="Pacote Dilatação Reto",
            record="PAIR-NO",
        )
        _login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert content.count("Agendamento casado") == 1
        assert "EDA + Colonoscopia · Agendamento casado" in content
        assert f">{PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_DILATION]}</span>" in content


# ── R5: uma data/hora/local e FSM/locks atuais para qualquer identidade ───


@pytest.mark.django_db
class TestSchedulerCatalogAppointment:
    def test_package_identity_keeps_single_appointment_and_fsm(self, client) -> None:
        nir = _login_as(client, "nir")
        case = _make_case(
            nir,
            approved=(ProcedureType.EDA_GASTROSTOMY,),
            detected=(ProcedureType.EDA_GASTROSTOMY,),
            name="GTT Agendada",
            record="APPT-GTT",
        )
        scheduler = _login_as(client, "scheduler")
        token = _claim_lock(case.case_id, scheduler)
        response = _confirm_appointment(client, case, token=token)
        assert response.status_code == 302

        confirmed = Case.objects.get(pk=case.pk)
        # FSM atual preservado: WAIT_APPT → APPT_CONFIRMED → resposta final.
        assert confirmed.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert confirmed.appointment_status == "confirmed"
        assert confirmed.appointment_at is not None
        assert confirmed.appointment_location == "Hospital Central - Sala de Endoscopia"
        assert timezone.localtime(confirmed.appointment_at).strftime("%d/%m/%Y %H:%M") == "05/10/2026 09:15"
        assert CaseEvent.objects.filter(case=confirmed, event_type="APPT_CONFIRMED").count() == 1

        content = client.get("/scheduler/?tab=processed").content.decode()
        assert 'data-approved-selection="eda_gastrostomy"' in content
        assert f">{PROCEDURE_LABELS[ProcedureType.EDA_GASTROSTOMY]}</span>" in content
        assert "Agendamento casado" not in content
        assert content.count("05/10/2026 09:15") == 1

    def test_specialized_identity_keeps_single_appointment(self, client) -> None:
        nir = _login_as(client, "nir")
        case = _make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.CPRE,),
            name="CPRE Agendada",
            record="APPT-CPRE",
        )
        scheduler = _login_as(client, "scheduler")
        token = _claim_lock(case.case_id, scheduler)
        assert _confirm_appointment(client, case, token=token, date="2026-10-06", hour="08:45").status_code == 302

        confirmed = Case.objects.get(pk=case.pk)
        assert confirmed.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert timezone.localtime(confirmed.appointment_at).strftime("%d/%m/%Y %H:%M") == "06/10/2026 08:45"

        content = client.get("/scheduler/?tab=processed").content.decode()
        assert f">{PROCEDURE_LABELS[ProcedureType.CPRE]}</span>" in content
        assert "Agendamento casado" not in content
        assert ">EDA</span>" not in content


# ── R7: templates iteram e script inicializa pelo DOM ─────────────────────


class TestSchedulerCatalogQueueStatic:
    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_queue_template_iterates_projected_options(self) -> None:
        html = self._read(QUEUE_HTML)
        assert html.count("{% for option in exam_type_options %}") == 1
        assert html.count("{% for option in processed_exam_type_options %}") == 1
        assert 'data-exam-type-count="{{ option.key }}"' in html
        assert 'data-exam-type-label="{{ option.label }}"' in html
        for key in SELECTION_KEYS:
            assert f'value="{key}"' not in html, f"opção literal no template: {key}"

    def test_historical_template_iterates_projected_options(self) -> None:
        html = self._read(HISTORICAL_HTML)
        assert "{% for option in exam_type_options %}" in html
        for key in SELECTION_KEYS:
            assert f'<option value="{key}"' not in html, f"opção literal no select: {key}"
        assert 'name="exam_type"' in html
        assert "Limpar" in html
        assert "exam_type_label" in html

    def test_script_initializes_counts_from_rendered_elements(self) -> None:
        """R7: chaves/contagens vêm dos elementos renderizados, não de lista fixa."""
        js = self._read(QUEUE_FILTER_JS)
        literal = re.search(r"var counts = \{([^}]*)\}", js)
        assert literal is not None
        assert literal.group(1).strip() == "", "objeto literal fechado de tipos no script"
        assert "[data-exam-type-count]" in js
        assert 'getAttribute("data-exam-type-count")' in js

    def test_script_reads_scope_label_from_rendered_element(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert 'getAttribute("data-exam-type-label")' in js
        for label in ("Ecoendoscopia", "CPRE", "EDA + Colonoscopia", "Colonoscopia", "EDA"):
            assert f'return "{label}"' not in js
        assert "scopeLabel" in js

    def test_script_keeps_projected_selection_and_polling(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert 'card.getAttribute("data-approved-selection")' in js
        assert "data-scheduler-exam-filter" in js
        assert "htmx:afterSwap" in js
        assert "scheduler-queue-content" in js
