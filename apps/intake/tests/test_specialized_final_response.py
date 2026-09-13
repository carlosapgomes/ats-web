"""Slice 003/004 — resposta final do NIR para procedimento especializado (R6).

Cobre o recorte NIR dos slices ``slice-003-echoendoscopy-doctor-swap-and-downstream``
e ``slice-004-cpre-end-to-end``:

- R6: a resposta final compara as TRÊS dimensões (declarado/detectado/
  autorizado), mostra as razões por componente e o badge do procedimento
  especializado — nunca o sufixo de agendamento casado;
- R7: o evento dedicado da troca tem label/dot na timeline NIR.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import (
    Case,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.intake.views import _procedure_comparison

User = get_user_model()


def _nir_client(client, username: str | None = None):
    """Cria usuário NIR autenticado com papel ativo na sessão."""
    from apps.accounts.models import Role

    user = User.objects.create_user(
        username=username or f"nir-final-{uuid.uuid4().hex[:8]}@test.com", password="testpass123"
    )
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _make_case(
    *,
    user: Any,
    declared: tuple[str, ...],
    detected: tuple[str, ...],
    approved: tuple[str, ...] = (),
    denied: tuple[str, ...] = (),
    reasons: dict[str, str] | None = None,
    status: str = CaseStatus.WAIT_DOCTOR,
) -> Case:
    """Caso 3.0 com as três dimensões explícitas em rows."""
    reasons = reasons or {}
    case = Case.objects.create(
        created_by=user,
        status=status,
        agency_record_number="ARN-FINAL-001",
        structured_data={"schema_version": "3.0", "patient": {"name": "Paciente Final", "age": 61, "sex": "F"}},
        suggested_action={"schema_version": "3.0", "procedure_recommendations": []},
    )
    for procedure_type in tuple(dict.fromkeys((*declared, *detected, *approved, *denied))):
        row = CaseProcedure.objects.create(
            case=case,
            procedure_type=procedure_type,
            declared_by_nir=procedure_type in declared,
        )
        fields: list[str] = []
        if procedure_type in detected:
            row.detection_status = DetectionStatus.DETECTED
            fields.append("detection_status")
        elif procedure_type in approved or procedure_type in denied:
            row.detection_status = DetectionStatus.NOT_DETECTED
            fields.append("detection_status")
        if procedure_type in approved:
            row.doctor_disposition = DoctorDisposition.APPROVED
            row.doctor_reason = reasons.get(procedure_type, "")
            fields += ["doctor_disposition", "doctor_reason"]
        elif procedure_type in denied:
            row.doctor_disposition = DoctorDisposition.DENIED
            row.doctor_reason = reasons.get(procedure_type, "Procedimento substituído.")
            fields += ["doctor_disposition", "doctor_reason"]
        if fields:
            row.save(update_fields=fields)
    return case


@pytest.mark.django_db
class TestSpecializedFinalResponse:
    """Comparação declarado → detectado → autorizado com tipo especializado."""

    def test_comparison_exposes_echoendoscopy_in_three_dimensions(self) -> None:
        """Ecoendoscopia autorizada aparece na dimensão autorizada, sem label casado."""
        from apps.accounts.models import Role

        nir_user = User.objects.create_user(username=f"nir-pure-{uuid.uuid4().hex[:8]}@test.com", password="pw")
        role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(role)
        case = _make_case(
            user=nir_user,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA,),
            approved=(ProcedureType.ECHOENDOSCOPY,),
            denied=(ProcedureType.EDA,),
            reasons={
                ProcedureType.ECHOENDOSCOPY: "Ecoendoscopia para caracterização",
                ProcedureType.EDA: "Substituída por Ecoendoscopia.",
            },
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        comparison = _procedure_comparison(case)

        assert comparison["declared_label"] == "EDA"
        assert comparison["detected_label"] == "EDA"
        assert comparison["authorized_label"] == "Ecoendoscopia"
        assert comparison["is_paired"] is False
        labels: dict[str, dict[str, object]] = {
            str(row["label"]): row for row in cast("list[dict[str, object]]", comparison["per_procedure"])
        }
        assert "Ecoendoscopia" in labels
        assert labels["Ecoendoscopia"]["reason"] == "Ecoendoscopia para caracterização"
        assert labels["Ecoendoscopia"]["status"] == "Aprovado"

    def test_case_detail_renders_three_dimensions_without_paired_badge(self, client) -> None:
        """A tela NIR mostra as três dimensões e não mostra badge de agenda casada."""
        client, user = _nir_client(client)
        case = _make_case(
            user=user,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA,),
            approved=(ProcedureType.ECHOENDOSCOPY,),
            denied=(ProcedureType.EDA,),
            reasons={ProcedureType.ECHOENDOSCOPY: "Ecoendoscopia para caracterização"},
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Solicitado pelo NIR" in content
        assert "Detectado na análise" in content
        assert "Decisão médica" in content
        assert "Ecoendoscopia" in content
        assert "Ecoendoscopia para caracterização" in content
        assert "Agendamento casado" not in content

    def test_echoendoscopy_declared_badge_uses_specialized_label(self, client) -> None:
        """Caso declarado como Ecoendoscopia recebe badge/label do tipo."""
        client, user = _nir_client(client)
        case = _make_case(
            user=user,
            declared=(ProcedureType.ECHOENDOSCOPY,),
            detected=(ProcedureType.ECHOENDOSCOPY,),
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Ecoendoscopia" in content
        assert "exam-type-echoendoscopy" in content
        assert "Agendamento casado" not in content

    def test_set_changed_event_has_timeline_label_and_dot(self) -> None:
        """R7: evento dedicado da troca é legível na timeline do NIR."""
        from apps.intake.views import EVENT_DOT_CSS, EVENT_LABELS

        assert EVENT_LABELS.get("DOCTOR_PROCEDURE_SET_CHANGED")
        assert EVENT_DOT_CSS.get("DOCTOR_PROCEDURE_SET_CHANGED")

    # ── Slice 004 (R6): CPRE na resposta final do NIR ───────────────────────

    def test_comparison_exposes_cpre_in_three_dimensions(self) -> None:
        """CPRE autorizada aparece na dimensão autorizada, sem label casado."""
        from apps.accounts.models import Role

        nir_user = User.objects.create_user(username=f"nir-cpre-{uuid.uuid4().hex[:8]}@test.com", password="pw")
        role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(role)
        case = _make_case(
            user=nir_user,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA,),
            approved=(ProcedureType.CPRE,),
            denied=(ProcedureType.EDA,),
            reasons={
                ProcedureType.CPRE: "CPRE para avaliacao de via biliar",
                ProcedureType.EDA: "Substituída por CPRE.",
            },
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        comparison = _procedure_comparison(case)

        assert comparison["declared_label"] == "EDA"
        assert comparison["detected_label"] == "EDA"
        assert comparison["authorized_label"] == "CPRE"
        assert comparison["is_paired"] is False
        labels: dict[str, dict[str, object]] = {
            str(row["label"]): row for row in cast("list[dict[str, object]]", comparison["per_procedure"])
        }
        assert "CPRE" in labels
        assert labels["CPRE"]["reason"] == "CPRE para avaliacao de via biliar"
        assert labels["CPRE"]["status"] == "Aprovado"

    def test_case_detail_renders_cpre_three_dimensions_without_paired_badge(self, client) -> None:
        client, user = _nir_client(client)
        case = _make_case(
            user=user,
            declared=(ProcedureType.EDA,),
            detected=(ProcedureType.EDA,),
            approved=(ProcedureType.CPRE,),
            denied=(ProcedureType.EDA,),
            reasons={ProcedureType.CPRE: "CPRE para avaliacao de via biliar"},
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Solicitado pelo NIR" in content
        assert "Detectado na análise" in content
        assert "Decisão médica" in content
        assert "CPRE" in content
        assert "CPRE para avaliacao de via biliar" in content
        assert "Agendamento casado" not in content

    def test_cpre_declared_badge_uses_specialized_label(self, client) -> None:
        client, user = _nir_client(client)
        case = _make_case(
            user=user,
            declared=(ProcedureType.CPRE,),
            detected=(ProcedureType.CPRE,),
            status=CaseStatus.WAIT_DOCTOR,
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "CPRE" in content
        assert "exam-type-cpre" in content
        assert "Agendamento casado" not in content

    # ── Slice 007 (R2/R5): detalhe encerrado com badge e legado legível ──

    @pytest.mark.parametrize(
        ("declared", "type_key"),
        [
            (ProcedureType.ECHOENDOSCOPY, "echoendoscopy"),
            (ProcedureType.CPRE, "cpre"),
        ],
    )
    def test_closed_case_detail_shows_specialized_declared_badge(self, client, declared: str, type_key: str) -> None:
        """R2: o detalhe do caso encerrado mostra o badge singleton do declarado."""
        client, user = _nir_client(client)
        case = _make_case(
            user=user,
            declared=(declared,),
            detected=(declared,),
            approved=(declared,),
            reasons={declared: "Autorizado após revisão."},
            status=CaseStatus.CLEANED,
        )

        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert f"exam-type-{type_key}" in content
        assert "Solicitado pelo NIR" in content
        assert "Agendamento casado" not in content

    def test_closed_case_detail_keeps_legacy_echo_signal_without_row(self, client) -> None:
        """R5: histórico legado de Ecoendoscopia continua legível e sem nova row."""
        client, user = _nir_client(client)
        legacy = Case.objects.create(
            created_by=user,
            status=CaseStatus.CLEANED,
            agency_record_number="CLOSED-LEGACY-ECO",
            structured_data={
                "schema_version": "2.0",
                "eda": {"requested_procedure": {"subtype": "echoendoscopy"}},
                "preop_screening": {"exam_type": "eda"},
            },
            priority_signals=[{"code": "echoendoscopy", "version": 1}],
        )

        response = client.get(reverse("intake:closed_case_detail", args=[legacy.case_id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-priority-signal-code="echoendoscopy"' in content
        # R5: nada de backfill — o sinal legado não vira procedimento declarado.
        assert CaseProcedure.objects.filter(case=legacy).count() == 0
        assert CaseProcedure.objects.filter(procedure_type=ProcedureType.ECHOENDOSCOPY).count() == 0
