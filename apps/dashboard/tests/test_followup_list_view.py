"""Testes da aba de listagem Follow-up do supervisor (Slice 002, R1–R6)."""

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.admission import ADMISSION_FLOW_MAP
from apps.cases.followup import ProcedureOutcomeInput, record_case_follow_up
from apps.cases.models import Case, CaseProcedure

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str):
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"followup-{role_name}@test", password="testpass123")
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _local_dt(*, day_offset: int, hour: int = 10, minute: int = 0) -> datetime:
    """Datetime aware no dia local (hoje + day_offset) no horário informado."""
    day = timezone.localdate() + timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())


def _create_scheduled_case(user, *, arn: str, name: str, when: datetime | None, status: str = "confirmed") -> Case:
    """Caso agendado (grupo confirmado) com nome do paciente estruturado."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        appointment_status=status,
        appointment_at=when,
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _create_immediate_case(user, *, arn: str, name: str, flow: str, decided_at: datetime | None) -> Case:
    """Caso de fluxo operacional (vinda imediata) com doctor_decided_at."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        doctor_admission_flow=flow,
        doctor_decided_at=decided_at,
        doctor_decision="accept",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _total_cases_in_groups(response) -> int:
    return sum(len(group["cases"]) for group in response.context["groups"])


def _group_dates(response):
    return [group["date"] for group in response.context["groups"]]


# ── R1: acesso e permissões ─────────────────────────────────────────────


class TestFollowUpListAccess:
    """GET /dashboard/follow-ups/ exige login + papel manager/admin."""

    def test_requires_login(self, client) -> None:
        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_manager_allowed(self, client) -> None:
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200

    def test_admin_allowed(self, client) -> None:
        _login_as(client, "admin")
        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200

    @pytest.mark.parametrize("role_name", ["nir", "doctor", "scheduler"])
    def test_other_roles_redirected(self, client, role_name: str) -> None:
        _login_as(client, role_name)
        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 302


# ── R2: default hoje + ontem e ordenação ────────────────────────────────


class TestFollowUpListDefault:
    """Default lista elegíveis de hoje + ontem, agrupados por data."""

    def test_default_lists_today_and_yesterday_excludes_older(self, client) -> None:
        user = _login_as(client, "manager")
        today_sched = _create_scheduled_case(user, arn="TODAY-SCHED", name="Ana Hoje", when=_local_dt(day_offset=0))
        yesterday_imm = _create_immediate_case(
            user,
            arn="YDAY-IMM",
            name="Bruno Ontem",
            flow="immediate",
            decided_at=_local_dt(day_offset=-1, hour=15),
        )
        old = _create_scheduled_case(user, arn="OLD-CASE", name="Carla Antiga", when=_local_dt(day_offset=-5))

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert today_sched.agency_record_number in content
        assert yesterday_imm.agency_record_number in content
        assert old.agency_record_number not in content
        assert _group_dates(response) == [timezone.localdate() - timedelta(days=1), timezone.localdate()]

    def test_default_excludes_ineligible(self, client) -> None:
        """Casos fora do predicado (R7) não entram na listagem."""
        user = _login_as(client, "manager")
        _create_scheduled_case(user, arn="NO-DATE", name="Sem Data", when=None)  # confirmado sem appointment_at
        _create_scheduled_case(user, arn="DENIED-TODAY", name="Negado", when=_local_dt(day_offset=0), status="denied")
        _create_immediate_case(user, arn="NO-DECIDED", name="Sem Decisão", flow="immediate", decided_at=None)
        _create_scheduled_case(user, arn="SCHED-NO-APPT", name="Sem Agendamento", when=None)
        # Fluxo agendado com doctor_decided_at (mas sem agendamento) não é elegível.
        wait_appt = Case.objects.create(
            created_by=user,
            agency_record_number="WAIT-APPT",
            doctor_admission_flow="scheduled",
            doctor_decided_at=_local_dt(day_offset=0, hour=9),
            doctor_decision="accept",
        )
        wait_appt.structured_data = {"patient": {"name": "Aguardando CHD"}}
        wait_appt.save(update_fields=["structured_data"])

        response = client.get(reverse("dashboard:followup_list"))
        content = response.content.decode()
        for arn in ("NO-DATE", "DENIED-TODAY", "NO-DECIDED", "SCHED-NO-APPT", "WAIT-APPT"):
            assert arn not in content

    def test_ordering_grouped_by_date_asc_then_name_then_time(self, client) -> None:
        user = _login_as(client, "manager")
        today = timezone.localdate()
        # Ontem: dois casos com nomes diferentes.
        _create_scheduled_case(user, arn="Y-B", name="Zeta", when=_local_dt(day_offset=-1, hour=8))
        _create_scheduled_case(user, arn="Y-A", name="Alfa", when=_local_dt(day_offset=-1, hour=11))
        # Hoje: mesmo nome em horários diferentes para validar a ordenação por horário.
        _create_scheduled_case(user, arn="T-B", name="Mesmo Nome", when=_local_dt(day_offset=0, hour=14))
        _create_scheduled_case(user, arn="T-A", name="Mesmo Nome", when=_local_dt(day_offset=0, hour=9))
        _create_scheduled_case(user, arn="T-C", name="Beta", when=_local_dt(day_offset=0, hour=10))

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        groups = response.context["groups"]
        assert [g["date"] for g in groups] == [today - timedelta(days=1), today]

        yesterday_cases = [item["case"].agency_record_number for item in groups[0]["cases"]]
        assert yesterday_cases == ["Y-A", "Y-B"]

        today_cases = [item["case"].agency_record_number for item in groups[1]["cases"]]
        # Nome primeiro (Beta < Mesmo Nome); mesmo nome → ordena por horário.
        assert today_cases == ["T-C", "T-A", "T-B"]


# ── R3: filtro ?date= ───────────────────────────────────────────────────


class TestFollowUpListSpecificDate:
    """?date=YYYY-MM-DD lista apenas a data; ausente/inválida → default."""

    def test_specific_date_lists_only_that_date(self, client) -> None:
        user = _login_as(client, "manager")
        today_sched = _create_scheduled_case(user, arn="TODAY-ONLY", name="Hoje", when=_local_dt(day_offset=0))
        yesterday_sched = _create_scheduled_case(
            user,
            arn="YDAY-ONLY",
            name="Ontem",
            when=_local_dt(day_offset=-1, hour=8),
        )
        yesterday_iso = (timezone.localdate() - timedelta(days=1)).isoformat()

        response = client.get(reverse("dashboard:followup_list"), {"date": yesterday_iso})
        assert response.status_code == 200
        content = response.content.decode()
        assert yesterday_sched.agency_record_number in content
        assert today_sched.agency_record_number not in content
        assert _group_dates(response) == [timezone.localdate() - timedelta(days=1)]

    def test_invalid_date_falls_back_to_default(self, client) -> None:
        user = _login_as(client, "manager")
        today_sched = _create_scheduled_case(user, arn="DEF-TODAY", name="Hoje", when=_local_dt(day_offset=0))

        for raw in ("not-a-date", "9999-99-99", ""):
            response = client.get(reverse("dashboard:followup_list"), {"date": raw})
            assert response.status_code == 200
            assert today_sched.agency_record_number in response.content.decode()


# ── R4: busca ?q= sobre elegíveis de qualquer data ──────────────────────


class TestFollowUpListSearch:
    """?q= busca ocorrência OU nome sobre elegíveis de qualquer data (limite 50)."""

    def test_search_by_record_number_over_any_date(self, client) -> None:
        user = _login_as(client, "manager")
        old = _create_scheduled_case(user, arn="ARCH-24-0001", name="Paciente Antigo", when=_local_dt(day_offset=-30))
        other = _create_scheduled_case(user, arn="TODAY-OTHER", name="Outro Hoje", when=_local_dt(day_offset=0))

        response = client.get(reverse("dashboard:followup_list"), {"q": "ARCH-24"})
        assert response.status_code == 200
        content = response.content.decode()
        assert old.agency_record_number in content
        assert other.agency_record_number not in content

    def test_search_by_patient_name_ignores_date(self, client) -> None:
        user = _login_as(client, "manager")
        old = _create_scheduled_case(user, arn="ANTIGO-001", name="Antônio Registro", when=_local_dt(day_offset=-60))
        _create_scheduled_case(user, arn="RECENTE-001", name="Maria Recente", when=_local_dt(day_offset=0))

        response = client.get(
            reverse("dashboard:followup_list"),
            {"date": timezone.localdate().isoformat(), "q": "antônio"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert old.agency_record_number in content
        assert "RECENTE-001" not in content

    def test_search_caps_at_50_results(self, client) -> None:
        user = _login_as(client, "manager")
        for i in range(60):
            _create_scheduled_case(
                user,
                arn=f"SEARCH-{i:02d}",
                name=f"Buscável {i:02d}",
                when=_local_dt(day_offset=-(i + 1), hour=8),
            )

        response = client.get(reverse("dashboard:followup_list"), {"q": "SEARCH-"})
        assert response.status_code == 200
        assert _total_cases_in_groups(response) == 50

    def test_search_only_returns_eligible_cases(self, client) -> None:
        user = _login_as(client, "manager")
        eligible = _create_scheduled_case(user, arn="ELEG-001", name="Elegível", when=_local_dt(day_offset=-10))
        ineligible = _create_scheduled_case(
            user,
            arn="ELEG-002",
            name="Inelegível",
            when=_local_dt(day_offset=-10),
            status="denied",
        )

        response = client.get(reverse("dashboard:followup_list"), {"q": "ELEG"})
        assert response.status_code == 200
        content = response.content.decode()
        assert eligible.agency_record_number in content
        assert ineligible.agency_record_number not in content


# ── R5: conteúdo dos cards e badges ─────────────────────────────────────


class TestFollowUpListCardBadges:
    """Cards exibem ocorrência, nome, data/hora ou fluxo, e badge de follow-up."""

    def _record_follow_up(self, case: Case, user) -> None:
        procedure = CaseProcedure.objects.create(case=case, procedure_type="eda")
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=procedure.id, performed=True)],
        )

    def test_registered_and_pending_badges(self, client) -> None:
        user = _login_as(client, "manager")
        recorded_case = _create_scheduled_case(
            user, arn="REGISTRADO-001", name="Registrado", when=_local_dt(day_offset=0)
        )
        _create_scheduled_case(user, arn="PENDENTE-001", name="Pendente", when=_local_dt(day_offset=0, hour=11))
        self._record_follow_up(recorded_case, user)

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Follow-up registrado" in content
        assert "v1" in content
        assert "Follow-up pendente" in content

    def test_card_shows_occurrence_name_and_scheduled_datetime(self, client) -> None:
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=9, minute=30)
        case = _create_scheduled_case(user, arn="CARD-001", name="Paciente Card", when=when)

        response = client.get(reverse("dashboard:followup_list"))
        content = response.content.decode()
        assert case.agency_record_number in content
        assert "Paciente Card" in content
        expected_time = timezone.localtime(case.appointment_at).strftime("%d/%m/%Y %H:%M")
        assert expected_time in content

    def test_immediate_card_shows_admission_flow_label(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_immediate_case(
            user,
            arn="IMM-001",
            name="Imediato",
            flow="immediate",
            decided_at=_local_dt(day_offset=0, hour=8),
        )

        response = client.get(reverse("dashboard:followup_list"))
        content = response.content.decode()
        assert case.agency_record_number in content
        assert ADMISSION_FLOW_MAP["immediate"] in content


# ── R6: pill Follow-up na navegação do dashboard ────────────────────────


class TestFollowUpListNav:
    """Pill "Follow-up" visível apontando para a rota da listagem."""

    def test_nav_shows_followup_pill_with_url(self, client) -> None:
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("dashboard:followup_list") in content
        assert "Follow-up" in content


# ── Regressão P1: caso híbrido (agendamento confirmado + fluxo operacional) ──


def _create_hybrid_case(
    user, *, arn: str, name: str, appointment_status: str, appointment_at: datetime | None, decided_at: datetime | None
) -> Case:
    """Caso híbrido: fluxo operacional combinado com campos de agendamento."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        appointment_status=appointment_status,
        appointment_at=appointment_at,
        doctor_admission_flow="immediate",
        doctor_decided_at=decided_at,
        doctor_decision="accept",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


class TestFollowUpListHybridCase:
    """Híbrido segue a precedência de ramo de is_followup_eligible (P1).

    Ramo agendado válido (confirmed + appointment_at) vence mesmo em fluxo
    operacional; sem agendamento válido, fluxo operacional com doctor_decided_at
    cai no ramo da vinda imediata. O caso elegível nunca some da listagem.
    """

    def test_confirmed_with_appointment_lists_under_appointment_date(self, client) -> None:
        """Operacional com doctor_decided_at nulo não esconde o caso agendado."""
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=14)
        case = _create_hybrid_case(
            user,
            arn="HB-APPT-0001",
            name="Híbrido Agendado",
            appointment_status="confirmed",
            appointment_at=when,
            decided_at=None,
        )

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content
        assert _group_dates(response) == [timezone.localdate()]

    def test_operational_without_valid_appointment_lists_under_decision_date(self, client) -> None:
        """Sem agendamento válido, o fluxo operacional usa doctor_decided_at."""
        user = _login_as(client, "manager")
        decided_at = _local_dt(day_offset=-1, hour=9)
        case = _create_hybrid_case(
            user,
            arn="HB-DEC-0001",
            name="Híbrido Decidido",
            appointment_status="",
            appointment_at=None,
            decided_at=decided_at,
        )

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content
        assert _group_dates(response) == [timezone.localdate() - timedelta(days=1)]

    def test_confirmed_with_appointment_wins_over_decision_timestamp(self, client) -> None:
        """Ambos os ramos válidos: agendamento confirmado tem precedência (D4)."""
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=14)
        case = _create_hybrid_case(
            user,
            arn="HB-BOTH-0001",
            name="Híbrido Ambos",
            appointment_status="confirmed",
            appointment_at=when,
            decided_at=_local_dt(day_offset=-1, hour=9),
        )

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content
        assert _group_dates(response) == [timezone.localdate()]
