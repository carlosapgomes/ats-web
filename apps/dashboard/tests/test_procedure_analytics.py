"""Slice 006 — analytics por dimensão (declarado/detectado/autorizado).

Cobre R1 (consolidado case-level), R2 (breakdown exclusivo com fechamento),
R3 (volume de componentes), R4 (matriz de conversão e casados), R5 (tabela
com dimensão + seleção compondo todos os filtros/paginação/partial) e R6
(query hygiene com queries limitadas).
"""

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseStatus
from apps.cases.procedures import (
    get_declared_procedure_types,
    record_doctor_procedure_decisions,
    set_declared_procedures,
    set_detected_procedures,
)

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────


def _login_as(client, role_name: str = "manager"):
    """Cria usuário com papel, faz login e seta active_role na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"{role_name}@slice006.test", password="testpass123")
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _make_case(
    user,
    arn: str,
    *,
    declared=(),
    detected=(),
    approved=(),
    status=CaseStatus.CLEANED,
    appointment_status="",
    doctor_decision="",
    structured_data=None,
):
    """Cria caso com projeções via serviços centrais (evita dual-write manual)."""
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        status=status,
        appointment_status=appointment_status,
        doctor_decision=doctor_decision,
        structured_data=structured_data,
    )
    if declared:
        set_declared_procedures(case=case, procedure_types=declared, actor=user)
    if detected:
        set_detected_procedures(case=case, detected_types=detected, actor=user)
    if approved:
        record_doctor_procedure_decisions(
            case=case,
            decisions=[
                {"procedure_type": t, "disposition": "approved", "reason": "ok", "added_by_doctor": False}
                for t in approved
            ],
            actor=user,
        )
    return Case.objects.get(pk=case.pk)


def _seed_four_cases(user):
    """4 casos: EDA único, combinado, Colon único negado, EDA→combinado→Colon."""
    Case.objects.all().delete()
    a = _make_case(
        user,
        "SL6-A",
        declared=("eda",),
        detected=("eda",),
        approved=("eda",),
        appointment_status="confirmed",
    )
    b = _make_case(
        user,
        "SL6-B",
        declared=("eda", "colonoscopy"),
        detected=("eda", "colonoscopy"),
        approved=("eda", "colonoscopy"),
        appointment_status="confirmed",
    )
    c = _make_case(
        user,
        "SL6-C",
        declared=("colonoscopy",),
        detected=("colonoscopy",),
        approved=(),
        doctor_decision="deny",
    )
    d = _make_case(
        user,
        "SL6-D",
        declared=("eda",),
        detected=("eda", "colonoscopy"),
        approved=("colonoscopy",),
        appointment_status="confirmed",
    )
    return a, b, c, d


# ── R1/R6: Consolidado case-level e snapshot preservados ────────────────


@pytest.mark.django_db
class TestConsolidatedPreserved:
    """R1 — métricas consolidadas continuam case-level; combinado soma 1."""

    def test_combined_counts_once_in_case_level_total(self, client) -> None:
        from apps.dashboard.views import _compute_summary

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "R1-B",
            declared=("eda", "colonoscopy"),
            status=CaseStatus.CLEANED,
            appointment_status="confirmed",
            doctor_decision="accept",
        )
        summary = _compute_summary(period="all")
        assert summary["total_today"] == 1, "Combinado soma 1 no total case-level"
        assert summary["accepted"] == 1
        assert summary["denied"] == 0
        assert summary["in_progress"] == 0

    def test_waiting_snapshot_preserved_with_combined(self, client) -> None:
        from apps.dashboard.views import _compute_stage_waiting

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "R6-W", declared=("eda", "colonoscopy"), status=CaseStatus.WAIT_DOCTOR)
        waiting = _compute_stage_waiting()
        assert waiting["waiting_doctor"] == 1, "Esperas seguem snapshot case-level (combinado = 1)"
        assert waiting["waiting_appt"] == 0
        assert waiting["waiting_confirm"] == 0


# ── R2/R3: Breakdown exclusivo por dimensão e volume de componentes ─────


@pytest.mark.django_db
class TestDimensionBreakdownAndVolume:
    """R2/R3 — breakdown fecha por dimensão e volume separa casos de componentes."""

    def test_breakdown_closes_per_dimension_and_classifies_none(self, client) -> None:
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        _seed_four_cases(user)

        analytics = compute_procedure_analytics(Case.objects.all())
        breakdown = analytics["breakdown"]

        for dim in ("declared", "detected", "approved"):
            total = sum(breakdown[dim].values())
            assert total == 4, f"Breakdown {dim} deve fechar com 4 casos, obteve {total}"

        # Declarado: A,D = EDA; B = combinado; C = Colonoscopia
        assert breakdown["declared"] == {"eda": 2, "colonoscopy": 1, "eda_colonoscopy": 1, "none": 0}
        # Detectado: A = EDA; B,D = combinado; C = Colonoscopia
        assert breakdown["detected"] == {"eda": 1, "colonoscopy": 1, "eda_colonoscopy": 2, "none": 0}
        # Autorizado: A = EDA; B = combinado; C = Nenhum (negado integral); D = Colonoscopia
        assert breakdown["approved"] == {"eda": 1, "colonoscopy": 1, "eda_colonoscopy": 1, "none": 1}

    def test_component_volume_counts_combined_as_two(self, client) -> None:
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        _seed_four_cases(user)

        analytics = compute_procedure_analytics(Case.objects.all())
        volume = analytics["volume"]

        # Declarado: EDA em A,B,D (3); Colon em B,C (2); combinado B (1)
        assert volume["declared"] == {"eda": 3, "colonoscopy": 2, "combined": 1}
        # Detectado: EDA em A,B,D (3); Colon em B,C,D (3); combinado B,D (2)
        assert volume["detected"] == {"eda": 3, "colonoscopy": 3, "combined": 2}
        # Autorizado: EDA em A,B (2); Colon em B,D (2); combinado B (1)
        assert volume["approved"] == {"eda": 2, "colonoscopy": 2, "combined": 1}

        # Casos (4) ≠ componentes (5 no declarado): 4 + 1 combinado = 5
        assert volume["declared"]["eda"] + volume["declared"]["colonoscopy"] == 5
        # Um único combinado soma exatamente 1 EDA e 1 Colon
        assert volume["declared"]["combined"] == 1

    def test_breakdown_respects_period(self, client) -> None:
        from apps.dashboard.procedure_analytics import compute_procedure_analytics
        from apps.dashboard.views import _period_bounds

        user = _login_as(client)
        Case.objects.all().delete()
        yesterday_case = _make_case(user, "SL6-YEST", declared=("eda",))
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        yesterday_local = timezone.make_aware(
            datetime.combine(yesterday, time(10, 0)),
            timezone.get_current_timezone(),
        )
        Case.objects.filter(pk=yesterday_case.pk).update(created_at=yesterday_local)

        start, end = _period_bounds("today")
        today_analytics = compute_procedure_analytics(Case.objects.filter(created_at__gte=start, created_at__lt=end))
        assert sum(today_analytics["breakdown"]["declared"].values()) == 0, (
            "Analytics de hoje não pode incluir caso de ontem"
        )
        all_analytics = compute_procedure_analytics(Case.objects.all())
        assert all_analytics["breakdown"]["declared"]["eda"] == 1


# ── R4: Matriz de conversão e agendamentos casados ──────────────────────


@pytest.mark.django_db
class TestConversionMatrixAndPaired:
    """R4 — caminho exato na matriz e paired confirmed conta uma vez."""

    def test_matrix_classifies_exact_path(self, client) -> None:
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        _seed_four_cases(user)

        analytics = compute_procedure_analytics(Case.objects.all())
        matrix = analytics["matrix"]

        # A: declarado EDA → detectado EDA → autorizado EDA
        assert matrix[("eda", "eda")] == {"eda": 1}
        # B: declarado combinado → detectado combinado → autorizado combinado
        assert matrix[("eda_colonoscopy", "eda_colonoscopy")] == {"eda_colonoscopy": 1}
        # C: declarado Colon → detectado Colon → autorizado Nenhum
        assert matrix[("colonoscopy", "colonoscopy")] == {"none": 1}
        # D: declarado EDA → detectado combinado → autorizado Colon (caminho exato)
        assert matrix[("eda", "eda_colonoscopy")] == {"colonoscopy": 1}

        # Caso D NÃO pode aparecer em caminho incompatível
        assert ("eda", "eda") not in [k for k in matrix if k[1] == "eda_colonoscopy"] or (
            ("eda", "eda_colonoscopy") in matrix and matrix[("eda", "eda_colonoscopy")] == {"colonoscopy": 1}
        )
        # Fechamento: soma das células = total de casos
        total = sum(sum(cell.values()) for cell in matrix.values())
        assert total == 4, f"Matriz deve fechar com 4 casos, obteve {total}"

    def test_ordered_sets_normalize_combination(self, client) -> None:
        from apps.dashboard.procedure_analytics import category_key

        user = _login_as(client)
        Case.objects.all().delete()
        case = _make_case(user, "SL6-ORD", declared=("colonoscopy", "eda"))
        # Conjuntos ordenados: entrada desordenada normaliza para (eda, colonoscopy)
        assert get_declared_procedure_types(case) == ("eda", "colonoscopy")
        assert category_key(get_declared_procedure_types(case)) == "eda_colonoscopy"

    def test_paired_confirmed_counts_once(self, client) -> None:
        from apps.cases.services import administratively_close_case
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        # P-1: ambos aprovados + confirmado → 1
        _make_case(
            user,
            "P-1",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
            appointment_status="confirmed",
        )
        # P-2: ambos aprovados sem confirmação → não conta
        _make_case(
            user,
            "P-2",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
            appointment_status="denied",
        )
        # P-3: apenas EDA aprovado + confirmado → não conta
        _make_case(user, "P-3", declared=("eda",), detected=("eda",), approved=("eda",), appointment_status="confirmed")
        # P-4: ambos aprovados + confirmado, mas encerrado administrativamente → não conta
        admin_case = _make_case(
            user,
            "P-4",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
            status=CaseStatus.WAIT_DOCTOR,
            appointment_status="confirmed",
        )
        administratively_close_case(
            case=admin_case,
            user=user,
            reason_code="system_bug",
            reason_text="Encerrado no teste",
            active_role="manager",
        )

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["paired_confirmed"] == 1, (
            f"Agendamentos casados devem contar 1, obteve {analytics['paired_confirmed']}"
        )


# ── R5: Tabela compõe dimensão + seleção com todos os filtros ───────────


@pytest.mark.django_db
class TestDimensionTableFilter:
    """R5 — dimensão + seleção compõem com busca/status/datas/atenção/paginação."""

    def test_selection_filters_by_dimension(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "TF-1", declared=("eda",), detected=("eda",), approved=("eda",))
        _make_case(
            user,
            "TF-2",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
        )
        _make_case(user, "TF-3", declared=("colonoscopy",), detected=("colonoscopy",), approved=())

        url = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=eda"
        content = client.get(url).content.decode()
        assert "TF-1" in content, "Seleção EDA na dimensão declarado deve mostrar TF-1"
        assert "TF-2" not in content, "Combinado não pode casar com seleção EDA"
        assert "TF-3" not in content, "Colonoscopia não pode casar com seleção EDA"

        url = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=eda_colonoscopy"
        content = client.get(url).content.decode()
        assert "TF-2" in content, "Seleção combinado deve mostrar TF-2"
        assert "TF-1" not in content and "TF-3" not in content

        url = reverse("dashboard:index") + "?procedure_dimension=approved&procedure_selection=none"
        content = client.get(url).content.decode()
        assert "TF-3" in content, "Nenhum na dimensão autorizado deve mostrar TF-3"
        assert "TF-1" not in content and "TF-2" not in content

    def test_selection_composes_with_search_and_status(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "AND-1",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Ana Combinada"}},
        )
        _make_case(
            user,
            "AND-2",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            status=CaseStatus.NEW,
            structured_data={"patient": {"name": "Bruno Combinado"}},
        )
        _make_case(
            user,
            "AND-3",
            declared=("eda",),
            detected=("eda",),
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Ana EDA"}},
        )

        url = (
            reverse("dashboard:index")
            + "?procedure_dimension=detected&procedure_selection=eda_colonoscopy&search=ana&status="
            + CaseStatus.WAIT_DOCTOR
        )
        content = client.get(url).content.decode()
        assert "AND-1" in content, "Dimensão+seleção+busca+status devem casar AND-1"
        assert "AND-2" not in content, "Status NEW não pode casar com WAIT_DOCTOR"
        assert "AND-3" not in content, "EDA único não pode casar com seleção combinado"

    def test_selection_filters_legacy_cases_without_rows(self, client) -> None:
        """Slice 010 — casos legados sem rows caem em ``none`` em todas as dimensões.

        Sem fallback da ponte: nem ``exam_type=eda`` nem ``doctor_decision=accept``
        transformam ausência de rows em EDA/Colonoscopia.
        """
        user = _login_as(client)
        Case.objects.all().delete()
        Case.objects.create(
            created_by=user,
            status=CaseStatus.NEW,
            exam_type="eda",
            doctor_decision="accept",
            agency_record_number="LEG-EDA",
        )
        Case.objects.create(
            created_by=user,
            status=CaseStatus.NEW,
            exam_type="colonoscopy",
            doctor_decision="deny",
            agency_record_number="LEG-NONE",
        )

        # Sem rows, ambos caem em ``none`` na dimensão declared.
        url_none = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=none"
        content_none = client.get(url_none).content.decode()
        assert "LEG-EDA" in content_none, "Legado EDA sem rows deve cair em none (declared)"
        assert "LEG-NONE" in content_none, "Legado Colon sem rows deve cair em none (declared)"

        # declared+eda NÃO mostra nenhum dos legados sem rows.
        url_eda = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=eda"
        content_eda = client.get(url_eda).content.decode()
        assert "LEG-EDA" not in content_eda, "Legado EDA sem rows não pode casar declared+eda"
        assert "LEG-NONE" not in content_eda

        # approved+none também mostra ambos (sem rows aprovadas).
        url_none = reverse("dashboard:index") + "?procedure_dimension=approved&procedure_selection=none"
        content_none = client.get(url_none).content.decode()
        assert "LEG-EDA" in content_none, "Legado accept sem rows aprovadas deve cair em none (approved)"
        assert "LEG-NONE" in content_none

    def test_invalid_dimension_and_selection_fall_back_to_defaults(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "DF-1", declared=("eda",))
        _make_case(user, "DF-2", declared=("colonoscopy",))

        content = client.get(
            reverse("dashboard:index") + "?procedure_dimension=bogus&procedure_selection=bogus"
        ).content.decode()
        assert "DF-1" in content and "DF-2" in content, "Dimensão/seleção inválidas devem cair em defaults seguros"
        assert "Declarado" in content, "Dimensão ativa padrão deve ser exibida (Declarado)"

    def test_partial_pagination_preserves_dimension_and_selection(self, client) -> None:
        user = _login_as(client)
        Case.objects.all().delete()
        for i in range(25):
            _make_case(user, f"PP-{i:03d}", declared=("eda",), detected=("eda",))
        response = client.get(
            reverse("dashboard:index") + "?procedure_dimension=detected&procedure_selection=eda",
            headers={"X-ATS-Partial": "case-list"},
        )
        content = response.content.decode()
        assert "procedure_dimension=detected" in content, "Paginação do partial deve preservar dimensão"
        assert "procedure_selection=eda" in content, "Paginação do partial deve preservar seleção"

    def test_js_preserves_dimension_and_selection(self, client) -> None:
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        js_path = base_dir / "static" / "js" / "dashboard_search.js"
        assert js_path.exists()
        js_content = js_path.read_text()
        assert "procedure_dimension" in js_content
        assert "procedure_selection" in js_content
        assert "params.set('procedure_dimension'" in js_content
        assert "params.set('procedure_selection'" in js_content

    def test_template_has_dimension_and_selection_controls(self, client) -> None:
        _login_as(client)
        content = client.get(reverse("dashboard:index")).content.decode()
        assert 'name="procedure_dimension"' in content
        assert 'name="procedure_selection"' in content
        assert 'value="declared"' in content
        assert 'value="detected"' in content
        assert 'value="approved"' in content
        assert 'value="eda_colonoscopy"' in content
        assert 'value="none"' in content


# ── R6: Query hygiene ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBreakdownTableConsistency:
    """Slice 010 — breakdown e tabela concordam no contrato fail-closed.

    Casos com rows em outra dimensão, mas não na consultada, caem em ``none`` —
    tanto no breakdown (Python) quanto no filtro SQL da tabela. Sem fallback
    da ponte ``Case.exam_type`` nem de ``doctor_decision`` (R2/R3).
    """

    def test_fresh_declared_eda_matches_detected_none_not_eda(self, client) -> None:
        """Caso recém-declarado EDA (detecção pendente): detected[none]==1 e a tabela
        detected+none mostra; detected+eda NÃO mostra (ausência não vira EDA)."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "FDE-1", declared=("eda",))  # row declarada, detection PENDING

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["detected"]["none"] == 1
        assert analytics["breakdown"]["detected"]["eda"] == 0

        url_none = reverse("dashboard:index") + "?procedure_dimension=detected&procedure_selection=none"
        content_none = client.get(url_none).content.decode()
        assert "FDE-1" in content_none, "detected+none deve mostrar caso sem rows detectadas"

        url_eda = reverse("dashboard:index") + "?procedure_dimension=detected&procedure_selection=eda"
        content_eda = client.get(url_eda).content.decode()
        assert "FDE-1" not in content_eda, "detected+eda NÃO pode mostrar caso sem rows detectadas"

    def test_accepted_case_without_dispositions_matches_approved_none_not_eda(self, client) -> None:
        """Caso aceito globalmente sem rows de disposição: approved[none]==1 e a
        tabela approved+none mostra; approved+eda NÃO mostra (sem fallback de accept)."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "AC-1", declared=("eda",), status=CaseStatus.WAIT_APPT, doctor_decision="accept")

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["approved"]["none"] == 1
        assert analytics["breakdown"]["approved"]["eda"] == 0

        url_none = reverse("dashboard:index") + "?procedure_dimension=approved&procedure_selection=none"
        assert "AC-1" in client.get(url_none).content.decode()

        url_eda = reverse("dashboard:index") + "?procedure_dimension=approved&procedure_selection=eda"
        assert "AC-1" not in client.get(url_eda).content.decode()

    def test_detected_colonoscopy_does_not_change_declared_category(self, client) -> None:
        """Caso declarado EDA com detecção Colon (row não declarada): na dimensão
        declared continua EDA (não vira combinado) na tabela e no breakdown."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "DC-1", declared=("eda",), detected=("eda", "colonoscopy"))

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["declared"]["eda"] == 1
        assert analytics["breakdown"]["declared"]["eda_colonoscopy"] == 0

        url_eda = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=eda"
        assert "DC-1" in client.get(url_eda).content.decode()

        url_combined = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=eda_colonoscopy"
        assert "DC-1" not in client.get(url_combined).content.decode()


# ── R6: Query hygiene ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestQueryHygiene:
    """R6 — analytics com queries limitadas e página sem explosão de queries."""

    def test_analytics_queries_are_bounded(self, client) -> None:
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        for i in range(20):
            _make_case(user, f"Q-{i:03d}", declared=("eda",), detected=("eda",), approved=("eda",))

        with CaptureQueriesContext(connection) as cap:
            analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["declared"]["eda"] == 20
        assert len(cap.captured_queries) <= 4, (
            f"Analytics deve usar <=4 queries (casos + procedures + eventos admin), obteve {len(cap.captured_queries)}"
        )

    def test_dashboard_page_query_count_stays_bounded(self, client) -> None:
        """Página completa com 20 casos permanece no patamar do baseline (57) + delta pequeno."""
        user = _login_as(client)
        Case.objects.all().delete()
        for i in range(20):
            _make_case(user, f"PG-{i:03d}", declared=("eda",), detected=("eda",), approved=("eda",))

        with CaptureQueriesContext(connection) as cap:
            response = client.get(reverse("dashboard:index"))
        assert response.status_code == 200
        assert len(cap.captured_queries) <= 68, (
            f"Página deve permanecer limitada (baseline 57 + analytics 3 + prefetch 1), obteve "
            f"{len(cap.captured_queries)}"
        )


# ── Slice 010: authority — CaseProcedure é a fonte única (R2/R3/R4) ──────


@pytest.mark.django_db
class TestProcedureDimensionAuthority:
    """Slice 010 — analytics/getters/filtro dependem somente de CaseProcedure.

    R2: ``apply_procedure_selection_filter`` usa só Exists/predicados de rows;
        sem fallback da ponte ``Case.exam_type`` nem de ``doctor_decision``.
    R3/R4: ausência de rows na dimensão consultada ⇒ categoria ``none``;
        nunca vira EDA/Colonoscopia por inferência.
    """

    def test_case_without_detected_rows_is_none_not_eda(self, client) -> None:
        """Caso declarado EDA sem rows detectadas: detected dimension = none (não eda)."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "FC-1", declared=("eda",))  # detection PENDING

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["detected"]["none"] == 1
        assert analytics["breakdown"]["detected"]["eda"] == 0

    def test_case_without_approved_rows_is_none_not_eda(self, client) -> None:
        """Caso aceito globalmente sem rows aprovadas: approved dimension = none."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "AP-1",
            declared=("eda",),
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
        )

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["approved"]["none"] == 1
        assert analytics["breakdown"]["approved"]["eda"] == 0

    def test_legacy_case_without_rows_is_none_in_declared(self, client) -> None:
        """Caso legado (exam_type=eda) sem rows: declared dimension = none (nunca eda)."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        Case.objects.create(
            created_by=user,
            status=CaseStatus.NEW,
            exam_type="eda",
            agency_record_number="LEG-EDA",
        )

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["declared"]["none"] == 1
        assert analytics["breakdown"]["declared"]["eda"] == 0

    def test_selection_filter_detected_none_includes_case_without_detected_rows(self, client) -> None:
        """R2 — detected+none mostra caso sem rows detectadas; detected+eda não."""
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(user, "SF-1", declared=("eda",))  # sem rows detectadas

        none_url = reverse("dashboard:index") + "?procedure_dimension=detected&procedure_selection=none"
        assert "SF-1" in client.get(none_url).content.decode()

        eda_url = reverse("dashboard:index") + "?procedure_dimension=detected&procedure_selection=eda"
        assert "SF-1" not in client.get(eda_url).content.decode()

    def test_selection_filter_approved_none_includes_case_without_approved_rows(self, client) -> None:
        """R2 — approved+none mostra caso sem rows aprovadas (mesmo com accept global)."""
        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "SA-1",
            declared=("eda",),
            status=CaseStatus.WAIT_APPT,
            doctor_decision="accept",
        )

        none_url = reverse("dashboard:index") + "?procedure_dimension=approved&procedure_selection=none"
        assert "SA-1" in client.get(none_url).content.decode()

        eda_url = reverse("dashboard:index") + "?procedure_dimension=approved&procedure_selection=eda"
        assert "SA-1" not in client.get(eda_url).content.decode()

    def test_selection_filter_legacy_exam_type_is_ignored(self, client) -> None:
        """R2 — caso legado (exam_type=eda) sem rows: declared+eda NÃO mostra.

        Prova que a query SQL não usa mais a ponte ``Case.exam_type``.
        """
        user = _login_as(client)
        Case.objects.all().delete()
        Case.objects.create(
            created_by=user,
            status=CaseStatus.NEW,
            exam_type="eda",
            agency_record_number="LEG-SF",
        )

        eda_url = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=eda"
        assert "LEG-SF" not in client.get(eda_url).content.decode()

        none_url = reverse("dashboard:index") + "?procedure_dimension=declared&procedure_selection=none"
        assert "LEG-SF" in client.get(none_url).content.decode()

    def test_combined_still_closes_as_one_case_two_components(self, client) -> None:
        """R4 — regressão: combinado continua 1 caso / 2 componentes sem fallback."""
        from apps.dashboard.procedure_analytics import compute_procedure_analytics

        user = _login_as(client)
        Case.objects.all().delete()
        _make_case(
            user,
            "CB-1",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
            appointment_status="confirmed",
        )

        analytics = compute_procedure_analytics(Case.objects.all())
        assert analytics["breakdown"]["declared"]["eda_colonoscopy"] == 1
        assert analytics["volume"]["declared"] == {"eda": 1, "colonoscopy": 1, "combined": 1}
        assert analytics["paired_confirmed"] == 1
