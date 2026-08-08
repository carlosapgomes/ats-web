"""Slice 003 — Histórico por procedimento (R6) e filas/filtros médicos (R7).

REDs 12–16 do slice:

- RED 12: EDA prévia negada + Colon prévia aprovada aparecem nas seções/decisões corretas;
- RED 13: same prior combined mantém prior_case_id, mas razão/disposição próprias por row;
- RED 14: agenda global negada aplica-se somente às rows previamente aprovadas;
- RED 15: janela de sete dias e deduplicação permanecem, e aprovação não incrementa
  prior_denial_count_7d;
- RED 16: filtros detectado/autorizado + busca/polling (inspeção estática + markup).
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import Case, CaseProcedure, CaseStatus
from apps.doctor.reporting import PRIOR_DECISION_DISPLAY, prepare_doctor_case_report

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "doctor" / "queue.html"
QUEUE_CONTENT_HTML = REPO_ROOT / "templates" / "doctor" / "_queue_content.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "doctor_queue_filter.js"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_user(username: str):
    return User.objects.create_user(username=username, password="pw")


def _v2_structured(name: str = "Paciente") -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "patient": {"name": name, "age": 40, "sex": "F"},
        "common_preop": {},
        "requested_procedures": [
            {"procedure_type": "eda", "subtype": "standard", "evidence_spans": [{"excerpt": "x"}]},
            {"procedure_type": "colonoscopy", "subtype": "standard", "evidence_spans": [{"excerpt": "y"}]},
        ],
    }


def _prior_case(
    user: Any,
    *,
    arn: str,
    rows: list[tuple[str, str]],
    status: str,
    doctor_decision: str,
    doctor_reason: str = "",
    doctor_decided_at: datetime | None = None,
    appointment_status: str = "",
    appointment_reason: str = "",
    appointment_decided_at: datetime | None = None,
    **fields: object,
) -> Case:
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        status=status,
        exam_type="eda_colonoscopy" if len(rows) == 2 else rows[0][0],
        structured_data=_v2_structured(),
        doctor_decision=doctor_decision,
        doctor_reason=doctor_reason,
        doctor_decided_at=doctor_decided_at,
        appointment_status=appointment_status,
        appointment_reason=appointment_reason,
        appointment_decided_at=appointment_decided_at,
        **fields,
    )
    for pt, disposition in rows:
        CaseProcedure.objects.create(
            case=case,
            procedure_type=pt,
            declared_by_nir=True,
            doctor_disposition=disposition,
        )
    return case


def _current_v2_case(user: Any, *, arn: str, detected: list[str]) -> Case:
    case = Case.objects.create(
        created_by=user,
        agency_record_number=arn,
        status=CaseStatus.WAIT_DOCTOR,
        exam_type="eda_colonoscopy" if len(detected) == 2 else detected[0],
        structured_data=_v2_structured(),
        suggested_action={
            "schema_version": "2.0",
            "procedure_recommendations": [],
            "global_support_recommendation": "none",
        },
    )
    for pt in ("eda", "colonoscopy"):
        CaseProcedure.objects.create(
            case=case,
            procedure_type=pt,
            declared_by_nir=pt in detected,
            detection_status="detected" if pt in detected else "not_detected",
        )
    return case


def _section_by_type(sections: list[dict[str, Any]], pt: str) -> dict[str, Any]:
    return next(s for s in sections if s["procedure_type"] == pt)


@pytest.mark.django_db
class TestPriorSectionsPerProcedure:
    """R6/D10: seções EDA/Colonoscopia com decisão/razão da row."""

    def test_eda_denied_and_colon_approved_in_correct_sections(self, django_user_model) -> None:
        user = _make_user("nir_prior1")
        now = _now()
        _prior_case(
            user,
            arn="AR-P1",
            rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        prior = Case.objects.get(agency_record_number="AR-P1")
        eda_row = prior.procedures.get(procedure_type="eda")
        eda_row.doctor_reason = "razão do componente EDA"
        eda_row.save(update_fields=["doctor_reason"])

        current = _current_v2_case(user, arn="AR-P1", detected=["eda", "colonoscopy"])
        prepared = prepare_doctor_case_report(current)

        sections = prepared.prior_sections
        assert [s["procedure_type"] for s in sections] == ["eda", "colonoscopy"]
        eda_section = _section_by_type(sections, "eda")
        colon_section = _section_by_type(sections, "colonoscopy")

        assert eda_section["decision"] == "doctor_denied"
        assert eda_section["decision_display"] == PRIOR_DECISION_DISPLAY["doctor_denied"]
        assert eda_section["reason"] == "razão do componente EDA"
        assert eda_section["prior_denial_count_7d"] == 1

        assert colon_section["decision"] == "doctor_approved"
        assert colon_section["decision_display"] == PRIOR_DECISION_DISPLAY["doctor_approved"]
        assert colon_section["prior_denial_count_7d"] == 0

    def test_same_prior_case_id_own_reason_per_row(self, django_user_model) -> None:
        user = _make_user("nir_prior2")
        now = _now()
        _prior_case(
            user,
            arn="AR-P2",
            rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        prior = Case.objects.get(agency_record_number="AR-P2")
        eda_row = prior.procedures.get(procedure_type="eda")
        eda_row.doctor_reason = "razão EDA própria"
        eda_row.save(update_fields=["doctor_reason"])

        current = _current_v2_case(user, arn="AR-P2", detected=["eda", "colonoscopy"])
        sections = prepare_doctor_case_report(current).prior_sections

        eda_section = _section_by_type(sections, "eda")
        colon_section = _section_by_type(sections, "colonoscopy")
        # Mesmo caso anterior nas duas seções…
        assert eda_section["prior_case_id"] == colon_section["prior_case_id"]
        assert eda_section["prior_case_id"] == str(prior.case_id)
        # …mas decisão/razão próprias por row.
        assert eda_section["decision"] == "doctor_denied"
        assert eda_section["reason"] == "razão EDA própria"
        assert colon_section["decision"] == "doctor_approved"
        assert colon_section["reason"] == ""

    def test_appointment_denial_only_approved_row_presentation(self, django_user_model) -> None:
        user = _make_user("nir_prior3")
        now = _now()
        _prior_case(
            user,
            arn="AR-P3",
            rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.APPT_DENIED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            appointment_status="denied",
            appointment_reason="sem vaga",
            appointment_decided_at=now - timedelta(hours=12),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        current = _current_v2_case(user, arn="AR-P3", detected=["eda", "colonoscopy"])
        sections = prepare_doctor_case_report(current).prior_sections

        eda_section = _section_by_type(sections, "eda")
        colon_section = _section_by_type(sections, "colonoscopy")
        # EDA negada pelo médico permanece doctor_denied (razão da row).
        assert eda_section["decision"] == "doctor_denied"
        # Somente a row aprovada recebe a negativa global de agendamento.
        assert colon_section["decision"] == "appointment_denied"
        assert colon_section["reason"] == "sem vaga"
        assert colon_section["prior_denial_count_7d"] == 1

    def test_window_dedup_and_approval_never_counts(self, django_user_model) -> None:
        user = _make_user("nir_prior4")
        now = _now()
        # Aprovação dentro da janela: aparece como contexto, mas não incrementa contador.
        _prior_case(
            user,
            arn="AR-P4",
            rows=[("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        # Negativa fora da janela (8 dias): fora do contexto.
        _prior_case(
            user,
            arn="AR-P4",
            rows=[("eda", "denied")],
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="antiga",
            doctor_decided_at=now - timedelta(days=8),
        )
        current = _current_v2_case(user, arn="AR-P4", detected=["eda", "colonoscopy"])
        sections = prepare_doctor_case_report(current).prior_sections

        colon_section = _section_by_type(sections, "colonoscopy")
        assert colon_section["decision"] == "doctor_approved"
        assert colon_section["prior_denial_count_7d"] == 0

        # EDA fora da janela não entra nas seções (sem seção EDA).
        assert all(s["procedure_type"] != "eda" for s in sections)

    def test_deduplication_most_recent_and_count_within_window(self, django_user_model) -> None:
        user = _make_user("nir_prior5")
        now = _now()
        # Duas negativas EDA dentro da janela: mais recente é o summary e contagem = 2.
        older = _prior_case(
            user,
            arn="AR-P5",
            rows=[("eda", "denied")],
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="primeira",
            doctor_decided_at=now - timedelta(days=3),
        )
        older_row = older.procedures.get(procedure_type="eda")
        older_row.doctor_reason = "primeira"
        older_row.save(update_fields=["doctor_reason"])
        newer = _prior_case(
            user,
            arn="AR-P5",
            rows=[("eda", "denied")],
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="segunda",
            doctor_decided_at=now - timedelta(days=1),
        )
        newer_row = newer.procedures.get(procedure_type="eda")
        newer_row.doctor_reason = "segunda"
        newer_row.save(update_fields=["doctor_reason"])

        current = _current_v2_case(user, arn="AR-P5", detected=["eda"])
        sections = prepare_doctor_case_report(current).prior_sections

        eda_section = _section_by_type(sections, "eda")
        assert eda_section["prior_case_id"] == str(newer.case_id)
        assert eda_section["reason"] == "segunda"
        assert eda_section["prior_denial_count_7d"] == 2

    def test_legacy_case_keeps_single_prior_context(self, django_user_model) -> None:
        """Casos 1.1 (sem schema 2.0) mantêm prior context único por derivação (R2)."""
        user = _make_user("nir_prior6")
        now = _now()
        legacy = Case.objects.create(
            created_by=user,
            agency_record_number="AR-P6",
            status=CaseStatus.DOCTOR_DENIED,
            exam_type="eda",
            doctor_decision="deny",
            doctor_reason="motivo global",
            doctor_decided_at=now - timedelta(days=1),
            structured_data={
                "schema_version": "1.1",
                "patient": {"name": "P", "age": 30, "sex": "M"},
                "preop_screening": {"exam_type": "eda"},
            },
        )
        CaseProcedure.objects.create(
            case=legacy, procedure_type="eda", declared_by_nir=True, doctor_disposition="denied"
        )
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-P6",
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="eda",
            structured_data={
                "schema_version": "1.1",
                "patient": {"name": "C", "age": 30, "sex": "M"},
                "preop_screening": {"exam_type": "eda"},
            },
        )
        prepared = prepare_doctor_case_report(current)
        assert prepared.prior_sections == []
        assert prepared.prior_context is not None
        assert prepared.prior_context.prior_case is not None
        assert prepared.prior_context.prior_case.prior_case_id == str(legacy.case_id)
        assert prepared.prior_context.prior_case.prior_case_id == str(legacy.case_id)

    def test_decision_page_renders_both_prior_sections(self, client, django_user_model) -> None:
        from apps.accounts.models import Role

        user = _make_user("nir_prior7")
        now = _now()
        _prior_case(
            user,
            arn="AR-P7",
            rows=[("eda", "denied"), ("colonoscopy", "approved")],
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor_decision="accept",
            doctor_decided_at=now - timedelta(days=1),
            doctor_support_flag="none",
            doctor_admission_flow="scheduled",
        )
        prior = Case.objects.get(agency_record_number="AR-P7")
        eda_row = prior.procedures.get(procedure_type="eda")
        eda_row.doctor_reason = "razão EDA"
        eda_row.save(update_fields=["doctor_reason"])

        current = _current_v2_case(user, arn="AR-P7", detected=["eda", "colonoscopy"])

        role, _ = Role.objects.get_or_create(name="doctor")
        doctor = _make_user("doc_prior7")
        doctor.roles.add(role)
        client.force_login(doctor)
        session = client.session
        session["active_role"] = "doctor"
        session.save()

        response = client.get(f"/doctor/{current.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Seções EDA e Colonoscopia com decisões próprias.
        assert "Histórico Anterior por Procedimento" in content or "Caso Anterior" in content
        assert "EDA" in content
        assert "Colonoscopia" in content
        assert PRIOR_DECISION_DISPLAY["doctor_denied"] in content
        assert PRIOR_DECISION_DISPLAY["doctor_approved"] in content
        assert "razão EDA" in content


@pytest.mark.django_db
class TestDoctorQueueProcedureFilters:
    """R7: dimensão detectado (Pendentes) / autorizado (Decididos) + busca."""

    def _role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}_s3q@test.com", password="testpass123")
        user.roles.add(self._role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _pending_v2(self, nir: Any, *, detected: list[str], name: str) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="eda_colonoscopy" if len(detected) == 2 else detected[0],
            agency_record_number="REC-" + name,
            structured_data={"patient": {"name": name, "age": 50, "sex": "F"}},
        )
        for pt in ("eda", "colonoscopy"):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                detection_status="detected" if pt in detected else "not_detected",
            )
        return case

    def _decided_v2(self, doctor: Any, nir: Any, *, approved: list[str], name: str) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            doctor=doctor,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
            exam_type="eda_colonoscopy" if len(approved) == 2 else (approved[0] if approved else "eda"),
            agency_record_number="REC-" + name,
            structured_data={"patient": {"name": name, "age": 50, "sex": "F"}},
        )
        for pt in ("eda", "colonoscopy"):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                detection_status="detected" if pt in ("eda", "colonoscopy") else "not_detected",
                doctor_disposition="approved" if pt in approved else "denied",
            )
        return case

    def test_pending_cards_expose_detected_selection(self, client) -> None:
        nir = self._login(client, "nir")
        self._pending_v2(nir, detected=["eda"], name="Joao")
        self._pending_v2(nir, detected=["eda", "colonoscopy"], name="Maria")
        self._login(client, "doctor")
        response = client.get("/doctor/")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-proc-selection="eda"' in content
        assert 'data-proc-selection="eda_colonoscopy"' in content
        # Busca/polling preservados.
        assert "data-doctor-queue-search" in content
        assert "partials/queue/" in content
        # Cards mostram transformação quando o detectado diverge do declarado.
        assert "Detectado" in content

    def test_decided_cards_expose_approved_selection_with_none(self, client) -> None:
        doctor = self._login(client, "doctor")
        nir = User.objects.create_user(username="nir_s3q2@test.com", password="pw")
        nir.roles.add(self._role("nir"))
        self._decided_v2(doctor, nir, approved=["eda"], name="AprovadoEDA")
        denied = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            doctor=doctor,
            doctor_decision="deny",
            doctor_decided_at=timezone.now(),
            exam_type="eda",
            agency_record_number="REC-NEG",
            structured_data={"patient": {"name": "Negado", "age": 50, "sex": "F"}},
        )
        CaseProcedure.objects.create(
            case=denied,
            procedure_type="eda",
            declared_by_nir=True,
            detection_status="detected",
            doctor_disposition="denied",
        )
        response = client.get("/doctor/?tab=decided")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-proc-selection="eda"' in content
        assert 'data-proc-selection="none"' in content
        assert "Nenhum autorizado" in content

    def test_queue_html_offers_combined_and_none_options(self) -> None:
        html = QUEUE_HTML.read_text(encoding="utf-8")
        assert 'value="eda_colonoscopy"' in html
        assert 'data-exam-type-count="eda_colonoscopy"' in html
        assert 'value="none"' in html  # Nenhum autorizado (Decididos Hoje)
        # Opções legadas preservadas.
        assert 'value="all" checked' in html
        assert 'value="eda"' in html
        assert 'value="colonoscopy"' in html
        assert "data-doctor-queue-search" in html

    def test_queue_partial_exposes_procedure_selection_attribute(self) -> None:
        content_html = QUEUE_CONTENT_HTML.read_text(encoding="utf-8")
        assert "data-proc-selection" in content_html
        assert 'data-exam-type="{{ c.exam_type }}"' in content_html  # bridge preservado

    def test_js_handles_combined_and_none_selection(self) -> None:
        js = QUEUE_FILTER_JS.read_text(encoding="utf-8")
        # Filtra pela dimensão projetada com fallback para a ponte legada.
        assert "data-proc-selection" in js
        assert "data-exam-type" in js
        assert "eda_colonoscopy" in js
        assert "none" in js
        # Comportamento legado preservado (busca/limpar/afterSwap).
        assert "htmx:afterSwap" in js
        assert "clearFilter" in js


# ── Slice 009 (R2): relatório 1.1 deriva tipo sem ler a coluna ─────────────


@pytest.mark.django_db
class TestLegacyReportDerivesTypeFromPayload:
    """R2: schema 1.1 deriva ``procedure_type`` do payload histórico ou de
    uma única row declarada inequívoca; ambíguo/ausente é fail-closed
    (sem lookup, label neutro), nunca default EDA."""

    def _legacy_structured(self, *, exam_type: str | None, name: str = "P") -> dict[str, Any]:
        payload: dict[str, Any] = {"schema_version": "1.1", "patient": {"name": name, "age": 30, "sex": "M"}}
        if exam_type is not None:
            payload["preop_screening"] = {"exam_type": exam_type}
        return payload

    def test_preop_screening_drives_colonoscopy_report(self, django_user_model) -> None:
        user = _make_user("nir_r2a")
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2A",
            status=CaseStatus.WAIT_DOCTOR,
            # Ponte oposta ao payload: o tipo 1.1 deve vir do preop_screening.
            exam_type="eda",
            structured_data=self._legacy_structured(exam_type="colonoscopy"),
        )
        prepared = prepare_doctor_case_report(current)
        report = prepared.presenter.build_report()
        # Tipo derivado do payload, vencendo a ponte oposta — nunca default EDA.
        assert report["context"]["procedure"] == "procedimento solicitado: Colonoscopia"

    def test_single_declared_row_derives_type_when_payload_absent(self, django_user_model) -> None:
        user = _make_user("nir_r2b")
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2B",
            status=CaseStatus.WAIT_DOCTOR,
            # Ponte oposta à row declarada: o tipo 1.1 deve vir da row única.
            exam_type="eda",
            structured_data=self._legacy_structured(exam_type=None),
        )
        CaseProcedure.objects.create(
            case=current,
            procedure_type="colonoscopy",
            declared_by_nir=True,
        )
        prepared = prepare_doctor_case_report(current)
        report = prepared.presenter.build_report()
        assert report["context"]["procedure"] == "procedimento solicitado: Colonoscopia"

    def test_ambiguous_legacy_is_fail_closed_no_default_eda(self, django_user_model) -> None:
        """Sem preop_screening.exam_type e sem row inequívoca → neutro, nunca EDA."""
        user = _make_user("nir_r2c")
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2C",
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="eda",
            structured_data=self._legacy_structured(exam_type=None),
        )
        prepared = prepare_doctor_case_report(current)
        report = prepared.presenter.build_report()
        procedure_line = report["context"]["procedure"]
        # Nunca cai no default EDA; label neutro/fail-closed.
        assert "EDA" not in procedure_line
        assert "Colonoscopia" not in procedure_line

    def test_two_declared_rows_without_payload_is_neutral(self, django_user_model) -> None:
        """Duas rows declaradas (ambíguo) sem payload válido → neutro, nunca EDA."""
        user = _make_user("nir_r2c2")
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2C2",
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="eda",
            structured_data=self._legacy_structured(exam_type=None),
        )
        for procedure_type in ("eda", "colonoscopy"):
            CaseProcedure.objects.create(
                case=current,
                procedure_type=procedure_type,
                declared_by_nir=True,
            )
        prepared = prepare_doctor_case_report(current)
        report = prepared.presenter.build_report()
        procedure_line = report["context"]["procedure"]
        assert "EDA" not in procedure_line
        assert "Colonoscopia" not in procedure_line

    def test_ambiguous_legacy_does_not_run_prior_lookup(self, django_user_model) -> None:
        """Tipo ambíguo → nenhum lookup anterior (spy fail-closed), mesmo com ARN."""
        user = _make_user("nir_r2d")
        # Caso anterior negado do mesmo ARN (com row EDA negada).
        prior = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2D",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="motivo",
            doctor_decided_at=_now() - timedelta(days=1),
            structured_data=self._legacy_structured(exam_type=None),
        )
        CaseProcedure.objects.create(
            case=prior, procedure_type="eda", declared_by_nir=True, doctor_disposition="denied"
        )
        # Caso atual 1.1 ambíguo (sem preop_screening.exam_type e sem rows).
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2D",
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="eda",
            structured_data=self._legacy_structured(exam_type=None),
        )
        # Spy obrigatório (R3): o lookup anterior NÃO pode ser chamado para ambíguo.
        with patch("apps.doctor.reporting.lookup_prior_case_context") as spy_lookup:
            prepared = prepare_doctor_case_report(current)
            spy_lookup.assert_not_called()
        assert prepared.prior_sections == []
        assert prepared.prior_context is None

    def test_legacy_payload_is_not_rewritten(self, django_user_model) -> None:
        """Nenhum JSON 1.1 é reescrito: o structured_data permanece idêntico."""
        user = _make_user("nir_r2f")
        payload = self._legacy_structured(exam_type="colonoscopy")
        payload_snapshot = copy.deepcopy(payload)
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2F",
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="colonoscopy",
            structured_data=copy.deepcopy(payload),
        )
        CaseProcedure.objects.create(case=current, procedure_type="colonoscopy", declared_by_nir=True)
        prepare_doctor_case_report(current)
        # Rebusca por query (refresh_from_db colide com o campo FSM protegido).
        reloaded = Case.objects.get(pk=current.pk)
        assert reloaded.structured_data == payload_snapshot

    def test_legacy_case_keeps_single_prior_context_via_payload(self, django_user_model) -> None:
        """Caso 1.1 com tipo derivável mantém o prior context legado (single)."""
        user = _make_user("nir_r2e")
        legacy = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2E",
            status=CaseStatus.DOCTOR_DENIED,
            doctor_decision="deny",
            doctor_reason="motivo global",
            doctor_decided_at=_now() - timedelta(days=1),
            structured_data=self._legacy_structured(exam_type="eda"),
        )
        CaseProcedure.objects.create(
            case=legacy, procedure_type="eda", declared_by_nir=True, doctor_disposition="denied"
        )
        current = Case.objects.create(
            created_by=user,
            agency_record_number="AR-R2E",
            status=CaseStatus.WAIT_DOCTOR,
            exam_type="eda",
            structured_data=self._legacy_structured(exam_type="eda"),
        )
        prepared = prepare_doctor_case_report(current)
        assert prepared.prior_sections == []
        assert prepared.prior_context is not None
        assert prepared.prior_context.prior_case is not None
        assert prepared.prior_context.prior_case.prior_case_id == str(legacy.case_id)
