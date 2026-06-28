"""Testes de view NIR para anexo complementar — Slice 004.

RED phase: testes falham antes da implementação.
"""

from __future__ import annotations

import io
from typing import Any

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseStatus
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


def _nir_client(client):
    """Cria usuário NIR logado."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nir_supp_view@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _doctor_client(client):
    """Cria usuário doctor logado."""
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doc_supp_view@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


@pytest.mark.django_db
class TestIntakeCaseDetailSupplementalForm:
    """Testes de exibição do formulário de anexo complementar no detalhe NIR."""

    # Test 9: formulário aparece quando elegível
    def test_intake_case_detail_shows_supplemental_attachment_form_when_eligible(self, client) -> None:
        """Detalhe NIR mostra formulário de anexo complementar para caso elegível."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        assert "Adicionar anexo complementar" in content
        assert "supplemental" in content.lower()
        assert "justificativa" in content.lower()
        assert "antes da decisão médica" in content.lower()

    def test_intake_case_detail_shows_supplemental_form_in_llm_suggest(self, client) -> None:
        """Detalhe NIR mostra formulário para caso em LLM_SUGGEST."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.LLM_SUGGEST)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adicionar anexo complementar" in content

    # Test 10: formulário escondido após decisão médica
    def test_intake_case_detail_hides_supplemental_form_after_doctor_decision(self, client) -> None:
        """Caso decidido não mostra formulário de anexo complementar."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.DOCTOR_ACCEPTED)
        case.doctor_decision = "accept"
        case.save()

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adicionar anexo complementar" not in content

    def test_intake_case_detail_hides_supplemental_form_after_doctor_deny(self, client) -> None:
        """Caso negado não mostra formulário de anexo complementar."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.DOCTOR_DENIED)
        case.doctor_decision = "deny"
        case.save()

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Adicionar anexo complementar" not in content

    def test_intake_case_detail_hides_supplemental_form_when_doctor_lock_active(self, client) -> None:
        """Caso WAIT_DOCTOR com lock médico ativo esconde o form e mostra aviso.

        Spec R5: o NIR deve ver mensagem com nome do médico EM VEZ do formulário.
        Regressão: antes deste fix, ``lock_locked_by_display`` só era populado para
        WAIT_R1_CLEANUP_THUMBS, então o form aparecia mesmo com lock médico.
        """
        from apps.accounts.models import Role

        # Médico reserva o caso
        doctor = User.objects.create_user(username="doc_lock_hide@test.com", password="testpass123")
        doc_role, _ = Role.objects.get_or_create(name="doctor")
        doctor.roles.add(doc_role)

        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Aviso de bloqueio visível com nome do médico
        assert "reservado por" in content.lower()
        assert doctor.display_name in content
        # Formulário NÃO deve aparecer (nem o action)
        form_action = reverse("intake:supplemental_attachment_add", args=[case.case_id])
        assert form_action not in content

    def test_intake_case_detail_shows_supplemental_form_when_wait_doctor_no_lock(self, client) -> None:
        """Caso WAIT_DOCTOR sem lock mostra o form normalmente (sem regressão)."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        form_action = reverse("intake:supplemental_attachment_add", args=[case.case_id])
        assert form_action in content
        assert "reservado por" not in content.lower()

    # Test 11: POST cria anexo e redireciona
    def test_nir_can_post_supplemental_attachment(self, client) -> None:
        """POST cria anexo complementar e redireciona com mensagem."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        url = reverse("intake:supplemental_attachment_add", args=[case.case_id])
        pdf_file = SimpleUploadedFile(
            "complemento.pdf", _create_pdf_bytes("complemento"), content_type="application/pdf"
        )

        response = client.post(
            url,
            {
                "attachment_files": pdf_file,
                "note": "Laudo complementar enviado pela unidade.",
            },
            follow=True,
        )

        assert response.status_code == 200
        # Deve redirecionar para o detalhe do caso
        assert "Anexo complementar adicionado" in response.content.decode()

        # Anexo deve existir
        attachments = list(case.attachments.filter(is_suppressed=False, upload_phase="supplemental"))
        assert len(attachments) == 1
        assert attachments[0].note == "Laudo complementar enviado pela unidade."

        # Evento deve existir
        event = CaseEvent.objects.filter(
            case=case,
            event_type="CASE_ATTACHMENT_SUPPLEMENT_ADDED",
        ).last()
        assert event is not None

    # Test 12: POST sem nota falha
    def test_supplemental_attachment_form_requires_note_in_view(self, client) -> None:
        """POST sem nota deve falhar com mensagem."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        url = reverse("intake:supplemental_attachment_add", args=[case.case_id])
        pdf_file = SimpleUploadedFile(
            "complemento.pdf", _create_pdf_bytes("complemento"), content_type="application/pdf"
        )

        response = client.post(
            url,
            {"attachment_files": pdf_file, "note": ""},
            follow=True,
        )

        assert response.status_code == 200
        assert (
            "justificativa" in response.content.decode().lower() or "obrigatória" in response.content.decode().lower()
        )

    # Test 7: lock médico bloqueia
    def test_nir_supplemental_attachment_blocked_when_doctor_lock_active(self, client) -> None:
        """Caso WAIT_DOCTOR com lock ativo de médico mostra mensagem no template."""
        from apps.accounts.models import Role

        # Criar médico
        doctor = User.objects.create_user(username="doc_lock_block@test.com", password="testpass123")
        doc_role, _ = Role.objects.get_or_create(name="doctor")
        doctor.roles.add(doc_role)

        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        # Médico adquire lock
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        # NIR tenta POST
        url = reverse("intake:supplemental_attachment_add", args=[case.case_id])
        pdf_file = SimpleUploadedFile(
            "complemento.pdf", _create_pdf_bytes("complemento"), content_type="application/pdf"
        )

        response = client.post(
            url,
            {
                "attachment_files": pdf_file,
                "note": "Documento complementar.",
            },
            follow=True,
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "reservado" in content.lower()
        assert "Dr(a)" in content or "Aguarde" in content or "comunique" in content

        # Nenhum anexo complementar criado
        supp_attachments = list(case.attachments.filter(is_suppressed=False, upload_phase="supplemental"))
        assert len(supp_attachments) == 0

    # Test 8: sem lock permite
    def test_nir_supplemental_attachment_allowed_when_wait_doctor_without_lock(self, client) -> None:
        """Caso WAIT_DOCTOR sem lock permite POST."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        url = reverse("intake:supplemental_attachment_add", args=[case.case_id])
        pdf_file = SimpleUploadedFile(
            "complemento.pdf", _create_pdf_bytes("complemento"), content_type="application/pdf"
        )

        response = client.post(
            url,
            {
                "attachment_files": pdf_file,
                "note": "Documento complementar.",
            },
            follow=True,
        )

        assert response.status_code == 200

        att = case.attachments.filter(is_suppressed=False, upload_phase="supplemental").first()
        assert att is not None
        assert att.upload_phase == "supplemental"


@pytest.mark.django_db
class TestSupplementalAttachmentDisplay:
    """Testes de exibição de anexo complementar (badge/nota)."""

    def _create_supplemental_attachment(
        self, case: Case, user: Any, note: str = "Documento complementar."
    ) -> CaseAttachment:
        """Cria anexo complementar diretamente."""
        return CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile("supp.pdf", _create_pdf_bytes("supp"), content_type="application/pdf"),
            original_filename="supp.pdf",
            stored_filename="supp.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="s" * 64,
            uploaded_by=user,
            upload_phase="supplemental",
            uploaded_when_case_status=CaseStatus.WAIT_DOCTOR,
            note=note,
        )

    # Test 14: badge no detalhe NIR
    def test_intake_case_detail_marks_supplemental_attachment(self, client) -> None:
        """Detalhe NIR mostra badge de anexo complementar e nota."""
        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        att = self._create_supplemental_attachment(case, user)

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Deve mostrar badge/label indicando que foi adicionado após upload inicial
        assert "Adicionado após upload inicial" in content
        assert "não analisado" in content.lower()
        assert att.note in content

    # Test 13: badge na tela médica
    def test_doctor_decision_marks_supplemental_attachment(self, client) -> None:
        """Tela médica mostra badge de anexo complementar e nota."""
        from apps.accounts.models import Role

        client, doctor = _doctor_client(client)
        nir_role, _ = Role.objects.get_or_create(name="nir")
        nir_user = User.objects.create_user(username="nir_supp_display@test.com", password="testpass123")
        nir_user.roles.add(nir_role)

        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        att = self._create_supplemental_attachment(case, nir_user, note="USG complementar.")

        # Doctor must acquire lock first
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True

        response = client.get(reverse("doctor:decision", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Deve mostrar badge
        assert "Adicionado após upload inicial" in content
        assert "não analisado" in content.lower()
        assert att.note in content

    # Test 15: timeline event label
    def test_attachment_supplement_event_has_timeline_label(self, client) -> None:
        """Timeline mostra 'Anexo complementar adicionado'."""
        from apps.cases.services import add_supplemental_case_attachment

        client, user = _nir_client(client)
        case = Case.objects.create(created_by=user, status=CaseStatus.NEW)
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)

        uploaded_file = SimpleUploadedFile("supp.pdf", _create_pdf_bytes("supp"), content_type="application/pdf")

        add_supplemental_case_attachment(
            case=case,
            uploaded_file=uploaded_file,
            user=user,
            note="Documento complementar.",
        )

        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        assert "Anexo complementar adicionado" in content
