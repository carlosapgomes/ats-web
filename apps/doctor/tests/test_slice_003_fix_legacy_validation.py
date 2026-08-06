"""Slice 003 fix — validação fail-closed de decisão ausente (legado e v2).

Correção pós-verificação (reprovação do Slice 003):

- BUG 1 (bloqueante): submit legado sem ``decision`` aceitava o caso
  silenciosamente — ``doctor_decide(decision="")`` gravava o evento corrompido
  ``DOCTOR_`` e transicionava para DOCTOR_ACCEPTED (qualquer valor ≠ "deny"
  vira accept) seguido de final reply.
- BUG 2 (importante): caso v2 sem nenhuma disposição de procedimento gerava
  ``deny`` global sem razão (approved_count == 0 com lista de razões vazia).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, DetectionStatus

User = get_user_model()


@pytest.mark.django_db
class TestFixLegacyAndV2FailClosedValidation:
    """Prova que decisão ausente/inválida não persiste nada (200 + rollback)."""

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login(self, client, role_name: str) -> Any:
        user = User.objects.create_user(username=f"{role_name}_fix@test.com", password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

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

    def _legacy_case(self) -> Case:
        """Caso 1.1 sem rows e sem structured_data (modo legado)."""
        nir = User.objects.create_user(username="nir_fix_legacy@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        return Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ARN-FIX-LEG",
            structured_data=None,
        )

    def _v2_case_zero_detected(self) -> Case:
        """Caso 2.0 com rows declaradas porém 0 detectadas (fora do domínio 1–2)."""
        nir = User.objects.create_user(username="nir_fix_v2@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ARN-FIX-V2",
            structured_data={"schema_version": "2.0", "patient": {"name": "P", "age": 40, "sex": "F"}},
            suggested_action={
                "schema_version": "2.0",
                "procedure_recommendations": [],
                "global_support_recommendation": "none",
            },
        )
        for pt in ("eda", "colonoscopy"):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                detection_status=DetectionStatus.NOT_DETECTED,
            )
        return case

    def test_legacy_submit_without_decision_is_invalid(self, client) -> None:
        case = self._legacy_case()
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(f"/doctor/{case.case_id}/submit/", data={"lock_token": token})
        assert response.status_code == 200  # re-render com erro

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

    def test_legacy_submit_with_invalid_decision_value_is_invalid(self, client) -> None:
        case = self._legacy_case()
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(
            f"/doctor/{case.case_id}/submit/",
            data={"decision": "maybe", "lock_token": token},
        )
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()

    def test_v2_submit_without_any_disposition_is_invalid(self, client) -> None:
        case = self._v2_case_zero_detected()
        doctor = self._login(client, "doctor")
        token = self._claim_lock(case.case_id, doctor)

        response = client.post(f"/doctor/{case.case_id}/submit/", data={"lock_token": token})
        assert response.status_code == 200

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.doctor_decision == ""
        for row in case.procedures.all():
            assert row.doctor_disposition == "pending"
        assert not CaseEvent.objects.filter(case=case, event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="DOCTOR_").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").exists()
