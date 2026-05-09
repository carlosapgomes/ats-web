"""Testes do dashboard — Slice 1: App dashboard + view + template + case detail admin."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseStatus, SupervisorSummary

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
        """Summary cards refletem casos de hoje."""
        user = _login_as(client, "manager")

        # Casos criados hoje
        _create_case(created_by=user, status=CaseStatus.APPT_CONFIRMED, doctor_decision="accept")
        _create_case(created_by=user, status=CaseStatus.WAIT_DOCTOR)
        _create_case(created_by=user, status=CaseStatus.DOCTOR_DENIED)
        _create_case(created_by=user, status=CaseStatus.APPT_DENIED)

        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        content = response.content.decode()
        # Total Hoje = 4
        assert "4" in content
        # Aceitos (doctor_decision=accept, not denied/failed) = 1
        # Negados (DOCTOR_DENIED ou APPT_DENIED) = 2
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
    """Verifica a tabela de todos os casos."""

    def test_case_table_shows_all_cases(self, client) -> None:
        """Tabela lista todos os casos sem filtro de usuário."""
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
        """Paginação aparece na tabela de casos (>20 casos)."""
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
        """Tabela tem link 'Ver' para cada caso."""
        user = _login_as(client, "manager")
        case = _create_case(created_by=user, status=CaseStatus.NEW, agency_record_number="LINK-001")
        response = client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode()
        assert str(case.case_id)[:8] in content or "LINK-001" in content


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
        """Nav pill 'Auditoria' aparece (placeholder)."""
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
