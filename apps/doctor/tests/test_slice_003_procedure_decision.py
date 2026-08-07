"""Slice 003 — Decisão médica por procedimento (form + submit v2).

Cobre os REDs 1–11 e 17 do slice:

- RED 1: combinado permite approve/deny independentes;
- RED 2: partial accept → Case accept e somente aprovado no conjunto autorizado;
- RED 3: all denied → deny;
- RED 4: razão obrigatória por negado;
- RED 5: inclusão sem razão inválida;
- RED 6: troca EDA→Colon exige duas razões;
- RED 7: EDA→both exige razão da Colon;
- RED 8: erro não persiste parcial/evento/transição;
- RED 9: inclusão não chama/enfileira LLM;
- RED 10: lock/status inválidos bloqueiam (role coberto por regressão);
- RED 11: suporte sugerido estrito exibido mas escolha final médica persiste;
- RED 17: fluxos accept/deny/admission existentes regressam verdes (v2 scheduled + operational notice).
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus, ProcedureType
from apps.cases.procedures import get_approved_procedure_types

User = get_user_model()

PROCEDURE_ORDER = (ProcedureType.EDA, ProcedureType.COLONOSCOPY)


def _v2_structured(patient_name: str = "Paciente V2") -> dict[str, Any]:
    """structured_data mínimo com contrato 2.0 (o suficiente para o modo v2)."""
    return {
        "schema_version": "2.0",
        "patient": {"name": patient_name, "age": 40, "sex": "F"},
        "common_preop": {
            "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
            "ecg": {"report_present": "yes", "abnormal_flag": "no"},
        },
        "requested_procedures": [
            {"procedure_type": t, "subtype": "standard", "evidence_spans": [{"excerpt": "x"}]}
            for t in ("eda", "colonoscopy")
        ],
    }


def _v2_suggested(*, global_support: str = "none") -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "procedure_recommendations": [
            {"procedure_type": "eda", "suggestion": "accept", "support_recommendation": "none"},
            {"procedure_type": "colonoscopy", "suggestion": "accept", "support_recommendation": "anesthesist"},
        ],
        "global_support_recommendation": global_support,
    }


@pytest.mark.django_db
class TestProcedureDecisionFormAndSubmit:
    """Fluxo completo: form por procedimento + submit atômico + FSM."""

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}_s3@test.com", password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_v2_case(
        self,
        *,
        detected: list[str],
        declared: list[str] | None = None,
        status: str = CaseStatus.WAIT_DOCTOR,
        global_support: str = "none",
        doctor: Any = None,
        doctor_decision: str = "",
    ) -> Case:
        declared = declared or detected
        nir = User.objects.create_user(username=f"nir_s3_{detected}@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        case = Case.objects.create(
            created_by=nir,
            status=status,
            exam_type="eda_colonoscopy" if len(declared) == 2 else declared[0],
            agency_record_number="ARN-S3-001",
            structured_data=_v2_structured(),
            suggested_action=_v2_suggested(global_support=global_support),
        )
        for pt in PROCEDURE_ORDER:
            row = CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=pt in declared,
                detection_status=DetectionStatus.DETECTED if pt in detected else DetectionStatus.NOT_DETECTED,
            )
            if doctor_decision and doctor:
                row.doctor_disposition = "approved" if doctor_decision == "accept" else "denied"
                row.save(update_fields=["doctor_disposition"])
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
        procedures: dict[str, dict[str, str]],
        support_flag: str = "",
        admission_flow: str = "",
        observation: str = "",
        token: str | None = None,
    ) -> Any:
        data: dict[str, str] = {"lock_token": token or ""}
        for pt, spec in procedures.items():
            data[f"procedure_{pt}"] = spec.get("disposition", "")
            data[f"procedure_{pt}_reason"] = spec.get("reason", "")
        if support_flag:
            data["support_flag"] = support_flag
        if admission_flow:
            data["admission_flow"] = admission_flow
        if observation:
            data["observation"] = observation
        return client.post(f"/doctor/{case.case_id}/submit/", data=data)

    # ── RED 1: combinado permite approve/deny independentes ──────────────

    def test_combined_allows_independent_approve_deny(self, client) -> None:
        case = self._make_v2_case(detected=["eda", "colonoscopy"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "denied", "reason": "Sem indicação para colonoscopia"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.status == CaseStatus.WAIT_APPT
        eda_row = case.procedures.get(procedure_type="eda")
        colon_row = case.procedures.get(procedure_type="colonoscopy")
        assert eda_row.doctor_disposition == "approved"
        assert eda_row.doctor_reason == ""
        assert colon_row.doctor_disposition == "denied"
        assert colon_row.doctor_reason == "Sem indicação para colonoscopia"

    # ── RED 2: partial accept → Case accept e somente aprovado no conjunto ──

    def test_partial_accept_maps_to_case_accept_and_authorized_set(self, client) -> None:
        case = self._make_v2_case(detected=["eda", "colonoscopy"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "denied", "reason": "recusa"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == ("eda",)

    # ── RED 3: all denied → deny ─────────────────────────────────────────

    def test_all_denied_maps_to_deny(self, client) -> None:
        case = self._make_v2_case(detected=["eda", "colonoscopy"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "denied", "reason": "sem critério"},
                "colonoscopy": {"disposition": "denied", "reason": "sem indicação"},
            },
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "deny"
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_approved_procedure_types(case) == ()

    # ── RED 4: razão obrigatória por negado ──────────────────────────────

    def test_denied_requires_reason_per_component(self, client) -> None:
        case = self._make_v2_case(detected=["eda", "colonoscopy"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "denied", "reason": ""},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200  # re-render com erros

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == ""
        assert case.status == CaseStatus.WAIT_DOCTOR
        colon_row = case.procedures.get(procedure_type="colonoscopy")
        assert colon_row.doctor_disposition == "pending"
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_ACCEPT").exists()

    # ── RED 5: inclusão sem razão inválida ───────────────────────────────

    def test_inclusion_without_reason_invalid(self, client) -> None:
        # Detectado apenas EDA; inclusão de Colonoscopia sem justificativa.
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "approved", "reason": ""},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == ""
        assert case.status == CaseStatus.WAIT_DOCTOR
        colon_row = case.procedures.get(procedure_type="colonoscopy")
        assert colon_row.doctor_disposition == "pending"

    # ── RED 6: troca EDA→Colon exige duas razões ─────────────────────────

    def test_eda_to_colon_swap_requires_two_reasons(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        # Negou EDA sem razão + incluiu Colon sem razão → inválido.
        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "denied", "reason": ""},
                "colonoscopy": {"disposition": "approved", "reason": ""},
            },
            token=token,
        )
        assert response.status_code == 200

        # Com ambas as razões → válido e somente Colon autorizada.
        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "denied", "reason": "EDA não indicada"},
                "colonoscopy": {"disposition": "approved", "reason": "Indicação clínica de rastreio"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == ("colonoscopy",)
        eda_row = case.procedures.get(procedure_type="eda")
        colon_row = case.procedures.get(procedure_type="colonoscopy")
        assert eda_row.doctor_disposition == "denied"
        assert eda_row.doctor_reason == "EDA não indicada"
        assert colon_row.doctor_disposition == "approved"
        assert colon_row.doctor_reason == "Indicação clínica de rastreio"

    # ── RED 7: EDA→both exige razão da Colon ─────────────────────────────

    def test_eda_to_both_requires_colon_reason(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "approved", "reason": ""},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200  # inclusão sem razão → inválido

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == ""
        assert case.status == CaseStatus.WAIT_DOCTOR

    # ── RED 8: erro não persiste parcial/evento/transição ────────────────

    def _silent_client(self, user: Any) -> Any:
        """Client sem re-lançamento de exceção (para provar rollback atômico)."""
        from django.test import Client as TestClient

        silent = TestClient(raise_request_exception=False)
        silent.force_login(user)
        session = silent.session
        session["active_role"] = "doctor"
        session.save()
        return silent

    def test_error_persists_nothing(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        with mock.patch(
            "apps.doctor.views.record_doctor_procedure_decisions",
            side_effect=RuntimeError("falha atômica"),
        ):
            silent = self._silent_client(doctor)
            response = self._submit(
                silent,
                case,
                procedures={
                    "eda": {"disposition": "approved"},
                    "colonoscopy": {"disposition": "approved", "reason": "inclusão"},
                },
                support_flag="none",
                admission_flow="scheduled",
                token=token,
            )
        assert response.status_code == 500

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        assert case.doctor is None  # nada foi persistido (nenhum autor/transição)
        for row in case.procedures.all():
            assert row.doctor_disposition == "pending"
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_ACCEPT").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_DENY").exists()

    # ── RED 9: inclusão não chama/enfileira LLM ───────────────────────────

    def test_inclusion_does_not_rerun_llm(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        with mock.patch(
            "apps.pipeline.orchestrator._run_v2_pipeline",
            side_effect=AssertionError("LLM rerun não permitido no submit médico"),
        ) as v2_run:
            response = self._submit(
                client,
                case,
                procedures={
                    "eda": {"disposition": "approved"},
                    "colonoscopy": {"disposition": "approved", "reason": "inclusão clínica"},
                },
                support_flag="none",
                admission_flow="scheduled",
                token=token,
            )
        assert response.status_code == 302
        v2_run.assert_not_called()
        # Slice 007: o branch legado 1.1 (_run_llm1_step) foi removido do
        # orchestrator; o patch do caminho v2 prova que o submit médico nunca
        # reenfileira/executa o pipeline.

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="LLM").exists()

    # ── RED 10: lock/status inválidos bloqueiam ───────────────────────────

    def test_invalid_lock_token_blocks_without_writes(self, client) -> None:
        case = self._make_v2_case(detected=["eda", "colonoscopy"])
        self._login(client, "doctor")

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "denied", "reason": "x"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token="00000000-0000-0000-0000-000000000000",
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "reserva" in content.lower() or "lock" in content.lower() or "expirou" in content.lower()

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        assert (
            not CaseEvent.objects.filter(case=case)
            .exclude(event_type__in=["CASE_CREATED", "WORK_LOCK_CLAIMED"])
            .exists()
        )

    def test_submit_non_wait_doctor_returns_404(self, client) -> None:
        case = self._make_v2_case(detected=["eda"], status=CaseStatus.LLM_SUGGEST)
        self._login(client, "doctor")
        response = self._submit(
            client,
            case,
            procedures={"eda": {"disposition": "approved"}},
            support_flag="none",
            admission_flow="scheduled",
        )
        assert response.status_code == 404

    # ── RED 11: sugestão estrita exibida, escolha final médica persiste ──

    def test_strictest_support_suggestion_shown_but_doctor_choice_persists(self, client) -> None:
        # global_support_recommendation = anesthesist_icu (mais restritivo).
        case = self._make_v2_case(detected=["eda", "colonoscopy"], global_support="anesthesist_icu")
        self._login(client, "doctor")

        # GET: a sugestão estrita aparece (card e decisão).
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Anestesista + UTI" in content

        # POST: o médico escolhe anestesista (override) e persiste.
        doctor = User.objects.get(username="doctor_s3@test.com")
        token = self._claim_lock(case.case_id, doctor)
        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "denied", "reason": "recusa"},
            },
            support_flag="anesthesist",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_support_flag == "anesthesist"
        assert case.doctor_support_flag != "anesthesist_icu"

    # ── RED 17: fluxos existentes regressam verdes (v2) ──────────────────

    def test_v2_accept_scheduled_flow_regression(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={"eda": {"disposition": "approved"}},
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_APPT
        assert CaseEvent.objects.filter(case=case, event_type="SCHEDULER_REQUEST_POSTED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()
        assert CaseEvent.objects.filter(case=case, event_type="DOCTOR_ACCEPT").exists()

    def test_v2_accept_operational_notice_regression(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={"eda": {"disposition": "approved"}},
            support_flag="none",
            admission_flow="immediate",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert CaseEvent.objects.filter(case=case, event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE").exists()
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="SCHEDULER_REQUEST_POSTED").exists()

    def test_v2_all_denied_posts_final_reply(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={"eda": {"disposition": "denied", "reason": "sem critério clínico"}},
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert CaseEvent.objects.filter(case=case, event_type="DOCTOR_DENY").exists()
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

    # ── RED 8b: auditoria do evento por componente (R8) ───────────────────

    def test_event_records_dispositions_with_added_by_doctor(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "approved", "reason": "inclusão justificada"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        event = CaseEvent.objects.get(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED")
        payload = event.payload
        assert "decisions" in payload
        decisions = {d["procedure_type"]: d for d in payload["decisions"]}
        assert decisions["eda"]["disposition"] == "approved"
        assert decisions["eda"]["reason_present"] is False
        assert decisions["eda"]["added_by_doctor"] is False
        assert decisions["colonoscopy"]["disposition"] == "approved"
        assert decisions["colonoscopy"]["reason_present"] is True
        assert decisions["colonoscopy"]["added_by_doctor"] is True
        # Ordem canônica: EDA antes de Colonoscopia.
        assert [d["procedure_type"] for d in payload["decisions"]] == ["eda", "colonoscopy"]

    def test_inclusion_keeps_detection_and_declaration(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                "eda": {"disposition": "approved"},
                "colonoscopy": {"disposition": "approved", "reason": "inclusão"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        colon_row = case.procedures.get(procedure_type="colonoscopy")
        assert colon_row.declared_by_nir is False
        assert colon_row.detection_status == DetectionStatus.NOT_DETECTED
        assert colon_row.doctor_disposition == "approved"

    # ── RED 2/3/6 complemento: GET renderiza entradas por procedimento ───

    def test_decision_page_renders_per_procedure_entries(self, client) -> None:
        case = self._make_v2_case(detected=["eda"])
        self._login(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="procedure_eda"' in content
        assert 'name="procedure_colonoscopy"' in content
        assert 'name="procedure_eda_reason"' in content
        assert 'name="procedure_colonoscopy_reason"' in content
        # Origem declarada/detectada visível.
        assert "Detectado na análise" in content
