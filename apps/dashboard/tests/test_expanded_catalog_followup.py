"""Slice 008 — follow-up pelo catálogo ampliado (R6).

- R6: o follow-up continua restrito às rows ``CaseProcedure`` AUTORIZADAS
  (ADR-0007) e cobre as novas identidades como uma row por identidade, com o
  código/label exatos do catálogo (pacote nunca exige desfecho da EDA base).
- Rows negadas/pendentes ficam isentas e um desfecho informado para elas é
  rejeitado fail-closed.
- O histórico projeta a label canônica de cada identidade, sem regra textual
  por ``+``/cardinalidade.
"""

from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.followup import ProcedureOutcomeInput, record_case_follow_up
from apps.cases.models import (
    Case,
    CaseEvent,
    CaseFollowUp,
    CaseProcedure,
    DoctorDisposition,
    ProcedureFollowUp,
    ProcedureType,
)
from apps.cases.procedures import PROCEDURE_LABELS, PROCEDURE_ORDER, SUPPORTED_PROCEDURE_TYPES

pytestmark = pytest.mark.django_db

User = get_user_model()

PLUS_LABEL_CODES = tuple(code for code in SUPPORTED_PROCEDURE_TYPES if "+" in PROCEDURE_LABELS[code])


def _login_as(client, role_name: str) -> Any:
    """``manager`` (supervisor CHD) recebe também o papel scheduler (matriz D6)."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username=f"followup-catalog-{role_name}@test", password="testpass123")
    role, _ = Role.objects.get_or_create(name=role_name)
    user.roles.add(role)
    if role_name == "manager":
        scheduler_role, _ = Role.objects.get_or_create(name="scheduler")
        user.roles.add(scheduler_role)
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _create_case(user, *, arn: str, name: str) -> Case:
    """Caso elegível ao follow-up (agendado confirmado com horário)."""
    day = timezone.localdate()
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        appointment_status="confirmed",
        appointment_at=timezone.make_aware(datetime.combine(day, time(10, 0)), timezone.get_current_timezone()),
        doctor_admission_flow="scheduled",
    )
    case.structured_data = {"patient": {"name": name}}
    case.save(update_fields=["structured_data"])
    return case


def _add_procedure(case: Case, procedure_type: str, *, disposition: str = DoctorDisposition.APPROVED) -> CaseProcedure:
    return CaseProcedure.objects.create(
        case=case,
        procedure_type=procedure_type,
        declared_by_nir=True,
        doctor_disposition=disposition,
    )


def _form_url(case: Case) -> str:
    return reverse("dashboard:followup_form", args=[str(case.case_id)])


def _valid_payload(procedure: CaseProcedure, *, performed: str = "yes") -> dict[str, str]:
    return {
        "patient_admitted": "yes",
        f"proc_{procedure.id}-performed": performed,
    }


# ── R6: cobertura restrita ao autorizado, uma row por identidade ──────────


class TestFollowUpCatalogCoverage:
    def test_form_lists_one_block_per_authorized_identity(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-PKG-001", name="Pacote")
        _add_procedure(case, ProcedureType.EDA_GASTROSTOMY)
        _add_procedure(case, ProcedureType.RECTOSIGMOIDOSCOPY_ARGON)

        content = client.get(_form_url(case)).content.decode()
        assert content.count("data-followup-proc-id=") == 2
        assert f"{PROCEDURE_LABELS[ProcedureType.EDA_GASTROSTOMY]}</h6>" in content
        assert f"{PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_ARGON]}</h6>" in content
        # Pacote é identidade única: nenhum bloco da base EDA/Retossigmoidoscopia.
        assert f"{PROCEDURE_LABELS[ProcedureType.EDA]}</h6>" not in content
        assert f"{PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY]}</h6>" not in content

    def test_form_blocks_follow_canonical_catalog_order(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-ORD-001", name="Ordem")
        procedures = {
            code: _add_procedure(case, code)
            for code in (ProcedureType.CPRE, ProcedureType.EDA_CAPSULE, ProcedureType.COLONOSCOPY)
        }
        content = client.get(_form_url(case)).content.decode()
        rendered = [int(pid) for pid in re.findall(r'data-followup-proc-id="(\d+)"', content)]
        expected = sorted(procedures, key=lambda code: PROCEDURE_ORDER[code])
        assert rendered == [procedures[code].id for code in expected]

    def test_denied_row_is_exempt_and_rejected(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-DEN-001", name="Negada")
        _add_procedure(case, ProcedureType.EDA)
        denied = _add_procedure(case, ProcedureType.EDA_CAPSULE, disposition=DoctorDisposition.DENIED)

        content = client.get(_form_url(case)).content.decode()
        assert content.count("data-followup-proc-id=") == 1
        assert f"{PROCEDURE_LABELS[ProcedureType.EDA_CAPSULE]}</h6>" not in content

        response = client.post(
            _form_url(case),
            data={"patient_admitted": "yes", f"proc_{denied.id}-performed": "yes"},
        )
        assert response.status_code == 200
        assert not CaseFollowUp.objects.filter(case=case).exists()

    def test_package_never_requires_the_base_identity(self, client) -> None:
        """R6: uma row por identidade — o pacote não exige desfecho da EDA base."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-BASE-001", name="Sem Base")
        package = _add_procedure(case, ProcedureType.EDA_DILATION)

        response = client.post(_form_url(case), data=_valid_payload(package))
        assert response.status_code == 302
        recorded = CaseFollowUp.objects.get(case=case)
        assert list(recorded.procedure_outcomes.values_list("procedure__procedure_type", flat=True)) == [
            ProcedureType.EDA_DILATION
        ]

    def test_coverage_requires_all_authorized_and_only_authorized(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-COV-001", name="Cobertura")
        first = _add_procedure(case, ProcedureType.EDA_GASTROSTOMY)
        _add_procedure(case, ProcedureType.RECTOSIGMOIDOSCOPY_DILATION)

        incomplete = client.post(_form_url(case), data=_valid_payload(first))
        assert incomplete.status_code == 200
        assert not CaseFollowUp.objects.filter(case=case).exists()


# ── R6: gravação e leitura sob o código/label exatos ─────────────────────


class TestFollowUpCatalogRowsAndLabels:
    @pytest.mark.parametrize("code", PLUS_LABEL_CODES)
    def test_service_records_outcome_under_exact_code(self, code: str) -> None:
        """R6: ProcedureFollowUp aponta para a row da identidade exata."""
        nir = User.objects.create_user(username=f"nir-fup-{code}@test", password="testpass123")
        case = _create_case(nir, arn=f"FUP-{code[:12]}", name="Pacote Serviço")
        package = _add_procedure(case, code)

        follow_up = record_case_follow_up(
            case=case,
            performed_by=nir,
            patient_admitted=False,
            procedure_outcomes=[
                ProcedureOutcomeInput(procedure_id=package.id, performed=True),
            ],
        )
        outcome = ProcedureFollowUp.objects.get(follow_up=follow_up)
        assert outcome.procedure.procedure_type == code
        assert outcome.procedure.get_procedure_type_display() == PROCEDURE_LABELS[code]

        event = CaseEvent.objects.get(case=case, event_type="FOLLOWUP_RECORDED")
        assert event.payload["outcomes"] == [
            {
                "procedure_id": package.id,
                "procedure_type": code,
                "performed": True,
                "non_performance_reason": "",
                "resource_shortage_detail": "",
                "other_reason": "",
            }
        ]

    def test_history_renders_catalog_label_for_new_identity(self, client) -> None:
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-HIST-001", name="Histórico")
        package = _add_procedure(case, ProcedureType.RECTOSIGMOIDOSCOPY_ARGON)
        record_case_follow_up(
            case=case,
            performed_by=user,
            patient_admitted=False,
            procedure_outcomes=[ProcedureOutcomeInput(procedure_id=package.id, performed=True)],
        )

        content = client.get(reverse("dashboard:followup_history")).content.decode()
        assert PROCEDURE_LABELS[ProcedureType.RECTOSIGMOIDOSCOPY_ARGON] in content
        assert "FUP-HIST-001" in content

    def test_combined_case_covers_both_authorized_components(self, client) -> None:
        """R6: par exato autorizado continua com uma row por componente."""
        user = _login_as(client, "manager")
        case = _create_case(user, arn="FUP-COMB-001", name="Combinado")
        eda = _add_procedure(case, ProcedureType.EDA)
        colon = _add_procedure(case, ProcedureType.COLONOSCOPY)

        response = client.post(
            _form_url(case),
            data={**_valid_payload(eda), **_valid_payload(colon)},
        )
        assert response.status_code == 302
        recorded = CaseFollowUp.objects.get(case=case)
        rows = set(recorded.procedure_outcomes.values_list("procedure__procedure_type", "performed"))
        assert rows == {(ProcedureType.EDA, True), (ProcedureType.COLONOSCOPY, True)}
