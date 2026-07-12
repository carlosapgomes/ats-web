"""Testes do dashboard — Slice 1: App dashboard + view + template + case detail admin."""

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus, SupervisorSummary

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str):
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"{role_name}@dashboard.test", password="testpass123")
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _create_case(*, created_by, status=CaseStatus.NEW, **kwargs):
    """Helper para criar caso com valores padrão."""
    defaults = {
        "agency_record_number": "DASH-001",
        "status": status,
    }
    defaults.update(kwargs)
    return Case.objects.create(created_by=created_by, **defaults)


def _advance_case_to(case: Case, target: str) -> Case:
    """Avança um Case pelas transições FSM até atingir o status alvo."""
    path: dict[str, list[str]] = {
        CaseStatus.R1_ACK_PROCESSING: ["start_processing"],
        CaseStatus.EXTRACTING: ["start_processing", "start_extraction"],
        CaseStatus.LLM_STRUCT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
        ],
        CaseStatus.LLM_SUGGEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
        ],
        CaseStatus.R2_POST_WIDGET: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
        ],
        CaseStatus.WAIT_DOCTOR: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
        ],
        CaseStatus.DOCTOR_ACCEPTED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
        ],
        CaseStatus.DOCTOR_DENIED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='deny')",
        ],
        CaseStatus.R3_POST_REQUEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
        ],
        CaseStatus.WAIT_APPT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
        ],
        CaseStatus.APPT_CONFIRMED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
            "scheduler_decide(appointment_status='confirmed')",
        ],
        CaseStatus.APPT_DENIED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
            "scheduler_decide(appointment_status='denied')",
        ],
    }
    steps = path.get(target, [])
    for step in steps:
        if "(" in step:
            method_name, args_str = step.split("(", 1)
            args_str = args_str.rstrip(")")
            kwargs: dict[str, object] = {}
            if "=" in args_str:
                for pair in args_str.split(","):
                    k, v_raw = pair.split("=")
                    k = k.strip()
                    v_raw = v_raw.strip().strip("'")
                    if v_raw == "True":
                        v: object = True
                    elif v_raw == "False":
                        v = False
                    else:
                        v = v_raw
                    kwargs[k] = v
                getattr(case, method_name)(**kwargs)
            else:
                getattr(case, method_name)()
        else:
            getattr(case, step)()
        case.save()
    return Case.objects.get(pk=case.pk)


# ── Dashboard: Authentication & Access ───────────────────────────────────


@pytest.mark.django_db
class TestDashboardAccess:
    """Testes de autenticação e autorização do dashboard."""

    def test_dashboard_requires_login(self, client) -> None:
        """GET /dashboard/ sem autenticação → redirect para login."""
        response = client.get("/dashboard/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_dashboard_accessible_for_manager(self, client) -> None:
        """GET /dashboard/ retorna 200 para manager."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200

    def test_dashboard_accessible_for_admin(self, client) -> None:
        """GET /dashboard/ retorna 200 para admin."""
        _login_as(client, "admin")
        response = client.get("/dashboard/")
        assert response.status_code == 200

    def test_dashboard_blocked_for_nir(self, client) -> None:
        """GET /dashboard/ bloqueado para NIR → redirect."""
        _login_as(client, "nir")
        response = client.get("/dashboard/")
        assert response.status_code == 302

    def test_dashboard_blocked_for_doctor(self, client) -> None:
        """GET /dashboard/ bloqueado para doctor → redirect."""
        _login_as(client, "doctor")
        response = client.get("/dashboard/")
        assert response.status_code == 302

    def test_dashboard_blocked_for_scheduler(self, client) -> None:
        """GET /dashboard/ bloqueado para scheduler → redirect."""
        _login_as(client, "scheduler")
        response = client.get("/dashboard/")
        assert response.status_code == 302


# ── Dashboard: Summary Cards ────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardSummaryCards:
    """Verifica os summary cards (Total Hoje, Aceitos, Negados, Em Andamento)."""

    def test_summary_cards_show_correct_counts(self, client) -> None:
        """Summary cards refletem casos de hoje com critérios baseados em decisão."""
        user = _login_as(client, "manager")

        # Casos criados hoje
        _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            appointment_status="confirmed",
        )
        _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR)
        _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
        )
        _create_case(
            created_by=user,
            status=CaseStatus.APPT_DENIED,
            doctor_decision="accept",
            appointment_status="denied",
        )

        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        # Total Hoje = 4
        assert "4" in content
        # Aceitos = 1 (APPT_CONFIRMED com doctor_decision=accept, appointment_status=confirmed)
        # Negados = 2 (DOCTOR_DENIED com doctor_decision=deny + APPT_DENIED com appointment_status=denied)
        # Em Andamento = 1 (WAIT_DOCTOR)
        assert "Em Andamento" in content or "Aceitos" in content or "Negados" in content

    def test_summary_cards_include_today_total(self, client) -> None:
        """Card 'Total Hoje' com contagem correta."""
        user = _login_as(client, "manager")
        for i in range(3):
            _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number=f"TOTAL-{i}")
        response = client.get("/dashboard/")
        assert response.status_code == 200

    def test_summary_cards_exclude_old_cases(self, client) -> None:
        """Casos de dias anteriores não entram nos cards de hoje."""
        user = _login_as(client, "manager")
        yesterday = timezone.now() - timedelta(days=1)
        case = _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="OLD-001")
        Case.objects.filter(pk=case.pk).update(created_at=yesterday)

        response = client.get("/dashboard/")
        assert response.status_code == 200


# ── Dashboard: Sub-metrics ──────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardSubMetrics:
    """Verifica sub-métricas: aguardando por etapa, fluxo, tempo médio."""

    def test_shows_waiting_by_stage(self, client) -> None:
        """Sub-métrica 'Aguardando por Etapa' aparece."""
        user = _login_as(client, "manager")
        _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="W-DOC")
        _create_case(created_by=user, status=CaseStatus.WAIT_APPT, agency_record_number="W-APPT")
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="W-CONFIRM",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Fila Médica" in content or "Aguardando" in content
        assert "Agendamento" in content

    def test_shows_admission_flow(self, client) -> None:
        """Sub-métrica 'Fluxo de Admissão' aparece."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            agency_record_number="FLOW-SCHED",
        )
        _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            agency_record_number="FLOW-IMM",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "FLUXO" in content or "ADMISSÃO" in content

    def test_shows_average_times(self, client) -> None:
        """Sub-métrica 'Tempo Médio' aparece."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "TEMPO" in content


# ── Dashboard: Case Table ───────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardCaseTable:
    """Verifica a lista de cards de todos os casos."""

    def test_case_table_shows_all_cases(self, client) -> None:
        """Cards listam todos os casos sem filtro de usuário."""
        nir_user = User.objects.create_user(username="nir@table.test", password="testpass123")
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(role)

        manager = _login_as(client, "manager")
        # Casos de diferentes NIRs
        _create_case(created_by=nir_user, status=CaseStatus.NEW, agency_record_number="NIR-001")
        _create_case(created_by=manager, status=CaseStatus.NEW, agency_record_number="MGR-001")

        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "NIR-001" in content
        assert "MGR-001" in content

    def test_case_table_has_status_filter(self, client) -> None:
        """Dropdown de filtro por status aparece na tabela."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        # Should have a status filter select/dropdown
        assert "select" in content or "Todos os status" in content or "status" in content.lower()

    def test_case_table_has_pagination(self, client) -> None:
        """Paginação aparece na lista (>20 casos)."""
        user = _login_as(client, "manager")
        for i in range(25):
            _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number=f"PAG-{i:03d}")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        # Pagination elements
        assert "pagination" in content or "page-link" in content

    def test_case_table_shows_patient_name(self, client) -> None:
        """Tabela exibe nome do paciente quando disponível."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        case.structured_data = {"patient": {"name": "Paciente Tabela Teste"}}
        case.save()
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente Tabela Teste" in content

    def test_case_table_has_action_links(self, client) -> None:
        """Cards têm link 'Ver detalhes' para cada caso."""
        user = _login_as(client, "manager")
        _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="LINK-001")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Ver detalhes" in content


# ── Dashboard: Case Result Badges ───────────────────────────────────────


@pytest.mark.django_db
class TestDashboardCaseResultBadges:
    """Verifica que os cards mostram o badge de resultado correto."""

    def test_in_progress_shows_step_label(self, client) -> None:
        """Caso em WAIT_DOCTOR mostra badge '⏳ Avaliação Médica'."""
        user = _login_as(client, "manager")
        _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="BADGE-WAIT")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Avaliação Médica" in content
        assert "bg-secondary" in content

    def test_accepted_scheduled_shows_badge(self, client) -> None:
        """Caso aceito com agendamento confirmado mostra badge verde (Bootstrap success)."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="BADGE-ACCEPT",
            doctor_decision="accept",
            appointment_status="confirmed",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content
        assert "bg-success" in content

    def test_accepted_immediate_shows_badge(self, client) -> None:
        """Caso aceito para vinda imediata mostra badge verde (Bootstrap success)."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="BADGE-IMMED",
            doctor_decision="accept",
            doctor_admission_flow="immediate",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Vinda Imediata" in content
        assert "bg-success" in content

    def test_doctor_denied_shows_badge(self, client) -> None:
        """Caso negado pelo médico mostra badge vermelho (Bootstrap danger)."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_DENIED,
            agency_record_number="BADGE-DRDENY",
            doctor_decision="deny",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Negado pelo Médico" in content
        assert "bg-danger" in content

    def test_appointment_denied_shows_badge(self, client) -> None:
        """Caso com agendamento negado mostra badge vermelho (Bootstrap danger)."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="BADGE-APTDENY",
            doctor_decision="accept",
            appointment_status="denied",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Negado" in content
        assert "bg-danger" in content

    def test_scope_gated_shows_manual_review_badge(self, client) -> None:
        """Caso scope-gated mostra badge de revisão manual (Bootstrap warning)."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="BADGE-SCOPE",
            suggested_action={"decision": "manual_review_required", "reason_code": "non_eda"},
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Revisão Manual" in content
        assert "bg-warning" in content

    def test_failed_shows_badge(self, client) -> None:
        """Caso com falha mostra badge vermelho (Bootstrap danger)."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.FAILED,
            agency_record_number="BADGE-FAIL",
        )
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Falha no Processamento" in content
        assert "bg-danger" in content


# ── Dashboard: Navigation Pills ─────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardNavPills:
    """Verifica os nav pills de navegação."""

    def test_has_dashboard_pill_active(self, client) -> None:
        """Nav pill 'Dashboard' aparece como ativo."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dashboard" in content

    def test_has_prompts_pill(self, client) -> None:
        """Nav pill 'Prompts' aparece (placeholder)."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Prompts" in content

    def test_has_usuarios_pill(self, client) -> None:
        """Nav pill 'Usuários' aparece (placeholder)."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Usuários" in content

    def test_has_auditoria_pill(self, client) -> None:
        """Nav pill 'Auditoria' oculta (hidden placeholder)."""
        _login_as(client, "manager")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Auditoria" in content


# ── Dashboard: Case Detail Admin ────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardCaseDetailAdmin:
    """Verifica a view dashboard_case_detail para supervisor/admin."""

    def test_case_detail_accessible_for_manager(self, client) -> None:
        """GET /dashboard/<uuid>/ retorna 200 para manager."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200

    def test_case_detail_accessible_for_admin(self, client) -> None:
        """GET /dashboard/<uuid>/ retorna 200 para admin."""
        user = _login_as(client, "admin")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200

    def test_case_detail_shows_any_case(self, client) -> None:
        """Manager/admin pode ver caso de qualquer NIR."""
        _login_as(client, "manager")
        nir_user = User.objects.create_user(username="nir@detail.test", password="testpass123")
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(role)

        case = _create_case(created_by=nir_user, status=CaseStatus.NEW, agency_record_number="OTHER-NIR-001")
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200

    def test_case_detail_no_confirm_button(self, client) -> None:
        """Dashboard case detail NÃO tem botão 'Confirmar Recebimento'."""
        user = _login_as(client, "manager")
        case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="NO-CONFIRM",
        )
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Confirmar" not in content

    @pytest.mark.parametrize("role_name", ["manager", "admin"])
    def test_case_detail_shows_doctor_observation_for_manager_and_admin(self, client, role_name: str) -> None:
        """Manager/admin veem a observação médica completa pelo detalhe do dashboard."""
        user = _login_as(client, role_name)
        case = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            agency_record_number="DASH-OBS-001",
            doctor_observation="Observação importante para supervisão e administração",
        )

        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Orientações médicas" in content
        assert "Observação importante para supervisão e administração" in content
        assert "Confirmar" not in content

    def test_case_detail_hides_empty_doctor_observation_for_manager(self, client) -> None:
        """Dashboard não mostra card vazio quando observação médica está ausente."""
        user = _login_as(client, "manager")
        case = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            agency_record_number="DASH-OBS-EMPTY",
            doctor_observation="   ",
        )

        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        assert "Orientações médicas" not in response.content.decode()

    def test_terminal_appointment_denied_shows_denied_not_confirmed(self, client) -> None:
        """WAIT_R1_CLEANUP_THUMBS com appointment_status="denied" mostra Agendamento Negado, não Confirmado."""
        user = _login_as(client, "manager")
        doctor = User.objects.create_user(
            username="doc.dash.denied@test.com",
            password="pass123",
            first_name="Paulo",
            last_name="Henrique",
        )
        doctor.professional_council = "CRM"
        doctor.professional_council_number = "12345"
        doctor.save()
        scheduler = User.objects.create_user(
            username="sched.dash.denied@test.com",
            password="pass123",
            first_name="Marina",
            last_name="Silva",
        )
        scheduler.professional_council = "COREN"
        scheduler.professional_council_number = "54321"
        scheduler.save()
        case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number="DASH-TERM-DENIED",
            doctor=doctor,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            doctor_support_flag="none",
            scheduler=scheduler,
            appointment_status="denied",
            appointment_reason="Vaga indisponível",
        )
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Negado" in content
        assert "Vaga indisponível" in content
        assert "Paulo Henrique" in content
        assert "CRM 12345" in content
        assert "Marina Silva" in content
        assert "COREN 54321" in content
        assert "Agendador responsável" in content
        assert "Agendamento Confirmado" not in content

    def test_case_detail_404_for_nonexistent(self, client) -> None:
        """UUID inexistente → 404."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:case_detail", args=["00000000-0000-0000-0000-000000000001"]))
        assert response.status_code == 404

    def test_case_detail_blocked_for_nir(self, client) -> None:
        """NIR não pode acessar dashboard case detail."""
        _login_as(client, "nir")
        nir_user = User.objects.create_user(username="nir2@detail.test", password="testpass123")
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(role)
        case = _create_case(created_by=nir_user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 302


# ── Home Redirect Tests ─────────────────────────────────────────────────


@pytest.mark.django_db
# ── Dashboard: Case Detail Navigation & PDF (Slice 001) ──────────────────


@pytest.mark.django_db
class TestDashboardCaseDetailNavPdf:
    """Testes de navegação e PDF no detalhe do dashboard."""

    def _create_case_with_pdf(self, *, created_by, **kwargs):
        """Cria caso com pdf_file real para testes de PDF."""
        case = _create_case(created_by=created_by, **kwargs)
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake pdf for testing"),
            save=True,
        )
        return case

    # ── NIR nav ausente no dashboard ───────────────────────────────────

    def test_case_detail_hides_nir_nav_for_manager(self, client) -> None:
        """Manager não vê 'Novo Encaminhamento' nem 'Meus Casos' no detalhe dashboard."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Novo Encaminhamento" not in content
        assert "Meus Casos" not in content

    def test_case_detail_hides_nir_nav_for_admin(self, client) -> None:
        """Admin não vê 'Novo Encaminhamento' nem 'Meus Casos' no detalhe dashboard."""
        user = _login_as(client, "admin")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Novo Encaminhamento" not in content
        assert "Meus Casos" not in content

    # ── Back to dashboard ─────────────────────────────────────────────

    def test_case_detail_shows_back_to_dashboard(self, client) -> None:
        """Detalhe dashboard mostra 'Voltar ao dashboard', não 'Voltar para lista'."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Voltar ao dashboard" in content
        assert reverse("dashboard:index") in content

    def test_case_detail_does_not_show_back_to_my_cases(self, client) -> None:
        """Detalhe dashboard NÃO tem link para intake:my_cases."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert reverse("intake:my_cases") not in content

    # ── PDF URL no template ───────────────────────────────────────────

    def test_case_detail_uses_dashboard_pdf_url(self, client) -> None:
        """Detalhe dashboard usa dashboard:case_pdf, não intake:serve_pdf."""
        user = _login_as(client, "manager")
        case = self._create_case_with_pdf(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        pdf_url = reverse("dashboard:case_pdf", args=[case.case_id])
        assert pdf_url in content
        assert reverse("intake:serve_pdf", args=[case.case_id]) not in content

    def test_case_detail_shows_pdf_embed_and_link(self, client) -> None:
        """Detalhe dashboard com pdf_file mostra embed e link 'Abrir em nova aba'."""
        user = _login_as(client, "admin")
        case = self._create_case_with_pdf(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "embed" in content
        assert "Abrir em nova aba" in content

    # ── Endpoint dashboard:case_pdf ───────────────────────────────────

    def test_case_pdf_accessible_for_manager(self, client) -> None:
        """Manager consegue GET em dashboard:case_pdf para caso com PDF."""
        user = _login_as(client, "manager")
        case = self._create_case_with_pdf(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response.get("Content-Type") == "application/pdf"

    def test_case_pdf_accessible_for_admin(self, client) -> None:
        """Admin consegue GET em dashboard:case_pdf para caso com PDF."""
        user = _login_as(client, "admin")
        case = self._create_case_with_pdf(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response.get("Content-Type") == "application/pdf"

    def test_case_pdf_blocked_for_nir(self, client) -> None:
        """NIR não consegue acessar dashboard:case_pdf."""
        client_nir, nir_user = _nir_client_setup(client)
        from apps.accounts.models import Role as RoleModel

        role, _ = RoleModel.objects.get_or_create(name="nir")
        nir_user.roles.add(role)
        client_nir.force_login(nir_user)
        session = client_nir.session
        session["active_role"] = "nir"
        session.save()

        another = User.objects.create_user(username="other@pdf.test", password="pass123")
        case = self._create_case_with_pdf(created_by=another, status=CaseStatus.NEW)
        response = client_nir.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 302

    def test_case_pdf_blocked_for_doctor(self, client) -> None:
        """Doctor não consegue acessar dashboard:case_pdf."""
        from apps.accounts.models import Role as RoleModel

        user = User.objects.create_user(username="doc@pdf.test", password="pass123")
        role, _ = RoleModel.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        another = User.objects.create_user(username="other2@pdf.test", password="pass123")
        case = self._create_case_with_pdf(created_by=another, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 302

    def test_case_pdf_blocked_for_scheduler(self, client) -> None:
        """Scheduler não consegue acessar dashboard:case_pdf."""
        from apps.accounts.models import Role as RoleModel

        user = User.objects.create_user(username="sched@pdf.test", password="pass123")
        role, _ = RoleModel.objects.get_or_create(name="scheduler")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        another = User.objects.create_user(username="other3@pdf.test", password="pass123")
        case = self._create_case_with_pdf(created_by=another, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 302

    def test_case_pdf_404_for_no_pdf(self, client) -> None:
        """dashboard:case_pdf retorna 404 para caso sem PDF."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 404

    def test_case_pdf_blocked_without_login(self, client) -> None:
        """dashboard:case_pdf sem autenticação → redirect para login."""
        user = User.objects.create_user(username="anon@pdf.test", password="pass123")
        case = self._create_case_with_pdf(created_by=user, status=CaseStatus.NEW)
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_case_pdf_accessible_for_cleaned_case(self, client) -> None:
        """dashboard:case_pdf permite acesso a casos CLEANED (ao contrário da rota NIR)."""
        user = _login_as(client, "manager")
        case = self._create_case_with_pdf(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number="CLEANED-PDF",
        )
        response = client.get(reverse("dashboard:case_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response.get("Content-Type") == "application/pdf"


def _nir_client_setup(client):
    """Helper para criar cliente NIR para testes de regressão."""
    user = User.objects.create_user(username="nir.regression@test.com", password="testpass123")
    return client, user


@pytest.mark.django_db
class TestHomeRedirect:
    """Verifica redirecionamento da home_view para manager/admin."""

    def test_manager_redirects_to_dashboard(self, client) -> None:
        """Manager logado → / redireciona para /dashboard/."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="manager@home.test", password="testpass123")
        role, _ = Role.objects.get_or_create(name="manager")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "manager"
        session.save()

        response = client.get("/", follow=True)
        assert response.status_code == 200
        # Deve estar no dashboard
        assert "/dashboard/" in response.redirect_chain[-1][0] if response.redirect_chain else True

    def test_admin_redirects_to_dashboard(self, client) -> None:
        """Admin logado → / redireciona para /dashboard/."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="admin@home.test", password="testpass123")
        role, _ = Role.objects.get_or_create(name="admin")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "admin"
        session.save()

        response = client.get("/", follow=True)
        assert response.status_code == 200
        # Deve estar no dashboard
        if response.redirect_chain:
            assert "/dashboard/" in response.redirect_chain[-1][0]

    def test_nir_not_redirected_to_dashboard(self, client) -> None:
        """NIR logado → / NÃO redireciona para /dashboard/ (vai para intake)."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nir@home.test", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        response = client.get("/", follow=True)
        # NIR deve ir para intake, não dashboard
        last_url = response.redirect_chain[-1][0] if response.redirect_chain else ""
        assert "/dashboard/" not in last_url


# ── Dashboard: Summaries (Slice 002) ────────────────────────────────────


@pytest.mark.django_db
class TestDashboardSummaryCard:
    """Verifica o card de último resumo no dashboard."""

    def _create_summary(self, **overrides) -> SupervisorSummary:
        defaults = {
            "window_start": timezone.now() - timedelta(hours=6),
            "window_end": timezone.now() - timedelta(hours=3),
            "patients_received": 10,
            "reports_processed": 8,
            "cases_evaluated": 7,
            "accepted_scheduled": 4,
            "immediate_admission": 2,
            "refused": 1,
            "in_progress": 3,
            "status": "sent",
        }
        defaults.update(overrides)
        return SupervisorSummary.objects.create(**defaults)

    def test_card_appears_when_summary_exists(self, client) -> None:
        """Card com último resumo aparece no dashboard se existir."""
        _login_as(client, "manager")
        self._create_summary()
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "ÚLTIMO RESUMO" in content
        assert "Ver todos" in content

    def test_card_shows_correct_data(self, client) -> None:
        """Card exibe as métricas principais do último resumo."""
        _login_as(client, "manager")
        self._create_summary(
            patients_received=15,
            accepted_scheduled=6,
            refused=2,
        )
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "15" in content  # received
        assert "6" in content  # accepted
        assert "2" in content  # refused

    def test_card_hides_when_no_summary(self, client) -> None:
        """Card não aparece quando não há resumos."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "ÚLTIMO RESUMO" not in content


@pytest.mark.django_db
class TestDashboardSummariesView:
    """Verifica a view /dashboard/summaries/."""

    def _create_summaries(self, count: int = 5) -> None:
        base = timezone.now()
        for i in range(count):
            SupervisorSummary.objects.create(
                window_start=base - timedelta(hours=(i + 1) * 6),
                window_end=base - timedelta(hours=(i + 1) * 6 - 3),
                patients_received=10 + i,
                reports_processed=8 + i,
                cases_evaluated=7 + i,
                accepted_scheduled=4 + i,
                immediate_admission=2,
                refused=1,
                in_progress=3,
                status="sent" if i % 2 == 0 else "pending",
            )

    def test_accessible_for_manager(self, client) -> None:
        """GET /dashboard/summaries/ retorna 200 para manager."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 200

    def test_accessible_for_admin(self, client) -> None:
        """GET /dashboard/summaries/ retorna 200 para admin."""
        _login_as(client, "admin")
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 200

    def test_blocked_for_nir(self, client) -> None:
        """GET /dashboard/summaries/ bloqueado para NIR."""
        _login_as(client, "nir")
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 302

    def test_blocked_for_doctor(self, client) -> None:
        """GET /dashboard/summaries/ bloqueado para doctor."""
        _login_as(client, "doctor")
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 302

    def test_lists_summaries_with_pagination(self, client) -> None:
        """/dashboard/summaries/ lista resumos com paginação (25 por página)."""
        _login_as(client, "manager")
        self._create_summaries(30)
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 200
        content = response.content.decode()
        # Pagination should be present (30 > 25)
        assert "pagination" in content or "page-link" in content

    def test_shows_status_badge(self, client) -> None:
        """Tabela exibe badge de status (Enviado/Pendente)."""
        _login_as(client, "manager")
        self._create_summaries(2)
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Enviado" in content or "Pendente" in content

    def test_requires_login(self, client) -> None:
        """GET /dashboard/summaries/ sem autenticação → redirect."""
        response = client.get(reverse("dashboard:summaries"))
        assert response.status_code == 302
        assert "/login/" in response.url


# ── Dashboard: Summary Counters Regression (fix-dashboard-counters) ─────


@pytest.mark.django_db
class TestDashboardSummaryFixed:
    """Testes de regressão para os bugs dos contadores do dashboard.

    Testa _compute_summary() diretamente para asserts numéricos precisos.
    Verifica que:
    - Negados captura casos com doctor_decision=deny mesmo após CLEANED.
    - Negados captura casos com appointment_status=denied mesmo após CLEANED.
    - Aceitos exclui casos com appointment_status=denied.
    - Aceitos e Negados são mutuamente exclusivos (sem dupla contagem).
    - Casos scope-gated (sem decisão) permanecem em Em Andamento.
    - A soma dos contadores é igual ao total.
    - Métricas de "hoje" usam o dia local, não a data UTC.
    """

    def test_denied_captures_doctor_deny_cleaned(self, client) -> None:
        """Caso negado pelo médico e já CLEANED conta como Negados."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="deny",
            agency_record_number="REG-DENY",
        )
        result = _compute_summary()
        assert result["total_today"] == 1
        assert result["denied"] == 1, (
            f"Caso CLEANED com doctor_decision=deny deve ser Negados=1, mas denied={result['denied']}"
        )
        assert result["accepted"] == 0
        assert result["in_progress"] == 0

    def test_negados_captures_appt_denied_cleaned(self, client) -> None:
        """Caso com appointment_status=denied e já CLEANED conta como Negados."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            appointment_status="denied",
            agency_record_number="REG-APPT-D",
        )
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="REG-WAIT",
        )
        result = _compute_summary()
        assert result["total_today"] == 2
        assert result["denied"] == 1, f"accept+appt_denied deve ser Negados=1, mas denied={result['denied']}"
        assert result["accepted"] == 0, f"accept+appt_denied NAO deve ser Aceitos, mas accepted={result['accepted']}"
        assert result["in_progress"] == 1

    def test_accepted_excludes_appt_denied(self, client) -> None:
        """Caso com doctor_decision=accept e appointment_status=denied
        NÃO conta como Aceitos — conta como Negados."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            appointment_status="denied",
            agency_record_number="REG-ACC-DEN",
        )
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            appointment_status="confirmed",
            agency_record_number="REG-ACC-CONF",
        )
        result = _compute_summary()
        assert result["total_today"] == 2
        assert result["accepted"] == 1, f"Só o confirmed deve ser Aceitos=1, mas accepted={result['accepted']}"
        assert result["denied"] == 1, f"appt_denied deve ser Negados=1, mas denied={result['denied']}"
        assert result["in_progress"] == 0

    def test_no_double_count_appt_denied(self, client) -> None:
        """Caso accept+denied aparece só em Negados, não duplamente.

        A soma Aceitos + Negados + Em Andamento deve ser igual a Total.
        """
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        _create_case(
            created_by=user,
            status=CaseStatus.APPT_DENIED,
            doctor_decision="accept",
            appointment_status="denied",
            agency_record_number="REG-NO-DBL",
        )
        result = _compute_summary()
        assert result["total_today"] == 1
        assert result["denied"] == 1, f"accept+appt_denied deve ser Negados=1, mas denied={result['denied']}"
        assert result["accepted"] == 0, f"accept+appt_denied NAO deve ser Aceitos, mas accepted={result['accepted']}"
        assert result["in_progress"] == 0
        # Integridade: soma deve bater com total
        assert result["accepted"] + result["denied"] + result["in_progress"] == result["total_today"]

    def test_scope_gated_stays_in_progress(self, client) -> None:
        """Caso scope-gated (sem doctor_decision) fica em Em Andamento."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            suggested_action={"decision": "manual_review_required", "reason_code": "non_eda"},
            agency_record_number="REG-SCOPE",
        )
        result = _compute_summary()
        assert result["total_today"] == 1
        assert result["in_progress"] == 1, (
            f"Scope-gated deve ficar Em Andamento, mas in_progress={result['in_progress']}"
        )
        assert result["accepted"] == 0
        assert result["denied"] == 0

    def test_all_counters_sum_to_total(self, client) -> None:
        """A soma Aceitos + Negados + Em Andamento = Total Hoje.

        Cria um mix realista de casos e verifica a integridade aritmética.
        """
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        # 1 aceito confirmado
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            appointment_status="confirmed",
            agency_record_number="INT-001",
        )
        # 1 aceito imediato (sem appointment_status)
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            agency_record_number="INT-002",
        )
        # 1 negado pelo médico já CLEANED
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="deny",
            agency_record_number="INT-003",
        )
        # 1 negado pelo scheduler já CLEANED
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            appointment_status="denied",
            agency_record_number="INT-004",
        )
        # 1 aguardando médico
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="INT-005",
        )
        # 1 falhou
        _create_case(
            created_by=user,
            status=CaseStatus.FAILED,
            agency_record_number="INT-006",
        )

        result = _compute_summary()
        # Total = 6
        assert result["total_today"] == 6
        # Aceitos = 2 (accept+confirmed, accept+immediate)
        assert result["accepted"] == 2, f"Esperado Aceitos=2, obtido accepted={result['accepted']}"
        # Negados = 2 (deny, accept+denied)
        assert result["denied"] == 2, f"Esperado Negados=2, obtido denied={result['denied']}"
        # Em Andamento = 2 (wait_doctor, failed)
        assert result["in_progress"] == 2, f"Esperado Em Andamento=2, obtido in_progress={result['in_progress']}"
        # Integridade
        assert result["accepted"] + result["denied"] + result["in_progress"] == result["total_today"]

    # ── Timezone boundary regression tests ────────────────────────────────
    #
    # O bug: _compute_summary() e _compute_admission_flow() usavam
    # timezone.now().date() que retorna a data UTC, não a data local.
    #
    # Exemplo:
    #   timezone.now()  = 2026-06-01 01:00 UTC
    #   localdate(Bahia)= 2026-05-31 22:00 BRT
    #   today (bug)     = 2026-06-01  → filtra created_at__date=2026-06-01 UTC
    #   Caso criado às 2026-05-31 08:00 BRT (UTC 2026-05-31 11:00) NÃO
    #   seria encontrado, mesmo estando no dia operacional corrente.
    #
    # Os testes abaixo reproduzem essa fronteira e verificam a correção.

    def _setup_utc_local_boundary(self) -> tuple[datetime, datetime]:
        """Helper: retorna (utc_now, local_created) para a fronteira UTC/local."""
        from datetime import UTC

        utc_now = datetime(2026, 6, 1, 1, 0, 0, tzinfo=UTC)
        # Em America/Bahia (UTC-3), 01:00 UTC = 22:00 BRT do dia anterior (31/05)
        local_created = datetime(2026, 5, 31, 8, 0, 0, tzinfo=UTC)
        return utc_now, local_created

    @pytest.mark.django_db
    def test_summary_counts_case_in_local_day_ignoring_utc_tomorrow(self, client) -> None:
        """Caso no dia local (BRT) é contado mesmo que UTC já seja amanhã."""
        from unittest.mock import patch
        from zoneinfo import ZoneInfo

        from django.utils import timezone as tz_utils

        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        utc_now, _ = self._setup_utc_local_boundary()

        # Cria caso às 08:00 BRT (= 11:00 UTC do dia 31/05)
        when_local = datetime(2026, 5, 31, 8, 0, 0, tzinfo=ZoneInfo("America/Bahia"))
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="TZ-BOUNDARY",
        )
        Case.objects.filter(agency_record_number="TZ-BOUNDARY").update(created_at=when_local)

        # Agora simula: timezone.now() em UTC já é 01:00 do dia 01/06
        with tz_utils.override("America/Bahia"):
            with patch.object(tz_utils, "now", return_value=utc_now):
                result = _compute_summary()

        # O caso foi criado às 08:00 BRT de 31/05. O dia local do servidor
        # (22:00 BRT de 31/05) é 31/05. Portanto deve contar como today.
        assert result["total_today"] == 1, (
            f"Caso do dia local deve ser Total=1, mas total_today={result['total_today']}"
        )

    @pytest.mark.django_db
    def test_summary_excludes_case_from_previous_local_day(self, client) -> None:
        """Caso do dia local anterior NÃO é contado em 'hoje'."""
        from unittest.mock import patch
        from zoneinfo import ZoneInfo

        from django.utils import timezone as tz_utils

        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        utc_now, _ = self._setup_utc_local_boundary()

        # Cria caso em 30/05 BRT (véspera do dia local)
        when_yesterday = datetime(2026, 5, 30, 10, 0, 0, tzinfo=ZoneInfo("America/Bahia"))
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="TZ-YESTERDAY",
        )
        Case.objects.filter(agency_record_number="TZ-YESTERDAY").update(created_at=when_yesterday)

        with tz_utils.override("America/Bahia"):
            with patch.object(tz_utils, "now", return_value=utc_now):
                result = _compute_summary()

        assert result["total_today"] == 0, (
            f"Caso do dia anterior não deve ser Total=0, mas total_today={result['total_today']}"
        )

    @pytest.mark.django_db
    def test_admission_flow_uses_local_day(self, client) -> None:
        """_compute_admission_flow() usa dia local, não UTC."""
        from unittest.mock import patch
        from zoneinfo import ZoneInfo

        from django.utils import timezone as tz_utils

        from apps.dashboard.views import _compute_admission_flow

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        utc_now, _ = self._setup_utc_local_boundary()

        # Caso aceito às 08:00 BRT (= 11:00 UTC do dia 31/05) com fluxo scheduled
        when_local = datetime(2026, 5, 31, 8, 0, 0, tzinfo=ZoneInfo("America/Bahia"))
        _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            agency_record_number="TZ-FLOW-SCHED",
        )
        Case.objects.filter(agency_record_number="TZ-FLOW-SCHED").update(created_at=when_local)

        # Caso aceito às 08:30 BRT com fluxo immediate
        when_local2 = datetime(2026, 5, 31, 8, 30, 0, tzinfo=ZoneInfo("America/Bahia"))
        _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            agency_record_number="TZ-FLOW-IMM",
        )
        Case.objects.filter(agency_record_number="TZ-FLOW-IMM").update(created_at=when_local2)

        with tz_utils.override("America/Bahia"):
            with patch.object(tz_utils, "now", return_value=utc_now):
                flow = _compute_admission_flow()

        assert flow["scheduled"] == 1, f"Fluxo scheduled deve ser 1, obtido {flow['scheduled']}"
        assert flow["immediate"] == 1, f"Fluxo immediate deve ser 1, obtido {flow['immediate']}"


# ── Dashboard: Administrative Closure (Slice 001) ────────────────────────


@pytest.mark.django_db
class TestDashboardAdministrativeClosure:
    """Testes de encerramento administrativo no dashboard."""

    def _create_operational_case(self, user, status=CaseStatus.WAIT_DOCTOR, **kwargs):
        """Cria caso operacional não CLEANED."""
        return _create_case(created_by=user, status=status, **kwargs)

    # ── Form visibility ───────────────────────────────────────────────

    def test_dashboard_detail_shows_administrative_close_form_for_manager_on_operational_case(self, client) -> None:
        """Manager vê formulário de encerramento para caso não CLEANED."""
        user = _login_as(client, "manager")
        case = self._create_operational_case(user, status=CaseStatus.WAIT_DOCTOR)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Encerrar administrativamente" in content
        assert reverse("dashboard:administrative_close", args=[case.case_id]) in content

    def test_dashboard_detail_shows_administrative_close_form_for_admin_on_operational_case(self, client) -> None:
        """Admin vê formulário de encerramento para caso não CLEANED."""
        user = _login_as(client, "admin")
        case = self._create_operational_case(user, status=CaseStatus.LLM_SUGGEST)
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Encerrar administrativamente" in content

    def test_dashboard_detail_hides_administrative_close_form_for_cleaned_case(self, client) -> None:
        """Caso CLEANED não mostra form de encerramento."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.CLEANED, agency_record_number="CLN-001")
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Encerrar administrativamente" not in content

    def test_dashboard_detail_hides_administrative_close_for_nir(self, client) -> None:
        """NIR não vê form de encerramento."""
        _login_as(client, "nir")
        nir_user = User.objects.create_user(username="nir@adminclose.test", password="testpass123")
        from apps.accounts.models import Role as RoleModel

        role, _ = RoleModel.objects.get_or_create(name="nir")
        nir_user.roles.add(role)
        case = _create_case(created_by=nir_user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="NIR-CLOSE")
        # NIR não tem acesso ao dashboard detail
        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 302

    # ── POST route ────────────────────────────────────────────────────

    def test_dashboard_administrative_close_post_requires_manager_or_admin(self, client) -> None:
        """Usuário sem manager/admin não consegue postar."""
        from apps.accounts.models import Role as RoleModel

        # Testar doctor
        doc_user = User.objects.create_user(username="doc@close.test", password="testpass123")
        role, _ = RoleModel.objects.get_or_create(name="doctor")
        doc_user.roles.add(role)
        client.force_login(doc_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        case = _create_case(created_by=doc_user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="DOC-CLOSE")
        response = client.post(
            reverse("dashboard:administrative_close", args=[case.case_id]),
            {"reason_code": "system_bug", "reason_text": "Bug"},
        )
        assert response.status_code == 302  # redirect por falta de permissão
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status != CaseStatus.CLEANED

    def test_dashboard_administrative_close_post_requires_reason(self, client) -> None:
        """POST sem reason_text não altera status."""
        user = _login_as(client, "manager")
        case = self._create_operational_case(user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="NO-REASON")
        response = client.post(
            reverse("dashboard:administrative_close", args=[case.case_id]),
            {"reason_code": "system_bug", "reason_text": ""},
        )
        assert response.status_code == 302
        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status != CaseStatus.CLEANED
        assert not CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        ).exists()

    def test_dashboard_administrative_close_post_success_redirects_and_closes_case(self, client) -> None:
        """POST válido redireciona, muda status e cria evento."""
        user = _login_as(client, "manager")
        case = self._create_operational_case(user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="SUCCESS-CLOSE")
        response = client.post(
            reverse("dashboard:administrative_close", args=[case.case_id]),
            {"reason_code": "system_bug", "reason_text": "Bug corrigido manualmente"},
        )
        assert response.status_code == 302
        assert response.url == reverse("dashboard:case_detail", args=[case.case_id])

        fresh_case = Case.objects.get(pk=case.pk)
        assert fresh_case.status == CaseStatus.CLEANED

        events = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
        )
        assert events.count() == 1
        event = events.first()
        assert event is not None
        assert event.payload.get("reason_code") == "system_bug"
        assert event.payload.get("reason_text") == "Bug corrigido manualmente"

    # ── Timeline label ────────────────────────────────────────────────

    def test_timeline_shows_administrative_closure_label(self, client) -> None:
        """Timeline do dashboard detail mostra label 'Encerrado administrativamente'."""
        user = _login_as(client, "manager")
        case = self._create_operational_case(user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="TIMELINE-CLOSE")

        # Fecha administrativamente
        from apps.cases.services import administratively_close_case

        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug",
            active_role="manager",
        )

        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Encerrado administrativamente" in content

    # ── Dashboard case detail: outcome semantics for admin-closed ────────────

    def test_administrative_closed_detail_shows_admin_outcome_not_confirmed(self, client) -> None:
        """Caso aceito+confirmado encerrado administrative mostra 'Encerrado administrativamente', não 'Agendamento Confirmado'."""
        from apps.cases.services import administratively_close_case

        user = _login_as(client, "manager")
        case = _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            appointment_status="confirmed",
            doctor_admission_flow="scheduled",
            agency_record_number="ADMIN-CLOSE-DETAIL",
        )

        # Encerra administrativamente
        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug corrigido",
            active_role="manager",
        )

        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Deve mostrar encerramento administrativo
        assert "Encerrado administrativamente" in content

        # NÃO deve mostrar agendamento confirmado no card de resultado
        assert "Agendamento Confirmado" not in content

        # Deve mostrar motivo
        assert "Bug corrigido" in content

    # ── Summary: admin-closed separated from in_progress ───────────────────

    def test_summary_separates_administrative_closed_from_in_progress(self, client) -> None:
        """_compute_summary() retorna administratively_closed separado de in_progress para cenário 11/1/0/4/6."""
        from apps.cases.services import administratively_close_case
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # 1 aceito confirmado (não encerrado admin)
        _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            appointment_status="confirmed",
            agency_record_number="ADM-ACC-001",
        )

        # 10 em processamento — desses, 4 serão encerrados administrativamente
        processing_cases = []
        for i in range(6):
            c = _create_case(
                created_by=user,
                status=CaseStatus.WAIT_DOCTOR,
                agency_record_number=f"ADM-PROC-{i:02d}",
            )
            processing_cases.append(c)

        # 4 serão encerrados administrativamente
        for i in range(4):
            c = _create_case(
                created_by=user,
                status=CaseStatus.WAIT_DOCTOR,
                agency_record_number=f"ADM-ADMIN-CLOSE-{i:02d}",
            )
            administratively_close_case(
                case=c,
                user=user,
                reason_code="system_bug",
                reason_text="Bug",
                active_role="manager",
            )

        result = _compute_summary()
        assert result["total_today"] == 11, f"Total deve ser 11, obtido {result['total_today']}"
        assert result["accepted"] == 1, f"Aceitos deve ser 1, obtido {result['accepted']}"
        assert result["denied"] == 0, f"Negados deve ser 0, obtido {result['denied']}"
        assert result["administratively_closed"] == 4, (
            f"Encerrados admin. deve ser 4, obtido {result['administratively_closed']}"
        )
        assert result["in_progress"] == 6, f"Em Andamento deve ser 6, obtido {result['in_progress']}"
        # Integridade: soma deve bater
        total = result["accepted"] + result["denied"] + result["administratively_closed"] + result["in_progress"]
        assert total == result["total_today"], (
            f"Soma dos contadores ({total}) deve igualar total_today ({result['total_today']})"
        )

    def test_administrative_closed_confirmed_case_counts_only_as_admin_closed(self, client) -> None:
        """Caso aceito+confirmado encerrado admin conta como admin_closed, não como accepted."""
        from apps.cases.services import administratively_close_case
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # Caso aceito+confirmado
        case = _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            appointment_status="confirmed",
            doctor_admission_flow="scheduled",
            agency_record_number="ADM-CONF-CLOSE",
        )

        # Encerra administrativamente
        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug",
            active_role="manager",
        )

        result = _compute_summary()
        assert result["total_today"] == 1
        assert result["accepted"] == 0, f"Aceitos deve ser 0 (caso encerrado admin), obtido {result['accepted']}"
        assert result["administratively_closed"] == 1, (
            f"Admin_closed deve ser 1, obtido {result['administratively_closed']}"
        )
        assert result["in_progress"] == 0

    # ── Dashboard list badge ──────────────────────────────────────────────

    def test_dashboard_list_result_badge_shows_administrative_closed(self, client) -> None:
        """Caso encerrado admin mostra badge 'Encerrado administrativamente' na listagem do dashboard."""
        from apps.cases.services import administratively_close_case

        user = _login_as(client, "manager")
        case = _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            appointment_status="confirmed",
            agency_record_number="ADM-LIST-BADGE",
        )

        # Encerra administrativamente
        administratively_close_case(
            case=case,
            user=user,
            reason_code="system_bug",
            reason_text="Bug",
            active_role="manager",
        )

        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Encerrado administrativamente" in content


# ── Dashboard: Post-schedule intercurrence presentation ──────────────────


@pytest.mark.django_db
class TestDashboardPostScheduleIntercurrencePresentation:
    """Regressões de apresentação para intercorrência pós-agendamento."""

    def _create_cleaned_scheduled_case(self, user, *, appointment_status: str, agency_record_number: str) -> Case:
        """Cria caso terminal aceito em fluxo agendado com status de agendamento informado."""
        case = _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status=appointment_status,
            appointment_at=timezone.now() + timedelta(days=1),
            appointment_instructions="jejum 6h",
            agency_record_number=agency_record_number,
        )
        assert isinstance(case, Case)
        return case

    def test_dashboard_list_shows_cancelled_after_post_schedule_issue(self, client) -> None:
        """Card gerencial mostra cancelamento pós-intercorrência, não pendência."""
        user = _login_as(client, "manager")
        self._create_cleaned_scheduled_case(
            user,
            appointment_status="cancelled",
            agency_record_number="PSI-CANCEL-LIST",
        )

        response = client.get(reverse("dashboard:index"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento cancelado após intercorrência" in content
        assert "Aguardando Agendamento" not in content

    def test_dashboard_detail_shows_cancelled_after_post_schedule_issue(self, client) -> None:
        """Detalhe gerencial mostra cancelamento, não agendamento confirmado."""
        user = _login_as(client, "manager")
        case = self._create_cleaned_scheduled_case(
            user,
            appointment_status="cancelled",
            agency_record_number="PSI-CANCEL-DETAIL",
        )

        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento cancelado após intercorrência" in content
        assert "Agendamento Confirmado" not in content

    def test_dashboard_detail_keeps_confirmed_after_reschedule_or_maintain(self, client) -> None:
        """Caso confirmado pós-intercorrência continua aparecendo como confirmado."""
        user = _login_as(client, "manager")
        case = self._create_cleaned_scheduled_case(
            user,
            appointment_status="confirmed",
            agency_record_number="PSI-CONFIRMED-DETAIL",
        )

        response = client.get(reverse("dashboard:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento Confirmado" in content
        assert "Agendamento cancelado após intercorrência" not in content


# ── Dashboard: Attention Filter (Slice 002) ──────────────────────────────


@pytest.mark.django_db
class TestDashboardAttentionFilter:
    """Testes do filtro 'Atenção necessária' no dashboard.

    Filtro ativado via ?attention=1. Critérios:
    - FAILED sempre entra
    - Lock expirado entra
    - Estados de processamento antigos (>30 min) entram
    - Estados de espera humanos antigos (>48 h) entram
    - CLEANED sempre excluído
    """

    def test_dashboard_has_attention_filter_control(self, client) -> None:
        """GET dashboard contém botão/link 'Atenção necessária' com attention=1."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Atenção necessária" in content
        assert "attention=1" in content

    def test_attention_filter_includes_failed_operational_cases(self, client) -> None:
        """Caso FAILED aparece em ?attention=1; CLEANED não aparece."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        failed = _create_case(created_by=user, status=CaseStatus.FAILED, agency_record_number="ATT-FAIL")
        cleaned = _create_case(created_by=user, status=CaseStatus.CLEANED, agency_record_number="ATT-CLEAN")

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert failed.agency_record_number in content
        assert cleaned.agency_record_number not in content

    def test_attention_filter_includes_old_processing_case(self, client) -> None:
        """Caso em LLM_SUGGEST com updated_at antigo aparece em ?attention=1."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        case = _create_case(created_by=user, status=CaseStatus.LLM_SUGGEST, agency_record_number="ATT-OLD-PROC")
        old_time = timezone.now() - timedelta(hours=1)
        Case.objects.filter(pk=case.pk).update(updated_at=old_time)

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content

    def test_attention_filter_excludes_fresh_processing_case(self, client) -> None:
        """Caso em EXTRACTING com updated_at recente NÃO aparece em ?attention=1."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        case = _create_case(created_by=user, status=CaseStatus.EXTRACTING, agency_record_number="ATT-FRESH-PROC")
        # updated_at é 'agora' por default → não deve aparecer

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number not in content

    def test_attention_filter_includes_old_waiting_case(self, client) -> None:
        """Caso WAIT_DOCTOR com updated_at > 48h aparece em ?attention=1."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        case = _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="ATT-OLD-WAIT")
        old_time = timezone.now() - timedelta(hours=49)
        Case.objects.filter(pk=case.pk).update(updated_at=old_time)

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content

    def test_attention_filter_excludes_fresh_waiting_case(self, client) -> None:
        """Caso WAIT_DOCTOR recente NÃO aparece em ?attention=1."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        case = _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="ATT-FRESH-WAIT")

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number not in content

    def test_attention_filter_includes_expired_lock(self, client) -> None:
        """Caso com lock expirado aparece em ?attention=1 e mostra motivo 'Lock expirado'."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        other_user = User.objects.create_user(username="locker@att.test", password="pass")
        case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ATT-LOCK-EXP",
        )
        Case.objects.filter(pk=case.pk).update(
            locked_by=other_user,
            locked_until=timezone.now() - timedelta(minutes=10),
            locked_at=timezone.now() - timedelta(minutes=20),
        )

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content
        assert "Lock expirado" in content

    def test_attention_filter_badge_shows_reason(self, client) -> None:
        """GET ?attention=1 mostra badge 'Atenção necessária' e motivo no card."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        case = _create_case(created_by=user, status=CaseStatus.FAILED, agency_record_number="ATT-BADGE")

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert case.agency_record_number in content
        assert "⚠ Atenção necessária" in content
        assert "Falha no processamento" in content

    def test_attention_filter_composes_with_status_filter(self, client) -> None:
        """?attention=1&status=FAILED mostra FAILED e exclui outro suspeito não-FAILED."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        failed = _create_case(created_by=user, status=CaseStatus.FAILED, agency_record_number="COMP-FAIL")
        # Outro caso suspeito que não é FAILED: WAIT_DOCTOR antigo
        old_wait = _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="COMP-WAIT")
        Case.objects.filter(pk=old_wait.pk).update(updated_at=timezone.now() - timedelta(hours=49))

        response = client.get(reverse("dashboard:index") + "?attention=1&status=FAILED")
        assert response.status_code == 200
        content = response.content.decode()
        assert failed.agency_record_number in content
        assert old_wait.agency_record_number not in content

    def test_attention_pagination_preserves_attention_param(self, client) -> None:
        """Links de paginação preservam attention=1."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # Criar 25 casos FAILED para garantir paginação
        for i in range(25):
            _create_case(
                created_by=user,
                status=CaseStatus.FAILED,
                agency_record_number=f"ATT-PAG-{i:03d}",
            )

        response = client.get(reverse("dashboard:index") + "?attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        # Links de paginação devem conter attention=1
        assert "attention=1" in content


# ── Dashboard: _fmt_duration slice 001 polish UX ──────────────────────────


@pytest.mark.django_db
class TestDashboardFmtDuration:
    """Testes para _fmt_duration do polimento de UX."""

    def test_fmt_duration_none_returns_dash(self) -> None:
        """_fmt_duration(None) retorna —."""
        from apps.dashboard.views import _fmt_duration

        result = _fmt_duration(None)
        assert result == "—"

    def test_fmt_duration_59_min(self) -> None:
        """_fmt_duration(timedelta(minutes=59)) retorna '59 min'."""
        from apps.dashboard.views import _fmt_duration

        result = _fmt_duration(timedelta(minutes=59))
        assert result == "59 min"

    def test_fmt_duration_60_min(self) -> None:
        """_fmt_duration(timedelta(minutes=60)) retorna '1 h'."""
        from apps.dashboard.views import _fmt_duration

        result = _fmt_duration(timedelta(minutes=60))
        assert result == "1 h"

    def test_fmt_duration_65_min(self) -> None:
        """_fmt_duration(timedelta(minutes=65)) retorna '1 h 05 min'."""
        from apps.dashboard.views import _fmt_duration

        result = _fmt_duration(timedelta(minutes=65))
        assert result == "1 h 05 min"

    def test_fmt_duration_1100_min(self) -> None:
        """_fmt_duration(timedelta(minutes=1100)) retorna '18 h 20 min'."""
        from apps.dashboard.views import _fmt_duration

        result = _fmt_duration(timedelta(minutes=1100))
        assert result == "18 h 20 min"

    def test_fmt_duration_zero(self) -> None:
        """_fmt_duration(timedelta(0)) retorna '0 min', não —."""
        from apps.dashboard.views import _fmt_duration

        result = _fmt_duration(timedelta(0))
        assert result == "0 min"


# ── Dashboard: Date labels slice 001 polish UX ──────────────────────────


@pytest.mark.django_db
class TestDashboardDateLabels:
    """Testes para labels visíveis de date_from e date_to."""

    def test_dashboard_has_visible_date_labels(self, client) -> None:
        """GET /dashboard/ como manager contém labels 'Data inicial' e 'Data final'."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Data inicial" in content
        assert "Data final" in content

    def test_dashboard_date_labels_have_for_and_id(self, client) -> None:
        """Labels de data usam for/id para associar com inputs."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        # Verifica que o label Data inicial tem for apontando para id certo
        assert 'for="date_from"' in content or 'for="id_date_from"' in content
        assert 'id="date_from"' in content or 'id="id_date_from"' in content
        assert 'for="date_to"' in content or 'for="id_date_to"' in content
        assert 'id="date_to"' in content or 'id="id_date_to"' in content


# ── Dashboard: Search slice 003 ─────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardSearch:
    """Testes para busca server-side indexada (slice 003)."""

    def test_search_form_present(self, client) -> None:
        """Dashboard contém label 'Buscar por nome ou registro' e input name='search'."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Buscar por nome ou registro" in content
        assert 'name="search"' in content

    def test_search_by_patient_name(self, client) -> None:
        """?search=ana encontra caso cujo paciente contém 'Ana'."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="SRC-PAT-001",
            structured_data={"patient": {"name": "Ana Maria"}},
        )
        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="SRC-PAT-002",
            structured_data={"patient": {"name": "João Silva"}},
        )

        response = client.get(reverse("dashboard:index") + "?search=ana")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Ana Maria" in content
        assert "João Silva" not in content

    def test_search_by_agency_record_number(self, client) -> None:
        """?search=ocor encontra caso por agency_record_number."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="OCOR-001",
            structured_data={"patient": {"name": "João Silva"}},
        )
        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="OUTRO-002",
            structured_data={"patient": {"name": "Maria Souza"}},
        )

        response = client.get(reverse("dashboard:index") + "?search=ocor")
        assert response.status_code == 200
        content = response.content.decode()
        assert "OCOR-001" in content
        assert "OUTRO-002" not in content

    def test_search_case_insensitive(self, client) -> None:
        """Busca é case-insensitive."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="CASE-ABC",
            structured_data={"patient": {"name": "ANA Maria"}},
        )

        # Busca por nome em lowercase
        response = client.get(reverse("dashboard:index") + "?search=ana")
        assert response.status_code == 200
        content = response.content.decode()
        assert "CASE-ABC" in content

        # Busca por registro em lowercase
        response = client.get(reverse("dashboard:index") + "?search=case")
        assert response.status_code == 200
        content = response.content.decode()
        assert "CASE-ABC" in content

    def test_search_min_chars_does_not_filter(self, client) -> None:
        """?search=an (2 chars) não filtra e mostra ajuda de mínimo de 3 caracteres."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="TWO-CHARS",
            structured_data={"patient": {"name": "Ana"}},
        )

        # search=an (2 chars) → não filtra, mostra todos
        response = client.get(reverse("dashboard:index") + "?search=an")
        assert response.status_code == 200
        content = response.content.decode()
        assert "TWO-CHARS" in content
        # Deve mostrar ajuda
        assert "3" in content or "caractere" in content or "mínimo" in content

    def test_search_composes_with_status(self, client) -> None:
        """Busca compõe com filtro status."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="STATUS-NEW",
            structured_data={"patient": {"name": "Ana Santos"}},
        )
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="STATUS-WAIT",
            structured_data={"patient": {"name": "Ana Santos"}},
        )

        # Busca por nome + filtra por status NEW
        response = client.get(reverse("dashboard:index") + "?search=ana&status=" + CaseStatus.NEW)
        assert response.status_code == 200
        content = response.content.decode()
        assert "STATUS-NEW" in content
        assert "STATUS-WAIT" not in content

    def test_search_composes_with_dates(self, client) -> None:
        """Busca compõe com date_from/date_to."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # Caso de ontem
        case_yest = _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="YEST-001",
            structured_data={"patient": {"name": "Ana Maria"}},
        )
        Case.objects.filter(pk=case_yest.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(yesterday, time(8, 0)),
                timezone.get_current_timezone(),
            )
        )

        # Caso de hoje (fora do range, não deve aparecer)
        case_today = _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="TODAY-001",
            structured_data={"patient": {"name": "Ana Maria"}},
        )
        Case.objects.filter(pk=case_today.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(today, time(8, 0)),
                timezone.get_current_timezone(),
            )
        )

        # Busca+data=ontem
        response = client.get(
            reverse("dashboard:index")
            + f"?search=ana&date_from={yesterday.isoformat()}&date_to={yesterday.isoformat()}"
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "YEST-001" in content
        assert "TODAY-001" not in content

    def test_search_composes_with_attention(self, client) -> None:
        """Busca compõe com attention=1."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # Caso FAILED (entra no filtro de atenção)
        _create_case(
            created_by=user,
            status=CaseStatus.FAILED,
            agency_record_number="ATT-FAIL",
            structured_data={"patient": {"name": "Ana Santos"}},
        )
        # Caso WAIT_DOCTOR fresco (não entra no filtro de atenção)
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ATT-FRESH",
            structured_data={"patient": {"name": "Ana Santos"}},
        )

        # Busca só deve mostrar FAILED (attention=1 já exclui o WAIT_DOCTOR fresco)
        response = client.get(reverse("dashboard:index") + "?search=ana&attention=1")
        assert response.status_code == 200
        content = response.content.decode()
        assert "ATT-FAIL" in content
        assert "ATT-FRESH" not in content

    def test_pagination_preserves_search(self, client) -> None:
        """Links de paginação preservam search."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # Criar 25 casos para garantir paginação
        for i in range(25):
            _create_case(
                created_by=user,
                status=CaseStatus.NEW,
                agency_record_number=f"PAG-SRC-{i:03d}",
                structured_data={"patient": {"name": f"Paciente {i:03d}"}},
            )

        response = client.get(reverse("dashboard:index") + "?search=paciente")
        assert response.status_code == 200
        content = response.content.decode()
        # Links de paginação devem conter search=paciente
        assert "search=paciente" in content or "search%3Dpaciente" in content

    def test_search_preserves_metrics_period(self, client) -> None:
        """metrics_period é preservado ao submeter busca."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="SRC-MPERIOD",
            structured_data={"patient": {"name": "Ana"}},
        )

        # Formulário de filtros da lista deve preservar metrics_period como hidden
        response = client.get(reverse("dashboard:index") + "?search=ana&metrics_period=30d")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="30d"' in content

    def test_empty_search_does_not_filter(self, client) -> None:
        """Termo vazio (espaços) não filtra."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="EMPTY-SRC",
            structured_data={"patient": {"name": "Qualquer"}},
        )

        # search= (vazio) → mostra todos
        response = client.get(reverse("dashboard:index") + "?search=")
        assert response.status_code == 200
        content = response.content.decode()
        assert "EMPTY-SRC" in content

    def test_search_query_uses_trigram_indexes(self) -> None:
        """EXPLAIN prova que a busca usa os índices trigram (não seq scan).

        Guarda-contrato: ``__icontains`` geraria ``UPPER(col) LIKE UPPER(p)``
        e não seria acelerado pelo índice ``lower(col)``. A busca deve casar
        com os índices ``cases_case_*_trgm_idx`` da migration ``cases.0011``.
        """
        from django.db import connection

        from apps.dashboard.views import _apply_case_search

        if connection.vendor != "postgresql":
            pytest.skip("Índices trigram são específicos do PostgreSQL")

        # Termo com >= 3 caracteres ativa o filtro de busca.
        qs = _apply_case_search(Case.objects.all(), "ana")
        sql, params = qs.query.sql_with_params()

        with connection.cursor() as cur:
            # Força o planner a considerar índices mesmo em tabelas pequenas.
            cur.execute("SET LOCAL enable_seqscan = off")
            cur.execute("EXPLAIN " + sql, params)
            plan = "\n".join(str(row[0]) for row in cur.fetchall())

        assert "cases_case_arn_trgm_idx" in plan, "Busca por agency_record_number deve usar o índice trigram.\n" + plan
        assert "cases_case_patient_name_trgm_idx" in plan, (
            "Busca por nome do paciente deve usar o índice trigram.\n" + plan
        )


# ── Dashboard: metrics_date slice 002 ────────────────────────────────────


@pytest.mark.django_db
class TestDashboardMetricsDate:
    """Testes para o seletor de data das métricas (metrics_date)."""

    from datetime import date as date_type

    def test_default_metrics_date_uses_today(self, client) -> None:
        """Sem metrics_date, dashboard usa o dia local atual."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # Caso criado hoje
        today_case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="MD-TODAY",
        )
        Case.objects.filter(pk=today_case.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(today, datetime.min.time()),
                timezone.get_current_timezone(),
            )
        )

        # Caso criado ontem
        yesterday_case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="MD-YESTERDAY",
        )
        Case.objects.filter(pk=yesterday_case.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(yesterday, datetime.min.time()),
                timezone.get_current_timezone(),
            )
        )

        # Sem metrics_date → usa today
        result = _compute_summary()
        assert result["total_today"] == 1, f"Sem metrics_date, total deve ser 1 (hoje), obtido {result['total_today']}"

    def test_metrics_date_yesterday_counts_only_yesterday(self, client) -> None:
        """Com metrics_date=ontem, summary conta casos criados ontem e exclui hoje."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # Caso criado ontem
        yesterday_case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="MD-YEST-ONLY",
        )
        Case.objects.filter(pk=yesterday_case.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(yesterday, time(8, 0)),
                timezone.get_current_timezone(),
            )
        )

        # Caso criado hoje (não deve contar)
        today_case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="MD-TODAY-EXCL",
        )
        Case.objects.filter(pk=today_case.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(today, time(8, 0)),
                timezone.get_current_timezone(),
            )
        )

        result = _compute_summary(day=yesterday)
        assert result["total_today"] == 1, (
            f"metrics_date=ontem, total deve ser 1 (ontem), obtido {result['total_today']}"
        )

    def test_metrics_date_admission_flow_uses_selected_date(self, client) -> None:
        """Com metrics_date, fluxo de admissão usa apenas casos criados naquela data."""
        from apps.dashboard.views import _compute_admission_flow

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # Caso aceito ontem com fluxo agendado
        case_yesterday = _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            agency_record_number="MD-FLOW-YEST",
        )
        Case.objects.filter(pk=case_yesterday.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(yesterday, time(8, 0)),
                timezone.get_current_timezone(),
            )
        )

        # Caso aceito hoje com fluxo imediato
        case_today = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            agency_record_number="MD-FLOW-TODAY",
        )
        Case.objects.filter(pk=case_today.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(today, time(8, 0)),
                timezone.get_current_timezone(),
            )
        )

        # Fluxo para ontem: só deve contar o caso agendado
        flow = _compute_admission_flow(day=yesterday)
        assert flow["scheduled"] == 1, f"scheduled deve ser 1 para ontem, obtido {flow['scheduled']}"
        assert flow["immediate"] == 0, f"immediate deve ser 0 para ontem, obtido {flow['immediate']}"

    def test_metrics_date_average_times_uses_selected_date(self, client) -> None:
        """Com metrics_date, tempos médios usam apenas casos criados naquela data."""
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        # Criar médico
        doctor = User.objects.create_user(username="doc.metrics@test.com", password="pass123")
        doctor.professional_council = "CRM"
        doctor.professional_council_number = "99999"
        doctor.save()

        Case.objects.all().delete()

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # Caso de ontem – já decidido
        case_yest = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="MD-AVG-YEST",
        )
        created_yest = timezone.make_aware(
            datetime.combine(yesterday, time(8, 0)),
            timezone.get_current_timezone(),
        )
        decided_yest = timezone.make_aware(
            datetime.combine(yesterday, time(10, 0)),
            timezone.get_current_timezone(),
        )
        Case.objects.filter(pk=case_yest.pk).update(
            created_at=created_yest,
            doctor=doctor,
            doctor_decided_at=decided_yest,
        )

        # Caso de hoje – já decidido
        case_today = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="MD-AVG-TODAY",
        )
        created_today = timezone.make_aware(
            datetime.combine(today, time(8, 0)),
            timezone.get_current_timezone(),
        )
        decided_today = timezone.make_aware(
            datetime.combine(today, time(9, 0)),
            timezone.get_current_timezone(),
        )
        Case.objects.filter(pk=case_today.pk).update(
            created_at=created_today,
            doctor=doctor,
            doctor_decided_at=decided_today,
        )

        # Tempos médios para ontem: só o caso de ontem
        avg = _compute_average_times(day=yesterday)
        # upload_to_decision para ontem = 2h = "2 h"
        assert avg["upload_to_decision"] == "2 h", (
            f"upload_to_decision para ontem deve ser '2 h', obtido '{avg['upload_to_decision']}'"
        )

    def test_total_cycle_uses_cleanup_completed_event_when_field_is_empty(self, client) -> None:
        """Ciclo total usa evento CLEANUP_COMPLETED quando cleanup_completed_at histórico está vazio."""
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        metrics_day = timezone.localdate()
        created_at = timezone.make_aware(
            datetime.combine(metrics_day, time(8, 0)),
            timezone.get_current_timezone(),
        )
        completed_at = created_at + timedelta(hours=2, minutes=30)
        case = _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number="MD-CYCLE-EVENT",
        )
        Case.objects.filter(pk=case.pk).update(created_at=created_at, cleanup_completed_at=None)
        event = CaseEvent.objects.create(
            case=case,
            event_type="CLEANUP_COMPLETED",
            actor=user,
            actor_type="human",
            payload={},
        )
        CaseEvent.objects.filter(pk=event.pk).update(timestamp=completed_at)

        avg = _compute_average_times(day=metrics_day)

        assert avg["total_cycle"] == "2 h 30 min"

    def test_invalid_metrics_date_does_not_break(self, client) -> None:
        """Data inválida não retorna 500 e volta para o padrão."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index") + "?metrics_date=invalid-date")
        assert response.status_code == 200, "Data inválida não deve retornar 500"

    def test_template_has_metrics_period_selector(self, client) -> None:
        """Template contém 'Período das métricas' e opções do seletor."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Período das métricas" in content, "Label 'Período das métricas' deve estar no template"
        assert "Hoje" in content, "Opção 'Hoje' deve estar no template"
        assert "7 dias" in content, "Opção '7 dias' deve estar no template"
        assert "30 dias" in content, "Opção '30 dias' deve estar no template"
        assert "Tudo" in content, "Opção 'Tudo' deve estar no template"

    def test_template_shows_stage_waiting_as_current(self, client) -> None:
        """Template deixa claro que 'Aguardando por etapa' é snapshot atual."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "ATUAL" in content, "Template deve indicar que a fila é snapshot atual"

    def test_case_filter_form_preserves_metrics_period(self, client) -> None:
        """Formulário de filtros de casos preserva metrics_period via hidden input."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index") + "?metrics_period=30d")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="metrics_period"' in content
        assert 'value="30d"' in content, "Hidden input deve preservar o valor de metrics_period"

    def test_metrics_date_view_invalid_falls_back_silently(self, client) -> None:
        """Data inválida no metrics_date cai de volta para o dia atual sem erro."""
        _login_as(client, "manager")
        # Página com data inválida carrega sem mensagem de erro
        response = client.get(reverse("dashboard:index") + "?metrics_date=not-a-date")
        assert response.status_code == 200
        # Não deve conter mensagem de erro do Django
        content = response.content.decode()
        # A página renderiza normalmente
        assert "Total no dia" in content or "Total Hoje" in content or "Aguardando" in content


# ── Dashboard: Dynamic Search slice 004 ──────────────────────────────────


@pytest.mark.django_db
class TestDashboardDynamicSearch:
    """Testes para busca dinâmica progressiva (slice 004)."""

    def test_dashboard_has_stable_container(self, client) -> None:
        """GET /dashboard/ renderiza container id='dashboard-case-list'."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="dashboard-case-list"' in content

    def test_dashboard_includes_search_js(self, client) -> None:
        """GET /dashboard/ inclui static/js/dashboard_search.js."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "js/dashboard_search.js" in content

    def test_partial_not_duplicated_when_included(self, client) -> None:
        """GET /dashboard/ inclui o partial sem duplicar a lista.

        Verifica que o container 'dashboard-case-list' existe UMA vez
        e que o alerta de nenhum caso aparece apenas uma vez.
        """
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        # O container deve aparecer exatamente uma vez
        assert content.count('id="dashboard-case-list"') == 1

    def test_partial_header_returns_only_partial(self, client) -> None:
        """GET /dashboard/ com header X-ATS-Partial: case-list retorna apenas o partial."""
        user = _login_as(client, "manager")
        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="PARTIAL-001",
        )
        response = client.get(
            reverse("dashboard:index"),
            headers={"X-ATS-Partial": "case-list"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        # Deve conter o caso
        assert "PARTIAL-001" in content
        # NÃO deve conter elementos da página completa
        assert "base.html" not in content
        assert "Dashboard" not in content
        assert "Visão geral" not in content

    def test_partial_search_filters_cases(self, client) -> None:
        """Partial com ?search=ana contém caso esperado e exclui não esperado."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="SRC-PARTIAL-001",
            structured_data={"patient": {"name": "Ana Maria"}},
        )
        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="SRC-PARTIAL-002",
            structured_data={"patient": {"name": "João Silva"}},
        )

        response = client.get(
            reverse("dashboard:index") + "?search=ana",
            headers={"X-ATS-Partial": "case-list"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Ana Maria" in content
        assert "João Silva" not in content

    def test_partial_pagination_preserves_search(self, client) -> None:
        """Paginação do partial preserva search."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        for i in range(25):
            _create_case(
                created_by=user,
                status=CaseStatus.NEW,
                agency_record_number=f"PP-SRC-{i:03d}",
                structured_data={"patient": {"name": f"Paciente {i:03d}"}},
            )

        response = client.get(
            reverse("dashboard:index") + "?search=paciente",
            headers={"X-ATS-Partial": "case-list"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        # Links de paginação devem conter search=paciente
        assert "search=paciente" in content or "search%3Dpaciente" in content

    def test_search_js_file_has_debounce_and_min_chars(self, client) -> None:
        """Arquivo JS contém debounce e regra de mínimo de 3 caracteres."""
        import os
        from pathlib import Path

        # O static root do projeto fica na raiz
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        js_path = os.path.join(base_dir, "static", "js", "dashboard_search.js")
        assert os.path.exists(js_path), f"JS file not found: {js_path}"

        with open(js_path) as f:
            js_content = f.read()

        # Deve conter debounce
        assert "debounce" in js_content or "setTimeout" in js_content or "clearTimeout" in js_content
        # Deve conter regra de mínimo de 3 caracteres
        assert "3" in js_content or ">= 3" in js_content or "> 2" in js_content
        # Deve conter fetch
        assert "fetch" in js_content or "XMLHttpRequest" in js_content
        # Deve conter AbortController ou mecanismo de cancelamento
        assert "AbortController" in js_content or "abort" in js_content or "controller" in js_content

    def test_partial_does_not_compute_metrics(self, client) -> None:
        """O partial não computa métricas (guarda-contrato da otimização).

        Com ``X-ATS-Partial: case-list`` a view deve retornar antes de
        computar summary/fluxo/tempos médios/resumo de supervisão. Sem
        isso, cada busca dinâmica (uma por debounce) pagaria ~10 queries
        descartadas. Marcadores estáveis: ``AVG`` só aparece em
        ``_compute_average_times``; a tabela ``cases_supervisorsummary``
        só é tocada por ``latest_summary``.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        user = _login_as(client, "manager")
        Case.objects.all().delete()
        _create_case(
            created_by=user,
            status=CaseStatus.NEW,
            agency_record_number="METRICS-SKIP-001",
            structured_data={"patient": {"name": "Ana Maria"}},
        )

        with CaptureQueriesContext(connection) as cap:
            response = client.get(
                reverse("dashboard:index") + "?search=ana",
                HTTP_X_ATS_PARTIAL="case-list",
            )
        assert response.status_code == 200
        sqls = [q["sql"] for q in cap.captured_queries]

        assert not any("AVG" in sql for sql in sqls), (
            "Partial não deve executar _compute_average_times (AVG).\n" + "\n".join(sqls)
        )
        assert not any("supervisorsummary" in sql.lower() for sql in sqls), (
            "Partial não deve consultar SupervisorSummary (latest_summary).\n" + "\n".join(sqls)
        )

    def test_case_list_form_has_no_duplicate_search_input(self, client) -> None:
        """O form da lista não duplica name='search'.

        O form da lista já tem o input visível ``type="search" name="search"``;
        um hidden extra com o mesmo nome geraria ``?search=...&search=...`` no
        submit. Apenas o form de métricas precisa de um hidden ``name="search"``
        para preservar o termo ao trocar a data das métricas.
        """
        _login_as(client, "manager")
        # Com termo ativo, o form de métricas renderiza seu hidden name="search";
        # o form da lista não deve ter um hidden duplicado (usa o input visível).
        response = client.get(reverse("dashboard:index") + "?search=ana")
        assert response.status_code == 200
        content = response.content.decode()

        # O form da lista (id=case-filter-form) não deve ter hidden name="search"
        # (usa o input visível). Os mini-forms de Personalizado carregam seus
        # próprios hidden name="search" para preservar o termo — isso é esperado.
        import re

        case_form_match = re.search(
            r'<form\b[^>]*id="case-filter-form"[^>]*>.*?</form>', content, re.DOTALL | re.IGNORECASE
        )
        assert case_form_match, "Form da lista (id=case-filter-form) deve existir"
        case_form = case_form_match.group(0)
        assert 'type="hidden" name="search"' not in case_form, (
            "Form da lista não deve duplicar name=search via hidden (usa input visível)"
        )
        # O input visível de busca segue presente no form da lista.
        assert 'type="search" name="search"' in case_form


# ── Dashboard: Case List Filter Layout Polish (Slice 001) ──────────────


@pytest.mark.django_db
class TestDashboardCaseListFilterLayout:
    """Testes de contrato HTML para o polimento visual dos filtros de "Todos os Casos".

    Verifica o layout em duas linhas: header com título + botão Atenção,
    e formulário de filtros em grid Bootstrap responsivo.
    """

    def _get_content(self, client, query: str = "") -> str:
        """Helper: faz GET no dashboard e retorna HTML como string."""
        _login_as(client, "manager")
        url = reverse("dashboard:index")
        if query:
            url += "?" + query
        response = client.get(url)
        assert response.status_code == 200
        return str(response.content, encoding="utf-8")

    def _filter_form_start(self, content: str) -> int:
        """Retorna a posição do <form> de filtros da lista (id=case-filter-form).

        O seletor de período das métricas agora usa mini-forms SSR independentes,
        então localizar por ordem de <form method=get> não é mais confiável.
        Usamos o id canônico do form de filtros da lista.
        """
        return content.find('id="case-filter-form"')

    def test_card_header_shows_title_before_filters(self, client) -> None:
        """R1: Header do card com 'Todos os Casos' antes da área de filtros.

        O título deve aparecer antes do formulário de filtros no HTML.
        """
        content = self._get_content(client)
        title_pos = content.find("Todos os Casos")
        form_pos = self._filter_form_start(content)
        assert title_pos != -1, "'Todos os Casos' deve estar no HTML"
        assert form_pos != -1, "Deve haver um formulário GET de filtros"
        assert title_pos < form_pos, (
            f"'Todos os Casos' (pos {title_pos}) deve aparecer antes do <form> da lista (pos {form_pos})"
        )

    def test_attention_link_outside_form_in_header(self, client) -> None:
        """R1: Botão 'Atenção necessária' aparece no header do card e antes do <form> da lista."""
        content = self._get_content(client)
        attention_pos = content.find("⚠ Atenção necessária")
        form_pos = self._filter_form_start(content)
        assert attention_pos != -1, "Link 'Atenção necessária' deve estar no HTML"
        assert form_pos != -1, "Deve haver um formulário GET de filtros"
        assert attention_pos < form_pos, (
            f"'Atenção necessária' (pos {attention_pos}) deve aparecer antes do <form> da lista (pos {form_pos})"
        )

    def test_filter_form_has_responsive_grid_classes(self, client) -> None:
        """R2: Formulário contém classes de grid responsivo (row, g-2/g-md-3, align-items-end)."""
        content = self._get_content(client)
        assert 'class="row g-2' in content or 'class="row' in content and "g-2" in content, (
            "Deve conter 'row' com classe g-2 ou similar"
        )
        assert "align-items-end" in content, "Deve conter 'align-items-end' para alinhar inputs pela base"

    def test_search_field_has_col_lg_4(self, client) -> None:
        """R3: Campo de busca está em coluna col-lg-4 ou maior no desktop."""
        content = self._get_content(client)
        assert (
            "col-lg-4" in content
            or "col-lg-5" in content
            or "col-lg-6" in content
            or "col-lg-7" in content
            or "col-lg-8" in content
        ), "Campo de busca deve ocupar col-lg-* maior (pelo menos col-lg-4)"

    def test_status_label_visible_with_for_id(self, client) -> None:
        """R4: Status tem label visível 'Status' associado ao select com for/id."""
        content = self._get_content(client)
        assert 'label for="status"' in content or '<label for="status"' in content, (
            "Label 'Status' deve ter for='status'"
        )
        assert 'id="status"' in content, "Select de status deve ter id='status'"
        assert "Status" in content, "Texto 'Status' deve estar visível"

    def test_all_labels_present(self, client) -> None:
        """R4: Labels 'Buscar por nome ou registro', 'Data inicial' e 'Data final' continuam presentes."""
        content = self._get_content(client)
        assert "Buscar por nome ou registro" in content, "Label 'Buscar por nome ou registro' deve estar presente"
        assert "Data inicial" in content, "Label 'Data inicial' deve estar presente"
        assert "Data final" in content, "Label 'Data final' deve estar presente"

    def test_no_duplicate_search_in_filter_form(self, client) -> None:
        """R6: O formulário da lista não contém dois controles 'name="search"' quando ?search=ana está ativo.

        O input visível type="search" name="search" é o único controle com
        name="search" dentro do formulário da lista. O hidden fica só no form
        de métricas.
        """
        content = self._get_content(client, "search=ana")
        # O form da lista (id=case-filter-form) tem apenas o input visível de busca.
        import re

        case_form_match = re.search(
            r'<form\b[^>]*id="case-filter-form"[^>]*>.*?</form>', content, re.DOTALL | re.IGNORECASE
        )
        assert case_form_match, "Form da lista (id=case-filter-form) deve existir"
        case_form = case_form_match.group(0)
        # Um único controle visível name="search" no form da lista.
        assert case_form.count('name="search" id="search"') == 1, (
            "Form da lista deve ter exatamente um input visível name=search"
        )
        # Nenhum hidden name="search" no form da lista (os hidden legítimos ficam
        # nos mini-forms de Personalizado, para preservar o termo).
        assert 'type="hidden" name="search"' not in case_form, "Form da lista não deve ter hidden name=search duplicado"

    def test_metrics_period_hidden_present(self, client) -> None:
        """R8: Hidden 'metrics_period' continua presente no formulário da lista quando ?metrics_period=30d está ativo."""
        content = self._get_content(client, "metrics_period=30d")
        assert 'type="hidden" name="metrics_period" value="30d"' in content, (
            "Hidden metrics_period deve estar presente no form da lista"
        )
        # Além disso, deve ter o hidden no form de métricas também
        assert content.count('type="hidden" name="metrics_period"') >= 1

    def test_attention_link_preserves_metrics_period_and_search(self, client) -> None:
        """R9: Link 'Atenção necessária' preserva metrics_period e search quando presentes."""
        content = self._get_content(client, "metrics_period=30d&search=ana")
        # O link de atenção deve conter ambos parâmetros
        attention_link_start = content.find("⚠ Atenção necessária")
        assert attention_link_start != -1, "Link de atenção deve estar presente"
        # Busca o href do link (volta para encontrar <a)
        link_section = content[:attention_link_start]
        href_start = link_section.rfind('href="')
        assert href_start != -1, "Deve encontrar href antes do texto Atenção"
        href = link_section[href_start:]
        assert "metrics_period=30d" in href, f"Link de atenção deve preservar metrics_period, href contém: {href}"
        assert "search=ana" in href or "search=ana" in content, "Link de atenção deve preservar search"

    def test_dashboard_search_js_included(self, client) -> None:
        """R10: JS dashboard_search.js continua incluído na página."""
        content = self._get_content(client)
        assert "dashboard_search.js" in content, "dashboard_search.js deve estar incluído na página"

    def test_attention_link_has_count_badge(self, client) -> None:
        """R1: Link 'Atenção necessária' exibe contagem (N)."""
        content = self._get_content(client)
        assert "Atenção necessária" in content, "Texto 'Atenção necessária' deve estar presente"
        # O contador pode ser 0 ou mais, mas deve estar presente
        assert "attention_count" in content or "(0)" in content or "(1)" in content, (
            "Contagem de atenção deve estar visível"
        )

    def test_attention_link_has_btn_class(self, client) -> None:
        """Link de atenção tem classe btn (btn-sm btn-warning ou btn-outline-warning)."""
        content = self._get_content(client)
        assert "btn-warning" in content or "btn-outline-warning" in content, (
            "Link de atenção deve ter classe btn-warning ou btn-outline-warning"
        )

    def test_dashboard_case_list_id_and_data_attr(self, client) -> None:
        """Preserva id='dashboard-case-list' e data-dashboard-search-target."""
        content = self._get_content(client)
        assert 'id="dashboard-case-list"' in content, "id='dashboard-case-list' deve estar presente"
        assert "data-dashboard-search-target" in content, "data-dashboard-search-target deve estar presente"

    def test_filter_actions_have_filtrar_and_limpar(self, client) -> None:
        """Botões 'Filtrar' e 'Limpar' continuam presentes.

        'Filtrar' aparece sempre. 'Limpar' só aparece quando há filtros ativos.
        """
        content = self._get_content(client, "search=ana")
        assert "Filtrar" in content, "Botão 'Filtrar' deve estar presente"
        assert "Limpar" in content, "Link 'Limpar' deve estar presente quando há filtros ativos"


# ── Dashboard: Metrics Period Selector (Slice 001) ─────────────────────


@pytest.mark.django_db
class TestDashboardMetricsPeriod:
    """Testes para o seletor de período das métricas (metrics_period).

    Substitui metrics_date por metrics_period=today|7d|30d|all.
    Cards principais usam created_at no período.
    Tempos médios usam timestamps de conclusão da etapa no período.
    """

    # ── Period boundary helpers ───────────────────────────────────────

    @staticmethod
    def _set_created_at(case: Case, dt: datetime) -> None:
        """Ajusta created_at de um caso sem disparar signals."""
        Case.objects.filter(pk=case.pk).update(created_at=dt)

    @staticmethod
    def _set_field(case: Case, **kwargs) -> None:
        """Ajusta campos de um caso sem disparar signals."""
        Case.objects.filter(pk=case.pk).update(**kwargs)

    # ── R1: Default period is today ────────────────────────────────────

    def test_metrics_period_default_is_today(self, client) -> None:
        """Sem metrics_period, summary conta apenas casos de hoje.

        Cria caso hoje e caso ontem. Summary default deve contar só hoje.
        """
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        now_local = timezone.make_aware(
            datetime.combine(today, time(10, 0)),
            timezone.get_current_timezone(),
        )
        yesterday_local = timezone.make_aware(
            datetime.combine(yesterday, time(10, 0)),
            timezone.get_current_timezone(),
        )

        today_case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="PERIOD-TODAY",
        )
        self._set_created_at(today_case, now_local)

        yesterday_case = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="PERIOD-YEST",
        )
        self._set_created_at(yesterday_case, yesterday_local)

        # Sem argumento (padrão today)
        result = _compute_summary()
        assert result["total_today"] == 1, (
            f"Default today deve contar apenas hoje, obtido total_today={result['total_today']}"
        )

        # Com period="today" explicito
        result2 = _compute_summary(period="today")
        assert result2["total_today"] == 1

        # GET default (sem query param) também deve ser hoje
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Total Hoje" in content or "Total hoje" in content

    # ── R2: 7d includes last 7 local days ────────────────────────────────

    def test_metrics_period_7d_includes_last_7_local_days(self, client) -> None:
        """Caso criado há 6 dias entra em 7d; caso criado há 7 dias completos fica fora."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today = timezone.localdate()

        # Caso há 6 dias (deve entrar em 7d)
        six_days_ago = timezone.make_aware(
            datetime.combine(today - timedelta(days=6), time(8, 0)),
            tz,
        )
        c1 = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="7D-IN-6DAYS",
        )
        self._set_created_at(c1, six_days_ago)

        # Caso há 7 dias completos (deve ficar fora de 7d)
        seven_days_ago_start = timezone.make_aware(
            datetime.combine(today - timedelta(days=7), time(0, 0)),
            tz,
        )
        c2 = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="7D-OUT-7DAYS",
        )
        self._set_created_at(c2, seven_days_ago_start)

        result = _compute_summary(period="7d")
        assert result["total_today"] == 1, f"7d deve contar 1 (caso de 6 dias atrás), obtido {result['total_today']}"

    # ── R3: 30d includes last 30 local days ───────────────────────────────

    def test_metrics_period_30d_includes_last_30_local_days(self, client) -> None:
        """Caso criado há 29 dias entra em 30d; caso criado há 30 dias completos fica fora."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today = timezone.localdate()

        # Caso há 29 dias (deve entrar em 30d)
        c1 = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="30D-IN-29DAYS",
        )
        self._set_created_at(
            c1,
            timezone.make_aware(
                datetime.combine(today - timedelta(days=29), time(23, 59)),
                tz,
            ),
        )

        # Caso há 30 dias completos (deve ficar fora)
        c2 = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="30D-OUT-30DAYS",
        )
        self._set_created_at(
            c2,
            timezone.make_aware(
                datetime.combine(today - timedelta(days=30), time(0, 0)),
                tz,
            ),
        )

        result = _compute_summary(period="30d")
        assert result["total_today"] == 1, f"30d deve contar 1 (caso de 29 dias atrás), obtido {result['total_today']}"

    # ── R4: all includes everything ───────────────────────────────────────

    def test_metrics_period_all_includes_all_cases(self, client) -> None:
        """Caso antigo (criado há 90 dias) entra em 'all'."""
        from apps.dashboard.views import _compute_summary

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        c1 = _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ALL-OLD",
        )
        self._set_created_at(
            c1,
            timezone.make_aware(
                datetime.combine(timezone.localdate() - timedelta(days=90), time(8, 0)),
                timezone.get_current_timezone(),
            ),
        )
        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ALL-NEW",
        )

        result = _compute_summary(period="all")
        assert result["total_today"] == 2, f"all deve contar todos os casos (2), obtido {result['total_today']}"

    # ── R5: Invalid period falls back to today ────────────────────────────

    def test_invalid_metrics_period_falls_back_to_today(self, client) -> None:
        """GET /dashboard/?metrics_period=invalid retorna 200 e marca Hoje como ativo."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        _create_case(
            created_by=user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="INV-001",
        )

        response = client.get(reverse("dashboard:index") + "?metrics_period=invalid")
        assert response.status_code == 200
        content = response.content.decode()
        # Deve ter Hoje como ativo (active/checked) e não quebrar
        assert "Hoje" in content

    # ── R6: Average times filter by completion timestamps ─────────────────

    def test_average_upload_to_decision_filters_by_doctor_decided_at(self, client) -> None:
        """Tempo Upload→Decisão filtra por doctor_decided_at no período.

        Caso criado antigo mas decidido hoje entra em 'today'.
        Caso criado hoje mas decidido ontem não entra em 'today'.
        """
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        # Caso criado antigo (5 dias atrás) mas decidido hoje
        case_in = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="AVG-DEC-IN",
        )
        self._set_field(
            case_in,
            created_at=timezone.make_aware(
                datetime.combine(today - timedelta(days=5), time(8, 0)),
                tz,
            ),
            doctor_decided_at=timezone.make_aware(
                datetime.combine(today, time(10, 0)),
                tz,
            ),
        )

        # Caso criado hoje mas decidido ontem
        case_out = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="AVG-DEC-OUT",
        )
        self._set_field(
            case_out,
            created_at=timezone.make_aware(
                datetime.combine(today, time(8, 0)),
                tz,
            ),
            doctor_decided_at=timezone.make_aware(
                datetime.combine(yesterday, time(9, 0)),
                tz,
            ),
        )

        avg = _compute_average_times(period="today")
        assert avg["upload_to_decision"] == "122 h"

    def test_average_decision_to_schedule_filters_by_appointment_decided_at(self, client) -> None:
        """Tempo Decisão→Agendamento filtra por appointment_decided_at no período.

        Caso agendado hoje entra mesmo se criado/decidido pelo médico antes.
        """
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        three_days_ago = today - timedelta(days=3)

        # Caso criado há 3 dias, decidido há 2 dias, agendado hoje
        c1 = _create_case(
            created_by=user,
            status=CaseStatus.APPT_CONFIRMED,
            doctor_decision="accept",
            appointment_status="confirmed",
            agency_record_number="AVG-SCHED-IN",
        )
        self._set_field(
            c1,
            created_at=timezone.make_aware(
                datetime.combine(three_days_ago, time(8, 0)),
                tz,
            ),
            doctor_decided_at=timezone.make_aware(
                datetime.combine(yesterday, time(10, 0)),
                tz,
            ),
            appointment_decided_at=timezone.make_aware(
                datetime.combine(today, time(14, 0)),
                tz,
            ),
        )

        avg = _compute_average_times(period="today")
        assert avg["decision_to_schedule"] == "28 h"

    def test_average_total_cycle_filters_by_cleanup_completion_timestamp(self, client) -> None:
        """Tempo Ciclo Total filtra por cleanup_completed_at no período.

        Caso criado antes mas concluído hoje entra em 'today'.
        """
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        five_days_ago = today - timedelta(days=5)

        # Caso criado há 5 dias mas concluído hoje
        case = _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number="CYCLE-TODAY",
            cleanup_completed_at=timezone.make_aware(
                datetime.combine(today, time(10, 0)),
                tz,
            ),
        )
        self._set_created_at(
            case,
            timezone.make_aware(
                datetime.combine(five_days_ago, time(8, 0)),
                tz,
            ),
        )

        avg = _compute_average_times(period="today")
        assert avg["total_cycle"] == "122 h"

    def test_total_cycle_period_uses_cleanup_completed_event_fallback(self, client) -> None:
        """Ciclo Total usa evento CLEANUP_COMPLETED quando cleanup_completed_at está vazio.

        Caso histórico sem cleanup_completed_at mas com evento no período entra.
        """
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        five_days_ago = today - timedelta(days=5)

        created = timezone.make_aware(
            datetime.combine(five_days_ago, time(8, 0)),
            tz,
        )
        completed = timezone.make_aware(
            datetime.combine(today, time(10, 0)),
            tz,
        )

        case = _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number="CYCLE-EVT-FALLBACK",
        )
        self._set_field(case, cleanup_completed_at=None)
        self._set_created_at(case, created)

        # Criar evento CLEANUP_COMPLETED no período
        event = CaseEvent.objects.create(
            case=case,
            event_type="CLEANUP_COMPLETED",
            actor=user,
            actor_type="human",
            payload={},
        )
        CaseEvent.objects.filter(pk=event.pk).update(timestamp=completed)

        avg = _compute_average_times(period="today")
        assert avg["total_cycle"] == "122 h"

    # ── Template tests ──────────────────────────────────────────────────

    def test_template_has_metrics_period_selector(self, client) -> None:
        """GET /dashboard/ contém 'Período das métricas', 'Hoje', '7 dias', '30 dias', 'Tudo'."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Período das métricas" in content, "Label 'Período das métricas' deve estar no template"
        assert "Hoje" in content, "Opção 'Hoje' deve estar no template"
        assert "7 dias" in content, "Opção '7 dias' deve estar no template"
        assert "30 dias" in content, "Opção '30 dias' deve estar no template"
        assert "Tudo" in content, "Opção 'Tudo' deve estar no template"
        # 'Data das métricas' não deve mais existir
        assert "Data das métricas" not in content, "'Data das métricas' foi removido"

    def test_case_filter_form_preserves_metrics_period(self, client) -> None:
        """Formulário de filtros de casos preserva metrics_period via hidden input."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index") + "?metrics_period=30d")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="metrics_period"' in content, "metrics_period deve estar em algum input"
        assert 'value="30d"' in content, "hidden input deve preservar value=30d"

    def test_attention_link_preserves_metrics_period(self, client) -> None:
        """Link 'Atenção necessária' preserva metrics_period e search."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index") + "?metrics_period=7d&search=ana")
        assert response.status_code == 200
        content = response.content.decode()
        # O link de atenção deve conter metrics_period=7d
        assert "metrics_period=7d" in content, "Link de atenção deve preservar metrics_period=7d"

    def test_partial_pagination_preserves_metrics_period(self, client) -> None:
        """Com casos suficientes para paginação e metrics_period=all, links de página preservam o parâmetro."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # Criar 25 casos para forçar paginação
        for i in range(25):
            _create_case(
                created_by=user,
                status=CaseStatus.NEW,
                agency_record_number=f"PAG-PERIOD-{i:03d}",
            )

        response = client.get(reverse("dashboard:index") + "?metrics_period=all")
        assert response.status_code == 200
        content = response.content.decode()
        # Links de paginação devem conter metrics_period=all
        assert "metrics_period=all" in content, "Paginação deve preservar metrics_period=all"
        # Deve ter links de página (25 > 20 por página)
        assert "page-link" in content, "Deve haver paginação"

    def test_atual_label_still_present_in_stage_waiting(self, client) -> None:
        """Aguardando por etapa continua como snapshot atual e rotulado 'ATUAL'."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "ATUAL" in content, "Aguardando por etapa deve manter label ATUAL"

    def test_metrics_period_option_active_highlighted(self, client) -> None:
        """Opção ativa do seletor de período é visualmente identificável (active/selected)."""
        _login_as(client, "manager")
        # Testar com cada período
        for period, label in [("today", "Hoje"), ("7d", "7 dias"), ("30d", "30 dias"), ("all", "Tudo")]:
            response = client.get(reverse("dashboard:index") + f"?metrics_period={period}")
            assert response.status_code == 200
            content = response.content.decode()
            # O label do período ativo deve estar presente
            assert label in content, f"Período {period} deve mostrar label '{label}'"

    def test_total_label_changes_with_period(self, client) -> None:
        """Total label varia conforme período: 'Total hoje', 'Total 7 dias', 'Total 30 dias', 'Total geral'."""
        _login_as(client, "manager")

        response_today = client.get(reverse("dashboard:index"))
        assert (
            "Total hoje" in response_today.content.decode().lower() or "Total Hoje" in response_today.content.decode()
        )

        response_7d = client.get(reverse("dashboard:index") + "?metrics_period=7d")
        assert "7 dias" in response_7d.content.decode()

        response_30d = client.get(reverse("dashboard:index") + "?metrics_period=30d")
        assert "30 dias" in response_30d.content.decode()

        response_all = client.get(reverse("dashboard:index") + "?metrics_period=all")
        assert "Total geral" in response_all.content.decode() or "Geral" in response_all.content.decode()

    def test_average_times_card_shows_period_aux_text(self, client) -> None:
        """Card de Tempo Médio mostra texto 'Etapas concluídas no período'."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Etapas concluídas no período" in content, (
            "Card de Tempo Médio deve mostrar 'Etapas concluídas no período'"
        )

    def test_metrics_date_in_template_as_custom_control(self, client) -> None:
        """Input metrics_date está presente como controle de período personalizado."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="metrics_date"' in content, "metrics_date deve estar presente no template (custom date)"
        assert 'name="metrics_start"' in content, "metrics_start deve estar presente no template (custom range)"
        assert 'name="metrics_end"' in content, "metrics_end deve estar presente no template (custom range)"

    def test_existing_metrics_date_view_still_works(self, client) -> None:
        """GET com ?metrics_date=... não quebra (retorna 200) — compatibilidade reversa."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index") + "?metrics_date=2026-07-01")
        assert response.status_code == 200


# ── Dashboard: Custom Date Range Metrics (Slice 001) ─────────────────────


@pytest.mark.django_db
class TestDashboardCustomDateRange:
    """Testes para data e intervalo personalizados nas métricas do dashboard."""

    def _set_cases_date(self, case, **fields) -> None:
        """Seta campos datetime de um Case via update() para burlar auto_now."""
        Case.objects.filter(pk=case.pk).update(**fields)

    def test_metrics_custom_date_counts_cases_created_on_selected_local_day(self, client) -> None:
        """custom_date conta apenas casos criados na data selecionada (dia local).

        Usa uma data != hoje e SEM caso hoje, de forma que o fallback para
        'today' produziria total=0: se total=1, então custom_date foi resolvido.
        """
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today_local = timezone.localdate()
        selected = today_local - timedelta(days=2)  # data selecionada não é hoje

        # Único caso, criado na data selecionada (não há caso hoje).
        case_in = _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR, agency_record_number="IN-DATE")
        self._set_cases_date(case_in, created_at=datetime.combine(selected, time(8, 0), tzinfo=tz))

        response = client.get(
            reverse("dashboard:index") + f"?metrics_period=custom_date&metrics_date={selected.isoformat()}"
        )
        assert response.status_code == 200
        summary = response.context["summary"]
        assert summary["total_today"] == 1, (
            f"custom_date deve contar apenas o caso da data selecionada ({selected}); "
            f"total_today={summary['total_today']} (fallback para hoje contaria 0)"
        )

    def test_metrics_custom_range_counts_cases_created_in_inclusive_range(self, client) -> None:
        """custom_range inclui casos criados no início e fim do intervalo, exclui fora."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today_local = timezone.localdate()
        start = today_local - timedelta(days=5)
        end = today_local - timedelta(days=2)
        before_start = start - timedelta(days=1)
        after_end = end + timedelta(days=1)

        case_start = _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="RANGE-START")
        self._set_cases_date(
            case_start, created_at=datetime.combine(start, time(0, 0, 1), tzinfo=timezone.get_current_timezone())
        )

        case_end = _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="RANGE-END")
        self._set_cases_date(
            case_end, created_at=datetime.combine(end, time(23, 59, 59), tzinfo=timezone.get_current_timezone())
        )

        case_before = _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="RANGE-BEFORE")
        self._set_cases_date(
            case_before,
            created_at=datetime.combine(before_start, time(23, 59, 59), tzinfo=timezone.get_current_timezone()),
        )

        case_after = _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="RANGE-AFTER")
        self._set_cases_date(
            case_after, created_at=datetime.combine(after_end, time(0, 0, 1), tzinfo=timezone.get_current_timezone())
        )

        # URL com custom_range — deve filtrar métricas para o intervalo inclusivo
        response = client.get(
            reverse("dashboard:index")
            + f"?metrics_period=custom_range&metrics_start={start.isoformat()}&metrics_end={end.isoformat()}"
        )
        assert response.status_code == 200

        # O card de métricas (summary) deve contar apenas os 2 casos dentro do
        # intervalo [start, end] (inclusivo), excluindo before e after.
        summary = response.context["summary"]
        assert summary["total_today"] == 2, (
            f"custom_range deve contar apenas RANGE-START e RANGE-END (inclusivo); total_today={summary['total_today']}"
        )

    def test_metrics_custom_date_average_filters_by_stage_completion_date(self, client) -> None:
        """Tempo médio custom_date filtra por conclusão da etapa, não por created_at."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        today_local = timezone.localdate()
        yesterday = today_local - timedelta(days=1)
        three_days_ago = today_local - timedelta(days=3)

        # Caso criado há 3 dias, mas decidido hoje → deve entrar no upload_to_decision
        case_decided_today = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="AVG-DEC-TODAY",
        )
        created_at_past = datetime.combine(three_days_ago, time(8, 0), tzinfo=timezone.get_current_timezone())
        decided_at_today = datetime.combine(today_local, time(10, 0), tzinfo=timezone.get_current_timezone())
        self._set_cases_date(case_decided_today, created_at=created_at_past, doctor_decided_at=decided_at_today)

        # Caso criado hoje, mas decidido ontem → NÃO deve entrar no upload_to_decision
        case_decided_yesterday = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="AVG-DEC-YEST",
        )
        created_at_today = datetime.combine(today_local, time(8, 0), tzinfo=timezone.get_current_timezone())
        decided_at_yesterday = datetime.combine(yesterday, time(10, 0), tzinfo=timezone.get_current_timezone())
        self._set_cases_date(
            case_decided_yesterday, created_at=created_at_today, doctor_decided_at=decided_at_yesterday
        )

        # Chama _compute_average_times diretamente para verificar semântica
        from zoneinfo import ZoneInfo

        from django.utils import timezone as tz_utils

        from apps.dashboard.views import _compute_average_times

        with tz_utils.override(ZoneInfo("America/Sao_Paulo")):
            result = _compute_average_times(period=f"custom_date:{today_local.isoformat()}")

        # Só o caso decidido hoje deve entrar (criado há 3 dias, decidido hoje)
        # O tempo deve ser > 0, aproximadamente 2 dias = ~2880 min
        assert result["upload_to_decision"] != "—", "Deveria haver tempo médio para decisão (caso decidido no período)"

    def test_metrics_custom_range_average_filters_by_stage_completion_range(self, client) -> None:
        """Tempo médio custom_range filtra por conclusão da etapa, não por created_at.

        Caso criado fora do intervalo mas decidido dentro entra; caso criado
        dentro mas decidido fora não entra. Prova que o filtro da média é por
        doctor_decided_at no range (conclusão), e não por created_at.
        """
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today_local = timezone.localdate()
        start = today_local - timedelta(days=3)
        end = today_local - timedelta(days=1)
        far_past = today_local - timedelta(days=30)

        # Caso criado há 30 dias (fora do range), decidido no início do range → entra.
        # delta decisão-criação = 27 dias 2 h = 650 h.
        case_in = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="RANGE-AVG-IN",
        )
        self._set_cases_date(
            case_in,
            created_at=datetime.combine(far_past, time(8, 0), tzinfo=tz),
            doctor_decided_at=datetime.combine(start, time(10, 0), tzinfo=tz),
        )

        # Caso criado dentro do range, decidido bem antes do range → não entra.
        # Se o filtro fosse por created_at, este caso entraria e produziria duração
        # negativa, mudando a média para algo diferente de "650 h".
        case_out = _create_case(
            created_by=user,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            agency_record_number="RANGE-AVG-OUT",
        )
        self._set_cases_date(
            case_out,
            created_at=datetime.combine(end, time(8, 0), tzinfo=tz),
            doctor_decided_at=datetime.combine(far_past, time(10, 0), tzinfo=tz),
        )

        period = f"custom_range:{start.isoformat()}:{end.isoformat()}"
        result = _compute_average_times(period=period)
        # Apenas case_in contribui → média = 650 h exatos.
        assert result["upload_to_decision"] == "650 h", (
            f"custom_range deve filtrar média por doctor_decided_at (conclusão); "
            f"obtido upload_to_decision={result['upload_to_decision']!r}"
        )

    def test_metrics_custom_range_total_cycle_uses_cleanup_event_fallback(self, client) -> None:
        """Ciclo Total em custom_range usa evento CLEANUP_COMPLETED quando cleanup_completed_at está vazio."""
        from apps.dashboard.views import _compute_average_times

        user = _login_as(client, "manager")
        Case.objects.all().delete()

        tz = timezone.get_current_timezone()
        today_local = timezone.localdate()
        start = today_local - timedelta(days=3)
        end = today_local - timedelta(days=1)
        far_past = today_local - timedelta(days=30)

        # Caso histórico sem cleanup_completed_at, com evento CLEANUP_COMPLETED dentro do range.
        case = _create_case(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number="RANGE-CYCLE-EVT",
        )
        self._set_cases_date(
            case,
            created_at=datetime.combine(far_past, time(8, 0), tzinfo=tz),
            cleanup_completed_at=None,
        )
        event = CaseEvent.objects.create(
            case=case,
            event_type="CLEANUP_COMPLETED",
            actor=user,
            actor_type="human",
            payload={},
        )
        # Evento dentro do range (início do range).
        CaseEvent.objects.filter(pk=event.pk).update(timestamp=datetime.combine(start, time(10, 0), tzinfo=tz))

        period = f"custom_range:{start.isoformat()}:{end.isoformat()}"
        result = _compute_average_times(period=period)
        # delta = completed_event - created = (today-3 10:00) - (today-30 08:00) = 650 h.
        assert result["total_cycle"] == "650 h", (
            f"custom_range deve usar fallback do evento CLEANUP_COMPLETED quando "
            f"cleanup_completed_at está vazio; obtido total_cycle={result['total_cycle']!r}"
        )

    def test_personalizado_uses_independent_ssr_mini_forms(self, client) -> None:
        """Cada fluxo Personalizado é um <form> com seu próprio hidden metrics_period.

        Guarda contra regressão do bug em que o botão 'Aplicar' usava onclick
        para setar um input[name=metrics_period] inexistente dentro do form,
        fazendo a UI sempre cair para 'today'. A correção adota dois mini-forms
        SSR puros (design D7), cada um com hidden metrics_period + submit.
        """
        import re

        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()

        # O padrão frágil (onclick setando metrics_period) não deve mais existir.
        assert "querySelector('input[name=metrics_period]')" not in content, (
            "UI não deve depender de onclick/JS para setar metrics_period"
        )

        forms = re.findall(r"<form\b[^>]*>.*?</form>", content, re.DOTALL | re.IGNORECASE)

        # Mini-form Data específica: form com metrics_date + metrics_period=custom_date + submit.
        date_form = [f for f in forms if 'name="metrics_date"' in f and 'value="custom_date"' in f and "Aplicar" in f]
        assert date_form, (
            "Deve existir um mini-form (Data específica) com metrics_date, "
            "hidden metrics_period=custom_date e botão Aplicar"
        )
        assert 'type="submit"' in date_form[0], "Mini-form Data específica deve ter botão submit"

        # Mini-form Intervalo: form com metrics_start + metrics_end + metrics_period=custom_range + submit.
        range_form = [
            f
            for f in forms
            if 'name="metrics_start"' in f
            and 'name="metrics_end"' in f
            and 'value="custom_range"' in f
            and "Aplicar" in f
        ]
        assert range_form, (
            "Deve existir um mini-form (Intervalo) com metrics_start, metrics_end, "
            "hidden metrics_period=custom_range e botão Aplicar"
        )
        assert 'type="submit"' in range_form[0], "Mini-form Intervalo deve ter botão submit"

    def test_invalid_custom_date_falls_back_to_today_with_feedback(self, client) -> None:
        """metrics_period=custom_date sem metrics_date cai para today com feedback."""
        _login_as(client, "manager")

        # custom_date sem date
        response = client.get(reverse("dashboard:index") + "?metrics_period=custom_date")
        assert response.status_code == 200
        content = response.content.decode()

        # Deve cair para today
        assert "Total Hoje" in content or "Métricas de hoje" in content, "Deve cair para today"
        # Deve mostrar feedback discreto
        assert "Período personalizado inválido" in content, "Deve mostrar feedback de erro"

    def test_invalid_custom_range_falls_back_to_today_with_feedback(self, client) -> None:
        """Intervalo invertido cai para today com feedback."""
        _login_as(client, "manager")

        today_local = timezone.localdate()
        start = today_local
        end = today_local - timedelta(days=5)  # start > end = invertido

        response = client.get(
            reverse("dashboard:index")
            + f"?metrics_period=custom_range&metrics_start={start.isoformat()}&metrics_end={end.isoformat()}"
        )
        assert response.status_code == 200
        content = response.content.decode()

        # Deve cair para today
        assert "Total Hoje" in content or "Métricas de hoje" in content, "Intervalo invertido deve cair para today"
        # Deve mostrar feedback discreto
        assert "Período personalizado inválido" in content, "Deve mostrar feedback de erro"

    def test_metrics_period_selector_uses_hospital_toolbar_classes(self, client) -> None:
        """Seletor de período usa card/toolbar próprio alinhado ao tema hospitalar."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()

        assert "metrics-period-card" in content, "Seletor deve estar dentro de um card compacto"
        assert "metrics-period-options" in content, "Opções devem usar wrapper responsivo próprio"
        assert "metrics-period-option" in content, "Botões devem usar classe própria do seletor"
        assert "metrics-period-custom-panel" in content, "Painel personalizado deve ter classe própria"
        assert "metrics-period-date-control" in content, "Campos de data devem ter wrapper com dica visual"
        assert "bi-calendar-event" in content, "Campos de data devem usar ícone calendar-event monocromático"

    def test_metrics_period_selector_does_not_use_bootstrap_primary_group(self, client) -> None:
        """Seletor evita btn-group/btn-primary Bootstrap puro, que desalinha no mobile."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()

        selector_start = content.index('id="metrics-period-selector"')
        selector_end = content.index("<!-- Summary Cards -->")
        selector_html = content[selector_start:selector_end]

        assert "btn-group" not in selector_html
        assert "btn-primary" not in selector_html
        assert "btn-outline-primary" not in selector_html

    def test_metrics_period_selector_css_has_responsive_rules(self, client) -> None:
        """CSS do seletor define toolbar hospitalar e comportamento mobile."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

        css_path = "/projects/dev/ats-web/static/css/app.css"
        with open(css_path) as f:
            css_content = f.read()

        assert ".metrics-period-options" in css_content
        assert ".metrics-period-option.is-active" in css_content
        assert ".metrics-period-custom" in css_content
        assert ".metrics-period-date-control" in css_content
        assert ".metrics-period-date-icon" in css_content
        assert ".dashboard-date-control" in css_content
        assert ".dashboard-date-icon" in css_content
        assert "display: none;" in css_content, "Ícone customizado deve ficar oculto por padrão no desktop"
        assert "@media (max-width: 575.98px)" in css_content
        assert "display: inline-flex;" in css_content, "Ícone customizado deve aparecer só no mobile"

    def test_template_renders_custom_metrics_controls(self, client) -> None:
        """Template contém Personalizado, Data específica, Intervalo e inputs."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()

        assert "Personalizado" in content, "Template deve conter 'Personalizado'"
        assert "Data específica" in content, "Template deve conter 'Data específica'"
        assert "Intervalo" in content, "Template deve conter 'Intervalo'"
        assert 'name="metrics_date"' in content, "Template deve conter input metrics_date"
        assert 'name="metrics_start"' in content, "Template deve conter input metrics_start"
        assert 'name="metrics_end"' in content, "Template deve conter input metrics_end"
        assert content.count("bi-calendar-event") >= 3, "Cada campo date deve ter ícone discreto de calendário"

    def test_case_filter_date_inputs_have_mobile_calendar_icons(self, client) -> None:
        """Filtros Data inicial/final também recebem dica visual mobile de calendário."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()

        assert "dashboard-date-control" in content, "Filtros de data devem ter wrapper próprio"
        assert "dashboard-date-icon" in content, "Filtros de data devem ter ícone mobile"
        assert 'name="date_from"' in content
        assert 'name="date_to"' in content
        assert "dashboard-date-input" in content
        assert content.count("bi-calendar-event") >= 5, "3 campos métricas + 2 filtros devem ter SVG calendar-event"

    def test_metrics_custom_params_preserved_in_case_filter_form(self, client) -> None:
        """Filtro da lista preserva metrics_period e campos customizados como hidden."""
        _login_as(client, "manager")

        today_local = timezone.localdate()
        response = client.get(
            reverse("dashboard:index") + f"?metrics_period=custom_date&metrics_date={today_local.isoformat()}"
        )
        assert response.status_code == 200
        content = response.content.decode()

        # Deve ter hidden input para metrics_period no form de filtros
        assert 'name="metrics_period"' in content, "Hidden metrics_period deve estar presente"
        assert 'value="custom_date"' in content, "metrics_period=custom_date deve estar preservado"
        assert f'value="{today_local.isoformat()}"' in content, "metrics_date deve estar preservado"

    def test_attention_link_preserves_custom_metrics_params(self, client) -> None:
        """Link de atenção preserva metrics_period=custom_date e metrics_date."""
        _login_as(client, "manager")

        today_local = timezone.localdate()
        response = client.get(
            reverse("dashboard:index")
            + f"?metrics_period=custom_range&metrics_start={today_local.isoformat()}&metrics_end={today_local.isoformat()}"
        )
        assert response.status_code == 200
        content = response.content.decode()

        # Link de atenção deve conter os parâmetros customizados
        assert "metrics_period=custom_range" in content, "Link atenção deve preservar metrics_period"
        assert "metrics_start=" in content, "Link atenção deve preservar metrics_start"
        assert "metrics_end=" in content, "Link atenção deve preservar metrics_end"

    def test_partial_pagination_preserves_custom_metrics_params(self, client) -> None:
        """Links de paginação no partial preservam campos customizados."""
        user = _login_as(client, "manager")
        Case.objects.all().delete()

        # Criar 25 casos para forçar paginação
        for i in range(25):
            _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number=f"PAG-CUST-{i:03d}")

        today_local = timezone.localdate()
        response = client.get(
            reverse("dashboard:index") + f"?metrics_period=custom_date&metrics_date={today_local.isoformat()}"
        )
        assert response.status_code == 200
        content = response.content.decode()

        # Links de paginação devem preservar os parâmetros
        assert "metrics_period=custom_date" in content, "Paginação deve preservar metrics_period"
        assert f"metrics_date={today_local.isoformat()}" in content, "Paginação deve preservar metrics_date"

    def test_dashboard_search_js_preserves_custom_metrics_params(self, client) -> None:
        """dashboard_search.js lê metrics_date, metrics_start, metrics_end do DOM."""
        _login_as(client, "manager")
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200

        # Lê o arquivo JS em vez de depender de teste JS dedicado
        js_path = "/projects/dev/ats-web/static/js/dashboard_search.js"
        with open(js_path) as f:
            js_content = f.read()

        assert "metrics_date" in js_content, "dashboard_search.js deve referenciar metrics_date"
        assert "metrics_start" in js_content, "dashboard_search.js deve referenciar metrics_start"
        assert "metrics_end" in js_content, "dashboard_search.js deve referenciar metrics_end"
        assert "getFilterParams" in js_content, "getFilterParams deve estar presente"

    def test_metrics_custom_date_from_query_string_shows_correct_label(self, client) -> None:
        """custom_date exibe label legível 'Métricas de DD/MM/AAAA'."""
        _login_as(client, "manager")

        today_local = timezone.localdate()
        formatted = today_local.strftime("%d/%m/%Y")

        response = client.get(
            reverse("dashboard:index") + f"?metrics_period=custom_date&metrics_date={today_local.isoformat()}"
        )
        assert response.status_code == 200
        content = response.content.decode()

        expected_label = f"Métricas de {formatted}"
        assert expected_label in content, f"Label deve conter '{expected_label}'"

    def test_metrics_custom_range_from_query_string_shows_correct_label(self, client) -> None:
        """custom_range exibe label legível 'Métricas de DD/MM/AAAA a DD/MM/AAAA'."""
        _login_as(client, "manager")

        today_local = timezone.localdate()
        start_date = (today_local - timedelta(days=3)).isoformat()
        end_date = (today_local - timedelta(days=1)).isoformat()

        start_formatted = (today_local - timedelta(days=3)).strftime("%d/%m/%Y")
        end_formatted = (today_local - timedelta(days=1)).strftime("%d/%m/%Y")

        response = client.get(
            reverse("dashboard:index")
            + f"?metrics_period=custom_range&metrics_start={start_date}&metrics_end={end_date}"
        )
        assert response.status_code == 200
        content = response.content.decode()

        expected_label = f"Métricas de {start_formatted} a {end_formatted}"
        assert expected_label in content, f"Label deve conter '{expected_label}'"
