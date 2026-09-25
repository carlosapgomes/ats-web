"""Slice 006 — Decisão médica pelo catálogo ampliado (R1–R4, R6–R7).

Cobertura canônica (Django/HTML/POST) da jornada médica de decisão/troca:

- **R1:** o médico decide/nega qualquer identidade canônica; um pacote é UMA
  row e somente EDA + Colonoscopia mantém duas decisões independentes;
- **R2:** a inclusão/substituição usa um combobox pesquisável com TODOS os
  destinos canônicos (o médico não é limitado pelas flags de intake); alias,
  texto livre e ``eda_colonoscopy`` como ``ProcedureType`` são rejeitados;
- **R3:** troca válida nega a origem e aprova o destino com razões, usando o
  evento/mensagem existentes e SEM reexecutar LLM, fila, orchestrator ou
  policy do destino;
- **R4:** o conjunto final aceita singleton canônico ou o par exato
  EDA + Colonoscopia; reter um componente e adicionar variação falha de forma
  atômica (nenhuma row/evento/FSM parcial);
- **R6:** destino não analisado NUNCA recebe painel GTT nem local de dilatação
  sintetizados (os detalhes ficam somente na origem analisada);
- **R7:** lock, fluxos de admissão e banner de erro existentes permanecem.
"""

from __future__ import annotations

import re
from typing import Any
from unittest import mock

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    ProcedureType,
)
from apps.cases.procedures import (
    PROCEDURE_ORDER,
    SUPPORTED_PROCEDURE_TYPES,
    get_approved_procedure_types,
)
from apps.doctor.forms import SELECTABLE_PROCEDURE_TYPES

User = get_user_model()

# Identidades atômicas (pacote/singleton): cada uma é UMA row de decisão.
ATOMIC_IDENTITIES = tuple(SUPPORTED_PROCEDURE_TYPES)

# Affordances de busca do destino médico (Slice 002, R3/D2/D3).
SEARCH_HINT = "Busca ignora acentos e aceita sinônimos aprovados. Navegue com ↑ ↓ e confirme com Enter."
DESTINATION_SEARCH_PLACEHOLDER = "Buscar procedimento de destino…"
DESTINATION_SEARCH_HINT_ID = "destination-procedure-search-hint"


def _v4_structured(detected: list[str]) -> dict[str, Any]:
    """structured_data 4.0 mínimo com o conjunto detectado de teste."""
    return {
        "schema_version": "4.0",
        "patient": {"name": "Paciente Catálogo", "age": 52, "sex": "F"},
        "common_preop": {
            "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
            "ecg": {"report_present": "yes", "abnormal_flag": "no"},
        },
        "requested_procedures": [{"procedure_type": t, "evidence_spans": [{"excerpt": "x"}]} for t in detected],
    }


def _hint_paragraph(html: str, hint_id: str) -> str:
    """Parágrafo do hint persistente de busca da superfície."""
    match = re.search(
        r'<p class="form-text procedure-combobox__hint" id="' + re.escape(hint_id) + r'">(.*?)</p>',
        html,
        re.DOTALL,
    )
    assert match is not None, f"hint persistente de busca ausente: {hint_id}"
    return match.group(0)


@pytest.mark.django_db
class TestExpandedProcedureDecision:
    """Jornada médica de decisão/troca sobre o catálogo de dez identidades."""

    # ── Infra ────────────────────────────────────────────────────────────

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}_cat@test.com", password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_case(
        self,
        *,
        detected: list[str],
        declared: list[str] | None = None,
        status: str = CaseStatus.WAIT_DOCTOR,
        suggested_action: dict[str, Any] | None = None,
    ) -> Case:
        declared = declared if declared is not None else detected
        nir = User.objects.create_user(username=f"nir_cat_{'_'.join(detected)}@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        case = Case.objects.create(
            created_by=nir,
            status=status,
            agency_record_number="ARN-CAT-001",
            structured_data=_v4_structured(detected),
            suggested_action=suggested_action or {"schema_version": "4.0", "procedure_recommendations": []},
        )
        for procedure_type in sorted(set(declared) | set(detected), key=lambda t: PROCEDURE_ORDER[t]):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=procedure_type,
                declared_by_nir=procedure_type in declared,
                detection_status=(
                    DetectionStatus.DETECTED if procedure_type in detected else DetectionStatus.NOT_DETECTED
                ),
            )
        return case

    def _claim_lock(self, case_id, doctor) -> str:
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        return str(result.token)

    def _submit(
        self,
        client,
        case: Case,
        *,
        procedures: dict[str, dict[str, str]] | None = None,
        destination: str = "",
        destination_reason: str = "",
        support_flag: str = "",
        admission_flow: str = "",
        token: str | None = None,
        **extra: str,
    ):
        data: dict[str, str] = {"lock_token": token or ""}
        for procedure_type, spec in (procedures or {}).items():
            data[f"procedure_{procedure_type}"] = spec.get("disposition", "")
            data[f"procedure_{procedure_type}_reason"] = spec.get("reason", "")
        if destination:
            data["destination_procedure"] = destination
        if destination_reason:
            data["destination_reason"] = destination_reason
        if support_flag:
            data["support_flag"] = support_flag
        if admission_flow:
            data["admission_flow"] = admission_flow
        data.update(extra)
        return client.post(f"/doctor/{case.case_id}/submit/", data=data)

    def _detected_row_count(self, html: str) -> int:
        """Número de rows marcadas como detectadas na análise."""
        return html.count("Detectado na análise")

    # ── R1: toda identidade é decidível; pacote é uma row ────────────────

    def test_selectable_types_cover_the_full_catalog(self) -> None:
        """A superfície selecionável é o catálogo inteiro (não quatro tipos)."""
        assert SELECTABLE_PROCEDURE_TYPES == SUPPORTED_PROCEDURE_TYPES
        assert len(SELECTABLE_PROCEDURE_TYPES) == 10
        assert set(SELECTABLE_PROCEDURE_TYPES) == {t for t in ProcedureType.values}

    @pytest.mark.parametrize("identity", ATOMIC_IDENTITIES)
    def test_each_atomic_identity_is_decidable_as_singleton(self, client, identity: str) -> None:
        """Aprovar qualquer identidade atômica compõe o singleton autorizado."""
        case = self._make_case(detected=[identity])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={identity: {"disposition": "approved", "reason": ""}},
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == (identity,)

    def test_package_identity_is_a_single_detected_row(self, client) -> None:
        """EDA + GTT é UMA row detectada (o pacote nunca é dividido na base)."""
        case = self._make_case(detected=[ProcedureType.EDA_GASTROSTOMY])
        self._login(client, "doctor")

        html = client.get(f"/doctor/{case.case_id}/").content.decode()

        assert self._detected_row_count(html) == 1
        assert html.count('name="procedure_eda_gastrostomy"') == 1
        # O pacote não é dividido em uma row EDA separada.
        assert 'name="procedure_eda"' not in html
        case = Case.objects.get(pk=case.pk)
        assert case.procedures.count() == 1

    def test_non_detected_identities_have_no_decision_row(self, client) -> None:
        """Rows de decisão existem só para o detectado; destinos via combobox (D9)."""
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")

        html = client.get(f"/doctor/{case.case_id}/").content.decode()

        assert self._detected_row_count(html) == 1
        assert 'name="procedure_eda"' in html
        for code in SUPPORTED_PROCEDURE_TYPES:
            if code == ProcedureType.EDA:
                continue
            assert f'name="procedure_{code}"' not in html, code

    def test_eda_colonoscopy_keeps_two_independent_rows(self, client) -> None:
        """Somente EDA + Colonoscopia mantém duas decisões independentes."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")

        html = client.get(f"/doctor/{case.case_id}/").content.decode()
        assert self._detected_row_count(html) == 2

        token = self._claim_lock(case.case_id, doctor)
        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "approved", "reason": ""},
                ProcedureType.COLONOSCOPY: {"disposition": "denied", "reason": "Sem indicação"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert get_approved_procedure_types(case) == (ProcedureType.EDA,)
        assert case.procedures.get(procedure_type=ProcedureType.COLONOSCOPY).doctor_disposition == "denied"

    # ── R2: combobox de destino canônico ─────────────────────────────────

    def test_destination_combobox_offers_all_canonical_codes(self, client) -> None:
        """Um único combobox pesquisável oferece os dez destinos canônicos."""
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")

        html = client.get(f"/doctor/{case.case_id}/").content.decode()
        select = re.search(r'<select[^>]*name="destination_procedure"[^>]*>.*?</select>', html, re.S)
        assert select is not None, "combobox de destino ausente na decisão médica"
        markup = select.group(0)
        assert "data-procedure-combobox" in markup, "destino não usa o combobox progressivo"
        values = [value for value in re.findall(r'<option value="([^"]*)"', markup) if value]
        assert values == list(SUPPORTED_PROCEDURE_TYPES)
        assert "eda_colonoscopy" not in values, "chave derivada não é ProcedureType de destino"

    def test_destination_selection_has_own_justification_control(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")
        html = client.get(f"/doctor/{case.case_id}/").content.decode()
        assert re.search(r'<textarea[^>]*name="destination_reason"', html)

    def test_js_asset_is_loaded_for_the_decision_page(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")
        html = client.get(f"/doctor/{case.case_id}/").content.decode()
        assert "js/procedure_combobox.js" in html

    def test_destination_search_affordances_are_wired(self, client) -> None:
        """R3/D2/D3: placeholder do destino e hint persistente associado ao select."""
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")

        html = client.get(f"/doctor/{case.case_id}/").content.decode()
        select = re.search(r'<select[^>]*name="destination_procedure"[^>]*>', html)
        assert select is not None, "combobox de destino ausente na decisão médica"
        assert f'data-combobox-placeholder="{DESTINATION_SEARCH_PLACEHOLDER}"' in select.group(0)
        assert f'aria-describedby="{DESTINATION_SEARCH_HINT_ID}"' in select.group(0)
        assert SEARCH_HINT in _hint_paragraph(html, DESTINATION_SEARCH_HINT_ID)

    @pytest.mark.parametrize(
        "value",
        ["GTT", "gastrostomia", "eda_colonoscopy", "EDA + GTT", "capsula", "eda-dilation"],
    )
    def test_alias_free_text_and_derived_key_are_rejected(self, client, value: str) -> None:
        """Alias/texto livre/chave derivada como destino nunca é aceito."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
            destination=value,
            destination_reason="destino inválido",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        assert case.procedures.get(procedure_type=ProcedureType.EDA).doctor_disposition == "pending"
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()

    def test_destination_without_reason_when_not_detected_is_rejected(self, client) -> None:
        """Aprovar destino não detectado exige justificativa própria."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
            destination=ProcedureType.CPRE,
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert get_approved_procedure_types(case) == ()

    # ── R3: troca via combobox nega origem / aprova destino ──────────────

    def test_combobox_swap_to_specialized_denies_origin_approves_destination(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "Substituída por CPRE"}},
            destination=ProcedureType.CPRE,
            destination_reason="CPRE indicada para via biliar",
            support_flag="anesthesist",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.status == CaseStatus.WAIT_APPT
        eda_row = case.procedures.get(procedure_type=ProcedureType.EDA)
        cpre_row = case.procedures.get(procedure_type=ProcedureType.CPRE)
        assert eda_row.doctor_disposition == "denied"
        assert eda_row.doctor_reason == "Substituída por CPRE"
        assert cpre_row.doctor_disposition == "approved"
        assert cpre_row.doctor_reason == "CPRE indicada para via biliar"
        assert get_approved_procedure_types(case) == (ProcedureType.CPRE,)

        event = CaseEvent.objects.get(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED")
        decisions = {d["procedure_type"]: d for d in event.payload["decisions"]}
        assert decisions[ProcedureType.CPRE]["added_by_doctor"] is True
        changed = CaseEvent.objects.get(case=case, event_type="DOCTOR_PROCEDURE_SET_CHANGED")
        assert changed.payload["approved"] == [ProcedureType.CPRE]

    def test_combobox_swap_to_package_denies_origin_approves_destination(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
            destination=ProcedureType.EDA_DILATION,
            destination_reason="Dilatação esofágica indicada",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert get_approved_procedure_types(case) == (ProcedureType.EDA_DILATION,)
        assert case.procedures.get(procedure_type=ProcedureType.EDA).doctor_disposition == "denied"

    def test_combobox_swap_does_not_call_llm_queue_or_policy(self, client) -> None:
        """Spies provam ausência de rerun/repolicy/enfileiramento no destino."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        with (
            mock.patch("apps.pipeline.orchestrator.run_pipeline") as run_pipeline,
            mock.patch("apps.pipeline.tasks.enqueue_pipeline") as enqueue_pipeline,
            mock.patch("apps.pipeline.tasks.async_task") as async_task,
            mock.patch("apps.pipeline.policy.procedure_policy.evaluate_procedure_policy") as evaluate_policy,
        ):
            response = self._submit(
                client,
                case,
                procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
                destination=ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
                destination_reason="troca sem reanálise",
                support_flag="none",
                admission_flow="scheduled",
                token=token,
            )

        assert response.status_code == 302
        run_pipeline.assert_not_called()
        enqueue_pipeline.assert_not_called()
        async_task.assert_not_called()
        evaluate_policy.assert_not_called()
        case = Case.objects.get(pk=case.pk)
        assert get_approved_procedure_types(case) == (ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,)

    def test_adding_destination_to_approved_row_amplia_combinado(self, client) -> None:
        """Ampliação EDA → EDA + Colonoscopia via combobox (justificativa obrigatória)."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "approved", "reason": ""}},
            destination=ProcedureType.COLONOSCOPY,
            destination_reason="Rastreio colorretal associado",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert get_approved_procedure_types(case) == (ProcedureType.EDA, ProcedureType.COLONOSCOPY)

    # ── R4: matriz fechada, atômica ──────────────────────────────────────

    def test_keep_component_and_add_variation_fails_atomically(self, client) -> None:
        """Manter Colonoscopia e adicionar variação é incompatível: zero write."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.COLONOSCOPY: {"disposition": "approved", "reason": ""}},
            destination=ProcedureType.EDA_DILATION,
            destination_reason="inclusão indevida",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        for row in case.procedures.all():
            assert row.doctor_disposition == "pending"
            assert row.doctor_reason == ""
        assert not case.procedures.filter(procedure_type=ProcedureType.EDA_DILATION).exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()

    def test_combined_full_replacement_via_combobox(self, client) -> None:
        """{EDA, Colonoscopia} substituído integralmente por uma Retossigmoidoscopia."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                ProcedureType.COLONOSCOPY: {"disposition": "denied", "reason": "troca"},
            },
            destination=ProcedureType.RECTOSIGMOIDOSCOPY,
            destination_reason="substitui ambos",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert get_approved_procedure_types(case) == (ProcedureType.RECTOSIGMOIDOSCOPY,)

    def test_service_guard_rejects_incompatible_decisions_without_write(self) -> None:
        """Guarda transacional: conjunto incompatível falha antes de qualquer write."""
        from apps.cases.procedures import record_doctor_procedure_decisions

        case = self._make_case(detected=[ProcedureType.EDA])
        with pytest.raises(ValueError):
            record_doctor_procedure_decisions(
                case=case,
                decisions=[
                    {
                        "procedure_type": ProcedureType.EDA,
                        "disposition": "approved",
                        "reason": "",
                        "added_by_doctor": False,
                    },
                    {
                        "procedure_type": ProcedureType.EDA_DILATION,
                        "disposition": "approved",
                        "reason": "inclusão",
                        "added_by_doctor": True,
                    },
                ],
            )
        case = Case.objects.get(pk=case.pk)
        assert case.procedures.get(procedure_type=ProcedureType.EDA).doctor_disposition == "pending"
        assert not case.procedures.filter(procedure_type=ProcedureType.EDA_DILATION).exists()

    # ── R6: detalhes consultivos não são sintetizados no destino ─────────

    def test_destination_never_gets_synthesized_consultive_details(self, client) -> None:
        """Destino incluído pelo médico não ganha painel GTT nem local de dilatação."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        # Falta suporte/fluxo → re-render com o formulário preenchido.
        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "approved", "reason": ""}},
            destination=ProcedureType.EDA_GASTROSTOMY,
            destination_reason="GTT indicada",
            token=token,
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert "Revisão infecciosa consultiva" not in html
        assert "Local da dilatação" not in html

    def test_presenter_does_not_synthesize_details_for_swapped_destination(self) -> None:
        """O relatório descreve somente o detectado; destino trocado não sintetiza detalhe."""
        from apps.doctor.reporting import prepare_doctor_case_report
        from apps.pipeline.infection_review import INFECTION_EVIDENCE_ARTIFACT_KEY

        case = self._make_case(detected=[ProcedureType.EDA])
        # Destino incluído pelo médico, sem nova análise.
        CaseProcedure.objects.create(
            case=case,
            procedure_type=ProcedureType.EDA_GASTROSTOMY,
            detection_status=DetectionStatus.NOT_DETECTED,
            doctor_disposition="approved",
        )
        case.suggested_action = {"schema_version": "4.0", "procedure_recommendations": []}
        case.save(update_fields=["suggested_action"])

        report = prepare_doctor_case_report(case).presenter.build_report()

        assert report["infection_review"] is None
        assert INFECTION_EVIDENCE_ARTIFACT_KEY not in (case.suggested_action or {})
        section_types = [section["procedure_type"] for section in report["procedure_sections"]]
        assert ProcedureType.EDA_GASTROSTOMY not in section_types
        assert section_types == [ProcedureType.EDA]

    # ── R7: lock, fluxos e banner permanecem ─────────────────────────────

    def test_invalid_lock_blocks_destination_swap_without_writes(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
            destination=ProcedureType.CPRE,
            destination_reason="troca",
            support_flag="none",
            admission_flow="scheduled",
            token="00000000-0000-0000-0000-000000000000",
        )
        assert response.status_code == 200
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        assert get_approved_procedure_types(case) == ()

    def test_error_banner_is_rendered_on_invalid_destination(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
            destination=ProcedureType.EDA_DILATION,
            destination_reason="",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert "decision-error-banner" in html
        assert "Não foi possível salvar a decisão." in html
        # R4: hint e associação sobrevivem ao re-render com erro.
        assert f'aria-describedby="{DESTINATION_SEARCH_HINT_ID}"' in html
        assert SEARCH_HINT in _hint_paragraph(html, DESTINATION_SEARCH_HINT_ID)

    def test_destination_swap_operational_notice_flow(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.CPRE])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={},
            destination="",
            support_flag="none",
            admission_flow="immediate",
            token=token,
        )
        # CPRE detectada exige disposição própria; sem destino preenchido nada é aceito.
        assert response.status_code == 200

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.CPRE: {"disposition": "approved", "reason": ""}},
            support_flag="none",
            admission_flow="immediate",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert CaseEvent.objects.filter(case=case, event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE").exists()

    # ── Review fix round 1 (P1): submissão dupla ambígua é fail-closed ───

    def test_dual_submission_same_procedure_is_rejected_without_writes(self, client) -> None:
        """Destino + row do MESMO procedimento com razões diferentes → erro, zero write.

        Sem a guarda, a razão do destino era validada e descartada em silêncio
        (a row vencia). Fail-closed: nenhuma das duas vias persiste — nada de
        row, evento ou transição FSM.
        """
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "approved", "reason": "razão da row"}},
            destination=ProcedureType.EDA,
            destination_reason="razão do destino",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert "decision-error-banner" in html
        assert "dois caminhos" in html

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        row = case.procedures.get(procedure_type=ProcedureType.EDA)
        assert row.doctor_disposition == "pending"
        assert row.doctor_reason == ""
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_SET_CHANGED").exists()

    def test_destination_for_other_procedure_with_row_decision_still_works(self, client) -> None:
        """Destino para procedimento DISTINTO da row decidida continua válido (sem overlap)."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "approved", "reason": ""}},
            destination=ProcedureType.COLONOSCOPY,
            destination_reason="Rastreio colorretal associado",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert get_approved_procedure_types(case) == (ProcedureType.EDA, ProcedureType.COLONOSCOPY)

    def test_rows_only_path_still_works(self, client) -> None:
        """Caminho somente-rows (sem destino) permanece aceito (regressão)."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "approved", "reason": ""}},
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        assert get_approved_procedure_types(Case.objects.get(pk=case.pk)) == (ProcedureType.EDA,)

    def test_destination_only_path_still_works(self, client) -> None:
        """Caminho somente-destino (troca via combobox) permanece aceito (regressão)."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.EDA: {"disposition": "denied", "reason": "troca"}},
            destination=ProcedureType.CPRE,
            destination_reason="CPRE indicada para via biliar",
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        assert get_approved_procedure_types(Case.objects.get(pk=case.pk)) == (ProcedureType.CPRE,)
