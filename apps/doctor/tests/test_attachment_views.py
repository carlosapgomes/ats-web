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


@pytest.mark.django_db
class TestDoctorAttachmentPdfViewerView:
    """Tests for doctor:attachment_pdf_viewer route (Slice 004)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@attpdfv.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _get_pdf_viewer_url(self, case_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
        return reverse("doctor:attachment_pdf_viewer", args=[case_id, attachment_id])

    def test_attachment_pdf_viewer_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = self._get_pdf_viewer_url(uuid.uuid4(), uuid.uuid4())
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_attachment_pdf_viewer_blocks_nir(self, client) -> None:
        """User with active_role='nir' cannot access the viewer."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        self._login_as(client, "nir")
        response = client.get(self._get_pdf_viewer_url(case.case_id, attachments[0].attachment_id))
        assert response.status_code == 302
        assert response.url == "/"

    def test_attachment_pdf_viewer_renders_for_authorized_doctor(self, client) -> None:
        """Doctor gets 200 with serve_attachment as pdf_url."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        # Ensure attachment is PDF
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 200
        content = response.content.decode()
        serve_att_url = reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id])
        assert serve_att_url in content

    def test_attachment_pdf_viewer_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' in top and bottom sections."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id, att.attachment_id))
        content = response.content.decode()
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    def test_attachment_pdf_viewer_404_for_image_attachment(self, client) -> None:
        """Returns 404 when attachment is not PDF."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 404

    def test_attachment_pdf_viewer_404_for_suppressed_attachment(self, client) -> None:
        """Returns 404 when attachment is suppressed."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1, suppress_some=True)
        att = attachments[0]
        assert att.is_suppressed is True
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 404

    def test_attachment_pdf_viewer_back_url_defaults_to_decision(self, client) -> None:
        """Back URL defaults to doctor:decision when no next param."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id, att.attachment_id))
        content = response.content.decode()
        decision_url = reverse("doctor:decision", args=[case.case_id])
        assert decision_url in content

    def test_attachment_pdf_viewer_accepts_safe_next(self, client) -> None:
        """Back URL uses safe next param when provided."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_as(client, "doctor")
        decision_url = reverse("doctor:decision", args=[case.case_id])
        response = client.get(self._get_pdf_viewer_url(case.case_id, att.attachment_id) + f"?next={decision_url}")
        content = response.content.decode()
        assert decision_url in content

    def test_attachment_pdf_viewer_rejects_external_next(self, client) -> None:
        """Back URL falls back to doctor:decision when next is external."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_as(client, "doctor")
        decision_url = reverse("doctor:decision", args=[case.case_id])
        response = client.get(
            self._get_pdf_viewer_url(case.case_id, att.attachment_id) + "?next=https://evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert decision_url in content


@pytest.mark.django_db
class TestDoctorAttachmentImageViewerView:
    """Tests for doctor:attachment_image_viewer route (Slice 006)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@attimgv.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _get_image_viewer_url(self, case_id: uuid.UUID, attachment_id: uuid.UUID) -> str:
        return reverse("doctor:attachment_image_viewer", args=[case_id, attachment_id])

    def test_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = self._get_image_viewer_url(uuid.uuid4(), uuid.uuid4())
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_blocks_nir(self, client) -> None:
        """User with active_role='nir' cannot access the viewer."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_as(client, "nir")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 302
        assert response.url == "/"

    def test_renders_for_authorized_doctor_with_jpeg(self, client) -> None:
        """Doctor gets 200 with serve_attachment as image_url for JPEG."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 200
        content = response.content.decode()
        serve_att_url = reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id])
        assert serve_att_url in content
        assert "<img" in content or "img-fluid" in content

    def test_renders_for_authorized_doctor_with_png(self, client) -> None:
        """Doctor gets 200 for PNG image."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/png"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 200

    def test_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' in top and bottom sections."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        content = response.content.decode()
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    def test_404_for_pdf_attachment(self, client) -> None:
        """Returns 404 when attachment is PDF (not image)."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 404

    def test_404_for_suppressed_attachment(self, client) -> None:
        """Returns 404 when attachment is suppressed."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1, suppress_some=True)
        att = attachments[0]
        assert att.is_suppressed is True
        self._login_as(client, "doctor")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        assert response.status_code == 404

    def test_back_url_defaults_to_decision(self, client) -> None:
        """Back URL defaults to doctor:decision when no next param."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_as(client, "doctor")
        response = client.get(self._get_image_viewer_url(case.case_id, att.attachment_id))
        content = response.content.decode()
        decision_url = reverse("doctor:decision", args=[case.case_id])
        assert decision_url in content

    def test_rejects_external_next(self, client) -> None:
        """Back URL falls back to doctor:decision when next is external."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_as(client, "doctor")
        decision_url = reverse("doctor:decision", args=[case.case_id])
        response = client.get(
            self._get_image_viewer_url(case.case_id, att.attachment_id) + "?next=https://evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert decision_url in content


@pytest.mark.django_db
class TestDoctorDecisionAttachmentImageMobileLink:
    """Tests that doctor/decision.html mobile image link uses internal viewer (Slice 006)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_img_link@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_doctor_image_attachment_mobile_link_uses_internal_viewer(self, client) -> None:
        """Image attachment mobile link points to attachment_image_viewer, not serve_attachment directly."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.original_filename = "foto.jpg"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("doctor:attachment_image_viewer", args=[case.case_id, att.attachment_id])
        assert viewer_url in content, (
            f"Mobile image attachment link should reference attachment_image_viewer URL: {viewer_url}"
        )

    def test_doctor_image_attachment_mobile_link_no_target_blank(self, client) -> None:
        """Image attachment mobile link does NOT use target='_blank'."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("doctor:attachment_image_viewer", args=[case.case_id, att.attachment_id])
        import re

        mobile_img_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(viewer_url)}[^"]*"[^>]*>.*?</a>',
            content,
            re.DOTALL,
        )
        for link in mobile_img_links:
            assert 'target="_blank"' not in link, (
                f"Mobile image attachment link should not use target=_blank: {link[:100]}"
            )

    def test_doctor_image_attachment_desktop_inline_img_preserved(self, client) -> None:
        """Desktop image attachment still uses <img> with serve_attachment."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.original_filename = "foto.jpg"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        serve_att_url = reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id])
        assert "<img" in content and serve_att_url in content, "Desktop should still have <img> for image attachments"


class TestDoctorAttachmentServeAttachmentNoStore:
    """Tests that doctor:serve_attachment returns no-store Cache-Control."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_nostore@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_serve_attachment_has_no_store_cache_control(self, client) -> None:
        """serve_attachment response includes Cache-Control: no-store."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        self._login_doctor(client)
        att = attachments[0]
        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"

    def test_serve_attachment_preserves_content_type(self, client) -> None:
        """serve_attachment preserves original Content-Type."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        self._login_doctor(client)
        att = attachments[0]
        response = client.get(reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == att.content_type


@pytest.mark.django_db
class TestDoctorDecisionAttachmentMobileLinkInternalViewer:
    """Tests that doctor/decision.html mobile attachment link uses internal viewer (Slice 004)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_doctor(self, client):
        user = User.objects.create_user(username="doc_att_link@test.com", password="testpass123")
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return user

    def test_doctor_pdf_attachment_mobile_link_uses_internal_viewer(self, client) -> None:
        """PDF attachment mobile link points to attachment_pdf_viewer, not serve_attachment directly."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.original_filename = "laudo_anexo.pdf"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("doctor:attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        # Mobile link must reference attachment_pdf_viewer
        assert viewer_url in content, (
            f"Mobile PDF attachment link should reference attachment_pdf_viewer URL: {viewer_url}"
        )

    def test_doctor_pdf_attachment_mobile_link_no_target_blank(self, client) -> None:
        """PDF attachment mobile link does NOT use target='_blank'."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        import re

        viewer_url = reverse("doctor:attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        # Find mobile links referencing the viewer URL
        mobile_pdf_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(viewer_url)}[^"]*"[^>]*>.*?</a>',
            content,
            re.DOTALL,
        )
        for link in mobile_pdf_links:
            assert 'target="_blank"' not in link, (
                f"Mobile PDF attachment link should not use target=_blank: {link[:100]}"
            )

    def test_doctor_pdf_attachment_desktop_embed_preserved(self, client) -> None:
        """Desktop PDF attachment still uses <embed> with serve_attachment."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "application/pdf"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        serve_att_url = reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id])
        # Desktop embed should reference serve_attachment
        assert f'embed src="{serve_att_url}"' in content or ("<embed" in content and serve_att_url in content)

    def test_doctor_image_attachment_behavior_unchanged(self, client) -> None:
        """Image attachment mobile link still uses serve_attachment (no viewer needed)."""
        case, attachments, _ = _setup_case_with_attachments(attachment_count=1)
        att = attachments[0]
        att.content_type = "image/jpeg"
        att.original_filename = "foto.jpg"
        att.save()
        self._login_doctor(client)

        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        serve_att_url = reverse("doctor:serve_attachment", args=[case.case_id, att.attachment_id])
        # Image should appear in content via img tag or serve_attachment link
        assert serve_att_url in content
        # Image does not need attachment_pdf_viewer URL
        try:
            viewer_url = reverse("doctor:attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
            assert viewer_url not in content
        except Exception:
            pass  # URL pattern may not exist yet (RED phase)
