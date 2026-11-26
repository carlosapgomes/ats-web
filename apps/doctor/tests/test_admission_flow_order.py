"""Guarda da ordem das opções de fluxo de admissão no formulário de decisão.

Task: ``tasks/quick-ui-admission-flow-mobile-order.md``.

O SSR é a fonte de verdade da ordem "desktop" (mais comum primeiro) e nunca
muda; a inversão no mobile é progressive enhancement de
``static/js/mobile_select_order.js`` sobre o select marcado com
``data-mobile-reverse-options``. Este teste fixa o contrato HTML:

- R1: ordem SSR exata nos dois ramos do template (legado 1.1 e por procedimento),
  igual a ``ADMISSION_FLOW_CHOICES``;
- R2: o select leva o atributo que habilita a inversão no mobile;
- R3: o script é carregado nos dois ramos.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from django.contrib.auth import get_user_model

from apps.cases.admission import ADMISSION_FLOW_CHOICES
from apps.cases.models import Case, CaseProcedure, CaseStatus, DetectionStatus, ProcedureType
from apps.cases.procedures import PROCEDURE_ORDER

User = get_user_model()

# Ordem desktop canônica: placeholder + valores de ADMISSION_FLOW_CHOICES.
DESKTOP_ORDER = [code for code, _ in ADMISSION_FLOW_CHOICES]
MOBILE_SCRIPT = "js/mobile_select_order.js"
REVERSE_ATTRIBUTE = "data-mobile-reverse-options"


def _v4_structured(detected: list[str]) -> dict[str, Any]:
    """structured_data 4.0 mínimo com o conjunto detectado de teste."""
    return {
        "schema_version": "4.0",
        "patient": {"name": "Paciente Ordem", "age": 52, "sex": "F"},
        "requested_procedures": [{"procedure_type": t, "evidence_spans": [{"excerpt": "x"}]} for t in detected],
    }


def _admission_flow_select(html: str) -> str:
    """Markup do único ``<select name="admission_flow">`` da página."""
    match = re.search(r'<select[^>]*name="admission_flow"[^>]*>.*?</select>', html, re.S)
    assert match is not None, "select de fluxo de admissão ausente na decisão médica"
    return match.group(0)


def _option_values(markup: str) -> list[str]:
    return re.findall(r'<option value="([^"]*)"', markup)


@pytest.mark.django_db
class TestAdmissionFlowOptionOrder:
    """Contrato HTML do select de fluxo de admissão (ordem SSR + marcador mobile)."""

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client, username: str):
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(self._role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def _make_case(self, *, structured_data: dict[str, Any], detected: list[str], agency_record_number: str) -> Case:
        nir = User.objects.create_user(username=f"nir_{agency_record_number}@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number=agency_record_number,
            structured_data=structured_data,
            suggested_action={"schema_version": "4.0", "procedure_recommendations": []},
        )
        for procedure_type in sorted(detected, key=lambda t: PROCEDURE_ORDER[t]):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=procedure_type,
                declared_by_nir=True,
                detection_status=DetectionStatus.DETECTED,
            )
        return case

    def _render_decision_page(self, client, case: Case) -> str:
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        html: str = response.content.decode("utf-8")
        return html

    def _legacy_case(self) -> Case:
        # Sem schema_version → ramo legado 1.1 (decisão global accept/deny).
        return self._make_case(
            structured_data={"patient": {"name": "Paciente Legado", "age": 60, "gender": "M"}},
            detected=[ProcedureType.EDA],
            agency_record_number="ARN-LEGACY-ORDER",
        )

    def _per_procedure_case(self) -> Case:
        return self._make_case(
            structured_data=_v4_structured([ProcedureType.EDA]),
            detected=[ProcedureType.EDA],
            agency_record_number="ARN-V4-ORDER",
        )

    @pytest.mark.parametrize("branch", ["legacy", "per_procedure"])
    def test_ssr_keeps_desktop_order_and_marks_select_for_mobile(self, client, branch: str) -> None:
        self._login_doctor(client, f"doctor_order_{branch}@test.com")
        case = self._legacy_case() if branch == "legacy" else self._per_procedure_case()

        html = self._render_decision_page(client, case)

        select = _admission_flow_select(html)
        # R1: ordem desktop (mais comum primeiro) é a do SSR, igual ao catálogo...
        assert _option_values(select) == DESKTOP_ORDER
        # ...com o placeholder em primeiro: pré-condição do script (original[0] fica).
        first_option = re.search(r"<option[^>]*>", select)
        assert first_option is not None
        assert 'value=""' in first_option.group(0)
        assert "disabled" in first_option.group(0)
        # R2: marcador declarativo consumido por mobile_select_order.js.
        assert REVERSE_ATTRIBUTE in select.split(">", 1)[0]
        # R3: script carregado no ramo (per_procedure não carrega decision.js).
        assert MOBILE_SCRIPT in html
