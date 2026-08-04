"""Slice 004 — Filtros médicos por tipo com busca preservada.

Proves R1–R5:

- R1: Pendentes tem controle secundário acessível `Todos | EDA | Colonoscopia`
  com contadores reais; Todos é o default; tabs primárias e contador principal
  permanecem totais.
- R2: cards pending/decided expõem `data-exam-type` a partir do campo
  persistido e mostram badge real de tipo (nunca inferido de texto/JSON).
- R3: `doctor_queue_filter.js` compõe tipo + termo num único filtro,
  preservando normalização, limiar de 3 letras e busca numérica.
- R4: Limpar/Esc/input vazio limpam o termo imediatamente preservando o tipo;
  `htmx:afterSwap` reaplica ambos; status usa "casos" e informa
  visível/total/escopo; sem resultado é claro.
- R5: Decididos Hoje tem badge por card e filtro client-side simples sem busca.

Sem runner JS, a prova comportamental do script é inspeção estática dos
marcadores e da matriz de casos documentada no relatório do slice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseStatus

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "doctor" / "queue.html"
QUEUE_CONTENT_HTML = REPO_ROOT / "templates" / "doctor" / "_queue_content.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "doctor_queue_filter.js"


@pytest.mark.django_db
class TestDoctorQueueExamTypeFilters:
    """Markup server-rendered das filas médicas (R1, R2, R5)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> Any:
        user = User.objects.create_user(username=f"{role_name}@filters.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_pending(self, nir: Any, *, exam_type: str, name: str, record: str) -> Case:
        return Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            exam_type=exam_type,
            agency_record_number=record,
            structured_data={"patient": {"name": name, "age": 50, "gender": "F"}},
        )

    def _make_decided(self, doctor: Any, nir: Any, *, exam_type: str, name: str) -> Case:
        return Case.objects.create(
            created_by=nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            exam_type=exam_type,
            structured_data={"patient": {"name": name, "age": 60, "gender": "F"}},
        )

    # ── R1 ───────────────────────────────────────────────────────────

    def test_pending_has_accessible_type_filter_with_todos_default(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_pending(nir, exam_type="eda", name="Joao EDA", record="1001")
        self._make_pending(nir, exam_type="colonoscopy", name="Maria Colon", record="1002")
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Controle secundário dentro de Pendentes (não substitui tabs primárias).
        assert 'id="doctor-queue-type-filter"' in content
        # Radios acessíveis Todos | EDA | Colonoscopia, Todos default.
        assert "data-doctor-exam-filter" in content
        assert 'value="all" checked' in content
        assert 'value="eda"' in content
        assert 'value="colonoscopy"' in content
        # Contadores reais por opção (preenchidos pelo JS a partir do tipo persistido).
        assert 'data-exam-type-count="all"' in content
        assert 'data-exam-type-count="eda"' in content
        assert 'data-exam-type-count="colonoscopy"' in content
        # Tabs primárias preservadas e busca ainda presente.
        assert "/doctor/?tab=pending" in content
        assert "/doctor/?tab=decided" in content
        assert "data-doctor-queue-search" in content

    def test_pending_nav_count_remains_total(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_pending(nir, exam_type="eda", name="A", record="1001")
        self._make_pending(nir, exam_type="colonoscopy", name="B", record="1002")
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        content = response.content.decode()
        # O badge primário de Pendentes continua total (2), não dividido por tipo.
        assert 'data-count="2"' in content

    # ── R5 ───────────────────────────────────────────────────────────

    def test_decided_has_type_filter_without_search(self, client) -> None:
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-decided@filters.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_decided(doctor, nir, exam_type="eda", name="A")
        self._make_decided(doctor, nir, exam_type="colonoscopy", name="B")
        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        # Filtro simples por tipo, sem busca.
        assert 'id="doctor-decided-type-filter"' in content
        assert "data-doctor-exam-filter" in content
        assert 'value="all" checked' in content
        assert 'value="colonoscopy"' in content
        assert "data-doctor-queue-search" not in content

    # ── R2 ───────────────────────────────────────────────────────────

    def test_pending_cards_expose_persisted_exam_type_and_badge(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_pending(nir, exam_type="eda", name="Joao EDA", record="1001")
        self._make_pending(nir, exam_type="colonoscopy", name="Maria Colon", record="1002")
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        content = response.content.decode()
        # Atributo de dados a partir do campo persistido + badge real de tipo.
        assert 'data-exam-type="eda"' in content
        assert 'data-exam-type="colonoscopy"' in content
        assert ">EDA</span>" in content
        assert ">Colonoscopia</span>" in content

    def test_decided_cards_expose_persisted_exam_type_and_badge(self, client) -> None:
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-decided2@filters.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_decided(doctor, nir, exam_type="eda", name="A")
        self._make_decided(doctor, nir, exam_type="colonoscopy", name="B")
        response = client.get("/doctor/?tab=decided")
        content = response.content.decode()
        assert "data-doctor-queue-card" in content
        assert 'data-exam-type="eda"' in content
        assert 'data-exam-type="colonoscopy"' in content
        assert ">EDA</span>" in content
        assert ">Colonoscopia</span>" in content

    # ── Regressões de contrato (links, polling, tabs) ─────────────────

    def test_links_polling_and_tabs_preserved(self, client) -> None:
        nir = self._login_as(client, "nir")
        c1 = self._make_pending(nir, exam_type="eda", name="Joao", record="1001")
        c2 = self._make_pending(nir, exam_type="colonoscopy", name="Maria", record="1002")
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        content = response.content.decode()
        assert f"/doctor/{c1.case_id}/" in content
        assert f"/doctor/{c2.case_id}/" in content
        assert 'hx-get="/doctor/partials/queue/?tab=pending"' in content


class TestDoctorQueueFilterStatic:
    """Inspeção estática do filtro composto (R3, R4) — sem runner JS.

    A matriz de casos manual (Todos+joao, Colonoscopia+joao, troca mantendo
    termo, Limpar mantendo tipo, Esc, no-results, afterSwap) está documentada
    no relatório do slice.
    """

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_js_composes_type_and_term(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        # Um único filtro composto por tipo + termo sobre os cards.
        assert "data-doctor-exam-filter" in js
        assert "getSelectedType" in js
        assert "data-exam-type" in js
        assert 'addEventListener("change"' in js

    def test_js_preserves_term_and_type_on_clear_escape_and_swap(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert "clearFilter" in js
        assert "Escape" in js
        assert "htmx:afterSwap" in js
        # Limpar mexe apenas no termo; o estado do tipo (radios) fica intacto.
        assert 'searchInput.value = ""' in js

    def test_js_status_uses_casos_with_scope(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert "casos" in js
        assert "scopeLabel" in js

    def test_html_clear_no_results_and_persisted_type_attribute(self) -> None:
        html = self._read(QUEUE_HTML)
        assert "Limpar" in html
        assert "Nenhum caso encontrado para os filtros selecionados." in html
        content_html = self._read(QUEUE_CONTENT_HTML)
        assert 'data-exam-type="{{ c.exam_type }}"' in content_html
