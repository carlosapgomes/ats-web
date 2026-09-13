"""Slice 003 — troca médica especializada: manter, negar e trocar/aprovar.

Cobre R1–R4 do slice ``slice-003-echoendoscopy-doctor-swap-and-downstream`` e
R5 do slice ``slice-004-cpre-end-to-end``:

- R1: singleton pode ser mantido, negado ou trocado/aprovado como Ecoendoscopia
  (Slice 003) ou CPRE (Slice 004) com uma justificativa; o template médico tem
  campo próprio por procedimento (fim do ``{% else %}`` que ligava qualquer
  tipo não-EDA a Colonoscopia);
- R2: origem denied + destino approved persistem atomicamente — falha
  estrutural não deixa write parcial, evento ou transição;
- R3: a troca NÃO chama LLM, fila django-q2 nem policy, e não exibe
  sugestão/checklist do destino;
- R4/R5: substituição integral de combinado por especializado é aceita;
  conjunto parcial incompatível é rejeitado sem write.
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
from apps.cases.procedures import get_approved_procedure_types

User = get_user_model()

ALL_TYPES = (
    ProcedureType.EDA,
    ProcedureType.COLONOSCOPY,
    ProcedureType.ECHOENDOSCOPY,
    ProcedureType.CPRE,
)


def _v3_structured(detected: list[str]) -> dict[str, Any]:
    """structured_data 3.0 mínimo com o conjunto declarável de teste."""
    return {
        "schema_version": "3.0",
        "patient": {"name": "Paciente Swap", "age": 52, "sex": "F"},
        "common_preop": {
            "labs": {"hb_g_dl": 13.0, "platelets_per_mm3": 200000, "inr": 1.0},
            "ecg": {"report_present": "yes", "abnormal_flag": "no"},
        },
        "requested_procedures": [{"procedure_type": t, "evidence_spans": [{"excerpt": "x"}]} for t in detected],
    }


@pytest.mark.django_db
class TestSpecializedProcedureSwap:
    """Fluxo completo de troca/aprovação especializada via submit médico."""

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}_swap@test.com", password="testpass123")
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
    ) -> Case:
        declared = declared if declared is not None else detected
        nir = User.objects.create_user(username=f"nir_swap_{'_'.join(detected)}@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        case = Case.objects.create(
            created_by=nir,
            status=status,
            agency_record_number="ARN-SWAP-001",
            structured_data=_v3_structured(detected),
            suggested_action={"schema_version": "3.0", "procedure_recommendations": []},
        )
        for procedure_type in ALL_TYPES:
            if procedure_type not in declared and procedure_type not in detected:
                continue
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
        procedures: dict[str, dict[str, str]],
        support_flag: str = "",
        admission_flow: str = "",
        token: str | None = None,
        **extra: str,
    ):
        data: dict[str, str] = {"lock_token": token or ""}
        for procedure_type, spec in procedures.items():
            data[f"procedure_{procedure_type}"] = spec.get("disposition", "")
            data[f"procedure_{procedure_type}_reason"] = spec.get("reason", "")
        if support_flag:
            data["support_flag"] = support_flag
        if admission_flow:
            data["admission_flow"] = admission_flow
        data.update(extra)
        return client.post(f"/doctor/{case.case_id}/submit/", data=data)

    # ── R1: manter / negar / trocar-e-aprovar como Ecoendoscopia ─────────

    def test_swap_singleton_eda_to_echoendoscopy(self, client) -> None:
        """EDA declarada/detectada → negada; Ecoendoscopia → aprovada."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "Melhor caracterização por Eco"},
                ProcedureType.ECHOENDOSCOPY: {
                    "disposition": "approved",
                    "reason": "Ecoendoscopia indicada para caracterização",
                },
            },
            support_flag="anesthesist",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.status == CaseStatus.WAIT_APPT
        eda_row = case.procedures.get(procedure_type=ProcedureType.EDA)
        echo_row = case.procedures.get(procedure_type=ProcedureType.ECHOENDOSCOPY)
        assert eda_row.doctor_disposition == "denied"
        assert eda_row.doctor_reason == "Melhor caracterização por Eco"
        assert echo_row.doctor_disposition == "approved"
        assert echo_row.doctor_reason == "Ecoendoscopia indicada para caracterização"
        assert get_approved_procedure_types(case) == (ProcedureType.ECHOENDOSCOPY,)

    def test_keep_singleton_echoendoscopy(self, client) -> None:
        """Ecoendoscopia detectada pode ser mantida e aprovada."""
        case = self._make_case(detected=[ProcedureType.ECHOENDOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": ""}},
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == (ProcedureType.ECHOENDOSCOPY,)

    def test_deny_singleton_echoendoscopy_requires_reason(self, client) -> None:
        """Negar Ecoendoscopia exige razão e resulta em deny do caso."""
        case = self._make_case(detected=[ProcedureType.ECHOENDOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.ECHOENDOSCOPY: {"disposition": "denied", "reason": "Sem indicação"}},
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "deny"
        assert get_approved_procedure_types(case) == ()

    def test_echoendoscopy_row_has_own_field_binding(self, client) -> None:
        """Ramo próprio: erro/valor da linha de Ecoendoscopia não vaza de Colonoscopia."""
        case = self._make_case(detected=[ProcedureType.ECHOENDOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        # Negar sem razão → erro do PRÓPRIO campo de Ecoendoscopia.
        response = self._submit(
            client,
            case,
            procedures={ProcedureType.ECHOENDOSCOPY: {"disposition": "denied", "reason": ""}},
            token=token,
        )
        assert response.status_code == 200
        html = response.content.decode()
        textarea = re.search(r'<textarea[^>]*name="procedure_echoendoscopy_reason"[^>]*>', html)
        assert textarea is not None, "textarea de razão da Ecoendoscopia ausente"
        assert "is-invalid" in textarea.group(0)

        # Valor enviado é preservado no re-render do próprio campo.
        response = self._submit(
            client,
            case,
            procedures={ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": "ok"}},
            token=token,
        )
        assert response.status_code == 200  # falta suporte/fluxo
        html = response.content.decode()
        select = re.search(r'<select[^>]*name="procedure_echoendoscopy"[^>]*>.*?</select>', html, re.S)
        assert select is not None, "select de Ecoendoscopia ausente"
        assert 'value="approved" selected' in select.group(0)

    def test_echoendoscopy_immediate_flow_bypasses_chd_gate(self, client) -> None:
        """Fluxo admissional não agendado (vinda imediata) segue aceito para Eco."""
        case = self._make_case(detected=[ProcedureType.ECHOENDOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": ""}},
            support_flag="none",
            admission_flow="immediate",
            token=token,
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert case.doctor_admission_flow == "immediate"
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert CaseEvent.objects.filter(case=case, event_type="ADMISSION_FLOW_OPERATIONAL_NOTICE").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_READY_FOR_SCHEDULER").exists()

    def test_cpre_is_selectable_and_unknown_field_fails_closed(self, client) -> None:
        """CPRE entra no catálogo selecionável (Slice 004); fora dele é rejeitado."""
        from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES
        from apps.doctor.forms import SELECTABLE_PROCEDURE_TYPES

        assert ProcedureType.CPRE in SUPPORTED_PROCEDURE_TYPES
        assert ProcedureType.CPRE in SELECTABLE_PROCEDURE_TYPES

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
            procedure_eda_colonoscopy="approved",
            procedure_eda_colonoscopy_reason="conjunto derivado não é procedimento do catálogo",
        )

        assert response.status_code == 200  # fail-closed, não descarta em silêncio
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert get_approved_procedure_types(case) == ()

    # ── R2: atomicidade ─────────────────────────────────────────────────

    def test_structural_failure_leaves_no_partial_write(self, client) -> None:
        """Falha estrutural no meio da troca não persiste row/evento/FSM."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        with mock.patch(
            "apps.cases.procedures.CaseEvent.objects.create",
            side_effect=RuntimeError("falha estrutural simulada"),
        ):
            with pytest.raises(RuntimeError):
                self._submit(
                    client,
                    case,
                    procedures={
                        ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                        ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": "troca"},
                    },
                    support_flag="none",
                    admission_flow="scheduled",
                    token=token,
                )

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        eda_row = case.procedures.get(procedure_type=ProcedureType.EDA)
        assert eda_row.doctor_disposition == "pending"
        assert not case.procedures.filter(procedure_type=ProcedureType.ECHOENDOSCOPY).exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()

    # ── R3: troca não dispara automação nem exibe sugestão do destino ────

    def test_swap_does_not_call_llm_queue_or_policy(self, client) -> None:
        """Spies provam zero rerun/repolicy/enfileiramento na troca."""
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
                procedures={
                    ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                    ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": "troca"},
                },
                support_flag="none",
                admission_flow="scheduled",
                token=token,
            )

        assert response.status_code == 302
        run_pipeline.assert_not_called()
        enqueue_pipeline.assert_not_called()
        async_task.assert_not_called()
        evaluate_policy.assert_not_called()

    def test_decision_page_shows_no_destination_suggestion(self, client) -> None:
        """A página de decisão não exibe sugestão/checklist da Ecoendoscopia destino."""
        case = self._make_case(detected=[ProcedureType.EDA])
        self._login(client, "doctor")

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        html = response.content.decode()
        echo_row = re.search(
            r'<div class="procedure-decision-row[^"]*"[^>]*>(?:(?!procedure-decision-row).)*'
            r'name="procedure_echoendoscopy"',
            html,
            re.S,
        )
        assert echo_row is not None, "linha de Ecoendoscopia ausente na página de decisão"
        assert "Sugestão do sistema" not in echo_row.group(0)

    # ── R4: substituição integral vs. conjunto parcial incompatível ──────

    def test_combined_full_replacement_by_echoendoscopy(self, client) -> None:
        """{EDA, Colonoscopia} integralmente substituído por {Ecoendoscopia}."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                ProcedureType.COLONOSCOPY: {"disposition": "denied", "reason": "troca"},
                ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": "substitui ambos"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == (ProcedureType.ECHOENDOSCOPY,)

    def test_partial_incompatible_set_rejected_without_write(self, client) -> None:
        """Manter Colonoscopia e incluir Ecoendoscopia é incompatível: zero write."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                ProcedureType.COLONOSCOPY: {"disposition": "approved", "reason": ""},
                ProcedureType.ECHOENDOSCOPY: {"disposition": "approved", "reason": "inclusão indevida"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200  # re-render com erro de matriz

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        for row in case.procedures.all():
            assert row.doctor_disposition == "pending"
            assert row.doctor_reason == ""
        assert not case.procedures.filter(procedure_type=ProcedureType.ECHOENDOSCOPY).exists()
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()

    # ── Slice 004 (R5): CPRE — manter, negar e trocar/aprovar ───────────────

    def test_swap_singleton_eda_to_cpre(self, client) -> None:
        """EDA declarada/detectada → negada; CPRE → aprovada com justificativa."""
        case = self._make_case(detected=[ProcedureType.EDA])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "Substituída por CPRE"},
                ProcedureType.CPRE: {"disposition": "approved", "reason": "CPRE indicada para via biliar"},
            },
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
        changed = CaseEvent.objects.get(case=case, event_type="DOCTOR_PROCEDURE_SET_CHANGED")
        assert changed.payload["detected"] == [ProcedureType.EDA]
        assert changed.payload["approved"] == [ProcedureType.CPRE]
        assert changed.payload["reason_present"] is True

    def test_detected_cpre_row_requires_a_disposition(self, client) -> None:
        """Dívida do Slice 003 (P2): row CPRE detectada exige decisão própria (R1)."""
        case = self._make_case(detected=[ProcedureType.CPRE])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(client, case, procedures={}, token=token)

        assert response.status_code == 200
        assert "Defina a decisão para este procedimento detectado." in response.content.decode()
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.procedures.get(procedure_type=ProcedureType.CPRE).doctor_disposition == "pending"

    def test_keep_singleton_cpre(self, client) -> None:
        case = self._make_case(detected=[ProcedureType.CPRE])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.CPRE: {"disposition": "approved", "reason": ""}},
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == (ProcedureType.CPRE,)

    def test_deny_singleton_cpre_requires_own_reason(self, client) -> None:
        """Negar CPRE exige razão no PRÓPRIO campo do procedimento."""
        case = self._make_case(detected=[ProcedureType.CPRE])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={ProcedureType.CPRE: {"disposition": "denied", "reason": ""}},
            token=token,
        )
        assert response.status_code == 200
        html = response.content.decode()
        textarea = re.search(r'<textarea[^>]*name="procedure_cpre_reason"[^>]*>', html)
        assert textarea is not None, "textarea de razão da CPRE ausente"
        assert "is-invalid" in textarea.group(0)

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert get_approved_procedure_types(case) == ()

    def test_cpre_swap_does_not_call_llm_queue_or_policy(self, client) -> None:
        """Spies provam zero rerun/repolicy/enfileiramento na troca para CPRE (R5)."""
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
                procedures={
                    ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                    ProcedureType.CPRE: {"disposition": "approved", "reason": "troca"},
                },
                support_flag="none",
                admission_flow="scheduled",
                token=token,
            )

        assert response.status_code == 302
        run_pipeline.assert_not_called()
        enqueue_pipeline.assert_not_called()
        async_task.assert_not_called()
        evaluate_policy.assert_not_called()

    def test_combined_full_replacement_by_cpre(self, client) -> None:
        """{EDA, Colonoscopia} integralmente substituído por {CPRE} (R5)."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                ProcedureType.COLONOSCOPY: {"disposition": "denied", "reason": "troca"},
                ProcedureType.CPRE: {"disposition": "approved", "reason": "substitui ambos"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.doctor_decision == "accept"
        assert get_approved_procedure_types(case) == (ProcedureType.CPRE,)

    def test_partial_incompatible_set_with_cpre_rejected_without_write(self, client) -> None:
        """Manter Colonoscopia e incluir CPRE é incompatível: zero write (R5)."""
        case = self._make_case(detected=[ProcedureType.EDA, ProcedureType.COLONOSCOPY])
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = self._submit(
            client,
            case,
            procedures={
                ProcedureType.EDA: {"disposition": "denied", "reason": "troca"},
                ProcedureType.COLONOSCOPY: {"disposition": "approved", "reason": ""},
                ProcedureType.CPRE: {"disposition": "approved", "reason": "inclusão indevida"},
            },
            support_flag="none",
            admission_flow="scheduled",
            token=token,
        )
        assert response.status_code == 200  # re-render com erro de matriz

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        for row in case.procedures.all():
            assert row.doctor_disposition == "pending"
        assert not case.procedures.filter(procedure_type=ProcedureType.CPRE).exists()
