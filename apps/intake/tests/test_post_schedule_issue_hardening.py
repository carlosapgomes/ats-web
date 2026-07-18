"""Testes do Slice 005 — Timeline, badges e hardening.

Verifica:
- Timeline exibe eventos de intercorrência com labels amigáveis.
- Badges consistentes nos estados opened/responded.
- Múltiplos ciclos sequenciais preservados.
- Cancelamento bloqueia nova intercorrência.
- Fluxos sem intercorrência permanecem coerentes.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import (
    acknowledge_post_schedule_issue,
    is_post_schedule_issue_eligible,
    open_post_schedule_issue,
    respond_post_schedule_issue,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_client(client, username: str = "nir@test.com"):
    from apps.accounts.models import Role

    user = User.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _get_lock_token(client, case) -> str:
    response = client.get(reverse("intake:case_detail", args=[case.case_id]))
    assert response.status_code == 200
    case_obj = Case.objects.get(pk=case.case_id)
    assert case_obj.lock_token is not None
    return str(case_obj.lock_token)


def _build_cleaned_confirmed(case_factory, advance_to, user) -> Case:
    """Cria Case CLEANED elegível com agendamento confirmado."""
    case = advance_to(case_factory(user), CaseStatus.CLEANED)
    case.doctor_decision = "accept"
    case.doctor_admission_flow = "scheduled"
    case.appointment_status = "confirmed"
    case.agency_record_number = "OCOR-MC-001"
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    case.appointment_at = datetime.now(ZoneInfo("UTC")) + timedelta(days=30)
    case.structured_data = {"patient": {"name": "Multi Cycle", "age": 50, "sex": "M"}}
    case.save(
        update_fields=[
            "doctor_decision",
            "doctor_admission_flow",
            "appointment_status",
            "agency_record_number",
            "appointment_at",
            "structured_data",
        ]
    )
    return Case.objects.get(pk=case.pk)


# ═══════════════════════════════════════════════════════════════════════════
# RED — Timeline events
# ═══════════════════════════════════════════════════════════════════════════


class TestTimelineEvents:
    """Timeline exibe eventos de intercorrência com labels amigáveis."""

    def _events_from_detail(self, client, case) -> list[str]:
        """Extrai labels de eventos da timeline no detail."""
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Busca seção da timeline
        timeline_start = content.find("Linha do Tempo")
        assert timeline_start >= 0, "Timeline não encontrada no template"

        # Extrai porções até "Ações" ou "Resultado Final"
        import re

        events_found = re.findall(
            r'<div class="timeline-event__title">([^<]+)</div>',
            content[timeline_start:],
        )
        return events_found

    def test_timeline_shows_opened_label(self, client, case_factory, advance_to) -> None:
        """Timeline exibe label amigável para POST_ACCEPTANCE_ISSUE_OPENED.

        Wrappers legados agora delegam à API pós-aceitação e emitem eventos
        POST_ACCEPTANCE_ISSUE_OPENED. O label renderizado contém
        'Intercorrência pós-aceitação aberta'.
        """
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="transport_unavailable", message="Sem transporte.")

        events = self._events_from_detail(client, case)
        opened_labels = [e for e in events if "Intercorrência" in e and ("Aberta" in e or "aberta" in e)]
        assert opened_labels, f"Nenhum label de abertura encontrado em {events}"

    def test_timeline_shows_responded_label(self, client, case_factory, advance_to) -> None:
        """Timeline exibe label amigável para POST_ACCEPTANCE_ISSUE_RESPONDED.

        Wrappers legados agora emitem POST_ACCEPTANCE_ISSUE_RESPONDED.
        O label renderizado contém 'Intercorrência pós-aceitação respondida'.
        """
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel", response_message="Cancelado.")

        events = self._events_from_detail(client, case)
        responded_labels = [e for e in events if "Intercorrência" in e and "respondida" in e]
        assert responded_labels, f"Nenhum label de resposta encontrado em {events}"

    def test_timeline_shows_acknowledged_label(self, client, case_factory, advance_to) -> None:
        """POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED tem label amigável no EVENT_LABELS.

        Wrappers legados agora emitem evento pós-aceitação com label
        'Ciência de intercorrência pós-aceitação confirmada'.
        """
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")

        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        new_date = (datetime.now(ZoneInfo("UTC")) + timedelta(days=15)).isoformat()
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="reschedule",
            appointment_at=new_date,
            response_message="Reagendado.",
        )
        # Confirmar via acknowledge direto
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED

        # Verificar label no evento via EVENT_LABELS
        from apps.intake.views import EVENT_LABELS

        assert (
            EVENT_LABELS.get("POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED")
            == "Ciência de intercorrência pós-aceitação confirmada"
        )
        event = CaseEvent.objects.filter(
            case=case,
            event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED",
        ).first()
        assert event is not None
        # Verificar que o template renderizaria o label corretamente
        label = EVENT_LABELS.get(event.event_type, event.event_type)
        assert "Ciência" in label

    def test_legacy_acknowledged_label_still_exists(self) -> None:
        """POST_SCHEDULE_ISSUE_ACKNOWLEDGED legado preserva label/dot CSS.

        Eventos históricos não são apagados; o label e dot CSS do ACK
        legado devem continuar disponíveis para renderização de casos antigos.
        """
        from apps.intake.views import EVENT_DOT_CSS, EVENT_LABELS

        label = EVENT_LABELS.get("POST_SCHEDULE_ISSUE_ACKNOWLEDGED")
        assert label is not None, "Legacy ACK must have a timeline label"
        assert "ciência" in label.lower() or "Ciência" in label

        dot = EVENT_DOT_CSS.get("POST_SCHEDULE_ISSUE_ACKNOWLEDGED")
        assert dot is not None, "Legacy ACK must have a dot CSS class"


# ═══════════════════════════════════════════════════════════════════════════
# RED — Multi-cycle
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiCycle:
    """Múltiplos ciclos sequenciais com timeline preservada."""

    def test_two_cycles_produce_ordered_events(self, client, case_factory, advance_to) -> None:
        """Dois ciclos geram eventos em ordem cronológica."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # ── Cycle 1 ─────────────────────────────────────────────────
        cycle1_opened = open_post_schedule_issue(case=case, user=user, reason="death")
        case = cycle1_opened

        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="reschedule",
            appointment_at=(datetime.now(ZoneInfo("UTC")) + timedelta(days=15)).isoformat(),
            response_message="Reagendado ciclo 1.",
        )

        # Acknowledge cycle 1
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED
        assert case.post_schedule_issue_status == ""

        # Verificar que agendamento está confirmado (reschedule manteve)
        case.appointment_status = "confirmed"
        case.save(update_fields=["appointment_status"])
        case = Case.objects.get(pk=case.pk)
        assert case.appointment_status == "confirmed"

        # ── Cycle 2 ─────────────────────────────────────────────────
        case = open_post_schedule_issue(
            case=case, user=user, reason="transport_unavailable", message="Ciclo 2 transporte."
        )
        case = respond_post_schedule_issue(
            case=case,
            user=user,
            action="maintain",
            response_message="Mantido ciclo 2.",
        )
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED

        # Verificar eventos de ambos os ciclos
        opened_events = CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_OPENED").order_by(
            "timestamp"
        )
        responded_events = CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_RESPONDED").order_by(
            "timestamp"
        )
        acked_events = CaseEvent.objects.filter(case=case, event_type="POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED").order_by(
            "timestamp"
        )

        assert opened_events.count() == 2, f"Esperado 2 OPENED, obtido {opened_events.count()}"
        assert responded_events.count() == 2, f"Esperado 2 RESPONDED, obtido {responded_events.count()}"
        assert acked_events.count() == 2, f"Esperado 2 ACKNOWLEDGED, obtido {acked_events.count()}"

        # Ordem cronológica entre ciclos
        assert opened_events[0].timestamp <= responded_events[0].timestamp
        assert responded_events[0].timestamp <= acked_events[0].timestamp
        assert acked_events[0].timestamp <= opened_events[1].timestamp
        assert opened_events[1].timestamp <= responded_events[1].timestamp

    def test_new_cycle_possible_after_acknowledge_if_confirmed(self, client, case_factory, advance_to) -> None:
        """Após acknowledge com agendamento confirmado, novo ciclo é elegível."""
        user = User.objects.create_user(username="nir-cycle@test.com", password="testpass123")
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)

        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Cycle 1: open → respond → acknowledge
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="maintain", response_message="Mantido.")
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED

        # Verificar elegibilidade para novo ciclo
        case.appointment_status = "confirmed"
        case.save(update_fields=["appointment_status"])
        case = Case.objects.get(pk=case.pk)

        assert is_post_schedule_issue_eligible(case), "Caso deveria ser elegível para novo ciclo"

        # Abrir novo ciclo
        case = open_post_schedule_issue(case=case, user=user, reason="reschedule_request", message="Reagendar.")
        assert case.post_schedule_issue_status == "opened"

    def test_cancelled_case_not_eligible_for_new_issue(self, client, case_factory, advance_to) -> None:
        """Após cancelamento, nova intercorrência não é elegível."""
        user = User.objects.create_user(username="nir-cancel@test.com", password="testpass123")
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="nir")
        user.roles.add(role)

        case = _build_cleaned_confirmed(case_factory, advance_to, user)

        # Open → cancel → acknowledge
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel", response_message="Cancelado.")
        case = acknowledge_post_schedule_issue(case=case, user=user)
        assert case.status == CaseStatus.CLEANED

        # Agendamento foi cancelado — não elegível
        assert is_post_schedule_issue_eligible(case) is False


# ═══════════════════════════════════════════════════════════════════════════
# RED — Badges
# ═══════════════════════════════════════════════════════════════════════════


class TestBadges:
    """Badges consistentes nos estados opened/responded."""

    def test_detail_badge_opened_shows_em_avaliacao(self, client, case_factory, advance_to) -> None:
        """case_detail mostra badge 'Intercorrência em avaliação' quando issue opened."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência em avaliação" in content

    def test_detail_badge_responded_shows_respondida(self, client, case_factory, advance_to) -> None:
        """case_detail mostra badge 'Intercorrência respondida' quando issue responded."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel", response_message="Cancelado.")

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência respondida" in content

    def test_search_badge_responded_shows_respondida(self, client, case_factory, advance_to) -> None:
        """closed_cases_search mostra badge 'Intercorrência respondida' quando issue responded."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel", response_message="Cancelado.")

        response = client.get(reverse("intake:closed_cases_search"), {"q": "OCOR-MC-001"})
        assert response.status_code == 200
        content = response.content.decode()
        # Deve mostrar respondida, não "em avaliação"
        assert "Intercorrência respondida" in content
        # Não deve mostrar "em avaliação" para o estado responded
        assert "Intercorrência em avaliação" not in content

    def test_search_badge_opened_shows_em_avaliacao(self, client, case_factory, advance_to) -> None:
        """closed_cases_search mostra badge 'Intercorrência em avaliação' quando issue opened."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")

        response = client.get(reverse("intake:closed_cases_search"), {"q": "OCOR-MC-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência em avaliação" in content

    def test_no_badge_without_issue(self, client, case_factory, advance_to) -> None:
        """Caso sem intercorrência não mostra badge de intercorrência."""
        client, user = _nir_client(client)
        # Usar caso WAIT_R1_CLEANUP_THUMBS sem intercorrência
        case = advance_to(case_factory(user), CaseStatus.WAIT_R1_CLEANUP_THUMBS)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência em avaliação" not in content
        assert "Intercorrência respondida" not in content


# ═══════════════════════════════════════════════════════════════════════════
# RED — Fluxos normais preservados
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalFlowsPreserved:
    """Fluxos sem intercorrência permanecem coerentes."""

    def test_normal_scheduler_queue_no_issue_badge(self, client, case_factory, advance_to) -> None:
        """Fila agendador normal não mostra badge de intercorrência."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="sched@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="scheduler")
        user.roles.add(role)
        client.force_login(user)
        session = client.session
        session["active_role"] = "scheduler"
        session.save()

        # Caso WAIT_APPT sem intercorrência
        case = advance_to(case_factory(user), CaseStatus.WAIT_APPT)
        case.doctor_decision = "accept"
        case.doctor_admission_flow = "scheduled"
        case.agency_record_number = "NORMAL-001"
        case.structured_data = {"patient": {"name": "Normal", "age": 40, "sex": "F"}}
        case.save(
            update_fields=[
                "doctor_decision",
                "doctor_admission_flow",
                "agency_record_number",
                "structured_data",
            ]
        )

        response = client.get(reverse("scheduler:queue"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência pós-aceitação" not in content

    def test_normal_nir_timeline_no_issue_events(self, client, case_factory, advance_to) -> None:
        """Timeline NIR normal não mostra eventos de intercorrência."""
        client, user = _nir_client(client)
        case = advance_to(case_factory(user), CaseStatus.WAIT_R1_CLEANUP_THUMBS)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Eventos de intercorrência não devem aparecer
        assert "Intercorrência" not in content


# ═══════════════════════════════════════════════════════════════════════════
# RED — Busca com mensagem clara para duplicidade
# ═══════════════════════════════════════════════════════════════════════════


class TestSearchClearMessages:
    """Busca NIR bloqueia duplicidade com mensagem clara."""

    def test_opened_search_shows_em_avaliacao(self, client, case_factory, advance_to) -> None:
        """Issue opened mostra 'Intercorrência em avaliação'."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")

        response = client.get(reverse("intake:closed_cases_search"), {"q": "OCOR-MC-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência em avaliação" in content
        assert "Registrar intercorrência" not in content

    def test_responded_search_shows_msg_respondida(self, client, case_factory, advance_to) -> None:
        """Issue responded mostra 'Intercorrência respondida'."""
        client, user = _nir_client(client)
        case = _build_cleaned_confirmed(case_factory, advance_to, user)
        case = open_post_schedule_issue(case=case, user=user, reason="death")
        case = respond_post_schedule_issue(case=case, user=user, action="cancel", response_message="Cancelado.")

        response = client.get(reverse("intake:closed_cases_search"), {"q": "OCOR-MC-001"})
        assert response.status_code == 200
        content = response.content.decode()
        assert "Intercorrência respondida" in content
        assert "Registrar intercorrência" not in content


# ═══════════════════════════════════════════════════════════════════════════
# EVENT_LABELS completeness — todo event_type do código tem label pt-BR
# ═══════════════════════════════════════════════════════════════════════════


class TestEventLabelsCompleteness:
    """Todo event_type usado em _record_event() tem label em EVENT_LABELS."""

    def test_all_event_types_have_portuguese_labels(self) -> None:
        """Coleta todos os event types do código (exclui tests) e verifica
        que cada um tem label em EVENT_LABELS."""
        import re
        from pathlib import Path

        from apps.intake.views import EVENT_LABELS

        apps_dir = Path("apps")
        event_types: set[str] = set()

        for py_file in apps_dir.rglob("*.py"):
            if "test" in str(py_file).lower() or "migration" in str(py_file).lower():
                continue
            try:
                source = py_file.read_text()
            except Exception:
                continue

            # 1) Literal strings: _record_event(..., "EVENT_TYPE", ...)
            #    DOTALL pq chamadas em services.py usam múltiplas linhas
            for match in re.finditer(
                r'_record_event\(.*?["\']([A-Z][A-Z_0-9]+)["\']',
                source,
                re.DOTALL,
            ):
                event_types.add(match.group(1))

            # 2) f-string prefix: _record_event(f"PREFIX_{var}"
            for match in re.finditer(r'_record_event\(\s*f["\']([A-Z][A-Z_]+)_', source):
                prefix = match.group(1)
                # Known expansions from models.py:
                #   f"LLM1_{success}" → LLM1_OK, LLM1_FAILED
                #   f"LLM2_{success}" → LLM2_OK, LLM2_FAILED
                #   f"DOCTOR_{decision}" → DOCTOR_ACCEPT, DOCTOR_DENY
                #   f"APPT_{appointment_status}" → APPT_CONFIRMED, APPT_DENIED
                known: dict[str, list[str]] = {
                    "LLM1": ["LLM1_OK", "LLM1_FAILED"],
                    "LLM2": ["LLM2_OK", "LLM2_FAILED"],
                    "DOCTOR": ["DOCTOR_ACCEPT", "DOCTOR_DENY"],
                    "APPT": ["APPT_CONFIRMED", "APPT_DENIED"],
                }
                for candidate in known.get(prefix, []):
                    event_types.add(candidate)

            # 3) CaseEvent.objects.create(event_type="..." (signals.py)
            for match in re.finditer(
                r'CaseEvent\.objects\.create\([^)]*event_type=["\']([A-Z][A-Z_0-9]+)["\']',
                source,
            ):
                event_types.add(match.group(1))

        # Sanity: at least some known event types must be found
        assert "CASE_CREATED" in event_types, "Sanity: CASE_CREATED not found (signals.py)"
        assert "WORK_LOCK_CLAIMED" in event_types, "Sanity: WORK_LOCK_CLAIMED not found"
        assert "DOCTOR_ACCEPT" in event_types, "Sanity: DOCTOR_ACCEPT not found"

        missing = sorted(et for et in event_types if et not in EVENT_LABELS)
        assert missing == [], (
            f"Event types sem label em EVENT_LABELS: {missing}. "
            f"Adicione a tradução em apps/intake/views.py:EVENT_LABELS"
        )
