"""Slice 005 — NIR corrige o conjunto declarado, filtra por declarado e recebe resposta comparativa.

Cobre R1–R7 (specs exam-type-correction, exam-type-work-queues, exam-type-intake-routing):

- R1: elegibilidade exata; upgrade automático single→combined em voo NÃO exige/mostra
      CTA/ACK; WAIT_DOCTOR ou posterior bloqueia a correção;
- R2: correção transacional do conjunto (EDA, Colonoscopia ou combinado) com
      ``select_for_update``/lease, reset de detecção/disposições, invalidação de
      derivados v2 e evento enxuto com conjuntos anterior/novo;
- R3: um único enqueue pós-commit; recovery no cluster pdf; sem reextração;
- R4: reenvio corrigido combinado não herda rows/artefatos do original e respeita a flag;
- R5: filtros NIR por declarado (operacional + encerrados), compostos e sem detected/approved;
- R6: resposta comparativa declarado→detectado→autorizado com razões por componente e
      agenda casada, visível em voo antes da decisão médica;
- R7: eventos de correção sem texto/PDF; ACK/cleanup idempotentes sem duplicação.
"""

from __future__ import annotations

import threading
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ExamType,
    ProcedureType,
)
from apps.cases.services import claim_case_lock
from apps.intake.services import correct_case_exam_type, is_exam_type_correction_eligible

pytestmark = pytest.mark.django_db

User = get_user_model()

_PROCEDURES_BY_SELECTION: dict[str, tuple[str, ...]] = {
    ExamType.EDA: (ProcedureType.EDA,),
    ExamType.COLONOSCOPY: (ProcedureType.COLONOSCOPY,),
    EDA_COLONOSCOPY: (ProcedureType.EDA, ProcedureType.COLONOSCOPY),
}


# ── Helpers ──────────────────────────────────────────────────────────────


def _nir_user(django_user_model, username: str = "nir-s5@test.com"):
    """Cria usuário com o papel NIR atribuído (sem sessão HTTP)."""
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _nir_client(client, username: str = "nir-s5-view@test.com"):
    """Cria usuário NIR, faz login e retorna (client, user)."""
    user = _nir_user(User, username)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _make_case(
    *,
    user,
    exam_type: str = ExamType.EDA,
    status: str = CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    reason_code: str = "exam_type_mismatch",
    detected: str | None = None,
    with_declared_rows: bool = True,
) -> Case:
    """Cria caso com projeção declarada (rows) e suggested_action de revisão."""
    case = Case.objects.create(
        created_by=user,
        exam_type=exam_type,
        status=status,
        extracted_text="RELATÓRIO DE OCORRÊNCIAS\nGoverno do Estado da Bahia\nCódigo: 123\nMotivo da Solicitação: EDA",
        agency_record_number="REC-S5-001",
        regulation_days_on_screen=3,
        structured_data={"patient": {"name": "Paciente de Teste"}},
        summary_text="Resumo antigo do perfil anterior.",
        suggested_action={
            "decision": "manual_review_required",
            "suggestion": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": "Conjunto declarado difere da solicitacao atual.",
            "exam_type": detected or "eda",
            "declared_exam_type": exam_type,
            "detected_exam_type": detected or "eda",
        },
        priority_signals=[{"code": "foreign_body", "label": "Corpo estranho"}],
    )
    if with_declared_rows:
        for procedure_type in _PROCEDURES_BY_SELECTION[exam_type]:
            CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
    return case


def _claim_receipt_lease(case: Case, user) -> uuid.UUID:
    """Adquire a reserva nir_receipt e retorna o token."""
    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        context="nir_receipt",
        role="nir",
    )
    assert result.acquired
    assert result.token is not None
    return result.token


def _set_detection(case: Case, detected: tuple[str, ...]) -> None:
    """Projeta detecção nas rows (simula CASE_PROCEDURES_DETECTED do pipeline)."""
    for procedure_type in detected:
        row, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type=procedure_type)
        row.detection_status = DetectionStatus.DETECTED
        row.save(update_fields=["detection_status"])


def _set_doctor_decision(
    case: Case,
    *,
    approved: tuple[str, ...],
    denied: tuple[str, ...] = (),
    reason: str = "",
) -> None:
    """Projeta decisões médicas nas rows (simula Slice 003)."""
    for procedure_type in approved:
        row, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type=procedure_type)
        row.doctor_disposition = DoctorDisposition.APPROVED
        row.doctor_reason = reason
        row.save(update_fields=["doctor_disposition", "doctor_reason"])
    for procedure_type in denied:
        row, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type=procedure_type)
        row.doctor_disposition = DoctorDisposition.DENIED
        row.doctor_reason = reason or "Procedimento não indicado."
        row.save(update_fields=["doctor_disposition", "doctor_reason"])


# ═══════════════════════════════════════════════════════════════════════════
# R1/R2 — elegibilidade exata e correção transacional do CONJUNTO
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionSetEligibility:
    """R1/R2: correção aceita as três seleções; combined→single e single→combined."""

    def test_combined_to_single_correction_reprocesses(self, django_user_model, monkeypatch) -> None:
        """Combinado declarado → correção para EDA reprocessa o mesmo caso."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-c2s@test.com")
        case = _make_case(user=user, exam_type=EDA_COLONOSCOPY)
        original_id = case.case_id
        token = _claim_receipt_lease(case, user)

        result = correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.EDA,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        assert result.case_id == original_id
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == ExamType.EDA
        eda = CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.EDA)
        colon = CaseProcedure.objects.get(case=reloaded, procedure_type=ProcedureType.COLONOSCOPY)
        assert eda.declared_by_nir is True
        assert colon.declared_by_nir is False
        assert pipeline_calls == [case.case_id]

    def test_single_to_combined_correction_reprocesses(self, django_user_model, monkeypatch) -> None:
        """EDA declarado → correção para combinado cria duas rows declaradas."""
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-s2c@test.com")
        case = _make_case(user=user, exam_type=ExamType.EDA)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=EDA_COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert reloaded.exam_type == EDA_COLONOSCOPY
        declared = {p.procedure_type for p in CaseProcedure.objects.filter(case=reloaded, declared_by_nir=True)}
        assert declared == {ProcedureType.EDA, ProcedureType.COLONOSCOPY}
        assert pipeline_calls == [case.case_id]

    @pytest.mark.parametrize(
        ("reason_code", "detected"),
        [
            ("mixed_exam_request", "mixed"),
            ("unknown_exam_type", "unknown"),
            ("exam_type_mismatch", "colonoscopy"),
        ],
    )
    def test_supported_reasons_eligible(self, django_user_model, reason_code: str, detected: str) -> None:
        """combined-incomplete/mismatch/unknown continuam elegíveis."""
        user = _nir_user(django_user_model, f"nir-reason-{reason_code}@test.com")
        case = _make_case(user=user, exam_type=ExamType.EDA, reason_code=reason_code, detected=detected)
        assert is_exam_type_correction_eligible(case) is True

    def test_correction_resets_detection_and_dispositions(self, django_user_model, monkeypatch) -> None:
        """R2: detecção/disposições voltam a pending; razão médica apagada."""
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-reset@test.com")
        case = _make_case(user=user, exam_type=ExamType.EDA)
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))
        _set_doctor_decision(
            case,
            approved=(ProcedureType.EDA,),
            denied=(ProcedureType.COLONOSCOPY,),
            reason="Razão antiga.",
        )
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        reloaded = Case.objects.get(pk=case.pk)
        rows = CaseProcedure.objects.filter(case=reloaded)
        assert rows.count() == 2
        for row in rows:
            assert row.detection_status == DetectionStatus.PENDING
            assert row.doctor_disposition == DoctorDisposition.PENDING
            assert row.doctor_reason == ""

    def test_derived_v2_cleared_sources_preserved_no_extraction(self, django_user_model, monkeypatch) -> None:
        """R2/R3: derivados v2 limpos; PDF/texto/ocorrência preservados; sem extração."""
        pipeline_calls: list[object] = []
        pdf_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        monkeypatch.setattr(
            "apps.intake.tasks.enqueue_pdf_extraction",
            lambda case_id: pdf_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-derived5@test.com")
        case = _make_case(user=user, exam_type=ExamType.EDA)
        case.pdf_file = "pdfs/2025/01/original.pdf"
        case.save()
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ExamType.COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.structured_data is None
        assert reloaded.summary_text == ""
        assert reloaded.suggested_action is None
        assert reloaded.priority_signals == []
        assert reloaded.pdf_file.name == "pdfs/2025/01/original.pdf"
        assert reloaded.extracted_text == case.extracted_text
        assert reloaded.agency_record_number == "REC-S5-001"
        assert pipeline_calls == [case.case_id]
        assert pdf_calls == []

    def test_correction_event_lean_sets_no_text(self, django_user_model, monkeypatch) -> None:
        """R7: evento enxuto com conjuntos anterior/novo e motivo codificado."""
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_user(django_user_model, "nir-lean-ev@test.com")
        case = _make_case(user=user, exam_type=ExamType.EDA)
        token = _claim_receipt_lease(case, user)

        correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=EDA_COLONOSCOPY,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        events = CaseEvent.objects.filter(case=case).order_by("id")
        corrected = events.get(event_type="CASE_PROCEDURE_DECLARATION_CORRECTED")
        assert corrected.payload == {
            "old_procedures": [ProcedureType.EDA],
            "new_procedures": [ProcedureType.EDA, ProcedureType.COLONOSCOPY],
            "reason_code": "nir_identified_exam",
        }
        assert corrected.actor_id == user.pk
        assert "extracted_text" not in corrected.payload
        assert "structured_data" not in corrected.payload

    def test_wait_doctor_blocks_correction_keeps_comparison_visible(self, django_user_model, client) -> None:
        """R1/R6: WAIT_DOCTOR bloqueia correção mas a comparação segue visível."""
        user = _nir_user(django_user_model, "nir-wd@test.com")
        case = _make_case(
            user=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.WAIT_DOCTOR,
            reason_code="exam_type_mismatch",
        )
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=EDA_COLONOSCOPY,
                user=user,
                active_role="nir",
                lock_token=uuid.uuid4(),
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_DOCTOR
        assert reloaded.exam_type == ExamType.EDA
        # Comparação em voo continua visível no refresh (sem CTA).
        client, _ = _nir_client(client, "nir-wd-view@test.com")
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Solicitado pelo NIR" in content
        assert "Detectado na análise" in content
        assert "EDA + Colonoscopia" in content
        assert "Correção de Tipo de Exame" not in content

    def test_invalid_actor_role_lease_block(self, django_user_model, monkeypatch) -> None:
        """R2: ator/role/lease inválidos bloqueiam sem mutação nem enqueue."""
        from django.contrib.auth import get_user_model as gum

        plain = gum().objects.create_user(username="not-nir5@test.com", password="x")
        enqueue_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: enqueue_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-inv@test.com")
        case = _make_case(user=user, exam_type=ExamType.EDA)
        token = _claim_receipt_lease(case, user)

        with pytest.raises(PermissionError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ExamType.COLONOSCOPY,
                user=plain,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert reloaded.exam_type == ExamType.EDA
        assert enqueue_calls == []


@pytest.mark.django_db(transaction=True)
class TestCorrectionConcurrency:
    """R2: dois requests concorrentes serializam; exatamente um enqueue."""

    def test_two_corrections_serialize_one_job(self, django_user_model, monkeypatch) -> None:
        pipeline_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-race5@test.com")
        case = _make_case(user=user, exam_type=EDA_COLONOSCOPY)
        token = _claim_receipt_lease(case, user)

        results: dict[str, object] = {}

        def run(target: str, key: str) -> None:
            try:
                correct_case_exam_type(
                    case_id=case.case_id,
                    new_exam_type=target,
                    user=user,
                    active_role="nir",
                    lock_token=token,
                    reason_code="nir_identified_exam",
                )
                results[key] = "ok"
            except Exception as exc:  # noqa: BLE001
                results[key] = type(exc).__name__

        threads = [
            threading.Thread(target=run, args=(ExamType.EDA, "t1"), daemon=True),
            threading.Thread(target=run, args=(ExamType.COLONOSCOPY, "t2"), daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads)

        # Exatamente um vencedor e um enqueue (o perdedor vê estado já movido).
        outcomes = sorted(str(v) for v in results.values())
        assert outcomes == ["ValueError", "ok"]
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert len(pipeline_calls) == 1
        assert not CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").exists()


# ═══════════════════════════════════════════════════════════════════════════
# R6 — resposta comparativa (declarado vs detectado vs autorizado)
# ═══════════════════════════════════════════════════════════════════════════


class TestComparativeResponse:
    """R6: comparativo em voo e final, com razões e agenda casada."""

    def test_detail_shows_declared_vs_detected_inflight(self, client) -> None:
        """Auto-upgrade em voo: Declarado EDA / Detectado EDA + Colonoscopia, sem CTA/ACK."""
        client, user = _nir_client(client, "nir-inflight@test.com")
        case = _make_case(
            user=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.WAIT_DOCTOR,
        )
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))

        for _ in range(2):  # polling/refresh — permanece visível
            response = client.get(reverse("intake:case_detail", args=[case.case_id]))
            assert response.status_code == 200
            content = response.content.decode()
            assert "Solicitado pelo NIR" in content
            assert "EDA" in content
            assert "Detectado na análise" in content
            assert "EDA + Colonoscopia" in content
            assert "Aguardando decisão médica" in content
            # Sem CTA obrigatório de correção nem ACK bloqueante.
            assert "Correção de Tipo de Exame" not in content
            assert "Confirmar Recebimento" not in content

    def test_detail_shows_partial_decision_with_reasons(self, client) -> None:
        """Aprovação parcial: EDA aprovado, Colon negado com motivo próprio."""
        client, user = _nir_client(client, "nir-partial@test.com")
        case = _make_case(
            user=user,
            exam_type=EDA_COLONOSCOPY,
            status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            reason_code="exam_type_mismatch",
            detected="colonoscopy",
        )
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))
        _set_doctor_decision(
            case,
            approved=(ProcedureType.EDA,),
            denied=(ProcedureType.COLONOSCOPY,),
            reason="Exame desnecessário neste momento.",
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Declaração original nunca é escondida após upgrade.
        assert "Solicitado pelo NIR" in content
        assert "EDA + Colonoscopia" in content
        assert "Decisão médica" in content
        assert "Exame desnecessário neste momento." in content
        assert "Aprovado" in content
        assert "Negado" in content

    def test_detail_shows_inclusion_with_reason(self, client) -> None:
        """Procedimento incluído pelo médico aparece com justificativa própria."""
        client, user = _nir_client(client, "nir-incl@test.com")
        case = _make_case(
            user=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.APPT_CONFIRMED,
        )
        _set_detection(case, (ProcedureType.EDA,))
        _set_doctor_decision(
            case,
            approved=(ProcedureType.EDA, ProcedureType.COLONOSCOPY),
            reason="Inclusão por histórico familiar de neoplasia.",
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Incluído pelo médico" in content
        assert "Inclusão por histórico familiar de neoplasia." in content

    def test_detail_paired_appointment_combined(self, client) -> None:
        """Combinado autorizado mostra agenda casada com uma data/hora."""
        from django.utils import timezone

        client, user = _nir_client(client, "nir-paired@test.com")
        case = _make_case(
            user=user,
            exam_type=EDA_COLONOSCOPY,
            status=CaseStatus.APPT_CONFIRMED,
        )
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))
        _set_doctor_decision(case, approved=(ProcedureType.EDA, ProcedureType.COLONOSCOPY))
        case.appointment_at = timezone.now()
        case.appointment_status = "confirmed"
        case.save(update_fields=["appointment_at", "appointment_status"])

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agendamento casado" in content
        assert "EDA + Colonoscopia · Agendamento casado" in content

    def test_closed_detail_shows_comparison(self, client) -> None:
        """Caso concluído: comparativo completo com razões no detalhe histórico."""
        client, user = _nir_client(client, "nir-closed5@test.com")
        case = _make_case(
            user=user,
            exam_type=EDA_COLONOSCOPY,
            status=CaseStatus.CLEANED,
        )
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))
        _set_doctor_decision(
            case,
            approved=(ProcedureType.EDA,),
            denied=(ProcedureType.COLONOSCOPY,),
            reason="Razão do procedimento.",
        )

        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Solicitado pelo NIR" in content
        assert "Detectado na análise" in content
        assert "Decisão médica" in content
        assert "Razão do procedimento." in content


# ═══════════════════════════════════════════════════════════════════════════
# R4 — reenvio corrigido combinado (sem herança, respeita flag)
# ═══════════════════════════════════════════════════════════════════════════


class TestResubmissionCombined:
    """R4: novo PDF combinado cria novo caso com duas rows; original intacto."""

    @staticmethod
    def _pdf() -> object:
        from io import BytesIO

        import fitz  # type: ignore[import-untyped]
        from django.core.files.uploadedfile import SimpleUploadedFile

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Paciente: Maria\nRegistro: 2026-1234", fontsize=12)
        buf = BytesIO()
        doc.save(buf)
        doc.close()
        return SimpleUploadedFile("relatorio.pdf", buf.getvalue(), content_type="application/pdf")

    def test_combined_resubmission_creates_two_declared_rows_original_intact(self, client) -> None:
        """Reenvio combinado: novo caso com duas rows; original não herda nada."""
        from unittest.mock import patch

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            client, user = _nir_client(client, "nir-resub5@test.com")
            original = Case.objects.create(
                created_by=user,
                exam_type=ExamType.EDA,
                agency_record_number="2026-EDA-ORIG",
            )
            CaseProcedure.objects.create(case=original, procedure_type=ProcedureType.EDA, declared_by_nir=True)

            with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
                response = client.post(
                    reverse("intake:corrected_resubmission", args=[original.case_id]),
                    {
                        "correction_reason": "Laudo corrigido com ambos os procedimentos",
                        "pdf_file": self._pdf(),
                        "confirmation": "on",
                        "exam_type": EDA_COLONOSCOPY,
                    },
                )

        assert response.status_code == 302
        new_case = Case.objects.exclude(case_id=original.case_id).first()
        assert new_case is not None
        # Slice 008 (R5): prova rows declaradas, não a coluna.
        declared = {p.procedure_type for p in CaseProcedure.objects.filter(case=new_case, declared_by_nir=True)}
        assert declared == {ProcedureType.EDA, ProcedureType.COLONOSCOPY}
        mock_enqueue.assert_called_once_with(new_case.case_id)

        # Original permanece EDA com uma única row; sem herança de rows/artefatos.
        original = Case.objects.get(pk=original.pk)
        assert original.status == CaseStatus.NEW
        assert CaseProcedure.objects.filter(case=original).count() == 1
        assert CaseProcedure.objects.get(case=original, procedure_type=ProcedureType.EDA).declared_by_nir is True
        assert not CaseProcedure.objects.filter(case=original, procedure_type=ProcedureType.COLONOSCOPY).exists()

    def test_combined_resubmission_flag_off_rejected(self, client) -> None:
        """Flag desligada bloqueia reenvio combinado; nada é criado."""
        from unittest.mock import patch

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=False):
            client, user = _nir_client(client, "nir-resub-off@test.com")
            original = Case.objects.create(created_by=user, exam_type=ExamType.EDA)
            with patch("apps.intake.tasks.enqueue_pdf_extraction") as mock_enqueue:
                response = client.post(
                    reverse("intake:corrected_resubmission", args=[original.case_id]),
                    {
                        "correction_reason": "Tentativa de combinado com flag off",
                        "pdf_file": self._pdf(),
                        "confirmation": "on",
                        "exam_type": EDA_COLONOSCOPY,
                    },
                )

        assert response.status_code == 200
        assert Case.objects.count() == 1
        mock_enqueue.assert_not_called()
        assert not CaseProcedure.objects.filter(case=original, procedure_type=ProcedureType.COLONOSCOPY).exists()


# ═══════════════════════════════════════════════════════════════════════════
# R5 — filtros NIR por DECLARADO (operacional + encerrados)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeclaredFilters:
    """R5: filtros usam a dimensão declarada, compostos com status/busca."""

    def test_my_cases_combined_filter(self, client) -> None:
        client, user = _nir_client(client, "nir-filter5@test.com")
        eda_case = _make_case(user=user, exam_type=ExamType.EDA, status=CaseStatus.NEW, with_declared_rows=False)
        CaseProcedure.objects.create(case=eda_case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        eda_case.exam_type = ExamType.EDA
        eda_case.save()

        combined_case = _make_case(
            user=user, exam_type=EDA_COLONOSCOPY, status=CaseStatus.NEW, with_declared_rows=False
        )
        for t in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
            CaseProcedure.objects.create(case=combined_case, procedure_type=t, declared_by_nir=True)
        combined_case.exam_type = EDA_COLONOSCOPY
        combined_case.save()

        colon_case = _make_case(
            user=user, exam_type=ExamType.COLONOSCOPY, status=CaseStatus.NEW, with_declared_rows=False
        )
        CaseProcedure.objects.create(case=colon_case, procedure_type=ProcedureType.COLONOSCOPY, declared_by_nir=True)
        colon_case.exam_type = ExamType.COLONOSCOPY
        colon_case.save()

        # Slice 008 (R3): caso legado/inválido sem rows é fail-closed — não cai
        # em bucket específico (não recebe default da coluna).
        orphan = Case.objects.create(created_by=user, exam_type=ExamType.COLONOSCOPY, status=CaseStatus.NEW)

        response = client.get(reverse("intake:my_cases") + "?exam_type=eda_colonoscopy")
        content = response.content.decode()
        assert str(combined_case.case_id) in content
        assert str(eda_case.case_id) not in content
        assert str(orphan.case_id) not in content

        response = client.get(reverse("intake:my_cases") + "?exam_type=colonoscopy")
        content = response.content.decode()
        assert str(colon_case.case_id) in content
        assert str(combined_case.case_id) not in content
        assert str(orphan.case_id) not in content

    def test_my_cases_filter_uses_declared_not_detected(self, client) -> None:
        """Filtro usa declarado: auto-upgrade em voo (detectado combinado) segue em EDA."""
        client, user = _nir_client(client, "nir-decl5@test.com")
        case = _make_case(
            user=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.WAIT_DOCTOR,
            with_declared_rows=False,
        )
        CaseProcedure.objects.create(case=case, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        _set_detection(case, (ProcedureType.EDA, ProcedureType.COLONOSCOPY))

        response = client.get(reverse("intake:my_cases") + "?exam_type=eda")
        assert str(case.case_id) in response.content.decode()

        response = client.get(reverse("intake:my_cases") + "?exam_type=eda_colonoscopy")
        assert str(case.case_id) not in response.content.decode()

    def test_my_cases_filter_composes_with_status_and_search(self, client) -> None:
        client, user = _nir_client(client, "nir-comp5@test.com")
        target = _make_case(
            user=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.WAIT_DOCTOR,
            with_declared_rows=False,
        )
        CaseProcedure.objects.create(case=target, procedure_type=ProcedureType.EDA, declared_by_nir=True)
        target.agency_record_number = "S5-COMP-001"
        target.save()
        other = _make_case(
            user=user,
            exam_type=ExamType.EDA,
            status=CaseStatus.NEW,
            with_declared_rows=False,
        )
        CaseProcedure.objects.create(case=other, procedure_type=ProcedureType.EDA, declared_by_nir=True)

        response = client.get(reverse("intake:my_cases") + "?exam_type=eda&status=WAIT_DOCTOR&q=S5-COMP")
        content = response.content.decode()
        assert str(target.case_id) in content
        assert str(other.case_id) not in content
        # Query string preservada no polling parcial.
        assert "exam_type=eda&amp;status=WAIT_DOCTOR" in content

    def test_closed_search_combined_filter(self, client) -> None:
        client, user = _nir_client(client, "nir-closed5f@test.com")
        combined = _make_case(user=user, exam_type=EDA_COLONOSCOPY, status=CaseStatus.CLEANED, with_declared_rows=False)
        for t in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
            CaseProcedure.objects.create(case=combined, procedure_type=t, declared_by_nir=True)
        combined.exam_type = EDA_COLONOSCOPY
        combined.save()
        eda_case = _make_case(user=user, exam_type=ExamType.EDA, status=CaseStatus.CLEANED, with_declared_rows=False)
        CaseProcedure.objects.create(case=eda_case, procedure_type=ProcedureType.EDA, declared_by_nir=True)

        response = client.get(reverse("intake:closed_cases_search") + "?exam_type=eda_colonoscopy")
        content = response.content.decode()
        assert str(combined.case_id) in content
        assert str(eda_case.case_id) not in content

        response = client.get(reverse("intake:closed_cases_search") + "?exam_type=eda")
        content = response.content.decode()
        assert str(eda_case.case_id) in content
        assert str(combined.case_id) not in content

    def test_closed_search_badge_uses_declared_label(self, client) -> None:
        """Badge dos resultados usa label declarado projetado (sem valor cru da ponte)."""
        client, user = _nir_client(client, "nir-badge5@test.com")
        combined = _make_case(user=user, exam_type=EDA_COLONOSCOPY, status=CaseStatus.CLEANED, with_declared_rows=False)
        for t in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
            CaseProcedure.objects.create(case=combined, procedure_type=t, declared_by_nir=True)
        combined.exam_type = EDA_COLONOSCOPY
        combined.save()

        response = client.get(reverse("intake:closed_cases_search") + "?exam_type=eda_colonoscopy")
        content = response.content.decode()
        # Badge textual amigável por conjunto declarado (nunca o valor cru como texto).
        assert 'exam-type-eda_colonoscopy">EDA + Colonoscopia</span>' in content
        assert ">eda_colonoscopy<" not in content.replace('value="eda_colonoscopy"', "")


# ═══════════════════════════════════════════════════════════════════════════
# R7 — ACK/cleanup idempotentes sem duplicação por componente
# ═══════════════════════════════════════════════════════════════════════════


class TestAckNoDuplication:
    """R7: confirm receipt de caso combinado conclui uma única vez."""

    def test_combined_confirm_receipt_cleanup_once_no_duplication(self, django_user_model) -> None:
        from apps.intake.services import confirm_case_receipt

        user = _nir_user(django_user_model, "nir-ack5@test.com")
        case = _make_case(user=user, exam_type=EDA_COLONOSCOPY)
        token = _claim_receipt_lease(case, user)

        result = confirm_case_receipt(
            case_id=case.case_id,
            user=user,
            active_role="nir",
            lock_token=token,
        )

        assert result.status == CaseStatus.CLEANED
        assert CaseEvent.objects.filter(case=case, event_type="CLEANUP_TRIGGERED").count() == 1
        assert CaseEvent.objects.filter(case=case, event_type="CLEANUP_COMPLETED").count() == 1
        # Resposta não é duplicada por componente.
        assert CaseEvent.objects.filter(case=case, event_type="FINAL_REPLY_POSTED").count() <= 1
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.locked_by is None
        assert reloaded.lock_token is None
