"""Testes unitários do predicado is_followup_eligible (Slice 002, R7).

Cobre o predicado combinado do design D4:
- grupo agendado: appointment_status="confirmed" E appointment_at presente;
- grupo vinda imediata (fluxo operacional): doctor_admission_flow ∈
  OPERATIONAL_NOTICE_FLOWS E doctor_decided_at presente;
- sem fallback para created_at ou para outros fluxos.
"""

import pytest
from django.utils import timezone

from apps.cases.admission import OPERATIONAL_NOTICE_FLOWS
from apps.cases.followup import is_followup_eligible

pytestmark = pytest.mark.django_db


class TestIsFollowUpEligible:
    """Predicado de elegibilidade para a aba Follow-up."""

    def test_agendado_confirmado_com_horario_elegivel(self, user, case_factory) -> None:
        case = case_factory(user)
        case.appointment_status = "confirmed"
        case.appointment_at = timezone.now()
        assert is_followup_eligible(case) is True

    def test_agendado_confirmado_sem_horario_nao_elegivel(self, user, case_factory) -> None:
        case = case_factory(user)
        case.appointment_status = "confirmed"
        assert is_followup_eligible(case) is False

    def test_agendamento_negado_nao_elegivel(self, user, case_factory) -> None:
        case = case_factory(user)
        case.appointment_status = "denied"
        case.appointment_at = timezone.now()
        assert is_followup_eligible(case) is False

    @pytest.mark.parametrize("flow", OPERATIONAL_NOTICE_FLOWS)
    def test_vinda_imediata_com_decisao_elegivel(self, user, case_factory, flow) -> None:
        case = case_factory(user)
        case.doctor_admission_flow = flow
        case.doctor_decided_at = timezone.now()
        assert is_followup_eligible(case) is True

    @pytest.mark.parametrize("flow", OPERATIONAL_NOTICE_FLOWS)
    def test_vinda_imediata_sem_decisao_nao_elegivel_sem_fallback(self, user, case_factory, flow) -> None:
        """Sem doctor_decided_at NÃO é elegível — created_at (default) não é fallback."""
        case = case_factory(user)
        case.doctor_admission_flow = flow
        assert case.created_at is not None
        assert is_followup_eligible(case) is False

    def test_fluxo_agendado_com_decisao_nao_elegivel(self, user, case_factory) -> None:
        """Fluxo agendado (fora de OPERATIONAL_NOTICE_FLOWS) não conta pela decisão."""
        case = case_factory(user)
        case.doctor_admission_flow = "scheduled"
        case.doctor_decided_at = timezone.now()
        assert is_followup_eligible(case) is False

    def test_sem_fluxo_com_decisao_nao_elegivel(self, user, case_factory) -> None:
        case = case_factory(user)
        case.doctor_decided_at = timezone.now()
        assert is_followup_eligible(case) is False

    def test_caso_vazio_nao_elegivel(self, user, case_factory) -> None:
        case = case_factory(user)
        assert is_followup_eligible(case) is False
