"""Slice 005 — Filtros CHD por tipo em Pendentes, Processados Hoje e Histórico.

Proves R1–R5:

- R1: contagens por tipo somam exatamente o universo de ``total_notice_count``
  (WAIT_APPT + notices iniciais + issues operacionais); Todos é o default e
  Processados/Histórico não entram no contador de pendentes.
- R2: cards dos três grupos pendentes expõem ``data-exam-type`` persistido +
  badge real; o filtro client-side abrange os três grupos sem remover
  grupos/copy/ações.
- R3: Processados Hoje tem badge e filtro simples por tipo, sem alterar
  ownership, período local ou ciências reconhecidas.
- R4: Histórico é server-side: ``exam_type=all|eda|colonoscopy`` com fallback
  para all, compõe com q, tipo sem q lista os últimos do tipo e os resultados
  mostram badge; botão Limpar zera q/tipo.
- R5: confirmação/negação, ACK de notices/issues, locks e autorização seguem
  intactos; nenhuma ação depende do filtro.

Sem runner JS, o comportamento do filtro client-side é provado por inspeção
estática dos marcadores e pela matriz documentada no relatório do slice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "scheduler" / "queue.html"
QUEUE_CONTENT_HTML = REPO_ROOT / "templates" / "scheduler" / "_queue_content.html"
HISTORICAL_HTML = REPO_ROOT / "templates" / "scheduler" / "historical_search.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "scheduler_queue_filter.js"


@pytest.mark.django_db
class TestSchedulerQueueExamTypeFilters:
    """Markup server-rendered das filas CHD (R1, R2, R3)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str | None = None) -> Any:
        final_username = username or f"{role_name}@schfilter.test"
        user = User.objects.create_user(username=final_username, password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _approve_procedures(self, case: Case, selection: str) -> None:
        """Cria rows aprovadas coerentes (R5) — a fila CHD projeta do aprovado."""
        from apps.cases.models import CaseProcedure, DoctorDisposition

        types = ("eda", "colonoscopy") if selection == "eda_colonoscopy" else (selection,)
        for procedure_type in types:
            CaseProcedure.objects.create(
                case=case,
                procedure_type=procedure_type,
                declared_by_nir=True,
                doctor_disposition=DoctorDisposition.APPROVED,
            )

    def _make_wait_appt(self, nir: Any, *, selection: str, name: str, record: str) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            agency_record_number=record,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": name, "age": 55, "gender": "F"}},
        )
        self._approve_procedures(case, selection)
        return case

    def _make_immediate_notice(self, nir: Any, *, selection: str, name: str, record: str) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number=record,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": name, "age": 60, "gender": "F"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        self._approve_procedures(case, selection)
        return case

    def _make_operational_issue(self, nir: Any, *, selection: str, name: str, record: str) -> Case:
        # Status fora de WAIT_APPT para manter os três grupos disjuntos no
        # teste (caso com issue em WAIT_APPT aparece também na lista pendente,
        # comportamento real do sistema que os contadores seguem fielmente).
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number=record,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            post_schedule_issue_status="opened",
            post_acceptance_issue_context="operational_notice",
            structured_data={"patient": {"name": name, "age": 50, "gender": "M"}},
        )
        self._approve_procedures(case, selection)
        return case

    def _make_processed(self, scheduler_user: Any, nir: Any, *, selection: str, name: str, record: str) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            agency_record_number=record,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            scheduler=scheduler_user,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            structured_data={"patient": {"name": name, "age": 45, "gender": "F"}},
        )
        self._approve_procedures(case, selection)
        return case

    def _make_historical(
        self, nir: Any, *, selection: str, name: str, record: str, patient_name: str | None = None
    ) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.CLEANED,
            agency_record_number=record,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            structured_data={"patient": {"name": patient_name or name, "age": 60, "gender": "F"}},
        )
        self._approve_procedures(case, selection)
        return case

    # ── R1: contagens pendentes por tipo fecham com o total ───────────

    def test_pending_type_counts_close_with_total(self, client) -> None:
        """Contadores por tipo somam o mesmo universo do badge primário."""
        nir = self._login_as(client, "nir")
        self._make_wait_appt(nir, selection="eda", name="EDA Wait", record="W-EDA")
        self._make_wait_appt(nir, selection="colonoscopy", name="COL Wait", record="W-COL")
        self._make_immediate_notice(nir, selection="eda", name="EDA Notice", record="N-EDA")
        self._make_immediate_notice(nir, selection="colonoscopy", name="COL Notice", record="N-COL")
        self._make_operational_issue(nir, selection="eda", name="EDA Issue", record="I-EDA")
        self._make_operational_issue(nir, selection="colonoscopy", name="COL Issue", record="I-COL")
        self._login_as(client, "scheduler")
        response = client.get("/scheduler/")
        assert response.status_code == 200
        content = response.content.decode()
        # Todos default com total == soma EDA + colonoscopia == badge primário.
        assert 'data-exam-type-count="all">6<' in content
        assert 'data-exam-type-count="eda">3<' in content
        assert 'data-exam-type-count="colonoscopy">3<' in content
        assert 'data-count="6"' in content

    def test_pending_count_excludes_processed(self, client) -> None:
        """Processados de hoje não entram no contador de pendentes por tipo."""
        scheduler_user = self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schfilter-proc@test.com", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_wait_appt(nir, selection="eda", name="EDA Wait", record="W-EDA")
        self._make_processed(scheduler_user, nir, selection="colonoscopy", name="COL Proc", record="P-COL")
        content = client.get("/scheduler/").content.decode()
        # Pendentes: 1 EDA e 0 colonoscopia — o processado colonoscopia não conta.
        assert 'data-exam-type-count="all">1<' in content
        assert 'data-exam-type-count="eda">1<' in content
        assert 'data-exam-type-count="colonoscopy">0<' in content

    # ── R2: controle acessível com Todos default ──────────────────────

    def test_pending_has_accessible_type_filter_todos_default(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_wait_appt(nir, selection="eda", name="A", record="1001")
        self._make_wait_appt(nir, selection="colonoscopy", name="B", record="1002")
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        # Controle secundário dentro de Pendentes (não substitui tabs primárias).
        assert 'id="scheduler-queue-type-filter"' in content
        assert "data-scheduler-exam-filter" in content
        assert 'value="all" checked' in content
        assert 'value="eda"' in content
        assert 'value="colonoscopy"' in content
        # Abas primárias preservadas.
        assert "?tab=pending" in content
        assert "?tab=processed" in content

    # ── R2: filtro cobre os três grupos pendentes ─────────────────────

    def test_pending_filter_covers_three_groups(self, client) -> None:
        """Cards de WAIT_APPT, notices e issues participam do filtro por tipo."""
        nir = self._login_as(client, "nir")
        self._make_wait_appt(nir, selection="eda", name="EDA Wait", record="W-EDA")
        self._make_wait_appt(nir, selection="colonoscopy", name="COL Wait", record="W-COL")
        self._make_immediate_notice(nir, selection="eda", name="EDA Notice", record="N-EDA")
        self._make_immediate_notice(nir, selection="colonoscopy", name="COL Notice", record="N-COL")
        self._make_operational_issue(nir, selection="eda", name="EDA Issue", record="I-EDA")
        self._make_operational_issue(nir, selection="colonoscopy", name="COL Issue", record="I-COL")
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        # 3 grupos × 2 tipos = 6 cards no escopo do filtro client-side.
        assert content.count("data-scheduler-queue-card") == 6
        assert content.count('data-exam-type="colonoscopy"') == 3
        assert content.count('data-exam-type="eda"') == 3
        # Nenhum grupo/copy/ação é removido.
        assert "Confirmar ciência" in content
        assert "Não abrir agendamento" in content
        assert "Agendar" in content

    # ── R2: cards expõem tipo persistido + badge real ────────────────

    def test_pending_cards_expose_exam_type_and_badge(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_wait_appt(nir, selection="eda", name="Joao EDA", record="1001")
        self._make_wait_appt(nir, selection="colonoscopy", name="Maria Colon", record="1002")
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert 'data-exam-type="eda"' in content
        assert 'data-exam-type="colonoscopy"' in content
        assert ">EDA</span>" in content
        assert ">Colonoscopia</span>" in content

    # ── R3: Processados Hoje badge + filtro ───────────────────────────

    def test_processed_has_type_filter_and_badges(self, client) -> None:
        scheduler_user = self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schfilter-proc2@test.com", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_processed(scheduler_user, nir, selection="eda", name="A EDA", record="P-EDA")
        self._make_processed(scheduler_user, nir, selection="colonoscopy", name="B COL", record="P-COL")
        response = client.get("/scheduler/?tab=processed")
        assert response.status_code == 200
        content = response.content.decode()
        # Filtro simples por tipo com contadores reais.
        assert 'id="scheduler-processed-type-filter"' in content
        assert "data-scheduler-exam-filter" in content
        assert 'value="all" checked' in content
        assert 'value="colonoscopy"' in content
        assert 'data-exam-type-count="all">2<' in content
        assert 'data-exam-type-count="eda">1<' in content
        assert 'data-exam-type-count="colonoscopy">1<' in content
        # Cards expõem tipo persistido e badge real.
        assert 'data-exam-type="eda"' in content
        assert 'data-exam-type="colonoscopy"' in content
        assert ">EDA</span>" in content
        assert ">Colonoscopia</span>" in content

    # ── R5: ACK e acesso preservados ──────────────────────────────────

    def test_immediate_ack_still_works_for_colonoscopy(self, client) -> None:
        """Confirmar ciência continua operável para casos colonoscopia."""
        self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schfilter-ack@test.com", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        case = self._make_immediate_notice(nir, selection="colonoscopy", name="Col Ack", record="A-COL")
        response = client.post(f"/scheduler/{case.case_id}/immediate-ack/")
        assert response.status_code == 302
        content = client.get("/scheduler/").content.decode()
        assert "Col Ack" not in content  # notice saiu da fila após ACK

    def test_scheduler_access_preserved(self, client) -> None:
        """Acesso scheduler preservado; outros papéis continuam bloqueados."""
        nir_user = User.objects.create_user(username="nir-schfilter-access@test.com")
        nir_user.roles.add(self._create_role("nir"))
        client.force_login(nir_user)
        session = client.session
        session["active_role"] = "nir"
        session.save()
        assert client.get("/scheduler/").status_code == 302

    def test_combined_wait_appt_badge_and_count_from_rows(self, client) -> None:
        """011-B: fluxo canônico CHD construído apenas com rows — combinado
        aprovado projeta badge casado e conta uma vez (sem coluna)."""
        nir = self._login_as(client, "nir")
        self._make_wait_appt(nir, selection="eda_colonoscopy", name="Comb Rows", record="W-COMB")
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert "EDA + Colonoscopia · Agendamento casado" in content
        assert 'data-exam-type-count="eda_colonoscopy">1<' in content
        assert 'data-approved-selection="eda_colonoscopy"' in content
        assert content.count("data-scheduler-queue-card") == 1


@pytest.mark.django_db
class TestSchedulerHistoricalExamType:
    """Busca histórica server-side por tipo (R4)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str, username: str | None = None) -> Any:
        final_username = username or f"{role_name}@schhist.test"
        user = User.objects.create_user(username=final_username, password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _approve_procedures(self, case: Case, selection: str) -> None:
        """Cria rows aprovadas coerentes (R5) — o histórico filtra pelo aprovado."""
        from apps.cases.models import CaseProcedure, DoctorDisposition

        types = ("eda", "colonoscopy") if selection == "eda_colonoscopy" else (selection,)
        for procedure_type in types:
            CaseProcedure.objects.create(
                case=case,
                procedure_type=procedure_type,
                declared_by_nir=True,
                doctor_disposition=DoctorDisposition.APPROVED,
            )

    def _make_historical(
        self, nir: Any, *, selection: str, name: str, record: str, patient_name: str | None = None
    ) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.CLEANED,
            agency_record_number=record,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            structured_data={"patient": {"name": patient_name or name, "age": 60, "gender": "F"}},
        )
        self._approve_procedures(case, selection)
        return case

    def test_historical_type_without_q_returns_latest_of_type(self, client) -> None:
        """Tipo específico sem termo lista os últimos casos daquele tipo."""
        self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schhist-1@test.com")
        nir.roles.add(self._create_role("nir"))
        for i in range(3):
            self._make_historical(nir, selection="colonoscopy", name=f"COL {i}", record=f"HC-{i}")
            self._make_historical(nir, selection="eda", name=f"EDA {i}", record=f"HE-{i}")
        response = client.get("/scheduler/historical/?exam_type=colonoscopy")
        assert response.status_code == 200
        content = response.content.decode()
        assert "HC-0" in content and "HC-1" in content and "HC-2" in content
        assert "HE-0" not in content and "HE-1" not in content and "HE-2" not in content

    def test_historical_q_and_type_intersect(self, client) -> None:
        """Termo e tipo são compostos com AND server-side."""
        self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schhist-2@test.com")
        nir.roles.add(self._create_role("nir"))
        self._make_historical(
            nir, selection="colonoscopy", name="Maria Colon", record="H-COL-1", patient_name="Maria Colon"
        )
        self._make_historical(
            nir, selection="colonoscopy", name="Joao Colon", record="H-COL-2", patient_name="Joao Colon"
        )
        self._make_historical(nir, selection="eda", name="Maria EDA", record="H-EDA-1", patient_name="Maria EDA")
        response = client.get("/scheduler/historical/?exam_type=colonoscopy&q=Maria")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Maria Colon" in content
        assert "Joao Colon" not in content
        assert "Maria EDA" not in content

    def test_historical_invalid_type_falls_back_to_all(self, client) -> None:
        """Tipo inválido cai para all e compõe com q sobre os dois tipos."""
        self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schhist-3@test.com")
        nir.roles.add(self._create_role("nir"))
        self._make_historical(nir, selection="eda", name="Maria EDA", record="H-EDA-2")
        self._make_historical(nir, selection="colonoscopy", name="Maria COL", record="H-COL-3")
        response = client.get("/scheduler/historical/?exam_type=bogus&q=Maria")
        assert response.status_code == 200
        content = response.content.decode()
        assert "H-EDA-2" in content
        assert "H-COL-3" in content

    def test_historical_results_show_exam_type_badge(self, client) -> None:
        """Resultados do histórico mostram badge real do tipo persistido."""
        self._login_as(client, "scheduler")
        nir = User.objects.create_user(username="nir-schhist-4@test.com")
        nir.roles.add(self._create_role("nir"))
        self._make_historical(nir, selection="colonoscopy", name="Col Badge", record="H-BADGE")
        response = client.get("/scheduler/historical/?exam_type=colonoscopy")
        assert response.status_code == 200
        content = response.content.decode()
        assert ">Colonoscopia</span>" in content

    def test_historical_form_has_type_select_and_limpar(self, client) -> None:
        """Formulário ganha seletor de tipo e botão Limpar que zera q/tipo."""
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/historical/").content.decode()
        assert 'name="exam_type"' in content
        assert 'value="all"' in content
        assert 'value="eda"' in content
        assert 'value="colonoscopy"' in content
        assert "Limpar" in content


class TestSchedulerQueueFilterStatic:
    """Inspeção estática do filtro client-side (R2/R3) — sem runner JS.

    Matriz manual documentada no relatório: Todos mostra 6; Colonoscopia mantém
    apenas cards colonoscopia dos três grupos; EDA oculta colonoscopias;
    afterSwap reaplica; sem resultado é claro.
    """

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_js_filters_by_type_across_all_pending_groups(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert "data-scheduler-exam-filter" in js
        assert "getSelectedType" in js
        assert "data-exam-type" in js
        assert "data-scheduler-queue-card" in js
        assert "data-scheduler-processed-card" in js
        assert 'addEventListener("change"' in js

    def test_js_reaplies_after_polling(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert "htmx:afterSwap" in js
        assert "scheduler-queue-content" in js

    def test_js_status_uses_casos_with_scope(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert "casos" in js
        assert "Mostrando" in js
        assert "scopeLabel" in js

    def test_html_has_no_results_and_persisted_type_attribute(self) -> None:
        html = self._read(QUEUE_HTML)
        assert "Nenhum caso pendente para o filtro selecionado." in html
        content_html = self._read(QUEUE_CONTENT_HTML)
        assert 'data-exam-type="{{ c.exam_type }}"' in content_html

    def test_historical_html_has_type_select_limpar_and_badge(self) -> None:
        html = self._read(HISTORICAL_HTML)
        assert 'name="exam_type"' in html
        assert "Limpar" in html
        assert "exam_type_label" in html
