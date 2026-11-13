"""Integração S2: Agendador pesquisa/registra/atualiza e consulta/exporta Pós-Procedimento (S2.R1–R5).

Scheduler-only na intranet: menu operacional → busca global de elegíveis →
formulário → versões auditáveis entre autores, e sub-aba Histórico &
Exportação com a mesma população/resumos/filtros/CSV do supervisor.
Demais superfícies gerenciais permanecem negadas.
"""

import csv
import io
import uuid
from datetime import datetime, time, timedelta
from typing import cast

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.cases.followup import ProcedureOutcomeInput, record_case_follow_up
from apps.cases.models import (
    Case,
    CaseAttachment,
    CaseEvent,
    CaseFollowUp,
    CaseProcedure,
    CaseStatus,
    ProcedureFollowUp,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

LIST_URL = reverse("dashboard:followup_list")
HISTORY_URL = reverse("dashboard:followup_history")
EXPORT_URL = reverse("dashboard:followup_history_export")
EXTERNAL_IP = "203.0.113.10"


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, username: str, role_names: list[str], *, active_role: str):
    """Cria/login usuário com os papéis exatos e papel ativo informado."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=username, password="testpass123")
    for role_name in role_names:
        role, _ = Role.objects.get_or_create(name=role_name)
        user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = active_role
    session.save()
    return user


def _scheduler_client(username: str = "sched-s1@test"):
    client = Client()
    user = _login_as(client, username, ["scheduler"], active_role="scheduler")
    return client, user


def _manager_client(username: str = "mgr-s1@test"):
    client = Client()
    user = _login_as(client, username, ["manager", "scheduler"], active_role="manager")
    return client, user


def _local_dt(*, day_offset: int, hour: int = 10, minute: int = 0) -> datetime:
    day = timezone.localdate() + timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())


def _scheduled_case(created_by, *, arn: str, name: str, when=None) -> Case:
    case = Case.objects.create(
        created_by=created_by,
        agency_record_number=arn,
        appointment_status="confirmed",
        appointment_at=when if when is not None else _local_dt(day_offset=0),
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _immediate_case(created_by, *, arn: str, name: str) -> Case:
    case = Case.objects.create(
        created_by=created_by,
        agency_record_number=arn,
        doctor_admission_flow="immediate",
        doctor_decided_at=_local_dt(day_offset=0, hour=8),
        doctor_decision="accept",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _ineligible_case(created_by, *, arn: str, name: str) -> Case:
    case = Case.objects.create(
        created_by=created_by,
        agency_record_number=arn,
        appointment_status="confirmed",
        appointment_at=None,
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _add_procedure(case: Case, procedure_type: str = "eda", *, disposition: str = "approved") -> CaseProcedure:
    return CaseProcedure.objects.create(case=case, procedure_type=procedure_type, doctor_disposition=disposition)


def _form_url(case: Case) -> str:
    return reverse("dashboard:followup_form", args=[str(case.case_id)])


def _payload(procedure: CaseProcedure, *, performed: str = "yes") -> dict[str, str]:
    return {"patient_admitted": "yes", f"proc_{procedure.id}-performed": performed}


def _assert_blocked_by_guard(response) -> None:
    """Negativa de autorização: 302 para "/" (guard), nunca 404/200/403."""
    assert response.status_code == 302
    assert response.url == "/"


def _assert_no_followup_writes(case: Case, *, count: int = 0) -> None:
    assert CaseFollowUp.objects.filter(case=case).count() == count
    if count == 0:
        assert not CaseEvent.objects.filter(
            case=case, event_type__in=("FOLLOWUP_RECORDED", "FOLLOWUP_UPDATED")
        ).exists()


# ── S1.R1: política HTTP lista/form; histórico/CSV ainda negados ──────────


class TestSchedulerFollowupPolicyHttp:
    """S2.R1 — scheduler acessa lista/form/histórico/CSV; demais papéis seguem negados."""

    def test_scheduler_only_list_and_form_200(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-LIST-001", name="Paciente Lista")
        _add_procedure(case)
        assert sched_client.get(LIST_URL).status_code == 200
        assert sched_client.get(_form_url(case)).status_code == 200

    def test_scheduler_only_post_valid_creates_v1(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-POST-001", name="Paciente Post")
        procedure = _add_procedure(case)
        response = sched_client.post(_form_url(case), data=_payload(procedure))
        assert response.status_code == 302
        assert response.url == LIST_URL
        follow_up = CaseFollowUp.objects.get(case=case)
        assert follow_up.version == 1
        assert follow_up.recorded_by_id == user.id
        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert event.payload  # snapshot do desfecho presente

    @pytest.mark.parametrize("url", [HISTORY_URL, EXPORT_URL])
    def test_scheduler_only_history_and_csv_allowed(self, client, url: str) -> None:
        """S2.R1: scheduler-only interno acessa histórico e CSV por URL direta."""
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S2-HIST-001", name="Paciente Histórico")
        procedure = _add_procedure(case)
        from apps.cases.followup import ProcedureOutcomeInput, record_case_follow_up

        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=procedure.id, performed=True)],
        )
        response = sched_client.get(url)
        assert response.status_code == 200
        if url == EXPORT_URL:
            assert response["Content-Type"] == "text/csv; charset=utf-8"

    @pytest.mark.parametrize("url", [HISTORY_URL, EXPORT_URL])
    def test_multi_role_scheduler_active_history_and_csv_allowed(self, client, url: str) -> None:
        """S2.R1: conta multi-role com scheduler ativo acessa histórico/CSV."""
        multi_client = Client()
        _login_as(multi_client, "multi-s2@test", ["scheduler", "manager"], active_role="scheduler")
        response = multi_client.get(url)
        assert response.status_code == 200

    @pytest.mark.parametrize("role_name", ["doctor", "nir"])
    def test_doctor_nir_history_and_csv_denied(self, client, role_name: str) -> None:
        """S2.R1: doctor/nir ativos (mesmo com scheduler atribuído) seguem negados."""
        other_client = Client()
        _login_as(other_client, f"{role_name}-s2-history@test", [role_name, "scheduler"], active_role=role_name)
        _assert_blocked_by_guard(other_client.get(HISTORY_URL))
        _assert_blocked_by_guard(other_client.get(EXPORT_URL))

    @pytest.mark.parametrize("role_name", ["doctor", "nir"])
    def test_doctor_nir_active_with_scheduler_assigned_denied(self, client, role_name: str) -> None:
        other_client = Client()
        _login_as(other_client, f"{role_name}-s1@test", [role_name, "scheduler"], active_role=role_name)
        _assert_blocked_by_guard(other_client.get(LIST_URL))

    def test_manager_without_chd_denied(self, client) -> None:
        plain_client = Client()
        _login_as(plain_client, "plain-mgr-s1@test", ["manager"], active_role="manager")
        _assert_blocked_by_guard(plain_client.get(LIST_URL))

    def test_anonymous_and_inactive_denied(self, client) -> None:
        response = client.get(LIST_URL)
        assert response.status_code == 302
        assert "/login/" in response.url

        inactive_client = Client()
        user = _login_as(inactive_client, "inactive-sched@test", ["scheduler"], active_role="scheduler")
        user.is_active = False
        user.save(update_fields=["is_active"])
        # Usuário inativo é tratado como anônimo pelo auth do Django:
        # redirect para login (ou "/"), sempre sem dados de follow-up.
        inactive_response = inactive_client.get(LIST_URL)
        assert inactive_response.status_code == 302
        inactive_url = getattr(inactive_response, "url", "")
        assert inactive_url == "/" or "/login/" in inactive_url

    def test_supervisor_and_admin_keep_list_and_form(self, client) -> None:
        mgr_client, mgr = _manager_client()
        case = _scheduled_case(mgr, arn="S1-KEEP-001", name="Mantém Acesso")
        _add_procedure(case)
        assert mgr_client.get(LIST_URL).status_code == 200
        assert mgr_client.get(_form_url(case)).status_code == 200

        admin_client = Client()
        _login_as(admin_client, "admin-s1@test", ["admin"], active_role="admin")
        assert admin_client.get(LIST_URL).status_code == 200


# ── S1.R2/R3: jornada global, navegação operacional e versões ─────────────


class TestSchedulerFollowupJourney:
    """S1.R2–R3 — busca global, nav operacional, versões entre autores."""

    def test_search_lists_third_party_and_immediate_by_name_occurrence_and_date(self, client) -> None:
        sched_client, _ = _scheduler_client()
        other = User.objects.create_user(username="other-sched@test", password="testpass123")
        third = _scheduled_case(other, arn="S1-THIRD-001", name="Terceiro Agendado")
        imm = _immediate_case(other, arn="S1-IMM-001", name="Vinda Imediata")
        _add_procedure(third)
        _add_procedure(imm)

        by_name = sched_client.get(LIST_URL, {"q": "Terceiro"})
        assert by_name.status_code == 200
        assert "S1-THIRD-001" in by_name.content.decode()

        by_occurrence = sched_client.get(LIST_URL, {"q": "S1-IMM-001"})
        assert "Vinda Imediata" in by_occurrence.content.decode()

        by_date = sched_client.get(LIST_URL, {"date": timezone.localdate().isoformat()})
        content = by_date.content.decode()
        assert "S1-THIRD-001" in content
        assert "S1-IMM-001" in content

    def test_scheduler_menu_entry_and_operational_nav(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-NAV-001", name="Paciente Nav")
        _add_procedure(case)

        queue = sched_client.get(reverse("scheduler:queue"))
        assert queue.status_code == 200
        assert LIST_URL in queue.content.decode()
        assert "Pós-Procedimento" in queue.content.decode()

        for response in (sched_client.get(LIST_URL), sched_client.get(_form_url(case))):
            content = response.content.decode()
            assert reverse("scheduler:queue") in content
            assert LIST_URL in content
            # Nav operacional: sem links administrativos.
            # (href exato: "/dashboard/" é prefixo de "/dashboard/follow-ups/".
            assert 'href="/dashboard/"' not in content
            assert reverse("admin_ui:prompt_list") not in content
            assert reverse("admin_ui:user_list") not in content

        # S2.R2: ambas as sub-abas visíveis na jornada do Agendador.
        for response in (sched_client.get(LIST_URL), sched_client.get(HISTORY_URL)):
            content = response.content.decode()
            assert HISTORY_URL in content
            assert "Histórico &amp; Exportação" in content
            assert LIST_URL in content
            assert reverse("scheduler:queue") in content
            assert 'href="/dashboard/"' not in content
            assert reverse("admin_ui:prompt_list") not in content
            assert reverse("admin_ui:user_list") not in content

        # Entrada Pós-Procedimento ativa na lista (sem ativar as abas operacionais).
        list_content = sched_client.get(LIST_URL).content.decode()
        assert "nav-link active" in list_content and LIST_URL in list_content
        assert "tab=pending" in list_content  # abas operacionais preservadas

    def test_supervisor_keeps_dashboard_nav_and_both_subtabs(self, client) -> None:
        mgr_client, _ = _manager_client()
        content = mgr_client.get(LIST_URL).content.decode()
        assert reverse("dashboard:index") in content
        assert reverse("admin_ui:prompt_list") in content
        assert HISTORY_URL in content
        assert "Histórico &amp; Exportação" in content

    def test_cross_role_versions_v1_supervisor_v2_scheduler_v3_supervisor(self, client) -> None:
        sched_client, scheduler = _scheduler_client()
        mgr_client, supervisor = _manager_client()
        case = _scheduled_case(supervisor, arn="S1-VERSIONS-001", name="Paciente Versões")
        procedure = _add_procedure(case)
        status_before = case.status
        appointment_before = case.appointment_at
        decision_before = case.doctor_decision

        record_case_follow_up(
            case=case,
            performed_by=supervisor,
            patient_admitted=True,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=procedure.id, performed=True)],
        )
        response = sched_client.post(_form_url(case), data=_payload(procedure))
        assert response.status_code == 302

        response = mgr_client.post(_form_url(case), data=_payload(procedure))
        assert response.status_code == 302

        follow_ups = list(CaseFollowUp.objects.filter(case=case).order_by("version"))
        assert [f.version for f in follow_ups] == [1, 2, 3]
        assert [f.recorded_by_id for f in follow_ups] == [supervisor.id, scheduler.id, supervisor.id]
        events = list(
            CaseEvent.objects.filter(case=case, event_type__in=("FOLLOWUP_RECORDED", "FOLLOWUP_UPDATED")).order_by(
                "timestamp"
            )
        )
        assert [e.event_type for e in events] == ["FOLLOWUP_RECORDED", "FOLLOWUP_UPDATED", "FOLLOWUP_UPDATED"]

        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status == status_before
        assert fresh_case.appointment_at == appointment_before
        assert fresh_case.doctor_decision == decision_before

        # Supervisor vê a versão corrente e o histórico de versões no formulário.
        form = mgr_client.get(_form_url(case))
        content = form.content.decode()
        assert "v3" in content
        assert "Versões do pós-procedimento" in content
        assert scheduler.username in content

    @pytest.mark.parametrize("kind", ["ineligible", "missing"])
    def test_ineligible_and_missing_case_404_without_writes(self, client, kind: str) -> None:
        sched_client, user = _scheduler_client()
        if kind == "ineligible":
            case = _ineligible_case(user, arn="S1-INEL-001", name="Inelegível")
            url = _form_url(case)
        else:
            case = None
            url = reverse("dashboard:followup_form", args=[str(uuid.uuid4())])
        assert sched_client.get(url).status_code == 404
        assert sched_client.post(url, data={}).status_code == 404
        if case is not None:
            _assert_no_followup_writes(case)

    @pytest.mark.parametrize(
        "mutate",
        ["missing_reason", "legacy_reason", "other_without_text", "foreign_procedure"],
    )
    def test_invalid_post_rejected_without_writes_and_keeps_journey(self, client, mutate: str) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn=f"S1-BAD-{mutate[:6]}-001", name="Paciente Inválido")
        procedure = _add_procedure(case)
        payload = _payload(procedure, performed="no")
        if mutate == "legacy_reason":
            payload[f"proc_{procedure.id}-non_performance_reason"] = "resource_shortage"
        elif mutate == "other_without_text":
            payload[f"proc_{procedure.id}-non_performance_reason"] = "other"
        elif mutate == "foreign_procedure":
            payload = _payload(procedure)
            payload["proc_99999-performed"] = "yes"
        # missing_reason: nenhum campo de causa enviado

        response = sched_client.post(_form_url(case), data=payload)
        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("scheduler:queue") in content  # jornada operacional preservada
        assert 'href="/dashboard/"' not in content
        _assert_no_followup_writes(case)

    def test_no_authorized_procedure_warns_and_post_writes_nothing(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-NOPROC-001", name="Sem Autorizado")
        # EDA negada não é autorizada: formulário sem campos graváveis.
        _add_procedure(case, "eda", disposition="denied")
        response = sched_client.get(_form_url(case))
        assert response.status_code == 200
        assert "sem procedimentos" in response.content.decode().lower()
        response = sched_client.post(_form_url(case), data={"patient_admitted": "yes"})
        assert response.status_code == 200
        _assert_no_followup_writes(case)

    def test_cancel_and_success_keep_scheduler_journey(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-CANCEL-001", name="Paciente Cancelar")
        procedure = _add_procedure(case)
        form = sched_client.get(_form_url(case)).content.decode()
        assert f'href="{LIST_URL}" class="btn btn-outline-secondary' in form or f'href="{LIST_URL}"' in form
        response = sched_client.post(_form_url(case), data=_payload(procedure))
        assert response.url == LIST_URL
        assert sched_client.get(LIST_URL).status_code == 200


# ── S1.R4: isolamento gerencial ──────────────────────────────────────────


class TestSchedulerManagerialIsolation:
    """S1.R4 — nenhuma superfície gerencial é liberada pelo pós-procedimento."""

    def _resources(self, created_by):
        case = Case.objects.create(
            created_by=created_by, status=CaseStatus.WAIT_DOCTOR, agency_record_number="S1-MGR-001"
        )
        case.pdf_file.save("test.pdf", ContentFile(b"%PDF-1.4 fake pdf"), save=True)
        attachment = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(b"%PDF-1.4 fake attachment", name="anexo.pdf"),
            original_filename="anexo.pdf",
            stored_filename="anexo.pdf",
            content_type="application/pdf",
            size_bytes=24,
            sha256="c" * 64,
            uploaded_by=created_by,
        )
        return case, attachment

    def _managerial_urls(self, case, attachment) -> list[str]:
        return [
            reverse("dashboard:index"),
            reverse("dashboard:summaries"),
            reverse("dashboard:case_detail", args=[case.case_id]),
            reverse("dashboard:case_pdf", args=[case.case_id]),
            reverse("dashboard:pdf_viewer", args=[case.case_id]),
            reverse("dashboard:case_attachment", args=[case.case_id, attachment.attachment_id]),
            reverse("dashboard:attachment_pdf_viewer", args=[case.case_id, attachment.attachment_id]),
            reverse("dashboard:attachment_image_viewer", args=[case.case_id, attachment.attachment_id]),
            reverse("admin_ui:prompt_list"),
            reverse("admin_ui:user_list"),
        ]

    @pytest.mark.parametrize("with_manager_role", [False, True])
    def test_managerial_get_routes_blocked_by_guard(self, client, with_manager_role: bool) -> None:
        """Scheduler-only e multi-role (scheduler ativo): 302 "/" em todas."""
        creator = User.objects.create_user(username="mgr-creator@test", password="testpass123")
        case, attachment = self._resources(creator)
        target_client = Client()
        roles = ["scheduler", "manager"] if with_manager_role else ["scheduler"]
        _login_as(target_client, "mgr-target@test", roles, active_role="scheduler")
        for url in self._managerial_urls(case, attachment):
            response = target_client.get(url)
            _assert_blocked_by_guard(response)
            assert response.get("Content-Type") != "application/pdf"

    def test_administrative_close_post_valid_blocked_without_mutation(self, client) -> None:
        creator = User.objects.create_user(username="close-creator@test", password="testpass123")
        case = Case.objects.create(
            created_by=creator, status=CaseStatus.WAIT_DOCTOR, agency_record_number="S1-CLOSE-001"
        )
        target_client = Client()
        _login_as(target_client, "close-target@test", ["scheduler", "manager"], active_role="scheduler")
        response = target_client.post(
            reverse("dashboard:administrative_close", args=[case.case_id]),
            {"reason_code": "system_bug", "reason_text": "Bug corrigido manualmente"},
        )
        _assert_blocked_by_guard(response)
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status == CaseStatus.WAIT_DOCTOR
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()


# ── S1.R5: política de rede ──────────────────────────────────────────────


class TestSchedulerNetworkPolicy:
    """S2.R4 — intranet/bypass preservados; bypass libera Pós-Procedimento, não gerencial."""

    def test_scheduler_only_external_403_on_list_form_and_post(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-EXT-001", name="Paciente Externo")
        procedure = _add_procedure(case)
        for response in (
            sched_client.get(LIST_URL, REMOTE_ADDR=EXTERNAL_IP),
            sched_client.get(_form_url(case), REMOTE_ADDR=EXTERNAL_IP),
            sched_client.post(_form_url(case), data=_payload(procedure), REMOTE_ADDR=EXTERNAL_IP),
            sched_client.get(HISTORY_URL, REMOTE_ADDR=EXTERNAL_IP),
            sched_client.get(EXPORT_URL, REMOTE_ADDR=EXTERNAL_IP),
        ):
            assert response.status_code == 403
        _assert_no_followup_writes(case)

    def test_scheduler_only_internal_access(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S1-INT-001", name="Paciente Interno")
        _add_procedure(case)
        assert sched_client.get(LIST_URL, REMOTE_ADDR="127.0.0.1").status_code == 200
        assert sched_client.get(_form_url(case), REMOTE_ADDR="127.0.0.1").status_code == 200

    def test_multi_role_external_bypass_preserved_but_not_managerial(self, client) -> None:
        multi_client = Client()
        multi_user = _login_as(multi_client, "multi-ext@test", ["scheduler", "manager"], active_role="scheduler")
        case = _scheduled_case(multi_user, arn="S1-MULTI-EXT-001", name="Paciente Multi")
        assert multi_client.get(LIST_URL, REMOTE_ADDR=EXTERNAL_IP).status_code == 200
        assert multi_client.get(_form_url(case), REMOTE_ADDR=EXTERNAL_IP).status_code == 200
        # S2.R4: bypass libera histórico/CSV (Pós-Procedimento), nunca o dashboard.
        assert multi_client.get(HISTORY_URL, REMOTE_ADDR=EXTERNAL_IP).status_code == 200
        assert multi_client.get(EXPORT_URL, REMOTE_ADDR=EXTERNAL_IP).status_code == 200
        _assert_blocked_by_guard(multi_client.get(reverse("dashboard:index"), REMOTE_ADDR=EXTERNAL_IP))


# ── S2.R2: navegação contextual e sub-abas operacionais ───────────────────


class TestSchedulerHistoryNavigation:
    """S2.R2 — duas sub-abas acessíveis/ativas; histórico usa nav operacional."""

    def test_scheduler_subtabs_active_states_and_navigation(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S2-NAV-001", name="Paciente Subabas")
        _add_procedure(case)

        lista = sched_client.get(LIST_URL)
        assert lista.status_code == 200
        content = lista.content.decode()
        assert f'class="nav-link active" href="{LIST_URL}"' in content
        assert f'class="nav-link " href="{HISTORY_URL}"' in content
        assert reverse("scheduler:queue") in content
        assert 'href="/dashboard/"' not in content
        assert reverse("admin_ui:prompt_list") not in content

        history = sched_client.get(HISTORY_URL)
        assert history.status_code == 200
        content = history.content.decode()
        assert f'class="nav-link active" href="{HISTORY_URL}"' in content
        assert f'class="nav-link " href="{LIST_URL}"' in content
        assert reverse("scheduler:queue") in content
        assert 'href="/dashboard/"' not in content
        assert reverse("admin_ui:prompt_list") not in content
        assert reverse("admin_ui:user_list") not in content
        assert LIST_URL in content
        assert "tab=pending" in content
        assert "Histórico &amp; Exportação" in content
        assert "nav-link active" in content

        back = sched_client.get(LIST_URL)
        assert back.status_code == 200
        assert sched_client.get(_form_url(case)).status_code == 200

    def test_supervisor_and_admin_keep_dashboard_nav_and_subtab_states(self, client) -> None:
        mgr_client, _ = _manager_client()
        for url, active_url, inactive_url in (
            (LIST_URL, LIST_URL, HISTORY_URL),
            (HISTORY_URL, HISTORY_URL, LIST_URL),
        ):
            content = mgr_client.get(url).content.decode()
            assert reverse("dashboard:index") in content
            assert reverse("admin_ui:prompt_list") in content
            assert f'class="nav-link active" href="{active_url}"' in content
            assert f'class="nav-link " href="{inactive_url}"' in content

        admin_client = Client()
        _login_as(admin_client, "admin-s2@test", ["admin"], active_role="admin")
        for url in (LIST_URL, HISTORY_URL):
            assert admin_client.get(url).status_code == 200
        history_content = admin_client.get(HISTORY_URL).content.decode()
        assert HISTORY_URL in history_content

    def test_scheduler_history_access_preserves_registration_flow(self, client) -> None:
        sched_client, user = _scheduler_client()
        case = _scheduled_case(user, arn="S2-FLOW-001", name="Paciente Fluxo")
        procedure = _add_procedure(case)
        assert sched_client.get(HISTORY_URL).status_code == 200
        assert sched_client.get(EXPORT_URL).status_code == 200
        response = sched_client.post(_form_url(case), data=_payload(procedure))
        assert response.status_code == 302
        assert response.url == LIST_URL
        follow_up = CaseFollowUp.objects.get(case=case)
        assert follow_up.version == 1
        history = sched_client.get(HISTORY_URL)
        assert history.status_code == 200
        assert "S2-FLOW-001" in history.content.decode()


# ── S2.R3: paridade de população/versões/filtros/CSV com o supervisor ─────


class TestSchedulerHistoryParity:
    """S2.R3 — mesma população global, versão corrente, autor, filtros e CSV."""

    def _csv_records(self, client, **params):
        response = client.get(EXPORT_URL, params or None)
        assert response.status_code == 200
        assert response.content.startswith(b"\xef\xbb\xbf")
        body = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(body), delimiter=";"))

    def _row_keys(self, response):
        return [
            (
                row["case"].agency_record_number,
                row["procedure_label"],
                row["performed"],
                row["reason"],
                row["admitted"],
                row["version"],
                row["author_label"],
            )
            for row in response.context["page_obj"].object_list
        ]

    def _recorded_population(self, client) -> Client:
        from apps.accounts.models import Role

        sched_client, scheduler = _scheduler_client("sched-parity@test")
        other = User.objects.create_user(username="other-sched-parity@test", password="testpass123")
        scheduler_role, _ = Role.objects.get_or_create(name="scheduler")
        other.roles.add(scheduler_role)
        _, supervisor = _manager_client("mgr-parity@test")

        third = _scheduled_case(other, arn="S2-THIRD-001", name="Terceiro Agendado")
        third_proc = _add_procedure(third)
        record_case_follow_up(
            case=third,
            performed_by=supervisor,
            patient_admitted=False,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=third_proc.id, performed=True)],
        )
        record_case_follow_up(
            case=third,
            performed_by=scheduler,
            patient_admitted=True,
            procedure_outcomes=[
                ProcedureOutcomeInput(
                    procedure_id=third_proc.id, performed=False, non_performance_reason="patient_no_show"
                )
            ],
        )

        immediate = _immediate_case(other, arn="S2-IMMED-001", name="Vinda Imediata")
        imm_proc = _add_procedure(immediate)
        record_case_follow_up(
            case=immediate,
            performed_by=supervisor,
            patient_admitted=False,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=imm_proc.id, performed=True)],
        )

        _add_procedure(_scheduled_case(other, arn="S2-NOFU-001", name="Sem Registro"))
        return cast(Client, sched_client)

    def test_parity_history_summary_rows_and_filters(self, client) -> None:
        sched_client = self._recorded_population(client)
        mgr_client, _ = _manager_client("mgr-parity-check@test")

        sched_history = sched_client.get(HISTORY_URL)
        mgr_history = mgr_client.get(HISTORY_URL)
        assert sched_history.status_code == 200 == mgr_history.status_code
        assert sched_history.context["summary"] == mgr_history.context["summary"]
        assert self._row_keys(sched_history) == self._row_keys(mgr_history)
        assert sched_history.context["rows_total"] == mgr_history.context["rows_total"] == 2
        by_arn = {row["case"].agency_record_number: row for row in sched_history.context["page_obj"].object_list}
        third_row = by_arn["S2-THIRD-001"]
        assert third_row["version"] == 2
        assert third_row["performed"] is False
        assert third_row["reason"] == "patient_no_show"
        assert third_row["admitted"] is True
        assert "sched-parity" in third_row["author_label"]
        assert by_arn["S2-IMMED-001"]["version"] == 1
        assert "S2-NOFU-001" not in sched_history.content.decode()

        for params in (
            {"q": "Terceiro"},
            {"q": "s2-immed"},
            {"performed": "yes"},
            {"performed": "no"},
            {"reason": "patient_no_show"},
            {"admitted": "yes"},
            {"admitted": "no"},
        ):
            sched_page = sched_client.get(HISTORY_URL, params)
            mgr_page = mgr_client.get(HISTORY_URL, params)
            assert self._row_keys(sched_page) == self._row_keys(mgr_page), params
            assert sched_page.context["summary"] == mgr_page.context["summary"], params

    def test_parity_csv_complete_with_filters_and_escaping(self, client) -> None:
        sched_client = self._recorded_population(client)
        mgr_client, _ = _manager_client("mgr-parity-csv@test")

        sched_csv = self._csv_records(sched_client)
        mgr_csv = self._csv_records(mgr_client)
        assert sched_csv == mgr_csv
        assert len(sched_csv) == 3
        assert sched_csv[0][1] == "Ocorrência"
        assert any("sched-parity" in row[11] for row in sched_csv[1:])

        for params in (
            {"q": "Terceiro"},
            {"performed": "no"},
            {"reason": "patient_no_show"},
            {"admitted": "yes"},
            {"performed": "no", "reason": "patient_no_show"},
        ):
            assert self._csv_records(sched_client, **params) == self._csv_records(mgr_client, **params), params

    def test_pagination_over_25_and_csv_not_truncated(self, client) -> None:
        sched_client, scheduler = _scheduler_client("sched-page@test")
        mgr_client, _ = _manager_client("mgr-page@test")
        for i in range(26):
            case = _scheduled_case(scheduler, arn=f"S2-PAGE-{i:02d}", name=f"Paciente Página {i:02d}")
            procedure = _add_procedure(case)
            record_case_follow_up(
                case=case,
                performed_by=scheduler,
                patient_admitted=False,
                procedure_outcomes=[ProcedureOutcomeInput(procedure_id=procedure.id, performed=True)],
            )
        first = sched_client.get(HISTORY_URL)
        assert first.context["page_obj"].paginator.per_page == 25
        assert len(first.context["page_obj"].object_list) == 25
        second = sched_client.get(HISTORY_URL, {"page": 2})
        assert len(second.context["page_obj"].object_list) == 1
        assert self._row_keys(first) == self._row_keys(mgr_client.get(HISTORY_URL))
        assert len(self._csv_records(sched_client)) == 27
        assert self._csv_records(sched_client) == self._csv_records(mgr_client)

    def test_history_and_export_write_nothing(self, client) -> None:
        sched_client = self._recorded_population(client)
        before = (
            CaseFollowUp.objects.count(),
            ProcedureFollowUp.objects.count(),
            CaseEvent.objects.count(),
        )
        assert sched_client.get(HISTORY_URL).status_code == 200
        assert sched_client.get(HISTORY_URL, {"performed": "no"}).status_code == 200
        assert sched_client.get(EXPORT_URL).status_code == 200
        assert sched_client.get(EXPORT_URL, {"reason": "patient_no_show"}).status_code == 200
        after = (
            CaseFollowUp.objects.count(),
            ProcedureFollowUp.objects.count(),
            CaseEvent.objects.count(),
        )
        assert after == before

    def test_scheduler_external_403_includes_new_routes(self, client) -> None:
        sched_client, _ = _scheduler_client("sched-ext-s2@test")
        assert sched_client.get(HISTORY_URL, REMOTE_ADDR=EXTERNAL_IP).status_code == 403
        assert sched_client.get(EXPORT_URL, REMOTE_ADDR=EXTERNAL_IP).status_code == 403

    def test_managerial_post_blocked_after_history_csv_access(self, client) -> None:
        creator = User.objects.create_user(username="close-s2-creator@test", password="testpass123")
        case = Case.objects.create(
            created_by=creator, status=CaseStatus.WAIT_DOCTOR, agency_record_number="S2-CLOSE-001"
        )
        target_client = Client()
        _login_as(target_client, "close-s2-target@test", ["scheduler", "manager"], active_role="scheduler")
        assert target_client.get(HISTORY_URL).status_code == 200
        assert target_client.get(EXPORT_URL).status_code == 200
        response = target_client.post(
            reverse("dashboard:administrative_close", args=[case.case_id]),
            {"reason_code": "system_bug", "reason_text": "Bug corrigido manualmente"},
        )
        _assert_blocked_by_guard(response)
        assert Case.objects.get(pk=case.pk).status == CaseStatus.WAIT_DOCTOR
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()
