"""Testes do formulário de pós-procedimento do supervisor (Slice 003, R1–R6)."""

import uuid
from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.followup import get_current_follow_up
from apps.cases.models import (
    CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES,
    Case,
    CaseEvent,
    CaseFollowUp,
    CaseProcedure,
)
from apps.dashboard.forms import REASON_PLACEHOLDER

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str):
    """Cria usuário com papel, faz login e seta active_role na sessão.

    ``manager`` representa o supervisor do CHD (matriz D6): além do papel
    manager recebe o papel scheduler (vínculo CHD). Para manager de papel
    único (sem CHD, bloqueado pelo guard), use ``_login_as_plain_manager``.
    """
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"followup-form-{role_name}@test", password="testpass123")
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    if role_name == "manager":
        scheduler_role, _ = Role.objects.get_or_create(name="scheduler")
        user.roles.add(scheduler_role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _login_as_plain_manager(client):
    """Cria usuário ``manager`` SEM o papel scheduler (sem CHD) — bloqueios D6."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="followup-form-plain-manager@test", password="testpass123")
    role, _ = Role.objects.get_or_create(name="manager")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "manager"
    session.save()
    return user


def _local_dt(*, day_offset: int, hour: int = 10, minute: int = 0) -> datetime:
    """Datetime aware no dia local (hoje + day_offset) no horário informado."""
    day = timezone.localdate() + timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())


def _create_case(user, *, arn: str, name: str) -> Case:
    """Caso agendado confirmado (elegível) com nome do paciente estruturado."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        appointment_status="confirmed",
        appointment_at=_local_dt(day_offset=0),
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _create_ineligible_case(user, *, arn: str, name: str) -> Case:
    """Caso fora do predicado: confirmado sem appointment_at."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        appointment_status="confirmed",
        appointment_at=None,
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _add_procedure(case: Case, procedure_type: str = "eda", *, disposition: str = "approved") -> CaseProcedure:
    """Row ``CaseProcedure`` autorizada por padrão (universo do follow-up)."""
    return CaseProcedure.objects.create(
        case=case,
        procedure_type=procedure_type,
        doctor_disposition=disposition,
    )


def _form_url(case: Case) -> str:
    return reverse("dashboard:followup_form", args=[str(case.case_id)])


def _valid_payload(procedure: CaseProcedure, *, performed: str = "yes") -> dict[str, str]:
    return {
        "patient_admitted": "yes",
        f"proc_{procedure.id}-performed": performed,
    }


# ── R1: acesso, permissões e elegibilidade ──────────────────────────────


class TestFollowUpFormAccess:
    """GET exige login + papel manager/admin com CHD (D6); inelegível → 404."""

    def test_get_requires_login(self, client) -> None:
        plain = User.objects.create_user(username="followup-form-anon@test", password="testpass123")
        case = _create_case(plain, arn="NEED-LOGIN", name="Anônimo")
        response = client.get(_form_url(case))
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_manager_allowed(self, client) -> None:
        """Manager de teste é supervisor do CHD: possui manager+scheduler (R4/D6)."""
        user = _login_as(client, "manager")
        role_names = set(user.roles.values_list("name", flat=True))
        assert {"manager", "scheduler"} <= role_names
        case = _create_case(user, arn="MGR-OK-001", name="Gerente")
        _add_procedure(case)
        response = client.get(_form_url(case))
        assert response.status_code == 200

    def test_get_chd_manager_allowed(self, client) -> None:
        """manager + scheduler com papel ativo manager → form 200 (fluxo atual)."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="CHD-MGR-001", name="Supervisor CHD")
        _add_procedure(case)
        response = client.get(_form_url(case))
        assert response.status_code == 200

    def test_get_manager_sem_chd_redirecionado(self, client) -> None:
        """manager sem o papel scheduler → 302 "/" + flash, form não é exposto."""
        manager = _login_as_plain_manager(client)
        case = _create_case(manager, arn="MGR-BLOCK-001", name="Sem CHD")
        _add_procedure(case)
        response = client.get(_form_url(case), follow=True)
        assert response.status_code == 200
        assert response.redirect_chain[0] == ("/", 302)
        content = response.content.decode()
        assert "Você não tem permissão para acessar esta página." in content
        assert case.agency_record_number not in content

    def test_admin_sem_chd_allowed(self, client) -> None:
        """admin ativo sem scheduler → form 200 (isenção D4)."""
        user = _login_as(client, "admin")
        assert not user.roles.filter(name="scheduler").exists()
        case = _create_case(user, arn="ADM-OK-001", name="Admin")
        _add_procedure(case)
        response = client.get(_form_url(case))
        assert response.status_code == 200

    def test_admin_com_scheduler_ativo_manager(self, client) -> None:
        """admin + scheduler com papel ativo manager → form 200 (matriz D6)."""
        from apps.accounts.models import Role

        user = _login_as(client, "admin")
        scheduler_role, _ = Role.objects.get_or_create(name="scheduler")
        user.roles.add(scheduler_role)
        session = client.session
        session["active_role"] = "manager"
        session.save()
        case = _create_case(user, arn="ADM-CHD-001", name="Admin Supervisor")
        _add_procedure(case)
        response = client.get(_form_url(case))
        assert response.status_code == 200

    @pytest.mark.parametrize("role_name", ["nir", "doctor", "scheduler"])
    def test_get_other_roles_redirected(self, client, role_name: str) -> None:
        user = _login_as(client, role_name)
        case = _create_case(user, arn=f"{role_name}-NO-001", name="Bloqueado")
        response = client.get(_form_url(case))
        assert response.status_code == 302

    def test_get_inexistent_case_returns_404(self, client) -> None:
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:followup_form", args=[str(uuid.uuid4())]))
        assert response.status_code == 404


class TestFollowUpFormIneligible:
    """Caso inelegível (design D4) nunca expõe o formulário (GET e POST → 404)."""

    @pytest.mark.parametrize("kind", ["confirmed_sem_data", "negado", "operacional_sem_decisao"])
    def test_get_ineligible_case_returns_404(self, client, kind: str) -> None:
        user = _login_as(client, "manager")
        if kind == "confirmed_sem_data":
            case = Case.objects.create(
                created_by=user,
                agency_record_number="INEL-NOAPPT",
                appointment_status="confirmed",
                appointment_at=None,
                doctor_admission_flow="scheduled",
            )
        elif kind == "negado":
            case = Case.objects.create(
                created_by=user,
                agency_record_number="INEL-DENIED",
                appointment_status="denied",
                appointment_at=_local_dt(day_offset=0),
                doctor_admission_flow="scheduled",
            )
        else:
            case = Case.objects.create(
                created_by=user,
                agency_record_number="INEL-NODECIDED",
                doctor_admission_flow="immediate",
                doctor_decided_at=None,
            )
        case.structured_data = {"patient": {"name": "Inelegível"}}
        case.save(update_fields=["structured_data"])

        assert client.get(_form_url(case)).status_code == 404
        assert client.post(_form_url(case), data={}).status_code == 404

    def test_get_eligible_without_procedures_shows_warning_without_fields(self, client) -> None:
        """Elegível sem rows CaseProcedure (defensivo): 200 com aviso, sem campos."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="NO-PROC-001", name="Sem Procedimento")

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert "sem procedimentos" in content.lower()
        assert "proc_" not in content

        # POST nessa condição também não grava nada.
        response = client.post(_form_url(case), data={"patient_admitted": "yes"})
        assert response.status_code == 200
        assert not CaseFollowUp.objects.filter(case=case).exists()


# ── R1: conteúdo do GET ─────────────────────────────────────────────────


class TestFollowUpFormGet:
    """GET exibe identificação, blocos por procedimento, internação e versões."""

    def test_get_shows_case_identification_and_procedure_blocks(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="GET-CASE-001", name="Paciente Get")
        _add_procedure(case, "eda")
        _add_procedure(case, "colonoscopy")

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content
        assert "Paciente Get" in content
        expected_time = timezone.localtime(case.appointment_at).strftime("%d/%m/%Y %H:%M")
        assert expected_time in content
        assert "EDA" in content
        assert "Colonoscopia" in content
        assert f'name="proc_{case.procedures.get(procedure_type="eda").id}-performed"' in content
        assert 'name="patient_admitted"' in content
        assert "cria nova versão" in content

    def test_get_renders_reason_section_fieldset_per_procedure_block(self, client) -> None:
        """Cada bloco de procedimento renderiza o fieldset data-followup-reason-section.

        A seção de causa (radios de non_performance_reason + grupos condicionais)
        é envolvida por um <fieldset> desabilitável nativamente; o teste garante um
        fieldset por bloco de procedimento (R4/R1 do slice 001).
        """
        user = _login_as(client, "manager")
        case = _create_case(user, arn="RSN-SEC-001", name="Causa Section")
        _add_procedure(case, "eda")
        _add_procedure(case, "colonoscopy")

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert content.count("data-followup-reason-section") == 2
        assert content.count('<fieldset class="mb-2" data-followup-reason-section>') == 2

    def test_get_immediate_case_shows_admission_flow(self, client) -> None:
        user = _login_as(client, "manager")
        case = Case.objects.create(
            created_by=user,
            agency_record_number="GET-IMM-001",
            doctor_admission_flow="immediate",
            doctor_decided_at=_local_dt(day_offset=0, hour=8),
            doctor_decision="accept",
        )
        case.structured_data = {"patient": {"name": "Imediato Get"}}
        case.save(update_fields=["structured_data"])
        _add_procedure(case)

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Vinda Imediata" in content
        expected_time = timezone.localtime(case.doctor_decided_at).strftime("%d/%m/%Y %H:%M")
        assert expected_time in content

    def test_get_shows_current_version_and_history(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="GET-VER-001", name="Versões")
        procedure = _add_procedure(case)
        from apps.cases.followup import ProcedureOutcomeInput, record_case_follow_up

        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=procedure.id, performed=True)],
        )
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[
                ProcedureOutcomeInput(
                    procedure_id=procedure.id, performed=False, non_performance_reason="patient_no_show"
                )
            ],
        )

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert "v2" in content
        assert user.username in content
        assert "v1" in content

    def test_get_renders_preparo_inadequado_reason_option(self, client) -> None:
        """GET renderiza a causa 'Preparo inadequado' entre as opções do bloco."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="GET-PREP-001", name="Preparo Get")
        procedure = _add_procedure(case)

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        fieldset_start = content.index(f"proc_{procedure.id}-performed")
        fieldset = content[fieldset_start:]
        assert 'value="inadequate_prep"' in fieldset
        assert ">Preparo inadequado<" in fieldset


# ── Regressão P1-2: caso híbrido (agendamento confirmado + fluxo operacional) ──


class TestFollowUpFormHybridCase:
    """Híbrido no formulário segue a precedência de ramo de is_followup_eligible.

    Ramo agendado válido (confirmed + appointment_at) vence mesmo em fluxo
    operacional: o caso é apresentado como AGENDADO (data/hora do agendamento),
    nunca como label do fluxo com decisão vazia. Sem agendamento válido, o
    fluxo operacional com doctor_decided_at cai no ramo da vinda imediata.
    """

    def test_confirmed_hybrid_case_shows_scheduled_datetime(self, client) -> None:
        """Operacional com doctor_decided_at nulo exibe a data agendada (P1-2)."""
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=14, minute=30)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="HYB-FORM-001",
            appointment_status="confirmed",
            appointment_at=when,
            doctor_admission_flow="immediate",
            doctor_decided_at=None,
        )
        case.structured_data = {"patient": {"name": "Híbrido Agendado"}}
        case.save(update_fields=["structured_data"])
        _add_procedure(case)

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        expected_time = timezone.localtime(when).strftime("%d/%m/%Y %H:%M")
        assert expected_time in content
        assert "Agendado" in content
        assert "Fluxo de admissão" not in content

    def test_confirmed_hybrid_with_decision_timestamp_still_shows_scheduled(self, client) -> None:
        """Ambos os ramos válidos: agendamento confirmado tem precedência (D4)."""
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=15)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="HYB-FORM-002",
            appointment_status="confirmed",
            appointment_at=when,
            doctor_admission_flow="immediate",
            doctor_decided_at=_local_dt(day_offset=0, hour=9),
            doctor_decision="accept",
        )
        case.structured_data = {"patient": {"name": "Híbrido Ambos"}}
        case.save(update_fields=["structured_data"])
        _add_procedure(case)

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert timezone.localtime(when).strftime("%d/%m/%Y %H:%M") in content
        assert "Fluxo de admissão" not in content

    def test_operational_hybrid_case_still_shows_admission_flow(self, client) -> None:
        """Sem agendamento válido, fluxo operacional com decisão mostra vinda imediata."""
        user = _login_as(client, "manager")
        decided_at = _local_dt(day_offset=0, hour=8)
        case = Case.objects.create(
            created_by=user,
            agency_record_number="HYB-FORM-003",
            appointment_status="",
            appointment_at=None,
            doctor_admission_flow="immediate",
            doctor_decided_at=decided_at,
            doctor_decision="accept",
        )
        case.structured_data = {"patient": {"name": "Híbrido Imediato"}}
        case.save(update_fields=["structured_data"])
        _add_procedure(case)

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Fluxo de admissão" in content
        assert timezone.localtime(decided_at).strftime("%d/%m/%Y %H:%M") in content


# ── R2: POST válido ─────────────────────────────────────────────────────


class TestFollowUpFormPostValid:
    """POST válido grava nova versão, registra CaseEvent e redireciona à lista."""

    def _assert_success_redirect(self, response) -> None:
        assert response.status_code == 302
        assert response.url == reverse("dashboard:followup_list")

    def test_post_valid_records_version_one_and_redirects(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-V1-001", name="Registro V1")
        procedure = _add_procedure(case)

        response = client.post(_form_url(case), data=_valid_payload(procedure))
        self._assert_success_redirect(response)

        follow_up = CaseFollowUp.objects.get(case=case)
        assert follow_up.version == 1
        assert follow_up.patient_admitted is True
        assert follow_up.recorded_by == user
        assert follow_up.procedure_outcomes.get(procedure=procedure).performed is True
        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert event.actor == user
        assert event.payload["version"] == 1

        # Volta à lista com messages.success.
        list_page = client.get(response.url)
        assert "Pós-procedimento registrado" in list_page.content.decode()

    def test_post_valid_not_performed_with_reason(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-NOSHOW-001", name="Não Comparecimento")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "patient_no_show"
        response = client.post(_form_url(case), data=payload)
        self._assert_success_redirect(response)

        row = CaseFollowUp.objects.get(case=case).procedure_outcomes.get(procedure=procedure)
        assert row.performed is False
        assert row.non_performance_reason == "patient_no_show"
        assert row.resource_shortage_detail == ""

    def test_post_legacy_reason_rejeitado_sem_persistencia(self, client) -> None:
        """R2/R3: código legado enviado no POST é rejeitado sem gravar rows/eventos."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-LEGACY-001", name="Causa Legada")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "resource_shortage"
        payload[f"proc_{procedure.id}-resource_shortage_detail"] = "equipment_unavailable"
        response = client.post(_form_url(case), data=payload)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Selecione uma causa da lista oficial." in content
        assert "Informe a causa do procedimento não realizado." not in content
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    def test_post_valid_other_with_text(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-OTH-001", name="Outra causa")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "other"
        payload[f"proc_{procedure.id}-other_reason"] = "Paciente chegou após o encerramento"
        response = client.post(_form_url(case), data=payload)
        self._assert_success_redirect(response)

        row = CaseFollowUp.objects.get(case=case).procedure_outcomes.get(procedure=procedure)
        assert row.performed is False
        assert row.other_reason == "Paciente chegou após o encerramento"

    def test_post_valid_preparo_inadequado(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-PREP-001", name="Preparo Inadequado")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "inadequate_prep"
        response = client.post(_form_url(case), data=payload)
        self._assert_success_redirect(response)

        row = CaseFollowUp.objects.get(case=case).procedure_outcomes.get(procedure=procedure)
        assert row.performed is False
        assert row.non_performance_reason == "inadequate_prep"
        assert row.resource_shortage_detail == ""
        assert row.other_reason == ""


# ── R3: POST inválido não persiste nada ────────────────────────────────


class TestFollowUpFormPostInvalid:
    """POST inválido re-renderiza com erro por campo e não cria rows/eventos."""

    def _post(self, client, case: Case, payload: dict[str, str]):
        return client.post(_form_url(case), data=payload)

    def _assert_nothing_persisted(self, case: Case) -> None:
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(
            case=case, event_type__in=("FOLLOWUP_RECORDED", "FOLLOWUP_UPDATED")
        ).exists()

    def test_post_invalid_missing_reason_for_not_performed(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="BAD-NOREASON", name="Sem Motivo")
        procedure = _add_procedure(case)

        response = self._post(client, case, _valid_payload(procedure, performed="no"))
        assert response.status_code == 200
        assert "Informe a causa do procedimento não realizado." in response.content.decode()
        self._assert_nothing_persisted(case)

    def test_post_invalid_submotivo_residual_nao_persiste(self, client) -> None:
        """R2: submotivo residual no POST é rejeitado sem rows/eventos.

        O form não renderiza o campo legado, mas o valor enviado é repassado ao
        service (``record_case_follow_up``), autoridade final que recusa
        qualquer submotivo em novas gravações (design D3).
        """
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-RSD-001", name="Submotivo Residual")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "missing_equipment"
        payload[f"proc_{procedure.id}-resource_shortage_detail"] = "equipment_unavailable"
        response = self._post(client, case, payload)

        assert response.status_code == 200
        assert "Submotivo de falta de recursos não é aceito em novas gravações." in response.content.decode()
        self._assert_nothing_persisted(case)

    def test_post_invalid_other_without_text(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="BAD-NOTEXT", name="Outro sem texto")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "other"
        response = self._post(client, case, payload)
        assert response.status_code == 200
        assert "Descreva a outra causa da não realização." in response.content.decode()
        self._assert_nothing_persisted(case)

    def test_post_invalid_foreign_procedure_id(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="BAD-FOREIGN", name="Id Estranho")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure)
        payload["proc_99999-performed"] = "yes"
        response = self._post(client, case, payload)
        assert response.status_code == 200
        assert "não pertence ao caso" in response.content.decode()
        self._assert_nothing_persisted(case)

    def test_post_invalid_missing_patient_admitted(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="BAD-NOADM", name="Sem Internação")
        procedure = _add_procedure(case)

        payload = {f"proc_{procedure.id}-performed": "yes"}
        response = self._post(client, case, payload)
        assert response.status_code == 200
        assert "Informe se o paciente foi internado." in response.content.decode()
        self._assert_nothing_persisted(case)


# ── R3: select compacto de causa (slice-001) ────────────────────────────


class TestFollowUpFormCompactReasonSelect:
    """R3 — um único ``select`` Bootstrap por bloco, com o catálogo oficial.

    A ordem/labels exatos de D1 são pinados contra
    ``CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES`` aqui e contra a lista
    literal da ficha em ``apps/cases/tests/test_followup_services.py``.
    """

    @staticmethod
    def _reason_select(content: str, procedure: CaseProcedure) -> str:
        start = content.index(f'<select name="proc_{procedure.id}-non_performance_reason"')
        return content[start : content.index("</select>", start)]

    @staticmethod
    def _option_attr(snippet: str, attribute: str) -> list[str]:
        return [option.split(f'{attribute}="', 1)[1].split('"', 1)[0] for option in snippet.split("<option ")[1:]]

    @staticmethod
    def _option_labels(snippet: str) -> list[str]:
        return [option.split(">", 1)[1].split("<", 1)[0] for option in snippet.split("<option ")[1:]]

    def test_compact_reason_select_unico_por_bloco_sem_radios(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="RSN-SELECT-001", name="Select Compacto")
        eda = _add_procedure(case, "eda")
        colon = _add_procedure(case, "colonoscopy")

        content = client.get(_form_url(case)).content.decode()

        for procedure in (eda, colon):
            name = f"proc_{procedure.id}-non_performance_reason"
            assert content.count(f'name="{name}"') == 1
            snippet = self._reason_select(content, procedure)
            assert snippet.startswith(f'<select name="{name}"')
            assert 'class="form-select"' in snippet

            fieldset_start = content.rindex("data-followup-reason-section", 0, content.index(f'<select name="{name}"'))
            fieldset = content[fieldset_start : content.index("</fieldset>", fieldset_start)]
            assert fieldset.count("<select") == 1
            assert 'type="radio"' not in fieldset
            assert "form-check" not in fieldset

    def test_compact_reason_select_placeholder_e_ordem_oficial_com_other_por_ultimo(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="RSN-ORDER-001", name="Ordem Causa")
        procedure = _add_procedure(case)

        snippet = self._reason_select(client.get(_form_url(case)).content.decode(), procedure)

        assert self._option_attr(snippet, "value")[0] == ""
        assert self._option_labels(snippet)[0] == REASON_PLACEHOLDER
        assert self._option_labels(snippet)[1:] == [
            label for _value, label in CURRENT_FOLLOWUP_NON_PERFORMANCE_REASON_CHOICES
        ]
        assert self._option_labels(snippet)[-1] == "Outras causas"

    def test_compact_reason_select_sem_legacy_reason_nem_submotivo(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="RSN-NOLEGACY-001", name="Sem Legado")
        procedure = _add_procedure(case)

        content = client.get(_form_url(case)).content.decode()
        snippet = self._reason_select(content, procedure)

        assert 'value="absenteeism"' not in content
        assert 'value="resource_shortage"' not in content
        assert 'value="absenteeism"' not in snippet
        assert 'value="resource_shortage"' not in snippet
        assert f'name="proc_{procedure.id}-resource_shortage_detail"' not in content
        assert "Submotivo da falta de recursos" not in content

    def test_compact_reason_select_mantem_grupo_condicional_de_other(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="RSN-GROUP-001", name="Grupo Other")
        procedure = _add_procedure(case)

        content = client.get(_form_url(case)).content.decode()
        snippet = content[content.index(f"proc_{procedure.id}-performed") :]

        assert '<fieldset class="mb-2" data-followup-reason-section>' in snippet
        assert 'data-followup-detail="other"' in snippet
        assert f'name="proc_{procedure.id}-other_reason"' in snippet
        assert 'data-followup-detail="resource_shortage"' not in content

    @pytest.mark.parametrize("reason", ["missing_exam_consent", "patient_no_show", "emergency_priority"])
    def test_post_official_reason_por_http_grava_sem_texto(self, client, reason: str) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-OFFICIAL", name="Causa Oficial")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = reason
        response = client.post(_form_url(case), data=payload)

        assert response.status_code == 302
        row = CaseFollowUp.objects.get(case=case).procedure_outcomes.get(procedure=procedure)
        assert row.non_performance_reason == reason
        assert row.other_reason == ""

    def test_compact_reason_select_rerender_pos_erro_preserva_estado(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="RSN-RERENDER-001", name="Re-render")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "other"
        response = client.post(_form_url(case), data=payload)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Descreva a outra causa da não realização." in content
        snippet = self._reason_select(content, procedure)
        assert '<option value="other" selected>Outras causas</option>' in snippet
        no_radio_tag = content[content.index('value="no"') :]
        assert "checked" in no_radio_tag[: no_radio_tag.index(">")]
        assert 'data-followup-detail="other"' in content
        assert not CaseFollowUp.objects.filter(case=case).exists()


# ── R4: re-gravação cria versão 2 preservando v1 ───────────────────────


class TestFollowUpSecondVersion:
    """Atualização via HTTP grava nova versão com recorded_by do usuário logado."""

    def test_second_version_http_flow_preserves_v1(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="VER-2-0001", name="Segunda Versão")
        procedure = _add_procedure(case)

        first = client.post(_form_url(case), data=_valid_payload(procedure))
        assert first.status_code == 302

        payload = _valid_payload(procedure, performed="no")
        payload["patient_admitted"] = "no"
        payload[f"proc_{procedure.id}-non_performance_reason"] = "patient_no_show"
        second = client.post(_form_url(case), data=payload)
        assert second.status_code == 302

        versions = list(CaseFollowUp.objects.filter(case=case).order_by("version"))
        assert [v.version for v in versions] == [1, 2]
        assert versions[0].patient_admitted is True
        assert versions[1].patient_admitted is False
        assert all(v.recorded_by == user for v in versions)
        assert versions[0].procedure_outcomes.get().performed is True
        assert versions[1].procedure_outcomes.get().performed is False

        events = {e.event_type for e in case.events.filter(event_type__in=("FOLLOWUP_RECORDED", "FOLLOWUP_UPDATED"))}
        assert events == {"FOLLOWUP_RECORDED", "FOLLOWUP_UPDATED"}

        # Formulário exibe a versão corrente v2 após a atualização.
        page = client.get(_form_url(case))
        assert "v2" in page.content.decode()
        current = get_current_follow_up(case)
        assert current is not None
        assert current.version == 2


# ── R4 (Slice 006): procedimentos especializados no formulário ────────


class TestFollowUpFormSpecializedProcedures:
    """Formulário de follow-up lista e grava Ecoendoscopia/CPRE por row.

    O modelo de follow-up permanece intacto: um ``ProcedureFollowUp`` por
    ``CaseProcedure`` do caso, com o label do catálogo; o que a jornada
    especializada exige é que o bloco apareça na ordem canônica de exibição e
    que o desfecho seja gravado para a row especializada.
    """

    def test_get_lists_specialized_block_with_catalog_label(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="SPEC-FORM-ECHO", name="Paciente Eco Form")
        echo = _add_procedure(case, "echoendoscopy")

        response = client.get(_form_url(case))

        assert response.status_code == 200
        content = response.content.decode()
        assert "🔬 Ecoendoscopia" in content
        assert f'name="proc_{echo.id}-performed"' in content

    def test_get_lists_cpre_block_with_catalog_label(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="SPEC-FORM-CPRE", name="Paciente CPRE Form")
        cpre = _add_procedure(case, "cpre")

        content = client.get(_form_url(case)).content.decode()

        assert "🔬 CPRE" in content
        assert f'name="proc_{cpre.id}-performed"' in content

    def test_get_orders_blocks_in_catalog_display_order(self, client) -> None:
        """Ordem canônica do catálogo: EDA → Colonoscopia → Ecoendoscopia → CPRE."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="SPEC-FORM-ORDER", name="Ordem Catalogo")
        cpre = _add_procedure(case, "cpre")
        echo = _add_procedure(case, "echoendoscopy")
        colon = _add_procedure(case, "colonoscopy")
        eda = _add_procedure(case, "eda")

        content = client.get(_form_url(case)).content.decode()

        positions = [content.index(f'data-followup-proc-id="{p.id}"') for p in (eda, colon, echo, cpre)]
        assert positions == sorted(positions)

    def test_post_records_outcome_for_echoendoscopy_row(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="SPEC-FORM-POST-ECHO", name="Registro Eco")
        echo = _add_procedure(case, "echoendoscopy")

        response = client.post(_form_url(case), data=_valid_payload(echo))

        assert response.status_code == 302
        outcome = CaseFollowUp.objects.get(case=case).procedure_outcomes.get()
        assert outcome.procedure_id == echo.id
        assert outcome.performed is True
        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert event.payload["outcomes"][0]["procedure_type"] == "echoendoscopy"

    def test_post_records_non_performance_for_cpre_row(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="SPEC-FORM-POST-CPRE", name="Registro CPRE")
        cpre = _add_procedure(case, "cpre")

        payload = _valid_payload(cpre, performed="no")
        payload[f"proc_{cpre.id}-non_performance_reason"] = "patient_no_show"
        response = client.post(_form_url(case), data=payload)

        assert response.status_code == 302
        outcome = CaseFollowUp.objects.get(case=case).procedure_outcomes.get()
        assert outcome.procedure_id == cpre.id
        assert outcome.performed is False
        assert outcome.non_performance_reason == "patient_no_show"


# ── Cobertura restrita às rows autorizadas (ADR-0007 / R2, R3) ─────────


class TestFollowUpFormAuthorizedOnly:
    """O formulário projeta somente rows autorizadas; o resto é rejeitado."""

    def test_get_shows_only_authorized_block_after_swap(self, client) -> None:
        """Troca (EDA negada + Ecoendoscopia autorizada): só o bloco autorizado."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="AUTH-SWAP-GET", name="Troca GET")
        eda = _add_procedure(case, "eda", disposition="denied")
        echo = _add_procedure(case, "echoendoscopy", disposition="approved")

        content = client.get(_form_url(case)).content.decode()

        assert f'name="proc_{echo.id}-performed"' in content
        assert f'name="proc_{eda.id}-performed"' not in content

    def test_post_swap_records_only_authorized_row(self, client) -> None:
        """POST cobrindo a Ecoendoscopia cria v1 e evento só com a autorizada."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="AUTH-SWAP-POST", name="Troca POST")
        _add_procedure(case, "eda", disposition="denied")
        echo = _add_procedure(case, "echoendoscopy", disposition="approved")

        response = client.post(_form_url(case), data=_valid_payload(echo))

        assert response.status_code == 302
        follow_up = CaseFollowUp.objects.get(case=case)
        assert follow_up.version == 1
        assert [row.procedure_id for row in follow_up.procedure_outcomes.all()] == [echo.id]
        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert [payload["procedure_id"] for payload in event.payload["outcomes"]] == [echo.id]
        assert not CaseEvent.objects.filter(case=case, event_type="FOLLOWUP_UPDATED").exists()

    def test_get_shows_only_authorized_block_partial_approval(self, client) -> None:
        """Aprovação parcial (EDA autorizada + Colonoscopia negada): só a EDA."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="AUTH-PARTIAL-GET", name="Parcial GET")
        eda = _add_procedure(case, "eda", disposition="approved")
        colon = _add_procedure(case, "colonoscopy", disposition="denied")

        content = client.get(_form_url(case)).content.decode()

        assert f'name="proc_{eda.id}-performed"' in content
        assert f'name="proc_{colon.id}-performed"' not in content

    def test_post_partial_approval_records_only_authorized(self, client) -> None:
        """POST cobrindo só a EDA é aceito sem exigir desfecho da negada."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="AUTH-PARTIAL-POST", name="Parcial POST")
        eda = _add_procedure(case, "eda", disposition="approved")
        _add_procedure(case, "colonoscopy", disposition="denied")

        response = client.post(_form_url(case), data=_valid_payload(eda))

        assert response.status_code == 302
        follow_up = CaseFollowUp.objects.get(case=case)
        assert [row.procedure_id for row in follow_up.procedure_outcomes.all()] == [eda.id]

    def test_zero_approved_shows_warning_and_rejects_post(self, client) -> None:
        """Sem rows autorizadas (defensivo): aviso, sem campos, POST rejeitado."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="AUTH-ZERO", name="Zero Autorizada")
        _add_procedure(case, "eda", disposition="denied")

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert "sem procedimentos" in content.lower()
        assert "proc_" not in content

        response = client.post(_form_url(case), data={"patient_admitted": "yes"})
        assert response.status_code == 200
        assert not CaseFollowUp.objects.filter(case=case).exists()
        assert not CaseEvent.objects.filter(case=case, event_type__startswith="FOLLOWUP").exists()

    def test_post_with_outcome_for_denied_row_rejected(self, client) -> None:
        """Desfecho para row negada no POST é rejeitado fail-closed."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="AUTH-DENIED-POST", name="Negada POST")
        eda = _add_procedure(case, "eda", disposition="approved")
        colon = _add_procedure(case, "colonoscopy", disposition="denied")

        payload = _valid_payload(eda)
        payload[f"proc_{colon.id}-performed"] = "yes"
        response = client.post(_form_url(case), data=payload)

        assert response.status_code == 200
        assert not CaseFollowUp.objects.filter(case=case).exists()


# ── R5: JS apenas show/hide, incluído pelo template ────────────────────


class TestFollowUpFormJs:
    """Template inclui static/js/followup_form.js (sem lógica de negócio no cliente)."""

    def test_js_include_on_form_page(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="JS-INC-001", name="Com JS")
        _add_procedure(case)

        response = client.get(_form_url(case))
        assert response.status_code == 200
        assert "/static/js/followup_form.js" in response.content.decode()


# ── R6: card da listagem linka para o formulário (fim a fim) ───────────


class TestFollowUpListLink:
    """Listagem → formulário → volta à lista funciona ponta a ponta."""

    def test_list_link_to_form_roundtrip(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="LINK-0001", name="Com Link")
        procedure = _add_procedure(case)

        response = client.get(reverse("dashboard:followup_list"))
        assert response.status_code == 200
        content = response.content.decode()
        form_url = _form_url(case)
        assert form_url in content

        # Segue o link do card → formulário 200 → POST válido volta à lista.
        form_page = client.get(form_url)
        assert form_page.status_code == 200
        posted = client.post(form_url, data=_valid_payload(procedure))
        assert posted.status_code == 302
        assert posted.url == reverse("dashboard:followup_list")
