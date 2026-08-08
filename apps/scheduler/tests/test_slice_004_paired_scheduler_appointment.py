"""Slice 004 — CHD recebe conjunto autorizado e faz um agendamento casado.

Prova R1–R6:

- R1: cards/detalhe usam exclusivamente o conjunto aprovado (badge
  ``EDA + Colonoscopia · Agendamento casado``); transformação detectado→
  autorizado e razões médicas textuais visíveis quando divergem.
- R2: submit combinado reutiliza ``SchedulerDecisionForm`` e persiste
  exatamente um ``appointment_at``, uma decisão e uma transição.
- R3: POST manipulado não altera ``CaseProcedure`` (nenhum controle write).
- R4: o MESMO evento de confirmação/negativa (APPT_*) carrega o snapshot
  do conjunto aprovado ordenado + flag ``paired`` — sem evento extra,
  sem duplicar transição, sem texto clínico.
- R5: Pendentes (WAIT_APPT + notices + issues), Processados Hoje e
  Histórico usam a dimensão autorizada; opções Todos/EDA/Colonoscopia/
  Combinado; combinado conta uma vez; histórico sem termo limita 50 e
  preserva ordem.
- R6: locks/ownership inválidos bloqueiam; notices/issues/ACKs regressam
  sem duplicação pelos dois componentes.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import (
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.scheduler.views import _approved_snapshot
from tests.shared_case_fixtures import attach_procedure_projection

User = get_user_model()

REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_HTML = REPO_ROOT / "templates" / "scheduler" / "queue.html"
QUEUE_CONTENT_HTML = REPO_ROOT / "templates" / "scheduler" / "_queue_content.html"
CONFIRM_HTML = REPO_ROOT / "templates" / "scheduler" / "confirm.html"
HISTORICAL_HTML = REPO_ROOT / "templates" / "scheduler" / "historical_search.html"
QUEUE_FILTER_JS = REPO_ROOT / "static" / "js" / "scheduler_queue_filter.js"


def _create_role(name: str) -> Any:
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


@pytest.mark.django_db
class TestSchedulerPairedAppointment:
    """Fluxo principal: badge casado, snapshot e invariante de um horário."""

    # ── Helpers ─────────────────────────────────────────────────────

    def _login_as(self, client, role_name: str) -> Any:
        username = f"{role_name}@slice004.{uuid.uuid4().hex[:8]}.test"
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(_create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_case(
        self,
        nir: Any,
        *,
        status: str = CaseStatus.WAIT_APPT,
        exam_type: str = "eda",
        approved: tuple[str, ...] = (),
        detected: tuple[str, ...] = (),
        reasons: dict[str, str] | None = None,
        **kw: Any,
    ) -> Case:
        reasons = reasons or {}
        kw.setdefault(
            "structured_data",
            {"patient": {"name": f"Paciente {exam_type}", "age": 55, "gender": "F"}},
        )
        case = Case.objects.create(
            created_by=nir,
            status=status,
            exam_type=exam_type,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            **kw,
        )
        proc_types: tuple[str, ...] = ("eda", "colonoscopy") if exam_type == "eda_colonoscopy" else (exam_type,)
        for pt in proc_types:
            row = CaseProcedure.objects.create(case=case, procedure_type=pt, declared_by_nir=True)
            fields: list[str] = []
            if pt in detected:
                row.detection_status = "detected"
                fields.append("detection_status")
            if pt in approved:
                row.doctor_disposition = DoctorDisposition.APPROVED
                row.doctor_reason = reasons.get(pt, "")
                fields += ["doctor_disposition", "doctor_reason"]
            if fields:
                row.save(update_fields=fields)
        return case

    def _make_notice(self, nir: Any, *, exam_type: str, approved: tuple[str, ...]) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type=exam_type,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": f"Notice {exam_type}", "age": 60, "gender": "F"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        for pt in ("eda", "colonoscopy") if exam_type == "eda_colonoscopy" else (exam_type,):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                doctor_disposition=DoctorDisposition.APPROVED if pt in approved else "pending",
            )
        return case

    def _make_issue(self, nir: Any, *, exam_type: str, approved: tuple[str, ...]) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type=exam_type,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            post_schedule_issue_status="opened",
            post_acceptance_issue_context="operational_notice",
            structured_data={"patient": {"name": f"Issue {exam_type}", "age": 50, "gender": "M"}},
        )
        for pt in ("eda", "colonoscopy") if exam_type == "eda_colonoscopy" else (exam_type,):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                doctor_disposition=DoctorDisposition.APPROVED if pt in approved else "pending",
            )
        return case

    def _claim_lock(self, case_id, scheduler: Any) -> str:
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=scheduler,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True
        return str(result.token)

    def _submit_payload(self, *, token: str, decision: str = "confirm", **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": decision,
            "appointment_date": "2026-06-01",
            "appointment_time": "09:00",
            "appointment_location": "Hospital Central - Sala 1",
            "notes": "Trazer jejum de 8h.",
            "reason": "Sem vaga na agenda." if decision == "deny" else "",
            "lock_token": token,
        }
        payload.update(extra)
        return payload

    # ── R1: badge casado no card pendente ───────────────────────────

    def test_combined_pending_card_shows_paired_badge(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
        )
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        # R1: badge textual "EDA + Colonoscopia · Agendamento casado".
        assert "EDA + Colonoscopia · Agendamento casado" in content
        # Filtro/JS: dimensão autorizada projetada no card.
        assert 'data-approved-selection="eda_colonoscopy"' in content
        # Ponte legada preservada (regressão test_exam_type_filters).
        assert 'data-exam-type="eda_colonoscopy"' in content

    # ── R1: transformação detectado→autorizado + razões no detalhe ──

    def test_transformation_and_reasons_visible(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            detected=("eda",),  # apenas EDA detectada
            approved=("eda", "colonoscopy"),  # Colonoscopia incluída pelo médico
            reasons={"colonoscopy": "Suspeita de doença inflamatória na anamnese."},
        )
        self._login_as(client, "scheduler")
        # Comparação no card da fila.
        content = client.get("/scheduler/").content.decode()
        assert "Detectado: EDA" in content
        assert "Autorizado: EDA + Colonoscopia" in content
        # Razão médica textual no detalhe de confirmação.
        scheduler_user = User.objects.get(username__startswith="scheduler@slice004.")
        self._claim_lock(case.case_id, scheduler_user)
        confirm = client.get(f"/scheduler/{case.case_id}/").content.decode()
        assert "EDA + Colonoscopia · Agendamento casado" in confirm
        assert "Suspeita de doença inflamatória na anamnese." in confirm

    # ── F2: fallback consistente quando não há aprovados ────────────

    def test_snapshot_fail_closed_without_approved_rows(self) -> None:
        """R4: sem rows aprovadas, fail-closed — badge vazio e key "none",
        independentemente da ponte ``exam_type`` ou ``doctor_decision``.

        O fallback transitivo (declarado/ponte) foi removido no Slice 009:
        caso sem autorização projetada não aparece nos buckets por tipo.
        """
        nir = User.objects.create_user(username=f"nir-slice009r4.{uuid.uuid4().hex[:8]}.test")
        nir.roles.add(_create_role("nir"))
        # Sem aprovados, mesmo com ponte eda e doctor_decision=accept → fail-closed.
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            exam_type="eda",
            doctor_decision="accept",
            structured_data={"patient": {"name": "Sem Aprovado", "age": 50, "gender": "F"}},
        )
        snap = _approved_snapshot(case)
        assert snap["approved_label"] == ""
        assert snap["approved_selection_key"] == "none"
        # Com row aprovada → label/key coerentes pela row.
        CaseProcedure.objects.create(
            case=case,
            procedure_type="eda",
            declared_by_nir=True,
            doctor_disposition=DoctorDisposition.APPROVED,
        )
        snap_ok = _approved_snapshot(case)
        assert snap_ok["approved_label"] == "EDA"
        assert snap_ok["approved_selection_key"] == "eda"

    # ── F3: confirm sem aprovados não renderiza card vazio ──────────

    def test_confirm_page_hides_empty_authorized_card(self, client) -> None:
        """F3: caso sem aprovados não renderiza o card 'Procedimentos Autorizados'."""
        nir = self._login_as(client, "nir")
        # Estado defensivo: sem rows e sem fallback válido (exam_type inválido)
        # → approved_label vazio → card oculto (regressão: combinado continua visível).
        empty_case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            exam_type="bogus",
            doctor_decision="accept",
            structured_data={"patient": {"name": "Sem Autorizado", "age": 50, "gender": "F"}},
        )
        combined = self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
        )
        self._login_as(client, "scheduler")
        content = client.get(f"/scheduler/{empty_case.case_id}/").content.decode()
        assert "Procedimentos Autorizados" not in content
        content = client.get(f"/scheduler/{combined.case_id}/").content.decode()
        assert "Procedimentos Autorizados" in content
        assert "EDA + Colonoscopia · Agendamento casado" in content

    # ── R2/R3/R4: confirm combinado → 1 appointment/event/transição ──

    def test_combined_confirm_single_appointment_event_transition(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            self._submit_payload(
                token=token,
                # R3: campos manipulados não criam segunda agenda/row.
                procedure_eda="approved",
                procedure_colonoscopy="approved",
                appointment_date2="2026-07-01",
            ),
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        # R2: uma transição, um horário, uma decisão.
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "confirmed"
        assert case.appointment_at is not None
        assert case.appointment_instructions == "Trazer jejum de 8h."
        # R2: um único evento operacional (sem duplicar por componente).
        assert CaseEvent.objects.filter(case=case, event_type="APPT_CONFIRMED").count() == 1
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").count() == 1
        # R3: nenhuma row criada/alterada por POST manipulado.
        rows = CaseProcedure.objects.filter(case=case).order_by("procedure_type")
        assert list(rows.values_list("procedure_type", "doctor_disposition")) == [
            (ProcedureType.COLONOSCOPY, DoctorDisposition.APPROVED),
            (ProcedureType.EDA, DoctorDisposition.APPROVED),
        ]

    # ── R4: snapshot no MESMO evento de confirmação ─────────────────

    def test_combined_confirm_snapshot_payload(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)
        client.post(f"/scheduler/{case.case_id}/submit/", self._submit_payload(token=token))

        payload = CaseEvent.objects.get(case=case, event_type="APPT_CONFIRMED").payload
        assert payload["approved_procedures"] == ["eda", "colonoscopy"]
        assert payload["paired"] is True
        # Payload sem texto clínico integral.
        assert not any(isinstance(v, str) and len(v) > 40 for v in payload.values())

    # ── R2/R4: negativa preserva motivo e snapshot no mesmo evento ──

    def test_deny_snapshot_includes_approved_set(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            self._submit_payload(token=token, decision="deny"),
        )
        assert response.status_code == 302

        case = Case.objects.get(pk=case.case_id)
        assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert case.appointment_status == "denied"
        assert case.appointment_reason == "Sem vaga na agenda."
        payload = CaseEvent.objects.get(case=case, event_type="APPT_DENIED").payload
        assert payload["approved_procedures"] == ["eda", "colonoscopy"]
        assert payload["paired"] is True

    # ── R6: locks inválidos bloqueiam sem escrever nada ─────────────

    def test_invalid_lock_blocks_submit(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_case(
            nir,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
        )
        scheduler = self._login_as(client, "scheduler")
        self._claim_lock(case.case_id, scheduler)

        # Sem token: re-renderiza com erro e não transiciona.
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            self._submit_payload(token=""),
        )
        assert response.status_code == 200
        assert "Sua reserva para este caso expirou" in response.content.decode()
        assert Case.objects.get(pk=case.case_id).status == CaseStatus.WAIT_APPT

        # Token inválido (uuid diferente do lock detido): bloqueia.
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            self._submit_payload(token=str(uuid.uuid4())),
        )
        assert response.status_code == 200
        assert "Token de lock inválido." in response.content.decode()
        assert Case.objects.get(pk=case.case_id).status == CaseStatus.WAIT_APPT
        assert CaseProcedure.objects.filter(case=case, doctor_disposition=DoctorDisposition.APPROVED).count() == 2


@pytest.mark.django_db
class TestSchedulerPairedQueueAndHistory:
    """Filtros/contadores por autorizado (R5) e regressões de grupos (R6)."""

    def _login_as(self, client, role_name: str) -> Any:
        username = f"{role_name}@slice004q.{uuid.uuid4().hex[:8]}.test"
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(_create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _make_case(self, nir: Any, **kw: Any) -> Case:
        from apps.cases.models import DetectionStatus

        kw.setdefault("status", CaseStatus.WAIT_APPT)
        kw.setdefault("doctor_admission_flow", "scheduled")
        kw.setdefault(
            "structured_data",
            {"patient": {"name": f"Paciente {kw.get('exam_type', 'eda')}", "age": 55, "gender": "F"}},
        )
        approved = tuple(kw.pop("approved", ()))
        detected = tuple(kw.pop("detected", ()))
        reasons = kw.pop("reasons", {})
        case = Case.objects.create(created_by=nir, doctor_decision="accept", **kw)
        proc_types: tuple[str, ...] = (
            ("eda", "colonoscopy") if case.exam_type == "eda_colonoscopy" else (case.exam_type,)
        )
        for pt in proc_types:
            row = CaseProcedure.objects.create(case=case, procedure_type=pt, declared_by_nir=True)
            fields: list[str] = []
            if pt in detected:
                row.detection_status = DetectionStatus.DETECTED
                fields.append("detection_status")
            if pt in approved:
                row.doctor_disposition = DoctorDisposition.APPROVED
                row.doctor_reason = reasons.get(pt, "")
                fields += ["doctor_disposition", "doctor_reason"]
            if fields:
                row.save(update_fields=fields)
        return case

    # ── R5: contagens pendentes por combinado, uma vez por grupo ────

    def test_pending_counts_combined_once_across_three_groups(self, client) -> None:
        nir = self._login_as(client, "nir")
        # WAIT_APPT combinado + notice combinado + issue combinado + EDA simples.
        self._make_case(nir, exam_type="eda_colonoscopy", approved=("eda", "colonoscopy"))
        notice = self._make_notice(nir, exam_type="eda_colonoscopy", approved=("eda", "colonoscopy"))
        self._make_issue(nir, exam_type="eda_colonoscopy", approved=("eda", "colonoscopy"))
        self._make_case(nir, exam_type="eda", approved=("eda",))
        self._login_as(client, "scheduler")

        content = client.get("/scheduler/").content.decode()
        # 4 cards no escopo; combinado conta UMA vez por grupo (3 grupos).
        assert content.count("data-scheduler-queue-card") == 4
        assert 'data-exam-type-count="all">4<' in content
        assert 'data-exam-type-count="eda_colonoscopy">3<' in content
        assert 'data-exam-type-count="eda">1<' in content
        assert 'data-exam-type-count="colonoscopy">0<' in content
        # Badge casado presente em cada grupo.
        assert content.count("Agendamento casado") == 3
        # ACK de notice combinado continua operacional (R6).
        assert f"/scheduler/{notice.case_id}/immediate-ack/" in content

    def _make_notice(self, nir: Any, *, exam_type: str, approved: tuple[str, ...]) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type=exam_type,
            doctor_decision="accept",
            doctor_admission_flow="immediate",
            structured_data={"patient": {"name": f"Notice {exam_type}", "age": 60, "gender": "F"}},
        )
        CaseEvent.objects.create(
            case=case,
            actor_type="human",
            actor=nir,
            event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
            timestamp=timezone.now(),
        )
        for pt in ("eda", "colonoscopy") if exam_type == "eda_colonoscopy" else (exam_type,):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                doctor_disposition=DoctorDisposition.APPROVED if pt in approved else "pending",
            )
        return case

    def _make_issue(self, nir: Any, *, exam_type: str, approved: tuple[str, ...]) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type=exam_type,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            post_schedule_issue_status="opened",
            post_acceptance_issue_context="operational_notice",
            structured_data={"patient": {"name": f"Issue {exam_type}", "age": 50, "gender": "M"}},
        )
        for pt in ("eda", "colonoscopy") if exam_type == "eda_colonoscopy" else (exam_type,):
            CaseProcedure.objects.create(
                case=case,
                procedure_type=pt,
                declared_by_nir=True,
                doctor_disposition=DoctorDisposition.APPROVED if pt in approved else "pending",
            )
        return case

    # ── R5: Processados Hoje e Histórico por combinado ──────────────

    def test_processed_and_historical_show_combined(self, client) -> None:
        scheduler = self._login_as(client, "scheduler")
        nir = User.objects.create_user(username=f"nir-slice004p.{uuid.uuid4().hex[:8]}.test")
        nir.roles.add(_create_role("nir"))
        self._make_case(
            nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            scheduler=scheduler,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
        )
        # Processados Hoje: badge casado + dimensão autorizada no card.
        content = client.get("/scheduler/?tab=processed").content.decode()
        assert "EDA + Colonoscopia · Agendamento casado" in content
        assert 'data-approved-selection="eda_colonoscopy"' in content
        assert 'data-exam-type-count="eda_colonoscopy">1<' in content
        # Histórico: filtro combinado (server-side) retorna o caso.
        content = client.get("/scheduler/historical/?exam_type=eda_colonoscopy").content.decode()
        assert "EDA + Colonoscopia" in content

    # ── R5: histórico combinado sem termo, top 50 e ordem ───────────

    def test_historical_combined_without_rows_not_listed(self, client) -> None:
        """R4: caso sem rows aprovadas NÃO aparece no bucket Combinado.

        O fallback legado ``filter(exam_type=eda_colonoscopy, procedures__isnull=True)``
        foi removido (Slice 009): buckets exigem rows aprovadas; caso sem
        autorização projetada não aparece. Apenas o caso com rows é listado.
        """
        nir = self._login_as(client, "nir")
        Case.objects.create(
            created_by=nir,
            status=CaseStatus.CLEANED,
            exam_type="eda_colonoscopy",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            agency_record_number="HC-LEG-COMB",
            structured_data={"patient": {"name": "Legado Combinado", "age": 61, "gender": "M"}},
        )
        # Caso combinado com rows aprovadas — aparece normalmente.
        self._make_case(
            nir,
            status=CaseStatus.CLEANED,
            exam_type="eda_colonoscopy",
            approved=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            appointment_status="confirmed",
            agency_record_number="HC-ROW-COMB",
            structured_data={"patient": {"name": "Row Combinado", "age": 62, "gender": "F"}},
        )
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/historical/?exam_type=eda_colonoscopy").content.decode()
        assert "HC-LEG-COMB" not in content
        assert "HC-ROW-COMB" in content

    # ── R5: histórico combinado sem termo, top 50 e ordem ───────────

    def test_historical_combined_without_term_limits_50(self, client) -> None:
        nir = self._login_as(client, "nir")
        cases: list[Case] = []
        now = timezone.now()
        for i in range(55):
            cases.append(
                self._make_case(
                    nir,
                    status=CaseStatus.CLEANED,
                    exam_type="eda_colonoscopy",
                    approved=("eda", "colonoscopy"),
                    detected=("eda", "colonoscopy"),
                    appointment_status="confirmed",
                    agency_record_number=f"HC-{i:03d}",
                    structured_data={"patient": {"name": f"Paciente {i:03d}", "age": 50, "gender": "F"}},
                )
            )
        # created_at explícito para ordem determinística (auto_now_add).
        for i, case in enumerate(cases):
            Case.objects.filter(pk=case.pk).update(created_at=now - timedelta(minutes=55 - i))
        self._login_as(client, "scheduler")

        content = client.get("/scheduler/historical/?exam_type=eda_colonoscopy").content.decode()
        assert "50 casos" in content
        assert "HC-054" in content  # mais recente incluído
        assert "HC-004" not in content  # mais antigo além do top 50

    # ── R6: notice combinado não duplica e ACK persiste ─────────────

    def test_notice_ack_no_duplication_for_combined(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_notice(nir, exam_type="eda_colonoscopy", approved=("eda", "colonoscopy"))
        self._login_as(client, "scheduler")

        # Combinado aparece UMA vez na fila (dois componentes não duplicam).
        content = client.get("/scheduler/").content.decode()
        assert content.count("data-scheduler-queue-card") == 1
        # ACK continua operando e remove o card.
        response = client.post(f"/scheduler/{case.case_id}/immediate-ack/")
        assert response.status_code == 302
        content = client.get("/scheduler/").content.decode()
        assert "data-scheduler-queue-card" not in content
        # Ciência registrada UMA vez no histórico de hoje.
        content = client.get("/scheduler/?tab=processed").content.decode()
        assert content.count("Ciência confirmada") == 1


class TestSchedulerPairedStatic:
    """Inspeção estática do filtro/opções Combinado (R5) — sem runner JS."""

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_queue_html_offers_combined_option(self) -> None:
        html = self._read(QUEUE_HTML)
        assert 'value="eda_colonoscopy"' in html
        assert "Combinado" in html

    def test_queue_cards_expose_approved_selection(self) -> None:
        html = self._read(QUEUE_CONTENT_HTML)
        assert 'data-approved-selection="{{ c.approved_selection_key }}"' in html
        # Badge casado textual renderizado via approved_label + paired_label.
        assert "paired_label" in html
        assert "transformation_approved" in html

    def test_historical_html_offers_combined_and_keeps_legacy_label(self) -> None:
        html = self._read(HISTORICAL_HTML)
        assert 'value="eda_colonoscopy"' in html
        # Regressão: teste estático existente exige a string exam_type_label.
        assert "exam_type_label" in html

    def test_confirm_html_shows_approved_and_reasons(self) -> None:
        html = self._read(CONFIRM_HTML)
        assert "paired_label" in html
        assert "approved_label" in html
        assert "procedure_reasons" in html

    def test_js_handles_combined_selection(self) -> None:
        js = self._read(QUEUE_FILTER_JS)
        assert "eda_colonoscopy" in js
        assert "data-approved-selection" in js
        assert "EDA + Colonoscopia" in js


@pytest.mark.django_db
class TestSchedulerExcludesAndBlocksUnauthorized:
    """Slice 009-B — todos os universos/ações CHD exigem aprovação projetada.

    Caso sem row ``CaseProcedure.doctor_disposition=approved`` não aparece em
    nenhum universo/contador CHD, não recebe CTA de agendamento;
    ``scheduler_confirm`` recusa antes de adquirir lock e ``scheduler_submit``
    revalida sob lock e falha fail-closed (sem transição FSM, sem
    ``appointment_at``, sem evento com ``approved_procedures=[]`` e sem lock
    abandonado). Combinado exige as duas aprovações e conta uma vez.
    """

    def _login_as(self, client, role_name: str) -> Any:
        username = f"{role_name}@slice009b.{uuid.uuid4().hex[:8]}.test"
        user = User.objects.create_user(username=username, password="testpass123")
        user.roles.add(_create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    # ── Helpers de fixtures (três dimensões explícitas; sem ler case.exam_type) ──
    def _make_wait_appt(
        self,
        nir: Any,
        *,
        name: str,
        declared: tuple[str, ...],
        detected: tuple[str, ...],
        approved: tuple[str, ...],
        exam_type: str = "eda",
    ) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            exam_type=exam_type,
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            structured_data={"patient": {"name": name, "age": 50, "gender": "F"}},
        )
        return attach_procedure_projection(case, declared=declared, detected=detected, approved=approved)

    def _make_notice(
        self,
        nir: Any,
        *,
        name: str,
        declared: tuple[str, ...],
        detected: tuple[str, ...],
        approved: tuple[str, ...],
    ) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type="eda",
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
        return attach_procedure_projection(case, declared=declared, detected=detected, approved=approved)

    def _make_issue(
        self,
        nir: Any,
        *,
        name: str,
        declared: tuple[str, ...],
        detected: tuple[str, ...],
        approved: tuple[str, ...],
    ) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type="eda",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            post_schedule_issue_status="opened",
            post_acceptance_issue_context="operational_notice",
            structured_data={"patient": {"name": name, "age": 50, "gender": "M"}},
        )
        return attach_procedure_projection(case, declared=declared, detected=detected, approved=approved)

    def _make_processed(
        self,
        scheduler: Any,
        *,
        name: str,
        declared: tuple[str, ...],
        detected: tuple[str, ...],
        approved: tuple[str, ...],
    ) -> Case:
        case = Case.objects.create(
            created_by=scheduler,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            exam_type="eda",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            scheduler=scheduler,
            appointment_status="confirmed",
            appointment_decided_at=timezone.now(),
            structured_data={"patient": {"name": name, "age": 55, "gender": "F"}},
        )
        return attach_procedure_projection(case, declared=declared, detected=detected, approved=approved)

    def _make_historical(
        self,
        nir: Any,
        *,
        agency: str,
        name: str,
        declared: tuple[str, ...],
        detected: tuple[str, ...],
        approved: tuple[str, ...],
    ) -> Case:
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.CLEANED,
            exam_type="eda",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            agency_record_number=agency,
            structured_data={"patient": {"name": name, "age": 61, "gender": "M"}},
        )
        return attach_procedure_projection(case, declared=declared, detected=detected, approved=approved)

    def _claim_lock(self, case_id, scheduler: Any) -> str:
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=scheduler,
            expected_status=CaseStatus.WAIT_APPT,
            context="scheduler_confirm",
            role="scheduler",
        )
        assert result.acquired is True
        return str(result.token)

    def _submit_payload(self, *, token: str, decision: str = "confirm", **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": decision,
            "appointment_date": "2026-06-01",
            "appointment_time": "09:00",
            "appointment_location": "Hospital Central - Sala 1",
            "notes": "Trazer jejum de 8h.",
            "reason": "Sem vaga na agenda." if decision == "deny" else "",
            "lock_token": token,
        }
        payload.update(extra)
        return payload

    # ── R1: WAIT_APPT sem aprovado excluído da fila/contador/CTA ──────
    def test_unauthorized_wait_appt_excluded_from_pending(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_wait_appt(
            nir,
            name="Autorizado Pendente",
            declared=("eda",),
            detected=("eda",),
            approved=("eda",),
        )
        # INVÁLIDA intencional: WAIT_APPT sem rows aprovadas.
        unauthorized = self._make_wait_appt(
            nir,
            name="Sem Aprovado Pendente",
            declared=(),
            detected=(),
            approved=(),
        )
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert "Autorizado Pendente" in content
        assert "Sem Aprovado Pendente" not in content
        # "Todos" conta somente o autorizado (1, não 2).
        assert 'data-exam-type-count="all">1<' in content
        assert 'data-exam-type-count="all">2<' not in content
        # Sem CTA de agendamento para o caso não autorizado.
        assert f"/scheduler/{unauthorized.case_id}/" not in content

    # ── R1: notice operacional sem aprovado excluída ─────────────────
    def test_unauthorized_notice_excluded(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_notice(nir, name="Notice Autorizada", declared=("eda",), detected=("eda",), approved=("eda",))
        self._make_notice(nir, name="Notice Sem Aprovado", declared=(), detected=(), approved=())
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert "Notice Autorizada" in content
        assert "Notice Sem Aprovado" not in content

    # ── R1: issue operacional sem aprovado excluída ──────────────────
    def test_unauthorized_issue_excluded(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_issue(nir, name="Issue Autorizada", declared=("eda",), detected=("eda",), approved=("eda",))
        self._make_issue(nir, name="Issue Sem Aprovado", declared=(), detected=(), approved=())
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert "Issue Autorizada" in content
        assert "Issue Sem Aprovado" not in content

    # ── R1: processado hoje sem aprovado excluído ────────────────────
    def test_unauthorized_processed_excluded(self, client) -> None:
        scheduler = self._login_as(client, "scheduler")
        self._make_processed(scheduler, name="Proc Autorizado", declared=("eda",), detected=("eda",), approved=("eda",))
        self._make_processed(scheduler, name="Proc Sem Aprovado", declared=(), detected=(), approved=())
        content = client.get("/scheduler/?tab=processed").content.decode()
        assert "Proc Autorizado" in content
        assert "Proc Sem Aprovado" not in content

    # ── R1: ciência reconhecida de caso sem aprovado excluída ────────
    def test_unauthorized_acknowledged_notice_excluded(self, client) -> None:
        nir = self._login_as(client, "nir")
        authorized = self._make_notice(
            nir, name="Ack Autorizada", declared=("eda",), detected=("eda",), approved=("eda",)
        )
        unauthorized = self._make_notice(nir, name="Ack Sem Aprovado", declared=(), detected=(), approved=())
        self._login_as(client, "scheduler")
        # Ambos recebem ACK (o ACK não depende de aprovação).
        assert client.post(f"/scheduler/{authorized.case_id}/immediate-ack/").status_code == 302
        assert client.post(f"/scheduler/{unauthorized.case_id}/immediate-ack/").status_code == 302
        content = client.get("/scheduler/?tab=processed").content.decode()
        assert "Ack Autorizada" in content
        assert "Ack Sem Aprovado" not in content

    # ── R1: histórico exam_type=all e busca por termo excluem sem aprovado
    def test_unauthorized_historical_excluded_from_all_and_term(self, client) -> None:
        nir = self._login_as(client, "nir")
        self._make_historical(
            nir,
            agency="HIST-AUTH",
            name="Hist Autorizado",
            declared=("eda",),
            detected=("eda",),
            approved=("eda",),
        )
        self._make_historical(nir, agency="HIST-NOAP", name="Hist Sem Aprovado", declared=(), detected=(), approved=())
        self._login_as(client, "scheduler")
        # "all" + termo: o predicado de aprovação é aplicado à base; o caso
        # sem aprovado não aparece (estado vazio puro é preservado por R6).
        all_content = client.get("/scheduler/historical/?exam_type=all&q=Hist").content.decode()
        assert "HIST-AUTH" in all_content
        assert "HIST-NOAP" not in all_content
        # Busca apenas por termo também aplica o predicado.
        term_content = client.get("/scheduler/historical/?q=Hist").content.decode()
        assert "HIST-AUTH" in term_content
        assert "HIST-NOAP" not in term_content

    # ── R2: confirm recusa sem aprovado antes de adquirir lock ───────
    def test_confirm_rejects_unauthorized_without_lock(self, client) -> None:
        nir = self._login_as(client, "nir")
        unauthorized = self._make_wait_appt(nir, name="Confirm Sem Aprovado", declared=(), detected=(), approved=())
        self._login_as(client, "scheduler")
        response = client.get(f"/scheduler/{unauthorized.case_id}/")
        assert response.status_code == 404
        refreshed = Case.objects.get(pk=unauthorized.case_id)
        # Lock NÃO adquirido (fail-closed antes do lock).
        assert refreshed.locked_by_id is None

    # ── R2: submit revalida sob lock e falha sem efeitos/lock abandonado ──
    def test_submit_fail_closed_when_approval_removed(self, client) -> None:
        nir = self._login_as(client, "nir")
        case = self._make_wait_appt(
            nir, name="Race Sem Aprovado", declared=("eda",), detected=("eda",), approved=("eda",)
        )
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)
        # Race: aprovação removida entre GET e POST.
        CaseProcedure.objects.filter(case=case, doctor_disposition=DoctorDisposition.APPROVED).delete()
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            self._submit_payload(token=token),
        )
        assert response.status_code == 302  # redirect seguro p/ fila
        refreshed = Case.objects.get(pk=case.case_id)
        # Nenhuma transição FSM.
        assert refreshed.status == CaseStatus.WAIT_APPT
        # Nenhum campo de agendamento novo.
        assert refreshed.appointment_at is None
        assert refreshed.appointment_status not in {"confirmed", "denied"}
        assert refreshed.appointment_decided_at is None
        assert refreshed.scheduler_id is None
        # Nenhum evento APPT_* (logo, nenhum com approved_procedures=[]).
        assert not CaseEvent.objects.filter(case=case, event_type__in=["APPT_CONFIRMED", "APPT_DENIED"]).exists()
        # Lock liberado (não abandonado).
        assert refreshed.locked_by_id is None

    # ── R4: combinado exige as duas aprovações e conta uma vez ───────
    def test_combined_requires_both_approved(self, client) -> None:
        nir = self._login_as(client, "nir")
        # INVÁLIDA intencional: combinado sem nenhuma aprovação.
        self._make_wait_appt(
            nir,
            name="Combinado Sem Aprovado",
            declared=(),
            detected=(),
            approved=(),
            exam_type="eda_colonoscopy",
        )
        # Combinado com ambas aprovadas — aparece uma vez.
        self._make_wait_appt(
            nir,
            name="Combinado Autorizado",
            declared=("eda", "colonoscopy"),
            detected=("eda", "colonoscopy"),
            approved=("eda", "colonoscopy"),
            exam_type="eda_colonoscopy",
        )
        self._login_as(client, "scheduler")
        content = client.get("/scheduler/").content.decode()
        assert content.count("data-scheduler-queue-card") == 1
        assert "Combinado Autorizado" in content
        assert "Combinado Sem Aprovado" not in content
        assert 'data-exam-type-count="eda_colonoscopy">1<' in content

    # ── R2 (correção 009-B): intercorrência direta também é fail-closed ──
    def _make_psi_case(
        self,
        nir: Any,
        *,
        name: str,
        declared: tuple[str, ...],
        detected: tuple[str, ...],
        approved: tuple[str, ...],
    ) -> Case:
        """Cria WAIT_APPT com intercorrência scheduled (PSI) aberta.

        Quando os três conjuntos são vazios, é uma fixture INVÁLIDA intencional:
        caso excluído dos universos CHD que ainda assim não pode ser aberto por
        URL direta (bypass PSI que a correção fecha).
        """
        case = Case.objects.create(
            created_by=nir,
            status=CaseStatus.WAIT_APPT,
            exam_type="eda",
            doctor_decision="accept",
            doctor_admission_flow="scheduled",
            appointment_status="confirmed",
            appointment_at=timezone.now(),
            post_schedule_issue_status="opened",
            post_schedule_issue_reason="reschedule_request",
            post_acceptance_issue_context="scheduled",
            post_acceptance_issue_cycle_id=uuid.uuid4(),
            structured_data={"patient": {"name": name, "age": 50, "gender": "F"}},
        )
        return attach_procedure_projection(case, declared=declared, detected=detected, approved=approved)

    def test_psi_confirm_rejects_unauthorized_without_lock(self, client) -> None:
        """GET de intercorrência sem approved retorna 404 e não adquire lock."""
        nir = self._login_as(client, "nir")
        # INVÁLIDA intencional: PSI aberta e ZERO rows aprovadas.
        case = self._make_psi_case(nir, name="PSI Sem Aprovado", declared=(), detected=(), approved=())
        self._login_as(client, "scheduler")
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 404
        refreshed = Case.objects.get(pk=case.case_id)
        # Lock NÃO adquirido (fail-closed antes do lock).
        assert refreshed.locked_by_id is None

    def test_psi_submit_fail_closed_when_approval_removed(self, client) -> None:
        """POST de intercorrência com aprovação removida falha sem efeitos e libera lock."""
        nir = self._login_as(client, "nir")
        case = self._make_psi_case(nir, name="PSI Race", declared=("eda",), detected=("eda",), approved=("eda",))
        scheduler = self._login_as(client, "scheduler")
        token = self._claim_lock(case.case_id, scheduler)
        # Race: aprovação removida entre GET/claim e POST.
        CaseProcedure.objects.filter(case=case, doctor_disposition=DoctorDisposition.APPROVED).delete()
        # Sentinela: snapshot completo do estado do caso antes do POST (fail-closed
        # não pode mutar nenhum campo de domínio/agenda/intercorrência/contexto).
        before = Case.objects.get(pk=case.case_id)
        snapshot_before = {
            "status": before.status,
            "scheduler_id": before.scheduler_id,
            "appointment_status": before.appointment_status,
            "appointment_at": before.appointment_at,
            "appointment_location": before.appointment_location,
            "appointment_instructions": before.appointment_instructions,
            "appointment_reason": before.appointment_reason,
            "appointment_decided_at": before.appointment_decided_at,
            "post_schedule_issue_status": before.post_schedule_issue_status,
            "post_schedule_issue_reason": before.post_schedule_issue_reason,
            "post_schedule_issue_message": before.post_schedule_issue_message,
            "post_schedule_issue_response_action": before.post_schedule_issue_response_action,
            "post_schedule_issue_response_message": before.post_schedule_issue_response_message,
            "post_schedule_issue_responded_by_id": before.post_schedule_issue_responded_by_id,
            "post_schedule_issue_responded_at": before.post_schedule_issue_responded_at,
            "post_acceptance_issue_context": before.post_acceptance_issue_context,
            "post_acceptance_issue_cycle_id": before.post_acceptance_issue_cycle_id,
        }
        # Conta somente eventos de domínio (exclui ciclo de vida do lock, que
        # pode registrar WORK_LOCK_RELEASED ao liberar a reserva).
        lock_lifecycle = {"WORK_LOCK_CLAIMED", "WORK_LOCK_RELEASED", "WORK_LOCK_RENEWED", "WORK_LOCK_EXPIRED"}
        domain_before = CaseEvent.objects.filter(case=case).exclude(event_type__in=lock_lifecycle).count()

        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {"psi_action": "maintain", "psi_response_message": "Mantido.", "lock_token": token},
        )
        assert response.status_code == 302  # redirect seguro p/ fila

        after = Case.objects.get(pk=case.case_id)
        # Nenhum campo de domínio/agenda/intercorrência/contexto é mutado.
        for field, value in snapshot_before.items():
            assert getattr(after, field) == value, (
                f"{field} mutado no fail-closed: {value!r} → {getattr(after, field)!r}"
            )
        # Nenhum evento de domínio (resposta/FSM/agenda) criado; WORK_LOCK_RELEASED
        # (ciclo de vida do lock) é o único permitido.
        domain_after = CaseEvent.objects.filter(case=case).exclude(event_type__in=lock_lifecycle).count()
        assert domain_after == domain_before
        forbidden_events = [
            "POST_ACCEPTANCE_ISSUE_RESPONDED",
            "APPT_CONFIRMED",
            "APPT_DENIED",
            "SCHEDULER_PAIRED_APPOINTMENT_CONFIRMED",
            "FINAL_REPLY_POSTED",
        ]
        assert not CaseEvent.objects.filter(case=case, event_type__in=forbidden_events).exists()
        # Lock liberado (não abandonado).
        assert after.locked_by_id is None

    # ── C2: semântica de detecção do helper compartilhado ───────────
    def test_helper_approved_not_detected_persists_not_detected(self, client) -> None:
        """Aprovação de procedimento NÃO detectado persiste ``NOT_DETECTED``.

        Projeção normalizada: row já decidida (approved/denied) e ausente de
        ``detected`` fica ``NOT_DETECTED``; apenas row ainda não analisada
        (somente declarada) pode permanecer ``PENDING``.
        """
        nir = self._login_as(client, "nir")
        case = Case.objects.create(created_by=nir, status=CaseStatus.WAIT_APPT, exam_type="colonoscopy")
        # Colonoscopia declarada e autorizada, mas NÃO detectada (inclusão médica).
        attach_procedure_projection(
            case,
            declared=("colonoscopy",),
            detected=(),
            approved=("colonoscopy",),
            reasons={"colonoscopy": "Inclusão médica por critério clínico"},
        )
        row = CaseProcedure.objects.get(case=case, procedure_type="colonoscopy")
        assert row.doctor_disposition == DoctorDisposition.APPROVED
        # Helper atual grava PENDING; o correto downstream é NOT_DETECTED.
        assert row.detection_status == DetectionStatus.NOT_DETECTED

        # Aprovação não detectada SEM razão → ValueError (contrato de domínio).
        case_no_reason = Case.objects.create(created_by=nir, status=CaseStatus.WAIT_APPT, exam_type="colonoscopy")
        with pytest.raises(ValueError):
            attach_procedure_projection(
                case_no_reason, declared=("colonoscopy",), detected=(), approved=("colonoscopy",)
            )

        # Sobreposição approved/denied → ValueError.
        case_overlap = Case.objects.create(created_by=nir, status=CaseStatus.WAIT_APPT, exam_type="colonoscopy")
        with pytest.raises(ValueError):
            attach_procedure_projection(
                case_overlap,
                declared=("colonoscopy",),
                detected=(),
                approved=("colonoscopy",),
                denied=("colonoscopy",),
            )
