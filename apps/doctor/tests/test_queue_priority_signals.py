"""Tests: badges de sinais prioritários na fila médica (valor persistido).

R7 — a fila projeta badges exclusivamente a partir de Case.priority_signals;
nenhum texto bruto é redetectado na view; caso vazio não renderiza container.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseStatus

User = get_user_model()


def _create_role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _signal(code: str, detail: str = "") -> dict[str, object]:
    return {
        "code": code,
        "category": {
            "foreign_body": "clinical_alert",
            "caustic_ingestion": "clinical_alert",
            "pediatric": "special_population",
            "echoendoscopy": "special_procedure",
            "esophageal_dilation": "special_procedure",
            "gastrostomy": "special_procedure",
        }[code],
        "detail": detail,
        "version": 1,
    }


@pytest.mark.django_db
class TestQueuePrioritySignalBadges:
    def _login_as_doctor(self, client) -> None:
        user = User.objects.create_user(username="doctor_sig@test.com", password="testpass123")
        user.roles.add(_create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

    def _make_wait_doctor_case(
        self,
        *,
        priority_signals: list[object],
        extracted_text: str = "",
        username: str | None = None,
    ) -> Case:
        nir_user = User.objects.create_user(
            username=username or f"nir_sig_{uuid.uuid4().hex[:8]}@test.com",
            password="testpass123",
        )
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            extracted_text=extracted_text,
            priority_signals=priority_signals,
        )
        case.agency_record_number = "2026-0001-001"
        case.save()
        return case

    def test_queue_shows_priority_signal_labels(self, client) -> None:
        self._make_wait_doctor_case(
            priority_signals=[_signal("pediatric", "10 anos"), _signal("foreign_body")],
        )
        self._login_as_doctor(client)
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Pediatria" in content
        assert "10 anos" in content
        assert "Suspeita de corpo estranho" in content

    def test_queue_renders_labels_in_canonical_order(self, client) -> None:
        self._make_wait_doctor_case(
            priority_signals=[
                _signal("gastrostomy"),
                _signal("caustic_ingestion", "há 2 dias"),
                _signal("foreign_body"),
            ],
        )
        self._login_as_doctor(client)
        content = client.get("/doctor/").content.decode()
        idx_fb = content.index("Suspeita de corpo estranho")
        idx_ci = content.index("Ingestão cáustica/corrosiva")
        idx_gs = content.index("Gastrostomia")
        assert idx_fb < idx_ci < idx_gs

    def test_queue_hides_container_when_no_signals(self, client) -> None:
        self._make_wait_doctor_case(priority_signals=[])
        self._login_as_doctor(client)
        content = client.get("/doctor/").content.decode()
        assert "data-priority-signals" not in content
        assert "Suspeita de corpo estranho" not in content
        assert "Pediatria" not in content

    def test_queue_two_cards_with_signals_have_no_duplicate_ids(self, client) -> None:
        """Dois cards com sinais não geram id fixo duplicado (D5/C7)."""
        self._make_wait_doctor_case(priority_signals=[_signal("foreign_body")])
        self._make_wait_doctor_case(priority_signals=[_signal("pediatric", "8 anos")])
        self._login_as_doctor(client)
        content = client.get("/doctor/").content.decode()
        assert 'id="priority-signals"' not in content
        # Cada container usa o marcador data-*; dois cards com sinais ⇒ 2 marcadores.
        assert content.count("data-priority-signals") == 2

    def test_queue_single_card_container_marker_appears_once(self, client) -> None:
        self._make_wait_doctor_case(priority_signals=[_signal("foreign_body")])
        self._login_as_doctor(client)
        content = client.get("/doctor/").content.decode()
        assert content.count("data-priority-signals") == 1

    def test_queue_uses_persisted_value_not_raw_text(self, client) -> None:
        """Texto bruto com sinal mas valor persistido vazio → nenhum badge."""
        self._make_wait_doctor_case(
            priority_signals=[],
            extracted_text="Suspeita de corpo estranho em esôfago.",
        )
        self._login_as_doctor(client)
        content = client.get("/doctor/").content.decode()
        assert "Suspeita de corpo estranho" not in content

    def test_queue_shows_persisted_badge_without_text(self, client) -> None:
        """Valor persistido com sinal mas texto vazio → badge é exibido."""
        self._make_wait_doctor_case(priority_signals=[_signal("foreign_body")], extracted_text="")
        self._login_as_doctor(client)
        content = client.get("/doctor/").content.decode()
        assert "Suspeita de corpo estranho" in content
