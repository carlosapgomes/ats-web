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

Slice 005 — Jornada médica nas filas especializadas (R1–R5):

- R1: Pendentes filtra por DETECTADO com o universo do catálogo (Todos, EDA,
  Colonoscopia, EDA + Colonoscopia, Ecoendoscopia, CPRE) e cards usam a
  dimensão detectada.
- R2: Decididos Hoje filtra por AUTORIZADO, preserva `Nenhum autorizado` e o
  badge principal é o conjunto aprovado.
- R3: busca, polling e seleção continuam compostos (filtro fora do alvo do
  swap HTMX).
- R4: cards especializados usam badge singleton e mostram a transformação
  detectado → autorizado quando os conjuntos divergem.
- R5: a seleção vem do atributo projetado no card — sem inferência por texto
  de badge e sem lógica binária de "outro tipo".
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseProcedure, CaseStatus
from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES, selection_key

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "doctor" / "queue.html"
QUEUE_CONTENT_HTML = REPO_ROOT / "templates" / "doctor" / "_queue_content.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "doctor_queue_filter.js"
DECISION_HTML = REPO_ROOT / "templates" / "doctor" / "decision.html"

# Universo de filtros do catálogo (design D13): `all` + cada singleton +
# o combinado exato EDA + Colonoscopia.
CATALOG_FILTER_VALUES = {"all", selection_key(("eda", "colonoscopy"))} | {
    selection_key((procedure_type,)) for procedure_type in SUPPORTED_PROCEDURE_TYPES
}

# Cutover 4.0: a fila médica ainda publica SOMENTE as opções anteriores ao
# catálogo ampliado. A expansão de filtros/badges para as dez identidades é do
# Slice 008 (design D12), que deve voltar a exigir igualdade com
# ``CATALOG_FILTER_VALUES``. Enquanto isso, este teste fixa o universo
# publicado para provar que o Slice 001 não alterou a fila.
PUBLISHED_QUEUE_FILTER_VALUES = {"all", "eda", "colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre"}


def _radio_values(html: str, name: str) -> list[str]:
    """Valores dos radios com `name` na ordem em que foram renderizados."""
    return re.findall(rf'name="{name}"[^>]*?value="([^"]+)"', html)


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

    def _make_pending(
        self,
        nir: Any,
        *,
        declared: tuple[str, ...] = (),
        detected: tuple[str, ...] = (),
        name: str,
        record: str,
    ) -> Case:
        # Slice 011-A: as rows vêm EXCLUSIVAMENTE dos conjuntos explícitos
        # ``declared``/``detected`` — nunca inferidas de campo/status/decisão.
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number=record,
            structured_data={"patient": {"name": name, "age": 50, "gender": "F"}},
        )
        for procedure_type in set(declared) | set(detected):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=procedure_type,
                declared_by_nir=procedure_type in declared,
                detection_status="detected" if procedure_type in detected else "not_detected",
            )
        return case

    def _make_decided(
        self,
        doctor: Any,
        nir: Any,
        *,
        declared: tuple[str, ...] = (),
        detected: tuple[str, ...] = (),
        approved: tuple[str, ...] = (),
        denied: tuple[str, ...] = (),
        name: str,
    ) -> Case:
        # Slice 011-A: as rows vêm da união explícita de ``declared``/
        # ``detected``/``approved``/``denied``. ``doctor_decision`` é setup
        # fixo, não fonte de inferência.
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            structured_data={"patient": {"name": name, "age": 60, "gender": "F"}},
        )
        for procedure_type in set(declared) | set(detected) | set(approved) | set(denied):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=procedure_type,
                declared_by_nir=procedure_type in declared,
                detection_status="detected" if procedure_type in detected else "not_detected",
                doctor_disposition=(
                    "approved" if procedure_type in approved else "denied" if procedure_type in denied else "pending"
                ),
            )
        return case

    # ── R1 ───────────────────────────────────────────────────────────

    def test_pending_has_accessible_type_filter_with_todos_default(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_pending(nir, declared=("eda",), detected=("eda",), name="Joao EDA", record="1001")
        self._make_pending(
            nir,
            declared=("colonoscopy",),
            detected=("colonoscopy",),
            name="Maria Colon",
            record="1002",
        )
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
        self._make_pending(nir, declared=("eda",), detected=("eda",), name="A", record="1001")
        self._make_pending(
            nir,
            declared=("colonoscopy",),
            detected=("colonoscopy",),
            name="B",
            record="1002",
        )
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
        self._make_decided(doctor, nir, declared=("eda",), detected=("eda",), approved=("eda",), name="A")
        self._make_decided(
            doctor,
            nir,
            declared=("colonoscopy",),
            detected=("colonoscopy",),
            approved=("colonoscopy",),
            name="B",
        )
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
        self._make_pending(nir, declared=("eda",), detected=("eda",), name="Joao EDA", record="1001")
        self._make_pending(
            nir,
            declared=("colonoscopy",),
            detected=("colonoscopy",),
            name="Maria Colon",
            record="1002",
        )
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
        self._make_decided(doctor, nir, declared=("eda",), detected=("eda",), approved=("eda",), name="A")
        self._make_decided(
            doctor,
            nir,
            declared=("colonoscopy",),
            detected=("colonoscopy",),
            approved=("colonoscopy",),
            name="B",
        )
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
        c1 = self._make_pending(nir, declared=("eda",), detected=("eda",), name="Joao", record="1001")
        c2 = self._make_pending(
            nir,
            declared=("colonoscopy",),
            detected=("colonoscopy",),
            name="Maria",
            record="1002",
        )
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        content = response.content.decode()
        assert f"/doctor/{c1.case_id}/" in content
        assert f"/doctor/{c2.case_id}/" in content
        assert 'hx-get="/doctor/partials/queue/?tab=pending"' in content

    # ── Slice 005 · R1: universo detectado inclui os tipos especializados ──

    def test_pending_filter_universe_is_the_catalog(self, client) -> None:
        """R1: Pendentes oferece Todos, EDA, Colonoscopia, combinado, Eco e CPRE.

        O universo publicado coincide com as opções vigentes e `none` não
        pertence a este universo. A expansão para as dez identidades do
        catálogo (igualdade derivada) é do Slice 008 (design D12).
        """
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        values = _radio_values(content, "doctor-queue-exam-type")
        assert values == ["all", "eda", "colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre"]
        assert set(values) == PUBLISHED_QUEUE_FILTER_VALUES
        assert 'id="doctor-queue-type-filter"' in content
        assert 'data-exam-type-count="echoendoscopy"' in content
        assert 'data-exam-type-count="cpre"' in content
        assert "Ecoendoscopia" in content
        assert "CPRE" in content

    def test_decided_filter_universe_is_authorized_catalog_with_none(self, client) -> None:
        """R2: Decididos Hoje filtra por autorizado e preserva Nenhum autorizado."""
        self._login_as(client, "doctor")
        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        values = _radio_values(content, "doctor-decided-exam-type")
        assert values == ["all", "eda", "colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre", "none"]
        assert set(values) == PUBLISHED_QUEUE_FILTER_VALUES | {"none"}
        assert 'value="all" checked' in content
        assert "Nenhum autorizado" in content
        assert 'id="doctor-decided-type-filter"' in content

    def test_pending_specialized_filter_keeps_search_and_polling(self, client) -> None:
        """R3: o filtro especializado convive com busca e polling (sem perder params)."""
        self._login_as(client, "doctor")
        content = client.get("/doctor/?tab=pending").content.decode()
        assert 'value="echoendoscopy"' in content
        assert 'value="cpre"' in content
        assert "data-doctor-queue-search" in content
        # Filtro e busca ficam FORA do alvo do swap HTMX, então o polling não
        # perde termo nem seleção.
        assert 'hx-get="/doctor/partials/queue/?tab=pending"' in content
        assert 'hx-trigger="every 20s"' in content

    # ── Slice 005 · R4: badge singleton da dimensão correta por aba ──────

    def test_pending_specialized_cards_use_detected_dimension(self, client) -> None:
        """R1/R4: card Pendente projeta o DETECTADO (badge singleton), não a declaração."""
        nir = self._login_as(client, "nir")
        self._make_pending(
            nir,
            declared=("eda",),
            detected=("echoendoscopy",),
            name="Eco Pend",
            record="2001",
        )
        self._make_pending(
            nir,
            declared=("eda", "colonoscopy"),
            detected=("cpre",),
            name="Cpre Pend",
            record="2002",
        )
        self._login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        assert 'data-proc-selection="echoendoscopy"' in content
        assert 'data-proc-selection="cpre"' in content
        assert 'data-exam-type="echoendoscopy"' in content
        assert 'data-exam-type="cpre"' in content
        assert ">Ecoendoscopia</span>" in content
        assert ">CPRE</span>" in content

    def test_pending_combined_card_uses_exact_pair_key(self, client) -> None:
        """R1: EDA + Colonoscopia preserva a semântica exata do conjunto casado."""
        nir = self._login_as(client, "nir")
        self._make_pending(
            nir,
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            name="Combinado Pend",
            record="3001",
        )
        self._login_as(client, "doctor")
        content = client.get("/doctor/").content.decode()
        assert 'data-proc-selection="eda_colonoscopy"' in content
        assert "EDA + Colonoscopia" in content

    def test_decided_specialized_cards_show_detected_to_approved(self, client) -> None:
        """R4: badge principal é o autorizado e a transformação detectado→autorizado aparece."""
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-slice5@filters.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_decided(
            doctor,
            nir,
            declared=("eda",),
            detected=("eda",),
            approved=("cpre",),
            name="Troca CPRE",
        )
        self._make_decided(
            doctor,
            nir,
            declared=("eda",),
            detected=("eda",),
            approved=("echoendoscopy",),
            name="Troca Eco",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        # Badge principal = conjunto autorizado (singleton especializado).
        assert 'data-proc-selection="cpre"' in content
        assert ">CPRE</span>" in content
        assert "Detectado: EDA · Autorizado: CPRE" in content
        assert 'data-proc-selection="echoendoscopy"' in content
        assert ">Ecoendoscopia</span>" in content
        assert "Detectado: EDA · Autorizado: Ecoendoscopia" in content
        # O badge principal não é mais o detectado.
        assert ">EDA</span>" not in content

    def test_decided_combined_partial_approval_keeps_transformation(self, client) -> None:
        """R4: combinado detectado autorizado só como EDA expõe a transformação."""
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-slice5b@filters.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_decided(
            doctor,
            nir,
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda",),
            denied=("colonoscopy",),
            name="Combinado Parcial",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert 'data-proc-selection="eda"' in content
        assert ">EDA</span>" in content
        assert "Detectado: EDA + Colonoscopia · Autorizado: EDA" in content

    def test_decided_specialized_without_divergence_has_no_transformation(self, client) -> None:
        """R4: sem divergência não há texto de transformação (badge principal basta)."""
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-slice5c@filters.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_decided(
            doctor,
            nir,
            declared=("echoendoscopy",),
            detected=("echoendoscopy",),
            approved=("echoendoscopy",),
            name="Eco Mantida",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert 'data-proc-selection="echoendoscopy"' in content
        assert ">Ecoendoscopia</span>" in content
        assert "Autorizado:" not in content

    def test_decided_denied_specialized_card_stays_nenhum_autorizado(self, client) -> None:
        """R2: caso negado projeta `none`/Nenhum autorizado (sem cair na ponte)."""
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-slice5d@filters.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        self._make_decided(
            doctor,
            nir,
            declared=("cpre",),
            detected=("cpre",),
            denied=("cpre",),
            name="Cpre Negada",
        )
        content = client.get("/doctor/?tab=decided").content.decode()
        assert 'data-proc-selection="none"' in content
        assert "Nenhum autorizado" in content


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
        # Atributo projetado no contexto do card (selection key da dimensão),
        # nunca leitura de campo do ``Case``.
        assert 'data-exam-type="{{ c.exam_type }}"' in content_html

    def test_html_projects_both_dimensions_and_transformation(self) -> None:
        """R4/R5: cards consomem as duas dimensões projetadas, sem tipo hardcoded."""
        content_html = self._read(QUEUE_CONTENT_HTML)
        # Pendentes = detectado; Decididos Hoje = autorizado (D12).
        assert 'data-proc-selection="{{ c.detected_selection_key }}"' in content_html
        assert 'data-proc-selection="{{ c.approved_selection_key }}"' in content_html
        assert "{{ c.detected_label }}" in content_html
        assert "{{ c.approved_label }}" in content_html
        # Transformação textual vem pronta do contexto (sem ramo por tipo).
        assert "{{ c.transformation_detected }}" in content_html
        assert "{{ c.transformation_approved }}" in content_html
        # Nenhum label de tipo é fixado no template (sem lógica binária).
        for hardcoded in ("Ecoendoscopia", "CPRE", "EDA", "Colonoscopia"):
            assert hardcoded not in content_html

    def test_js_counts_and_scope_cover_specialized_catalog(self) -> None:
        """R1/R2: contadores e rótulo de escopo acompanham o catálogo (D13)."""
        js = self._read(QUEUE_FILTER_JS)
        counts = re.search(r"var counts = \{([^}]*)\}", js)
        assert counts is not None, "objeto de contadores ausente no JS"
        counts_keys = counts.group(1)
        for key in ("all", "eda", "colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre", "none"):
            assert f"{key}:" in counts_keys, f"contador ausente: {key}"
        assert 'if (type === "echoendoscopy") return "Ecoendoscopia";' in js
        assert 'if (type === "cpre") return "CPRE";' in js
        assert 'if (type === "none") return "Nenhum autorizado";' in js

    def test_js_has_no_text_inference_nor_binary_other_type(self) -> None:
        """R5: seleção vem exclusivamente do atributo projetado (nunca do texto)."""
        js = self._read(QUEUE_FILTER_JS)
        # Fonte da verdade: atributo projetado no card.
        assert 'card.getAttribute("data-proc-selection")' in js
        # Sem leitura de texto/HTML de badge para inferir tipo.
        assert ".badge" not in js
        assert "exam-type-badge" not in js
        assert "innerHTML" not in js
        # Sem fallback binário "outro tipo" entre EDA e Colonoscopia.
        assert "outro tipo" not in js
        assert '"eda" ? "colonoscopy"' not in js
        assert '"colonoscopy" : "eda"' not in js


# ── Slice 009-A (R1): autoridade da projeção nos cards médicos ────────────


@pytest.mark.django_db
class TestDoctorQueueProcedureAuthority:
    """R1: os cards médicos usam getters estritos (fonte única: rows).

    Um caso sem rows nunca projeta EDA/Colonoscopia; rows detectadas definem a
    seleção do card. A projeção vem somente das rows (Pendentes=detected,
    Decididos=autorizado).
    """

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> Any:
        user = User.objects.create_user(username=f"{role_name}@auth9a.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def test_pending_without_rows_is_never_colonoscopy(self, client) -> None:
        """WAIT_DOCTOR sem rows → projeção none/neutra."""
        nir = self._login_as(client, "nir")
        # Caso sem nenhuma row.
        Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="NO-ROWS-PEND",
            structured_data={"patient": {"name": "Sem Rows Pend", "age": 50, "gender": "F"}},
        )
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Projeção detectada vazia/none; a ponte NÃO participa do card.
        assert 'data-proc-selection="none"' in content
        assert 'data-exam-type="colonoscopy"' not in content
        assert ">Colonoscopia</span>" not in content

    def test_decided_without_approved_rows_is_never_eda(self, client) -> None:
        """Decididos Hoje sem approved rows → none/Nenhum autorizado."""
        doctor = self._login_as(client, "doctor")
        nir = User.objects.create_user(username="nir-dec9a@auth9a.test", password="testpass123")
        nir.roles.add(self._create_role("nir"))
        # Caso aceito sem rows aprovadas.
        Case.objects.create(
            created_by=nir,
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            agency_record_number="NO-APPR-DEC",
            structured_data={"patient": {"name": "Sem Approved", "age": 60, "gender": "F"}},
        )
        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-proc-selection="none"' in content
        assert 'data-exam-type="eda"' not in content
        assert "Nenhum autorizado" in content

    def test_pending_detected_rows_define_card_selection(self, client) -> None:
        """Rows detectadas definem a seleção do card médico."""
        nir = self._login_as(client, "nir")
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ROWS-OPP-PEND",
            structured_data={"patient": {"name": "Rows Opp", "age": 50, "gender": "F"}},
        )
        CaseProcedure.objects.create(
            case=case,
            procedure_type="eda",
            declared_by_nir=True,
            detection_status="detected",
        )
        self._login_as(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        # Card mostra o detectado (EDA), via projeção das rows.
        assert 'data-proc-selection="eda"' in content
        assert 'data-exam-type="colonoscopy"' not in content
        assert ">EDA</span>" in content


# ── Slice 009-A (R2): a tela de decisão não lê a coluna ───────────────────


class TestDoctorDecisionTemplateNoColumnReader:
    """R2: ``decision.html`` não acessa ``case.exam_type``/``get_exam_type_display``;
    o badge consome contexto projetado da dimensão detectada (strict)."""

    def test_decision_html_has_no_case_exam_type_access(self) -> None:
        html = DECISION_HTML.read_text(encoding="utf-8")
        assert "case.exam_type" not in html
        assert "case.get_exam_type_display" not in html
        # O badge usa as variáveis de contexto projetadas pela view.
        assert "exam-type-{{ exam_type" in html
        assert "{{ exam_type_label }}" in html


@pytest.mark.django_db
class TestDoctorDecisionProjectionAuthority:
    """R2: a view projeta a dimensão detectada em modo estrito; ausência/ambiguidade
    renderiza label neutro e classe segura, nunca default EDA/Colonoscopia da ponte."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str) -> Any:
        user = User.objects.create_user(username=f"{role_name}@dec9a.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def test_decision_page_without_rows_is_neutral(self, client) -> None:
        """Decisão sem rows → badge neutro, nunca colonoscopia."""
        nir = self._login_as(client, "nir")
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="NO-ROWS-DEC",
            structured_data={"patient": {"name": "Sem Rows Decisão", "age": 50, "gender": "F"}},
        )
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Badge projetado neutro.
        assert "exam-type-colonoscopy" not in content
        assert "Não identificado" in content

    def test_decision_page_detected_rows_define_badge(self, client) -> None:
        """Rows detectadas definem o badge da tela de decisão."""
        nir = self._login_as(client, "nir")
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="ROWS-OPP-DEC",
            structured_data={"patient": {"name": "Rows Opp Dec", "age": 50, "gender": "F"}},
        )
        CaseProcedure.objects.create(
            case=case,
            procedure_type="eda",
            declared_by_nir=True,
            detection_status="detected",
        )
        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "exam-type-eda" in content
        assert "exam-type-colonoscopy" not in content
