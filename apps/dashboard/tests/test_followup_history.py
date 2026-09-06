"""Testes da página Histórico & Exportação de follow-ups (Slice 001 R1–R8; Slice 002 R1–R7)."""

import csv
import io
from datetime import date, datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.followup import ProcedureOutcomeInput, record_case_follow_up
from apps.cases.models import Case, CaseEvent, CaseFollowUp, CaseProcedure

pytestmark = pytest.mark.django_db

User = get_user_model()

HISTORY_URL = reverse("dashboard:followup_history")
LIST_URL = reverse("dashboard:followup_list")
EXPORT_URL = reverse("dashboard:followup_history_export")

# Header PT-BR fixo do CSV (design D5 / R2) — ordem exata das 13 colunas.
CSV_HEADER = [
    "Case ID",
    "Ocorrência",
    "Paciente",
    "Data",
    "Procedimento",
    "Desfecho",
    "Causa",
    "Submotivo",
    "Outra causa (texto)",
    "Internação",
    "Versão",
    "Registrado por",
    "Registrado em",
]
CSV_COL = {name: index for index, name in enumerate(CSV_HEADER)}


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str):
    """Cria usuário com papel, faz login e define active_role na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"followup-history-{role_name}@test", password="testpass123")
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


def _local_day(day_offset: int) -> datetime:
    """Datetime aware à meia-noite local do dia (hoje + day_offset)."""
    day = timezone.localdate() + timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(day, time(0, 0)), timezone.get_current_timezone())


def _create_scheduled_case(user, *, arn: str, name: str, when: datetime) -> Case:
    """Caso agendado confirmado (data de grupo = dia local de appointment_at)."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        appointment_status="confirmed",
        appointment_at=when,
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _outcome_inputs(
    case: Case,
    *,
    procedure_types: tuple[str, ...] = ("eda",),
    performed: bool = True,
    reason: str = "",
    detail: str = "",
    other: str = "",
) -> list[ProcedureOutcomeInput]:
    """Inputs de desfecho para os tipos informados (cria CaseProcedure se faltar)."""
    outcomes: list[ProcedureOutcomeInput] = []
    for procedure_type in procedure_types:
        procedure, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type=procedure_type)
        outcomes.append(
            ProcedureOutcomeInput(
                procedure_id=procedure.id,
                performed=performed,
                non_performance_reason=reason,
                resource_shortage_detail=detail,
                other_reason=other,
            )
        )
    return outcomes


def _record(
    case: Case,
    user,
    *,
    admitted: bool = False,
    procedure_types: tuple[str, ...] = ("eda",),
    performed: bool = True,
    reason: str = "",
    detail: str = "",
    other: str = "",
) -> CaseFollowUp:
    """Grava uma nova versão do follow-up do caso."""
    return record_case_follow_up(
        case=case,
        performed_by=user,
        patient_admitted=admitted,
        procedure_outcomes=_outcome_inputs(
            case,
            procedure_types=procedure_types,
            performed=performed,
            reason=reason,
            detail=detail,
            other=other,
        ),
    )


def _set_recorded_at(case: Case, when: datetime) -> None:
    """Reescreve o instante de gravação (para dissociá-lo da data de grupo)."""
    CaseFollowUp.objects.filter(case=case).update(recorded_at=when)


def _history_arns(response) -> list[str]:
    """Ocorrências (ARNs) na ordem das linhas da tabela da página."""
    return [row["case"].agency_record_number for row in response.context["page_obj"].object_list]


def _default_window() -> tuple[date, date]:
    """Janela default: hoje-6 .. hoje (datas locais)."""
    today = timezone.localdate()
    return today - timedelta(days=6), today


def _window_header(start, end) -> str:
    """Texto do header da página com a janela ativa (dd/mm/yyyy)."""
    return f"Janela: {start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}"


def _export_csv(client, **params) -> list[list[str]]:
    """Baixa o CSV e re-parseia com csv.reader (delimiter ';'), BOM removido.

    Re-parse obrigatório para conteúdos escapados: nunca assert de string crua
    quando a célula contém ';', aspas ou quebras (R4).
    """
    response = client.get(EXPORT_URL, params or None)
    assert response.status_code == 200
    body = response.content.decode("utf-8-sig")  # remove o BOM \ufeff
    return list(csv.reader(io.StringIO(body), delimiter=";"))


# ── R8: acesso e guard ──────────────────────────────────────────────────


class TestHistoryAccess:
    """GET /dashboard/follow-ups/history/ exige login + papel manager/admin."""

    def test_anonymous_redirected_to_login(self, client) -> None:
        response = client.get(HISTORY_URL)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_manager_allowed(self, client) -> None:
        _login_as(client, "manager")
        response = client.get(HISTORY_URL)
        assert response.status_code == 200

    def test_admin_allowed(self, client) -> None:
        _login_as(client, "admin")
        response = client.get(HISTORY_URL)
        assert response.status_code == 200

    @pytest.mark.parametrize("role_name", ["nir", "doctor", "scheduler"])
    def test_other_roles_redirected(self, client, role_name: str) -> None:
        _login_as(client, role_name)
        response = client.get(HISTORY_URL)
        assert response.status_code == 302


# ── R2: sub-abas Registrar | Histórico & Exportação ─────────────────────


class TestFollowupTabs:
    """Sub-abas via partial sob o pill Follow-up, ativa conforme a página."""

    def test_list_page_shows_tabs_with_registrar_active(self, client) -> None:
        _login_as(client, "manager")
        response = client.get(LIST_URL)
        content = response.content.decode()
        assert "Registrar" in content
        assert "Histórico &amp; Exportação" in content
        assert f'class="nav-link active" href="{LIST_URL}"' in content
        assert f'class="nav-link " href="{HISTORY_URL}"' in content

    def test_history_page_shows_tabs_with_history_active(self, client) -> None:
        _login_as(client, "manager")
        response = client.get(HISTORY_URL)
        content = response.content.decode()
        assert "Registrar" in content
        assert "Histórico &amp; Exportação" in content
        assert f'class="nav-link active" href="{HISTORY_URL}"' in content
        assert f'class="nav-link " href="{LIST_URL}"' in content


# ── R3: população = casos com follow-up, versão corrente ────────────────


class TestHistoryPopulation:
    """Só casos com follow-up entram; cada caso 1x pela versão corrente."""

    def test_casos_elegiveis_sem_followup_nao_aparecem(self, client) -> None:
        user = _login_as(client, "manager")
        com_followup = _create_scheduled_case(user, arn="COM-FU", name="Com Follow-up", when=_local_dt(day_offset=0))
        _record(com_followup, user)
        _create_scheduled_case(user, arn="SEM-FU", name="Elegível sem follow-up", when=_local_dt(day_offset=0, hour=15))

        response = client.get(HISTORY_URL)
        assert _history_arns(response) == ["COM-FU"]
        content = response.content.decode()
        assert "SEM-FU" not in content

    def test_versao_corrente_aparece_uma_vez_com_dados_da_v2(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_scheduled_case(user, arn="VERSAO-001", name="Paciente Versão", when=_local_dt(day_offset=0))
        _record(case, user, performed=False, reason="absenteeism")  # v1
        _record(case, user, performed=True, admitted=True)  # v2

        response = client.get(HISTORY_URL)
        rows = response.context["page_obj"].object_list
        assert len(rows) == 1
        assert rows[0]["version"] == 2
        assert rows[0]["performed"] is True
        assert rows[0]["admitted"] is True
        assert response.context["summary"]["cases"] == 1

        content = response.content.decode()
        assert content.count("VERSAO-001") == 1
        assert "v2" in content
        assert "Absenteísmo" not in content


# ── R4/R4b: janela por data de grupo (nunca recorded_at) ────────────────


class TestHistoryWindow:
    """Default hoje-6..hoje; ?start/?end válidos respeitados; inválidos caem no default."""

    def test_default_window_inclui_hoje_e_hoje_menos_6(self, client) -> None:
        user = _login_as(client, "manager")
        for arn, offset in (("HOJE", 0), ("MENOS-6", -6), ("MENOS-7", -7), ("MAIS-1", 1)):
            case = _create_scheduled_case(user, arn=arn, name=f"Paciente {arn}", when=_local_dt(day_offset=offset))
            _record(case, user)

        response = client.get(HISTORY_URL)
        assert sorted(_history_arns(response)) == ["HOJE", "MENOS-6"]
        start, end = _default_window()
        assert _window_header(start, end) in response.content.decode()

    def test_custom_window_valid_respected_with_header_and_echo(self, client) -> None:
        user = _login_as(client, "manager")
        start_day = timezone.localdate() - timedelta(days=2)
        end_day = timezone.localdate() + timedelta(days=2)
        cases = (
            ("INI-2", start_day, 9),
            ("FIM-2", end_day, 11),
            ("FORA-3", end_day + timedelta(days=1), 9),
        )
        for arn, day, hour in cases:
            when = timezone.make_aware(datetime.combine(day, time(hour)), timezone.get_current_timezone())
            case = _create_scheduled_case(user, arn=arn, name=f"Paciente {arn}", when=when)
            _record(case, user)

        params = {"start": start_day.isoformat(), "end": end_day.isoformat()}
        response = client.get(HISTORY_URL, params)
        assert sorted(_history_arns(response)) == ["FIM-2", "INI-2"]
        assert response.context["start_value"] == start_day.isoformat()
        assert response.context["end_value"] == end_day.isoformat()
        assert _window_header(start_day, end_day) in response.content.decode()

    @pytest.mark.parametrize("scenario", ["invalid", "inverted", "too_wide"])
    def test_window_inconsistente_cai_no_default(self, client, scenario: str) -> None:
        user = _login_as(client, "manager")
        today = timezone.localdate()
        end_10 = (today + timedelta(days=10)).isoformat()
        if scenario == "invalid":
            start_raw, end_raw = "nao-e-data", end_10
        elif scenario == "inverted":
            start_raw, end_raw = end_10, today.isoformat()
        else:  # too_wide: período > 31 dias
            start_raw = (today - timedelta(days=20)).isoformat()
            end_raw = (today + timedelta(days=20)).isoformat()

        hoje = _create_scheduled_case(user, arn="HOJE-FALLBACK", name="Hoje", when=_local_dt(day_offset=0))
        _record(hoje, user)
        futuro = _create_scheduled_case(user, arn="FUTURO-FALLBACK", name="Futuro", when=_local_dt(day_offset=10))
        _record(futuro, user)

        response = client.get(HISTORY_URL, {"start": start_raw, "end": end_raw})
        assert _history_arns(response) == ["HOJE-FALLBACK"]
        assert "FUTURO-FALLBACK" not in response.content.decode()
        start, end = _default_window()
        assert _window_header(start, end) in response.content.decode()

    def test_eixo_eh_data_de_grupo_e_nao_recorded_at(self, client) -> None:
        """R4b: grupo dentro/recorded fora aparece; grupo fora/recorded dentro não aparece."""
        user = _login_as(client, "manager")
        hoje = timezone.localdate()

        grupo_dentro = _create_scheduled_case(
            user, arn="GRUPO-DENTRO", name="Grupo Hoje", when=_local_dt(day_offset=0, hour=9)
        )
        _record(grupo_dentro, user)
        _set_recorded_at(grupo_dentro, _local_dt(day_offset=-20, hour=23, minute=59))

        grupo_fora = _create_scheduled_case(
            user, arn="GRUPO-FORA", name="Grupo Antigo", when=_local_dt(day_offset=-20, hour=9)
        )
        _record(grupo_fora, user)
        _set_recorded_at(grupo_fora, _local_dt(day_offset=0, hour=8))

        assert _default_window()[0] <= hoje <= _default_window()[1]
        response = client.get(HISTORY_URL)
        assert _history_arns(response) == ["GRUPO-DENTRO"]


# ── R5: busca ?q= por ocorrência/nome dentro da janela ─────────────────


class TestHistorySearch:
    """Busca filtra a população da janela; o termo persiste no input."""

    def test_busca_por_ocorrencia_case_insensitive(self, client) -> None:
        user = _login_as(client, "manager")
        alvo = _create_scheduled_case(user, arn="HIS-ABC-001", name="Maria Silva", when=_local_dt(day_offset=0))
        _record(alvo, user)
        outro = _create_scheduled_case(
            user, arn="HIS-XYZ-002", name="João Souza", when=_local_dt(day_offset=0, hour=15)
        )
        _record(outro, user)

        response = client.get(HISTORY_URL, {"q": "his-abc"})
        assert _history_arns(response) == ["HIS-ABC-001"]
        assert 'value="his-abc"' in response.content.decode()

    def test_busca_por_nome_case_insensitive(self, client) -> None:
        user = _login_as(client, "manager")
        alvo = _create_scheduled_case(user, arn="HIS-ABC-001", name="Maria Silva", when=_local_dt(day_offset=0))
        _record(alvo, user)
        outro = _create_scheduled_case(
            user, arn="HIS-XYZ-002", name="João Souza", when=_local_dt(day_offset=0, hour=15)
        )
        _record(outro, user)

        response = client.get(HISTORY_URL, {"q": "maria"})
        assert _history_arns(response) == ["HIS-ABC-001"]
        assert 'value="maria"' in response.content.decode()

    def test_busca_fica_dentro_da_janela(self, client) -> None:
        user = _login_as(client, "manager")
        dentro = _create_scheduled_case(user, arn="JANELA-DENTRO", name="Alvo Na Janela", when=_local_dt(day_offset=0))
        _record(dentro, user)
        fora = _create_scheduled_case(user, arn="JANELA-FORA", name="Alvo Fora", when=_local_dt(day_offset=-20))
        _record(fora, user)

        response = client.get(HISTORY_URL, {"q": "Alvo"})
        assert _history_arns(response) == ["JANELA-DENTRO"]
        assert "JANELA-FORA" not in response.content.decode()


# ── R6: cards-resumo do período (janela + busca) ────────────────────────


class TestHistoryCards:
    """Cards refletem a população da janela + busca, sem JS."""

    def test_cards_resumo_do_periodo_no_html(self, client) -> None:
        user = _login_as(client, "manager")
        caso_a = _create_scheduled_case(user, arn="CARDS-A", name="Paciente A", when=_local_dt(day_offset=0, hour=9))
        _record(caso_a, user, performed=True, admitted=True)
        caso_b = _create_scheduled_case(user, arn="CARDS-B", name="Paciente B", when=_local_dt(day_offset=0, hour=11))
        _record(
            caso_b,
            user,
            performed=False,
            reason="resource_shortage",
            detail="emergency_occupied",
            admitted=False,
        )

        response = client.get(HISTORY_URL)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Resumo do período" in content
        assert "Casos com follow-up no período" in content
        assert "Internações no período" in content
        assert "Taxa de realização por procedimento" in content
        assert "Causas de não realização" in content
        assert "1 de 2 realizados (50%)" in content
        assert "width: 50%" in content
        assert "Cancelamento por falta de recursos no dia" in content
        assert "Urgências que ocuparam o horário" in content

        summary = response.context["summary"]
        assert summary["cases"] == 2
        assert summary["admissions"] == 1
        assert summary["not_performed"] == 1
        assert len(summary["procedures"]) == 1
        proc = summary["procedures"][0]
        assert proc["label"] == "EDA"
        assert (proc["performed"], proc["total"], proc["percent"]) == (1, 2, 50)
        assert len(summary["reasons"]) == 1
        reason = summary["reasons"][0]
        assert reason["reason"] == "resource_shortage"
        assert reason["count"] == 1
        assert reason["details"][0]["label"] == "Urgências que ocuparam o horário"
        assert reason["details"][0]["count"] == 1

    def test_cards_respeitam_janela_e_busca(self, client) -> None:
        user = _login_as(client, "manager")
        hoje = _create_scheduled_case(user, arn="SUM-HOJE", name="Resumo Hoje", when=_local_dt(day_offset=0))
        _record(hoje, user, performed=True)
        _create_scheduled_case(user, arn="SUM-FORA", name="Resumo Fora", when=_local_dt(day_offset=-20))

        response = client.get(HISTORY_URL, {"q": "Resumo"})
        summary = response.context["summary"]
        assert summary["cases"] == 1
        assert summary["procedures"][0]["performed"] == 1
        assert summary["procedures"][0]["total"] == 1


# ── R7: tabela paginada, 1 linha por desfecho, ordenação por grupo ──────


class TestHistoryTable:
    """25/página; 1 linha por ProcedureFollowUp; grupos desc + nome/horário."""

    def test_ordenacao_grupo_desc_depois_nome_e_horario(self, client) -> None:
        user = _login_as(client, "manager")
        hoje_a = _create_scheduled_case(user, arn="T-ALFA", name="Alfa", when=_local_dt(day_offset=0, hour=8))
        _record(hoje_a, user)
        hoje_b = _create_scheduled_case(user, arn="T-BETA", name="Beta", when=_local_dt(day_offset=0, hour=10))
        _record(hoje_b, user)
        ontem_a = _create_scheduled_case(user, arn="Y-ANA", name="Ana", when=_local_dt(day_offset=-1, hour=9))
        _record(ontem_a, user)
        ontem_z = _create_scheduled_case(user, arn="Y-ZE", name="Zé", when=_local_dt(day_offset=-1, hour=11))
        _record(ontem_z, user)

        response = client.get(HISTORY_URL)
        assert _history_arns(response) == ["T-ALFA", "T-BETA", "Y-ANA", "Y-ZE"]

    def test_tabela_exibe_colunas_do_desfecho(self, client) -> None:
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=9, minute=30)
        case = _create_scheduled_case(user, arn="TABELA-001", name="Paciente Tabela", when=when)
        _record(case, user, performed=False, reason="other", other="Equipe indisponível")  # v1 (não exibida)
        v2 = _record(
            case,
            user,
            admitted=True,
            procedure_types=("eda", "colonoscopy"),
            performed=False,
            reason="resource_shortage",
            detail="equipment_unavailable",
        )

        response = client.get(HISTORY_URL)
        rows = response.context["page_obj"].object_list
        assert len(rows) == 2
        assert {row["case"].agency_record_number for row in rows} == {"TABELA-001"}
        assert {row["version"] for row in rows} == {2}
        assert {row["admitted_label"] for row in rows} == {"Sim"}
        assert {row["procedure_label"] for row in rows} == {"Colonoscopia", "EDA"}

        content = response.content.decode()
        assert content.count("TABELA-001") == 2
        assert "Paciente Tabela" in content
        assert _local_day(0).strftime("%d/%m/%Y") in content
        assert "Não realizado" in content
        assert "Cancelamento por falta de recursos no dia" in content
        assert "Equipamento quebrado/não disponível" in content
        assert "v2" in content
        assert user.username in content  # registrado por (author_label)
        expected_recorded = timezone.localtime(v2.recorded_at).strftime("%d/%m/%Y %H:%M")
        assert expected_recorded in content
        assert "Equipe indisponível" not in content  # dados da v1 fora da população

    def test_paginacao_25_por_pagina(self, client) -> None:
        user = _login_as(client, "manager")
        for i in range(26):
            case = _create_scheduled_case(
                user, arn=f"PAGE-{i:02d}", name=f"Paciente {i:02d}", when=_local_dt(day_offset=0)
            )
            _record(case, user)

        response = client.get(HISTORY_URL)
        page_obj = response.context["page_obj"]
        assert page_obj.paginator.per_page == 25
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 25

        second = client.get(HISTORY_URL, {"page": 2})
        assert len(second.context["page_obj"].object_list) == 1


# ── R1/R7: rota de exportação, content-type, filename e guard ───────────


class TestHistoryExportAccess:
    """GET /dashboard/follow-ups/history/export/ exige manager/admin."""

    def test_export_content_type_disposition_e_bom(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_scheduled_case(user, arn="CSV-HEAD", name="Header Export", when=_local_dt(day_offset=0))
        _record(case, user)

        response = client.get(EXPORT_URL)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        window_start, window_end = _default_window()
        expected = f'attachment; filename="followups_{window_start:%Y%m%d}_{window_end:%Y%m%d}.csv"'
        assert response["Content-Disposition"] == expected
        assert response.content.startswith("\ufeff".encode("utf-8"))

    def test_export_filename_usa_janela_custom(self, client) -> None:
        user = _login_as(client, "manager")
        start_day = timezone.localdate() - timedelta(days=3)
        end_day = timezone.localdate() + timedelta(days=1)
        case = _create_scheduled_case(
            user, arn="CSV-JANELA", name="Janela Custom", when=_local_dt(day_offset=0, hour=9)
        )
        _record(case, user)

        params = {"start": start_day.isoformat(), "end": end_day.isoformat()}
        response = client.get(EXPORT_URL, params)
        assert response.status_code == 200
        expected = f'attachment; filename="followups_{start_day:%Y%m%d}_{end_day:%Y%m%d}.csv"'
        assert response["Content-Disposition"] == expected

    def test_export_janela_invalida_cai_no_default_no_filename(self, client) -> None:
        user = _login_as(client, "manager")
        hoje = _create_scheduled_case(user, arn="CSV-FALLBACK", name="Fallback", when=_local_dt(day_offset=0))
        _record(hoje, user)

        response = client.get(EXPORT_URL, {"start": "nao-e-data", "end": "2020-01-01"})
        assert response.status_code == 200
        window_start, window_end = _default_window()
        expected = f'attachment; filename="followups_{window_start:%Y%m%d}_{window_end:%Y%m%d}.csv"'
        assert response["Content-Disposition"] == expected

    @pytest.mark.parametrize("role_name", ["manager", "admin"])
    def test_export_roles_permitidos_200(self, client, role_name: str) -> None:
        user = _login_as(client, role_name)
        case = _create_scheduled_case(user, arn="CSV-ROLE", name=f"Role {role_name}", when=_local_dt(day_offset=0))
        _record(case, user)
        assert client.get(EXPORT_URL).status_code == 200

    def test_export_anonimo_redirecionado(self, client) -> None:
        response = client.get(EXPORT_URL)
        assert response.status_code == 302
        assert "/login/" in response.url

    @pytest.mark.parametrize("role_name", ["nir", "scheduler", "doctor"])
    def test_export_papeis_sem_acesso_bloqueados_sem_conteudo(self, client, role_name: str) -> None:
        # Dados existem, mas não podem vazar para papéis sem acesso.
        data_user = User.objects.create_user(username=f"export-data-{role_name}@test", password="testpass123")
        case = _create_scheduled_case(
            data_user, arn="CSV-SECRET", name="Paciente Secreto", when=_local_dt(day_offset=0)
        )
        _record(case, data_user)

        _login_as(client, role_name)
        response = client.get(EXPORT_URL)
        assert response.status_code == 302
        assert "CSV-SECRET" not in response.content.decode()
        assert "Paciente Secreto" not in response.content.decode()


# ── R2: header fixo PT-BR de 13 colunas ────────────────────────────────


class TestHistoryExportHeader:
    """Corpo: BOM + header único com as 13 colunas exatas na ordem fixada."""

    def test_header_exato(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_scheduled_case(user, arn="CSV-HEADER", name="Header", when=_local_dt(day_offset=0))
        _record(case, user)

        records = _export_csv(client)
        assert records[0] == CSV_HEADER
        assert len(records[0]) == 13


# ── R3: 1 linha por desfecho da versão corrente, labels humanos ─────────


class TestHistoryExportRows:
    """MESMA composição da página (versão corrente, janela, busca), todas as linhas."""

    def test_uma_linha_por_desfecho_da_versao_corrente_com_labels(self, client) -> None:
        user = _login_as(client, "manager")
        when = _local_dt(day_offset=0, hour=9, minute=30)
        case = _create_scheduled_case(user, arn="CSV-001", name="Maria Export", when=when)
        _record(case, user, performed=False, reason="other", other="Equipe indisponível")  # v1 — fora da população

        procedure_eda, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type="eda")
        procedure_colo, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type="colonoscopy")
        v2 = record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=True,
            procedure_outcomes=[
                ProcedureOutcomeInput(procedure_id=procedure_eda.id, performed=True),
                ProcedureOutcomeInput(
                    procedure_id=procedure_colo.id,
                    performed=False,
                    non_performance_reason="resource_shortage",
                    resource_shortage_detail="equipment_unavailable",
                ),
            ],
        )

        records = _export_csv(client)
        data_rows = records[1:]
        assert len(data_rows) == 2  # 1 por desfecho, apenas v2

        by_procedure = {row[CSV_COL["Procedimento"]]: row for row in data_rows}
        assert set(by_procedure) == {"EDA", "Colonoscopia"}
        assert "Equipe indisponível" not in " ".join(" ".join(row) for row in data_rows)

        shared = {
            "Case ID": str(case.case_id),
            "Ocorrência": "CSV-001",
            "Paciente": "Maria Export",
            "Data": _local_day(0).strftime("%d/%m/%Y"),
            "Internação": "Sim",
            "Versão": "2",
            "Registrado por": user.username,
            "Registrado em": timezone.localtime(v2.recorded_at).strftime("%d/%m/%Y %H:%M"),
        }
        for row in data_rows:
            for column, expected in shared.items():
                assert row[CSV_COL[column]] == expected, f"coluna {column} divergiu: {row}"

        performed_row = by_procedure["EDA"]
        assert performed_row[CSV_COL["Desfecho"]] == "Realizado"
        assert performed_row[CSV_COL["Causa"]] == ""
        assert performed_row[CSV_COL["Submotivo"]] == ""
        assert performed_row[CSV_COL["Outra causa (texto)"]] == ""

        not_performed_row = by_procedure["Colonoscopia"]
        assert not_performed_row[CSV_COL["Desfecho"]] == "Não realizado"
        assert not_performed_row[CSV_COL["Causa"]] == "Cancelamento por falta de recursos no dia"
        assert not_performed_row[CSV_COL["Submotivo"]] == "Equipamento quebrado/não disponível"
        assert not_performed_row[CSV_COL["Outra causa (texto)"]] == ""

    def test_outra_causa_texto_e_nao_realizado_nao_internado(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_scheduled_case(user, arn="CSV-002", name="Outra Causa", when=_local_dt(day_offset=0, hour=9))
        _record(case, user, performed=False, reason="other", other="Paciente recusou o exame")

        records = _export_csv(client)
        (row,) = records[1:]
        assert row[CSV_COL["Desfecho"]] == "Não realizado"
        assert row[CSV_COL["Causa"]] == "Outras causas"
        assert row[CSV_COL["Submotivo"]] == ""
        assert row[CSV_COL["Outra causa (texto)"]] == "Paciente recusou o exame"
        assert row[CSV_COL["Internação"]] == "Não"
        assert row[CSV_COL["Versão"]] == "1"

    def test_export_ignora_paginacao(self, client) -> None:
        user = _login_as(client, "manager")
        for i in range(26):
            case = _create_scheduled_case(
                user, arn=f"PAGE-CSV-{i:02d}", name=f"Export {i:02d}", when=_local_dt(day_offset=0)
            )
            _record(case, user)

        records = _export_csv(client)
        assert len(records) == 1 + 26  # header + TODAS as linhas (>25)

        records_page2 = _export_csv(client, page="2")
        assert records_page2 == records  # ?page= da tabela não afeta o CSV

    def test_export_mesma_populacao_e_ordem_da_pagina(self, client) -> None:
        user = _login_as(client, "manager")
        cases = (
            ("EXP-ALFA", "Alfa", 8),
            ("EXP-BETA", "Beta", 10),
            ("EXP-ANA", "Ana", 9),
            ("EXP-ZE", "Zé", 11),
        )
        for arn, name, hour in cases:
            case = _create_scheduled_case(user, arn=arn, name=name, when=_local_dt(day_offset=0, hour=hour))
            _record(case, user)

        page = client.get(HISTORY_URL)
        assert page.status_code == 200
        page_arns = _history_arns(page)
        assert len(page_arns) == 4

        records = _export_csv(client)
        csv_arns = [row[CSV_COL["Ocorrência"]] for row in records[1:]]
        assert csv_arns == page_arns


# ── R3 (filtros): janela e busca idênticas à página ────────────────────


class TestHistoryExportFilters:
    """Export respeita a janela ativa e a busca ?q= da página."""

    def test_export_respeita_janela_custom(self, client) -> None:
        user = _login_as(client, "manager")
        start_day = timezone.localdate() - timedelta(days=2)
        end_day = timezone.localdate() + timedelta(days=2)
        casos = (
            ("CSV-INI", start_day, 9),
            ("CSV-FIM", end_day, 11),
            ("CSV-FORA", end_day + timedelta(days=1), 9),
        )
        for arn, day, hour in casos:
            when = timezone.make_aware(datetime.combine(day, time(hour)), timezone.get_current_timezone())
            case = _create_scheduled_case(user, arn=arn, name=f"Paciente {arn}", when=when)
            _record(case, user)

        params = {"start": start_day.isoformat(), "end": end_day.isoformat()}
        records = _export_csv(client, **params)
        csv_arns = [row[CSV_COL["Ocorrência"]] for row in records[1:]]
        assert sorted(csv_arns) == ["CSV-FIM", "CSV-INI"]

    def test_export_respeita_busca_dentro_da_janela(self, client) -> None:
        user = _login_as(client, "manager")
        alvo = _create_scheduled_case(user, arn="CSV-ABC", name="Maria Alvo", when=_local_dt(day_offset=0))
        _record(alvo, user)
        outro = _create_scheduled_case(user, arn="CSV-XYZ", name="João Souza", when=_local_dt(day_offset=0, hour=15))
        _record(outro, user)
        fora = _create_scheduled_case(user, arn="CSV-ABC-FORA", name="Maria Alvo", when=_local_dt(day_offset=-20))
        _record(fora, user)

        records = _export_csv(client, q="maria alvo")
        csv_arns = [row[CSV_COL["Ocorrência"]] for row in records[1:]]
        assert csv_arns == ["CSV-ABC"]  # busca dentro da janela default (fora excluído)


# ── R4: escaping automático do módulo csv ───────────────────────────────


class TestHistoryExportEscaping:
    """Campo com ';', aspas e quebra de linha permanece em UMA célula parseável."""

    def test_campo_com_separador_aspas_e_quebra_fica_em_uma_celula(self, client) -> None:
        user = _login_as(client, "manager")
        other = 'Equipe ausente; "sem substituto"\nsegunda linha do motivo'
        case = _create_scheduled_case(
            user, arn="CSV-ESC", name="Paciente Escaping", when=_local_dt(day_offset=0, hour=9)
        )
        _record(case, user, performed=False, reason="other", other=other)

        records = _export_csv(client)
        assert len(records) == 2  # header + 1 linha: ';' e quebra não fragmentam o registro
        (row,) = records[1:]
        assert len(row) == 13
        assert row[CSV_COL["Outra causa (texto)"]] == other
        assert row[CSV_COL["Causa"]] == "Outras causas"
        assert row[CSV_COL["Paciente"]] == "Paciente Escaping"


# ── R5: exportação é leitura pura (nenhum CaseEvent) ────────────────────


class TestHistoryExportNoEvents:
    """Exportar não grava auditoria nem altera estado."""

    def test_export_nao_cria_case_events(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_scheduled_case(user, arn="CSV-EVENTOS", name="Sem Eventos", when=_local_dt(day_offset=0))
        _record(case, user)

        before = CaseEvent.objects.count()
        response = client.get(EXPORT_URL)
        assert response.status_code == 200
        assert CaseEvent.objects.count() == before


# ── R6: botão Exportar CSV no form de filtros da página ─────────────────


class TestHistoryExportButton:
    """Botão dentro do form de filtros, herda a querystring, sem JS."""

    def test_botao_exportar_csv_no_form_de_filtros(self, client) -> None:
        _login_as(client, "manager")
        content = client.get(HISTORY_URL).content.decode()
        assert "Exportar CSV" in content
        assert EXPORT_URL in content
        assert 'class="btn btn-sm btn-outline-primary"' in content
        # Form de filtros da página (method="get"); o botão fica dentro dele e,
        # via formaction, herda q/start/end ao exportar.
        filter_form_start = content.index('<form method="get"')
        filter_form_end = content.index("</form>", filter_form_start)
        assert filter_form_start < content.index("Exportar CSV") < filter_form_end
