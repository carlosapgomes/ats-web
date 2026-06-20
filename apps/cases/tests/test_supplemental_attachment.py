"""Testes do serviço de anexo complementar — Slice 004.

RED phase: testes falham antes da implementação.
"""

from __future__ import annotations

import io
from typing import Any

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import claim_case_lock

User = get_user_model()


def _create_pdf_bytes(text: str = "Test") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _advance_case_to(case: Case, target: str) -> Case:
    """Avança Case por FSM até o status alvo."""
    path: dict[str, list[str]] = {
        CaseStatus.R1_ACK_PROCESSING: ["start_processing"],
        CaseStatus.EXTRACTING: ["start_processing", "start_extraction"],
        CaseStatus.LLM_STRUCT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
        ],
        CaseStatus.LLM_SUGGEST: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
        ],
        CaseStatus.R2_POST_WIDGET: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
        ],
        CaseStatus.WAIT_DOCTOR: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
        ],
        CaseStatus.DOCTOR_ACCEPTED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
        ],
        CaseStatus.DOCTOR_DENIED: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='deny')",
        ],
    }
    steps = path.get(target, [])
    for step in steps:
        if "(" in step:
            method_name, args_str = step.split("(", 1)
            args_str = args_str.rstrip(")")
            kwargs: dict[str, object] = {}
            if "=" in args_str:
                for pair in args_str.split(","):
                    k, v = pair.split("=")
                    k = k.strip()
                    v = v.strip().strip("'")
                    if v == "True":
                        v = True
                    elif v == "False":
                        v = False
                    kwargs[k] = v
                getattr(case, method_name)(**kwargs)
            else:
                getattr(case, method_name)()
        else:
            getattr(case, step)()
        case.save()
    return Case.objects.get(pk=case.pk)


@pytest.mark.django_db
class TestAddSupplementalAttachment:
    """Testes do serviço add_supplemental_case_attachment."""

    def _create_case_and_user(
        self, status: str = CaseStatus.WAIT_DOCTOR, doctor_decision: str = ""
    ) -> tuple[Case, Any]:
        user = User.objects.create_user(username="nir_supp@test.com", password="testpass123")
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, status)
        if doctor_decision:
            case.doctor_decision = doctor_decision
            case.save()
        return case, user

    def _make_file(self, name: str = "supplement.pdf") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, _create_pdf_bytes("suplementar"), content_type="application/pdf")

    # ── Test 1: note obrigatória ────────────────────────────────────────

    def test_add_supplemental_attachment_requires_note(self) -> None:
        """nota vazia deve falhar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user()
        uploaded_file = self._make_file()

        with pytest.raises(ValueError, match="obrigatória"):
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=uploaded_file,
                user=user,
                note="",
            )

    # ── Test 2: elegível antes da decisão médica ────────────────────────

    def test_add_supplemental_attachment_allowed_before_doctor_decision(self) -> None:
        """Caso em WAIT_DOCTOR sem doctor_decision aceita anexo complementar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.WAIT_DOCTOR)
        uploaded_file = self._make_file()

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note="Laudo complementar enviado pela unidade.",
        )

        assert attachment is not None
        assert attachment.case == case
        assert attachment.uploaded_by == user

    def test_add_supplemental_attachment_allowed_in_r2_post_widget(self) -> None:
        """Caso em R2_POST_WIDGET sem doctor_decision aceita anexo complementar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.R2_POST_WIDGET)
        uploaded_file = self._make_file()

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note="Documento adicional.",
        )
        assert attachment is not None

    def test_add_supplemental_attachment_allowed_in_llm_suggest(self) -> None:
        """Caso em LLM_SUGGEST aceita anexo complementar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.LLM_SUGGEST)
        uploaded_file = self._make_file()

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note="Documento adicional.",
        )
        assert attachment is not None

    def test_add_supplemental_attachment_allowed_in_extracting(self) -> None:
        """Caso em EXTRACTING aceita anexo complementar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.EXTRACTING)
        uploaded_file = self._make_file()

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note="Documento adicional.",
        )
        assert attachment is not None

    # ── Test 3: campos setados corretamente ─────────────────────────────

    def test_add_supplemental_attachment_sets_phase_status_and_note(self) -> None:
        """upload_phase='supplemental', uploaded_when_case_status e note preenchidos."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.WAIT_DOCTOR)
        uploaded_file = self._make_file()
        note = "Laudo de USG enviado posteriormente pela unidade de origem."

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note=note,
        )

        assert attachment.upload_phase == "supplemental"
        assert attachment.uploaded_when_case_status == CaseStatus.WAIT_DOCTOR
        assert attachment.note == note.strip()
        assert attachment.is_suppressed is False

    # ── Test 4: evento específico registrado ────────────────────────────

    def test_add_supplemental_attachment_records_specific_event(self) -> None:
        """CASE_ATTACHMENT_SUPPLEMENT_ADDED registrado."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.WAIT_DOCTOR)
        uploaded_file = self._make_file()
        note = "Documento complementar."

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note=note,
        )

        event = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ATTACHMENT_SUPPLEMENT_ADDED",
        ).last()
        assert event is not None
        payload = event.payload or {}
        assert str(attachment.attachment_id) in str(payload.get("attachment_id", ""))
        assert payload.get("case_status_at_upload") == CaseStatus.WAIT_DOCTOR
        assert payload.get("note") == note.strip()

    # ── Test 5: rejeita após decisão médica ─────────────────────────────

    def test_add_supplemental_attachment_rejects_after_doctor_decision(self) -> None:
        """doctor_decision='accept' ou 'deny' deve falhar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.DOCTOR_ACCEPTED, doctor_decision="accept")
        uploaded_file = self._make_file()

        with pytest.raises(ValueError, match="decisão médica"):
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=uploaded_file,
                user=user,
                note="Tentativa após decisão.",
            )

    def test_add_supplemental_attachment_rejects_after_doctor_deny(self) -> None:
        """doctor_decision='deny' deve falhar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, user = self._create_case_and_user(status=CaseStatus.DOCTOR_DENIED, doctor_decision="deny")
        uploaded_file = self._make_file()

        with pytest.raises(ValueError, match="decisão médica"):
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=uploaded_file,
                user=user,
                note="Tentativa após negativa.",
            )

    # ── Test 6: rejeita caso CLEANED ────────────────────────────────────

    def test_add_supplemental_attachment_rejects_cleaned_case(self) -> None:
        """Caso CLEANED deve falhar."""
        from apps.cases.services import add_supplemental_case_attachment, administratively_close_case

        case, user = self._create_case_and_user(status=CaseStatus.WAIT_DOCTOR)
        # Avançar para CLEANED via serviço de encerramento administrativo
        cleaned_case = administratively_close_case(
            case=case,
            user=user,
            reason_code="other",
            reason_text="Test cleanup",
            active_role="nir",
        )
        assert cleaned_case.status == CaseStatus.CLEANED

        uploaded_file = self._make_file()

        with pytest.raises(ValueError, match="CLEANED|encerrado|concluído"):
            add_supplemental_case_attachment(
                case=cleaned_case,
                uploaded_file=uploaded_file,
                user=user,
                note="Tentativa em caso encerrado.",
            )

    # ── Test 6b: defesa em profundidade — limite de anexos no serviço ───

    def test_add_supplemental_attachment_rejects_when_max_attachments_reached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O serviço valida o limite de anexos por caso, mesmo chamado direto.

        A view valida o lote inteiro antes do loop; este teste garante que o
        serviço de domínio também rejeita quando chamado por outro caller,
        sem depender da view.
        """
        import django.conf

        from apps.cases.models import CaseAttachment
        from apps.cases.services import add_supplemental_case_attachment

        # Limite baixo para evitar criar 10 anexos reais
        monkeypatch.setattr(django.conf.settings, "INTAKE_MAX_ATTACHMENTS_PER_CASE", 2)

        case, user = self._create_case_and_user(status=CaseStatus.WAIT_DOCTOR)

        # Criar 2 anexos ativos (até o limite)
        for i in range(2):
            CaseAttachment.objects.create(
                case=case,
                file=SimpleUploadedFile(
                    f"att_{i}.pdf", _create_pdf_bytes(f"anexo {i}"), content_type="application/pdf"
                ),
                original_filename=f"att_{i}.pdf",
                stored_filename=f"stored_{i}.pdf",
                content_type="application/pdf",
                size_bytes=100,
                sha256=f"{i}" * 64,
                uploaded_by=user,
                upload_phase="initial",
                uploaded_when_case_status=CaseStatus.WAIT_DOCTOR,
            )

        # O 3º anexo deve falhar
        uploaded_file = self._make_file(name="terceiro.pdf")
        with pytest.raises(ValueError, match="Máximo de 2 anexos"):
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=uploaded_file,
                user=user,
                note="Tentativa acima do limite.",
            )


@pytest.mark.django_db
class TestSupplementalLockBlocking:
    """Testes de lock médico bloqueando anexo complementar."""

    def _create_case_in_wait_doctor(self) -> tuple[Case, Any, Any]:
        """Cria caso em WAIT_DOCTOR e dois usuários (NIR + médico)."""
        from apps.accounts.models import Role

        nir_user = User.objects.create_user(username="nir_lock@test.com", password="testpass123")
        nir_role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(nir_role)

        doctor = User.objects.create_user(username="doc_lock@test.com", password="testpass123")
        doc_role, _ = Role.objects.get_or_create(name="doctor")
        doctor.roles.add(doc_role)

        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
        return case, nir_user, doctor

    def test_nir_supplemental_attachment_blocked_when_doctor_lock_active(self) -> None:
        """Caso WAIT_DOCTOR com lock ativo de médico bloqueia anexo complementar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, nir_user, doctor = self._create_case_in_wait_doctor()

        # Médico adquire lock
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        uploaded_file = SimpleUploadedFile("supp.pdf", _create_pdf_bytes("test"), content_type="application/pdf")

        with pytest.raises(ValueError, match="reservado|Dr\\(a\\)|Aguarde|comunique"):
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=uploaded_file,
                user=nir_user,
                note="Tentativa com lock ativo.",
            )

    def test_nir_supplemental_attachment_allowed_when_wait_doctor_without_lock(self) -> None:
        """Caso WAIT_DOCTOR sem lock ativo permite anexo complementar."""
        from apps.cases.services import add_supplemental_case_attachment

        case, nir_user, doctor = self._create_case_in_wait_doctor()

        uploaded_file = SimpleUploadedFile("supp.pdf", _create_pdf_bytes("test"), content_type="application/pdf")

        attachment = add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=nir_user,
            note="Sem lock, permitido.",
        )
        assert attachment is not None
        assert attachment.upload_phase == "supplemental"
