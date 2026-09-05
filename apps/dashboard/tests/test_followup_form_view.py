"""Testes do formulário de follow-up do supervisor (Slice 003, R1–R6)."""

import uuid
from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.followup import get_current_follow_up
from apps.cases.models import Case, CaseEvent, CaseFollowUp, CaseProcedure

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str):
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"followup-form-{role_name}@test", password="testpass123")
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


def _add_procedure(case: Case, procedure_type: str = "eda") -> CaseProcedure:
    return CaseProcedure.objects.create(case=case, procedure_type=procedure_type)


def _form_url(case: Case) -> str:
    return reverse("dashboard:followup_form", args=[str(case.case_id)])


def _valid_payload(procedure: CaseProcedure, *, performed: str = "yes") -> dict[str, str]:
    return {
        "patient_admitted": "yes",
        f"proc_{procedure.id}-performed": performed,
    }


# ── R1: acesso, permissões e elegibilidade ──────────────────────────────


class TestFollowUpFormAccess:
    """GET exige login + papel manager/admin; caso inelegível/inválido → 404."""

    def test_get_requires_login(self, client) -> None:
        plain = User.objects.create_user(username="followup-form-anon@test", password="testpass123")
        case = _create_case(plain, arn="NEED-LOGIN", name="Anônimo")
        response = client.get(_form_url(case))
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_get_manager_allowed(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="MGR-OK-001", name="Gerente")
        _add_procedure(case)
        response = client.get(_form_url(case))
        assert response.status_code == 200

    def test_get_admin_allowed(self, client) -> None:
        user = _login_as(client, "admin")
        case = _create_case(user, arn="ADM-OK-001", name="Admin")
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
                ProcedureOutcomeInput(procedure_id=procedure.id, performed=False, non_performance_reason="absenteeism")
            ],
        )

        response = client.get(_form_url(case))
        assert response.status_code == 200
        content = response.content.decode()
        assert "v2" in content
        assert user.username in content
        assert "v1" in content


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
        assert "Follow-up registrado" in list_page.content.decode()

    def test_post_valid_not_performed_with_reason(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-ABS-001", name="Absenteísmo")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "absenteeism"
        response = client.post(_form_url(case), data=payload)
        self._assert_success_redirect(response)

        row = CaseFollowUp.objects.get(case=case).procedure_outcomes.get(procedure=procedure)
        assert row.performed is False
        assert row.non_performance_reason == "absenteeism"

    def test_post_valid_resource_shortage_with_detail(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="POST-RS-001", name="Falta de recursos")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "resource_shortage"
        payload[f"proc_{procedure.id}-resource_shortage_detail"] = "equipment_unavailable"
        response = client.post(_form_url(case), data=payload)
        self._assert_success_redirect(response)

        row = CaseFollowUp.objects.get(case=case).procedure_outcomes.get(procedure=procedure)
        assert row.performed is False
        assert row.resource_shortage_detail == "equipment_unavailable"

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

    def test_post_invalid_resource_shortage_without_detail(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="BAD-NODETAIL", name="Sem Submotivo")
        procedure = _add_procedure(case)

        payload = _valid_payload(procedure, performed="no")
        payload[f"proc_{procedure.id}-non_performance_reason"] = "resource_shortage"
        response = self._post(client, case, payload)
        assert response.status_code == 200
        assert "Informe o submotivo da falta de recursos." in response.content.decode()
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
        payload[f"proc_{procedure.id}-non_performance_reason"] = "absenteeism"
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
