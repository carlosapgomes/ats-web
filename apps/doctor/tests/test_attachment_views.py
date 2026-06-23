"""Testes da tela médica com anexos — Slice 001.

RED phase: testes falham antes da implementação.
"""

from __future__ import annotations

import io
import uuid

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cases.models import Case, CaseAttachment, CaseStatus

User = get_user_model()


def _create_pdf_bytes(text: str = "Paciente: Teste\nRegistro: 2026-0001") -> bytes:
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
        CaseStatus.WAIT_APPT: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decide(decision='accept')",
            "ready_for_scheduler",
            "scheduler_request_posted",
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


def _setup_case_with_attachments(
    attachment_count: int = 2,
    suppress_some: bool = False,
):
    """Helper: cria NIR, caso WAIT_DOCTOR e attachments."""
    from apps.accounts.models import Role

    nir_user = User.objects.create_user(username="nir_doc_attach@test.com", password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    nir_user.roles.add(role)

    case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
    case.structured_data = {"patient": {"name": "Paciente Anexos", "age": 45, "gender": "Masculino"}}
    case.save()
    case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
    case.structured_data = {"patient": {"name": "Paciente Anexos", "age": 45, "gender": "Masculino"}}
    case.save()

    attachments = []
    for i in range(attachment_count):
        is_supp = suppress_some and i == 0
        content_type = "application/pdf" if i % 2 == 0 else "image/jpeg"
        ext = ".pdf" if i % 2 == 0 else ".jpg"
        content = (
            _create_pdf_bytes(f"Attachment {i}") if ext == ".pdf" else b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"\xff\xd9"
        )
        filename = f"att_{i}{ext}"

        att = CaseAttachment.objects.create(
            case=case,
            file=SimpleUploadedFile(filename, content, content_type=content_type),
            original_filename=filename,
            stored_filename=f"stored_{i}{ext}",
            content_type=content_type,
            size_bytes=len(content),
            sha256="a" * 64,
            uploaded_by=nir_user,
            is_suppressed=is_supp,
            suppressed_at="2026-06-01T00:00:00Z" if is_supp else None,
            suppression_reason="Test suppression" if is_supp else "",
            upload_phase="initial",
            uploaded_when_case_status=CaseStatus.NEW,
        )
        attachments.append(att)

    return case, attachments, nir_user


@pytest.mark.django_db
class TestDoctorDecisionAttachmentDisplay:
    """Testes de exibição de anexos na tela de decisão médica."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_display_att@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_doctor_decision_displays_attachment_section(self, client) -> None:
        """Tela médica exibe seção de anexos com aviso."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Deve conter o nome original do anexo
        assert attachments[0].original_filename in content
        # Deve conter o aviso de que anexos não foram analisados pelo sistema
        assert "não analisados" in content.lower() or "automaticamente" in content.lower()

    def test_doctor_decision_embeds_pdf_attachment(self, client) -> None:
        """Anexo PDF gera embed/link da rota protegida."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        # Garantir que o anexo 0 é PDF
        att = attachments[0]
        att.content_type = "application/pdf"
        att.original_filename = "laudo.pdf"
        att.save()

        self._login_doctor(client)
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Deve conter embed/link para a rota protegida dentro de um collapse fechado por padrão
        collapse_id = f"attachment-collapse-{att.attachment_id}"
        assert f"/doctor/cases/{case.case_id}/attachments/{att.attachment_id}/" in content
        assert f'href="#{collapse_id}"' in content or f'data-bs-target="#{collapse_id}"' in content
        assert f'id="{collapse_id}"' in content
        assert 'data-bs-toggle="collapse"' in content
        assert "embed" in content.lower() or 'type="application/pdf"' in content.lower()

    def test_doctor_decision_embeds_image_attachment(self, client) -> None:
        """Anexo JPEG/PNG gera <img>."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        # Garantir que o anexo 0 é imagem
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.original_filename = "foto.jpg"
        att.save()

        self._login_doctor(client)
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Deve conter <img> com src para a rota protegida dentro de um collapse fechado por padrão
        collapse_id = f"attachment-collapse-{att.attachment_id}"
        assert f"/doctor/cases/{case.case_id}/attachments/{att.attachment_id}/" in content
        assert f'href="#{collapse_id}"' in content or f'data-bs-target="#{collapse_id}"' in content
        assert f'id="{collapse_id}"' in content
        assert 'data-bs-toggle="collapse"' in content
        assert "<img" in content.lower() or "img-fluid" in content.lower()

    def test_doctor_decision_does_not_show_suppressed_attachments(self, client) -> None:
        """Anexo suprimido não aparece na tela médica."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=2, suppress_some=True)
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        # Anexo suprimido (primeiro) não deve aparecer
        assert attachments[0].original_filename not in content
        # Anexo ativo (segundo) deve aparecer
        assert attachments[1].original_filename in content


@pytest.mark.django_db
class TestDoctorServeAttachmentView:
    """Testes da view protegida de servir anexo."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_serve_att@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_serves_authorized_attachment(self, client) -> None:
        """Médico acessa anexo de caso em WAIT_DOCTOR."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        self._login_doctor(client)
        att = attachments[0]

        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == att.content_type

    def test_requires_authorized_case(self, client) -> None:
        """Médico não acessa anexo de caso decidido por outro médico e fora de sua fila."""
        case, attachments, nir_user = _setup_case_with_attachments(attachment_count=1)

        # Avançar caso decidido por outro médico via FSM
        other_doctor = User.objects.create_user(username="other_doc@test.com", password="testpass123")
        other_doctor.roles.add(self._create_role("doctor"))
        other_doctor.save()

        # Advances via FSM: WAIT_DOCTOR → DOCTOR_ACCEPTED → R3_POST_REQUEST → WAIT_APPT
        case.doctor = other_doctor
        case.doctor_decision = "accept"
        case.doctor_decided_at = "2026-06-01T00:00:00Z"
        case.doctor_decide(decision="accept", user=other_doctor)
        case.save()
        case.ready_for_scheduler(user=other_doctor)
        case.save()
        case.scheduler_request_posted(user=other_doctor)
        case.save()

        self._login_doctor(client)
        att = attachments[0]

        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id]))
        # Deve retornar 404 pois o médico logado não é o doctor do caso
        # e o caso não está em WAIT_DOCTOR
        assert response.status_code == 404

    def test_does_not_serve_suppressed_attachment(self, client) -> None:
        """Anexo suprimido retorna 404."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1, suppress_some=True)
        self._login_doctor(client)

        # Primeiro anexo é suprimido
        suppressed_att = attachments[0]
        assert suppressed_att.is_suppressed is True

        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, suppressed_att.attachment_id]))
        assert response.status_code == 404

    def test_returns_404_for_nonexistent_attachment(self, client) -> None:
        """Anexo inexistente retorna 404."""
        case, _, _ = _setup_case_with_attachments(attachment_count=1)
        self._login_doctor(client)

        fake_id = uuid.uuid4()
        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, fake_id]))
        assert response.status_code == 404

    def test_requires_doctor_role(self, client) -> None:
        """Usuário NIR não pode acessar rota de anexo médico."""
        from apps.accounts.models import Role

        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)

        nir_user = User.objects.create_user(username="nir_serve_att@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nir")
        nir_user.roles.add(role)
        client.force_login(nir_user)
        session = client.session
        session["active_role"] = "nir"
        session.save()

        att = attachments[0]
        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 302  # redirect to /

    def test_serves_attachment_for_own_decided_case(self, client) -> None:
        """Médico acessa anexo de caso que ele mesmo decidiu."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        doctor = self._login_doctor(client)

        # Mark as decided by this doctor via FSM
        case.doctor = doctor
        case.doctor_decision = "accept"
        case.doctor_decided_at = "2026-06-01T00:00:00Z"
        case.doctor_decide(decision="accept", user=doctor)
        case.save()

        att = attachments[0]
        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == att.content_type


@pytest.mark.django_db
class TestDoctorDecisionRegressionAfterTemplateChanges:
    """Regressão: alterações no template compartilhado não quebram tela médica."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_regr_att@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_doctor_decision_still_renders_attachments_after_shared_template_changes(self, client) -> None:
        """Tela médica continua exibindo anexos após alterações no template compartilhado."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=2)
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Ambos os anexos devem aparecer
        assert attachments[0].original_filename in content
        assert attachments[1].original_filename in content
        # Aviso sobre anexos não analisados pelo sistema deve estar presente
        assert "não analisados" in content.lower() or "automaticamente" in content.lower()
        # Seção de anexos deve existir
        assert "Anexos Clínicos" in content or "📎" in content
        # PDF principal não está presente neste setup (sem pdf_file),
        # mas os anexos devem estar completos
        assert attachments[0].original_filename in content
        assert attachments[1].original_filename in content


@pytest.mark.django_db
class TestDoctorAttachmentSuppressionRegression:
    """Regressão: anexos suprimidos não aparecem para o médico (Slice 003)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_supp_regr@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_doctor_decision_does_not_render_suppressed_attachment(self, client) -> None:
        """Anexo suprimido não aparece na tela médica (apenas ativos)."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=2, suppress_some=True)
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Anexo suprimido (primeiro) não deve aparecer
        assert attachments[0].original_filename not in content
        # Anexo ativo (segundo) deve aparecer
        assert attachments[1].original_filename in content

    def test_doctor_attachment_view_does_not_serve_suppressed_attachment(self, client) -> None:
        """Rota médica retorna 404 para anexo suprimido."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1, suppress_some=True)
        self._login_doctor(client)

        # Primeiro anexo é suprimido
        suppressed_att = attachments[0]
        assert suppressed_att.is_suppressed is True

        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, suppressed_att.attachment_id]))
        assert response.status_code == 404
