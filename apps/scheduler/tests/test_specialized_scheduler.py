"""Slice 003/004 — CHD agenda procedimento especializado uma única vez (R5/R6).

Cobre o recorte CHD dos slices ``slice-003-echoendoscopy-doctor-swap-and-downstream``
e ``slice-004-cpre-end-to-end``:

- R5: card/confirmação de Ecoendoscopia/CPRE autorizada não recebe label de
  agendamento casado nem validação de sala; um único ``appointment_at`` é
  persistido e os fluxos admissionais existentes continuam aceitos;
- R6: quando o autorizado difere do detectado, CHD exibe a comparação
  detectado → autorizado com o badge do procedimento especializado.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.scheduler.views import _approved_snapshot

User = get_user_model()


def _create_role(name: str) -> Any:
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


@pytest.mark.django_db
class TestSpecializedSchedulerQueue:
    """Procedimento especializado autorizado no CHD: badge, agendamento único e comparação."""

    def _login_as(self, client, role_name: str) -> Any:
        username = f"{role_name}@slice003.{uuid.uuid4().hex[:8]}.test"
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(_create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_case(
        self,
        nir: Any,
        *,
        status: str = CaseStatus.WAIT_APPT,
        approved: tuple[str, ...] = (),
        detected: tuple[str, ...] = (),
        reasons: dict[str, str] | None = None,
        admission_flow: str = "scheduled",
        **kw: Any,
    ) -> Case:
        reasons = reasons or {}
        kw.setdefault(
            "structured_data",
            {"schema_version": "3.0", "patient": {"name": "Paciente Eco", "age": 58, "gender": "F"}},
        )
        case = Case.objects.create(
            created_by=nir,
            status=status,
            doctor_decision="accept",
            doctor_admission_flow=admission_flow,
            doctor_support_flag="none",
            **kw,
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
                row.doctor_reason = reasons.get(procedure_type, "")
                fields += ["doctor_disposition", "doctor_reason"]
            if fields:
                row.save(update_fields=fields)
        return case

    def _claim_lock(self, case_id, scheduler: Any) -> str:
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

    # ── R5: badge sem label casado ───────────────────────────────────────

    def test_approved_snapshot_marks_echoendoscopy_as_not_paired(self) -> None:
        """Ecoendoscopia autorizada nunca é agendamento casado."""
        nir = User.objects.create_user(username="nir_snap@test.com", password="pw")
        case = self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.ECHOENDOSCOPY,),
        )

        snapshot = _approved_snapshot(case)

        assert snapshot["approved_selection_key"] == ProcedureType.ECHOENDOSCOPY
        assert snapshot["approved_label"] == "Ecoendoscopia"
        assert snapshot["is_paired"] is False

    def test_echoendoscopy_pending_card_shows_badge_without_paired_label(self, client) -> None:
        """Card pendente do CHD mostra Ecoendoscopia sem 'Agendamento casado'."""
        nir = self._login_as(client, "nir")
        self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.ECHOENDOSCOPY,),
        )
        self._login_as(client, "scheduler")

        content = client.get("/scheduler/").content.decode()

        assert "Ecoendoscopia" in content
        assert 'data-approved-selection="echoendoscopy"' in content
        assert "Agendamento casado" not in content

    def test_echoendoscopy_card_shows_detected_to_approved_transformation(self, client) -> None:
        """R6: troca EDA → Ecoendoscopia aparece como comparação no card CHD."""
        nir = self._login_as(client, "nir")
        self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.EDA,),
            reasons={ProcedureType.ECHOENDOSCOPY: "caracterização"},
        )
        self._login_as(client, "scheduler")

        content = client.get("/scheduler/").content.decode()

        assert "Detectado: EDA · Autorizado: Ecoendoscopia" in content

    # ── R5: agendamento único, sem validação de sala ─────────────────────

    def test_echoendoscopy_confirmation_persists_single_appointment(self, client) -> None:
        """Confirmar Ecoendoscopia grava um único appointment_at/local livre."""
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.ECHOENDOSCOPY,),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "confirm",
                "appointment_date": "2026-07-15",
                "appointment_time": "08:30",
                "appointment_location": "Hospital Central - Sala de Endoscopia",
                "notes": "Jejum de 8h.",
                "reason": "",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"
        assert case.appointment_at is not None
        assert case.appointment_location == "Hospital Central - Sala de Endoscopia"

        event = CaseEvent.objects.get(case=case, event_type="APPT_CONFIRMED")
        assert event.payload["approved_procedures"] == [ProcedureType.ECHOENDOSCOPY]
        assert event.payload["paired"] is False

    def test_echoendoscopy_denial_keeps_specialized_set(self, client) -> None:
        """Negativa do CHD não altera o conjunto autorizado especializado."""
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.ECHOENDOSCOPY,),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "appointment_location": "",
                "notes": "",
                "reason": "Sem agenda disponível.",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.appointment_status == "denied"
        assert [row.procedure_type for row in case.procedures.all()] == [ProcedureType.ECHOENDOSCOPY]

    def test_echoendoscopy_with_pediatric_flow_still_schedulable(self, client) -> None:
        """Fluxo admissional existente (pediátrico com agendamento) segue aceito."""
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.ECHOENDOSCOPY,),
            admission_flow="pediatric_appt",
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "confirm",
                "appointment_date": "2026-07-20",
                "appointment_time": "10:00",
                "appointment_location": "Ambulatório Pediátrico",
                "notes": "",
                "reason": "",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        confirmed = Case.objects.get(pk=case.pk)
        assert confirmed.appointment_status == "confirmed"
        assert confirmed.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    def test_echoendoscopy_confirm_page_shows_authorized_and_reasons(self, client) -> None:
        """R6: confirmação CHD mostra autorizado + comparação + razão registrada."""
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.EDA,),
            reasons={ProcedureType.ECHOENDOSCOPY: "Troca por melhor caracterização"},
        )
        self._login_as(client, "scheduler")

        response = client.get(f"/scheduler/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Ecoendoscopia" in content
        assert "Detectado: EDA · Autorizado: Ecoendoscopia" in content
        assert "Troca por melhor caracterização" in content
        assert "Agendamento casado" not in content

    # ── Slice 004 (R6): CPRE no CHD ─────────────────────────────────────────

    def test_approved_snapshot_marks_cpre_as_not_paired(self) -> None:
        nir = User.objects.create_user(username="nir_snap_cpre@test.com", password="pw")
        case = self._make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.CPRE,),
        )

        snapshot = _approved_snapshot(case)

        assert snapshot["approved_selection_key"] == ProcedureType.CPRE
        assert snapshot["approved_label"] == "CPRE"
        assert snapshot["is_paired"] is False

    def test_cpre_pending_card_shows_badge_without_paired_label(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.CPRE,),
        )
        self._login_as(client, "scheduler")

        content = client.get("/scheduler/").content.decode()

        assert "CPRE" in content
        assert 'data-approved-selection="cpre"' in content
        assert "Agendamento casado" not in content

    def test_cpre_card_shows_detected_to_approved_transformation(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.EDA,),
            reasons={ProcedureType.CPRE: "troca para via biliar"},
        )
        self._login_as(client, "scheduler")

        content = client.get("/scheduler/").content.decode()

        assert "Detectado: EDA · Autorizado: CPRE" in content

    def test_cpre_confirmation_persists_single_appointment(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.CPRE,),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "confirm",
                "appointment_date": "2026-08-12",
                "appointment_time": "07:30",
                "appointment_location": "Hospital Central - Sala de Endoscopia",
                "notes": "Jejum de 8h.",
                "reason": "",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"
        assert case.appointment_at is not None
        assert case.appointment_location == "Hospital Central - Sala de Endoscopia"

        event = CaseEvent.objects.get(case=case, event_type="APPT_CONFIRMED")
        assert event.payload["approved_procedures"] == [ProcedureType.CPRE]
        assert event.payload["paired"] is False

    def test_cpre_denial_keeps_specialized_set(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.CPRE,),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            data={
                "decision": "deny",
                "appointment_date": "",
                "appointment_time": "",
                "appointment_location": "",
                "notes": "",
                "reason": "Sem agenda disponível.",
                "lock_token": token,
            },
        )

        assert response.status_code == 302
        case = Case.objects.get(pk=case.pk)
        assert case.appointment_status == "denied"
        assert [row.procedure_type for row in case.procedures.all()] == [ProcedureType.CPRE]

    def test_cpre_confirm_page_shows_authorized_and_reasons(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            approved=(ProcedureType.CPRE,),
            detected=(ProcedureType.EDA,),
            reasons={ProcedureType.CPRE: "Troca para avaliacao de via biliar"},
        )
        self._login_as(client, "scheduler")

        response = client.get(f"/scheduler/{case.case_id}/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "CPRE" in content
        assert "Detectado: EDA · Autorizado: CPRE" in content
        assert "Troca para avaliacao de via biliar" in content
        assert "Agendamento casado" not in content
