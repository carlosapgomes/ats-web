"""Tests for closed-case attachment PDF viewer (Slice 005).

Tests:
- closed_case_attachment binary route (R1)
- closed_case_attachment_pdf_viewer route (R2)
- Template updates in closed_case_detail.html (R3)
- Operational serve_attachment still blocks CLEANED (R4)
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.cases.models import Case, CaseAttachment, CaseStatus

User = get_user_model()


def _create_role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _login_as(client, role_name: str, username_suffix: str = "@ca-vw"):
    user = User.objects.create_user(username=f"{role_name}{username_suffix}", password="testpass123")
    user.roles.add(_create_role(role_name))
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


_ca_fixture_counter: int = 0


def _create_cleaned_case_with_pdf_and_attachment(
    pdf_content: bytes | None = None,
    username_suffix: str | None = None,
) -> tuple[Case, CaseAttachment]:
    """Create a CLEANED case with pdf_file + one non-suppressed PDF attachment.

    Creates the case directly via FSM-compatible approach: set status directly
    in the database using update() to bypass FSM protection.
    """
    global _ca_fixture_counter
    _ca_fixture_counter += 1
    suffix = username_suffix or f"@ca-fix-{_ca_fixture_counter}"
    nir_user = User.objects.create_user(
        username=f"nir-fixture-{suffix}",
        password="testpass123",
    )
    nir_user.roles.add(_create_role("nir"))
    case = Case.objects.create(
        created_by=nir_user,
        status=CaseStatus.NEW,
        structured_data={"patient": {"name": "Closed Attachment", "age": 50, "gender": "Feminino"}},
    )
    # Set to CLEANED via queryset update to bypass FSM
    Case.objects.filter(pk=case.pk).update(status=CaseStatus.CLEANED)
    # Re-fetch from DB to get updated status
    case = Case.objects.get(pk=case.pk)
    assert case.status == CaseStatus.CLEANED

    case.pdf_file.save("test.pdf", ContentFile(b"%PDF-1.4 fake pdf"), save=True)

    att_content = pdf_content or b"%PDF-1.4 fake attachment pdf for closed case"
    attachment = CaseAttachment.objects.create(
        case=case,
        file=ContentFile(att_content, name="attached_report.pdf"),
        original_filename="attached_report.pdf",
        content_type="application/pdf",
        size_bytes=len(att_content),
        uploaded_by=nir_user,
        upload_phase="initial",
    )
    return case, attachment


# ── R1: closed_case_attachment binary route ──────────────────────────


@pytest.mark.django_db
class TestClosedCaseAttachmentBinary:
    """Tests for intake:closed_case_attachment binary route."""

    def test_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = reverse("intake:closed_case_attachment", args=[uuid.uuid4(), uuid.uuid4()])
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_blocks_doctor(self, client) -> None:
        """User with active_role='doctor' cannot access closed_case_attachment."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "doctor", "@ca-bin-doctor")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 302
        assert response.url == "/"

    def test_blocks_scheduler(self, client) -> None:
        """User with active_role='scheduler' cannot access closed_case_attachment."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "scheduler", "@ca-bin-sch")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 302
        assert response.url == "/"

    def test_serves_pdf_for_authorized_nir(self, client) -> None:
        """NIR with active_role='nir' gets 200 + correct Content-Type."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-bin-nir")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_has_no_store_cache_control(self, client) -> None:
        """Response includes Cache-Control: no-store."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-bin-nocache")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        cache_control = response.get("Cache-Control", "")
        assert "no-store" in cache_control

    def test_404_for_suppressed_attachment(self, client) -> None:
        """Returns 404 when attachment is suppressed."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        att.is_suppressed = True
        att.suppression_reason = "Test suppression"
        att.save()
        _login_as(client, "nir", "@ca-bin-sup")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 404

    def test_404_for_case_outside_historical_scope(self, client) -> None:
        """Returns 404 when case is not in historical scope NIR."""
        nir_user = User.objects.create_user(username="nir-outscope@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Out Scope", "age": 40, "gender": "M"}},
        )
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(b"%PDF-1.4 fake", name="test.pdf"),
            original_filename="test.pdf",
            content_type="application/pdf",
            size_bytes=20,
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ca-bin-outscope")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 404

    def test_404_for_attachment_not_belonging_to_case(self, client) -> None:
        """Returns 404 when attachment_id does not belong to the given case."""
        case1, _ = _create_cleaned_case_with_pdf_and_attachment()
        # Create another case with a different attachment
        case2, att2 = _create_cleaned_case_with_pdf_and_attachment(pdf_content=b"%PDF-1.4 other case pdf")
        _login_as(client, "nir", "@ca-bin-wrong")
        # Try to access att2 through case1 URL — should 404
        response = client.get(reverse("intake:closed_case_attachment", args=[case1.case_id, att2.attachment_id]))
        assert response.status_code == 404

    def test_xframe_options_sameorigin(self, client) -> None:
        """Response has X-Frame-Options: SAMEORIGIN for embed compatibility."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-bin-xfo")
        response = client.get(reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 200
        assert response.get("X-Frame-Options") == "SAMEORIGIN"


# ── R2: closed_case_attachment_pdf_viewer route ──────────────────────


@pytest.mark.django_db
class TestClosedCaseAttachmentPdfViewer:
    """Tests for intake:closed_case_attachment_pdf_viewer route."""

    def test_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = reverse("intake:closed_case_attachment_pdf_viewer", args=[uuid.uuid4(), uuid.uuid4()])
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_renders_for_authorized_nir(self, client) -> None:
        """NIR with active_role='nir' gets 200."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 200

    def test_404_for_image_attachment(self, client) -> None:
        """Returns 404 when attachment is an image, not PDF."""
        nir_user = User.objects.create_user(username="nir-img-vw@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake image bytes"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="photo.jpg"),
            original_filename="photo.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ca-vw-img")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 404

    def test_contains_closed_case_attachment_url_as_pdf_source(self, client) -> None:
        """Viewer page contains closed_case_attachment URL as the PDF source."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-src")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        content = response.content.decode()
        att_url = reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id])
        assert att_url in content

    def test_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' in top nav and bottom section."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-back")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        content = response.content.decode()
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    def test_has_fallback_open_original(self, client) -> None:
        """Viewer contains fallback to open original PDF."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-fb")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        content = response.content.decode()
        assert "Abrir PDF original" in content or "PDF original" in content

    def test_back_url_defaults_to_closed_detail(self, client) -> None:
        """Back URL defaults to intake:closed_case_detail when no next param."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-def")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        content = response.content.decode()
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        assert closed_detail_url in content

    def test_rejects_external_next(self, client) -> None:
        """Back URL falls back to closed_case_detail when next is external."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-ext")
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
            + "?next=https://evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert closed_detail_url in content

    def test_rejects_protocol_relative_next(self, client) -> None:
        """Back URL falls back to closed_case_detail when next is protocol-relative."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-vw-pr")
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
            + "?next=//evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert closed_detail_url in content

    def test_blocks_doctor_role(self, client) -> None:
        """User with active_role='doctor' gets redirected."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "doctor", "@ca-vw-doc")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 302
        assert response.url == "/"

    def test_404_for_suppressed_attachment(self, client) -> None:
        """Returns 404 when attachment is suppressed."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        att.is_suppressed = True
        att.suppression_reason = "Test suppression"
        att.save()
        _login_as(client, "nir", "@ca-vw-sup")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 404

    def test_404_for_case_outside_historical_scope(self, client) -> None:
        """Returns 404 when case is not in historical scope NIR."""
        nir_user = User.objects.create_user(username="nir-outscope-vw@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Out Scope", "age": 40, "gender": "M"}},
        )
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(b"%PDF-1.4 fake", name="test.pdf"),
            original_filename="test.pdf",
            content_type="application/pdf",
            size_bytes=20,
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ca-vw-outscope")
        response = client.get(
            reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 404


# ── R3: closed_case_detail.html template updates ─────────────────────


@pytest.mark.django_db
class TestClosedCaseDetailAttachmentLinks:
    """Tests that closed_case_detail.html has correct attachment links."""

    def _create_cleaned_case_with_pdf_and_attachments(self) -> tuple[Case, CaseAttachment]:
        """Create CLEANED case with PDF + PDF attachment + image attachment."""
        nir_user = User.objects.create_user(username="nir-tmpl@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Template Test", "age": 45, "gender": "M"}},
        )
        case.pdf_file.save("test.pdf", ContentFile(b"%PDF-1.4 fake"), save=True)

        # PDF attachment
        pdf_content = b"%PDF-1.4 attachment pdf"
        pdf_att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(pdf_content, name="report.pdf"),
            original_filename="report.pdf",
            content_type="application/pdf",
            size_bytes=len(pdf_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        return case, pdf_att

    def test_mobile_pdf_attachment_link_uses_internal_viewer(self, client) -> None:
        """Mobile PDF attachment link points to closed_case_attachment_pdf_viewer."""
        case, att = self._create_cleaned_case_with_pdf_and_attachments()
        _login_as(client, "nir", "@ca-tmpl-nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        assert viewer_url in content, (
            f"Mobile PDF attachment link should reference closed_case_attachment_pdf_viewer URL: {viewer_url}"
        )

    def test_mobile_pdf_attachment_link_no_target_blank(self, client) -> None:
        """Mobile PDF attachment link does NOT use target='_blank'."""
        case, att = self._create_cleaned_case_with_pdf_and_attachments()
        _login_as(client, "nir", "@ca-tmpl-notb")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("intake:closed_case_attachment_pdf_viewer", args=[case.case_id, att.attachment_id])
        import re

        mobile_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(viewer_url)}[^"]*"[^>]*>.*?</a>',
            content,
            re.DOTALL,
        )
        for link in mobile_links:
            assert 'target="_blank"' not in link, "Mobile PDF attachment link should not use target='_blank'"

    def test_desktop_embed_uses_closed_case_attachment(self, client) -> None:
        """Desktop <embed> for PDF attachment uses closed_case_attachment binary route."""
        case, att = self._create_cleaned_case_with_pdf_and_attachments()
        _login_as(client, "nir", "@ca-tmpl-emb")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        att_url = reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id])
        assert f'<embed src="{att_url}"' in content or ('<embed src="' in content and att_url in content), (
            f"Desktop embed for attachment should use closed_case_attachment URL: {att_url}"
        )

    def test_desktop_new_tab_button_uses_closed_case_attachment(self, client) -> None:
        """Desktop 'Abrir em nova aba' button uses closed_case_attachment binary route."""
        case, att = self._create_cleaned_case_with_pdf_and_attachments()
        _login_as(client, "nir", "@ca-tmpl-ntab")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        att_url = reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id])
        # Find Abrir em nova aba buttons that reference the attachment URL
        import re

        new_tab_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(att_url)}[^"]*"[^>]*target="_blank"[^>]*>.*?Abrir em nova aba.*?</a>',
            content,
            re.DOTALL,
        )
        assert len(new_tab_links) >= 1, f"Should find at least one 'Abrir em nova aba' with attachment URL {att_url}"


# ── R4: Operational serve_attachment still blocks CLEANED ────────────


@pytest.mark.django_db
# ── Slice 006: Image viewer for closed-case (historical) ────────────────


@pytest.mark.django_db
class TestClosedCaseAttachmentImageViewer:
    """Tests for intake:closed_case_attachment_image_viewer route (Slice 006)."""

    def test_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = reverse("intake:closed_case_attachment_image_viewer", args=[uuid.uuid4(), uuid.uuid4()])
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_renders_for_authorized_nir_with_jpeg(self, client) -> None:
        """NIR with active_role='nir' gets 200 for JPEG image."""
        nir_user = User.objects.create_user(username="nir-ccimg-jpeg@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake image bytes"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="photo.jpg"),
            original_filename="photo.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-jpeg-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 200
        content = response.content.decode()
        att_url = reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id])
        assert att_url in content
        assert "<img" in content or "img-fluid" in content

    def test_renders_for_authorized_nir_with_png(self, client) -> None:
        """NIR gets 200 for PNG image."""
        nir_user = User.objects.create_user(username="nir-ccimg-png@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake png bytes"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="image.png"),
            original_filename="image.png",
            content_type="image/png",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-png-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 200

    def test_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' in top and bottom sections."""
        nir_user = User.objects.create_user(username="nir-ccimg-back@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="img.jpg"),
            original_filename="img.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-back-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        content = response.content.decode()
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    def test_404_for_pdf_attachment(self, client) -> None:
        """Returns 404 when attachment is PDF, not image."""
        nir_user = User.objects.create_user(username="nir-ccimg-pdf@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(b"%PDF-1.4", name="doc.pdf"),
            original_filename="doc.pdf",
            content_type="application/pdf",
            size_bytes=20,
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-pdf-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 404

    def test_404_for_suppressed_attachment(self, client) -> None:
        """Returns 404 when attachment is suppressed."""
        nir_user = User.objects.create_user(username="nir-ccimg-sup@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="img.jpg"),
            original_filename="img.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
            is_suppressed=True,
            suppression_reason="Test suppression",
        )
        _login_as(client, "nir", "@ccimg-sup-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 404

    def test_blocks_doctor_role(self, client) -> None:
        """User with active_role='doctor' gets redirected."""
        case, _ = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "doctor", "@ccimg-doc")
        response = client.get(reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, uuid.uuid4()]))
        assert response.status_code == 302
        assert response.url == "/"

    def test_back_url_defaults_to_closed_detail(self, client) -> None:
        """Back URL defaults to intake:closed_case_detail when no next param."""
        nir_user = User.objects.create_user(username="nir-ccimg-def@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="img.jpg"),
            original_filename="img.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-def-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        content = response.content.decode()
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        assert closed_detail_url in content

    def test_rejects_external_next(self, client) -> None:
        """Back URL falls back to closed_case_detail when next is external."""
        nir_user = User.objects.create_user(username="nir-ccimg-ext@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="img.jpg"),
            original_filename="img.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-ext-nir")
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
            + "?next=https://evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert closed_detail_url in content

    def test_404_for_case_outside_historical_scope(self, client) -> None:
        """Returns 404 when case is not in historical scope NIR."""
        nir_user = User.objects.create_user(username="nir-ccimg-out@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="img.jpg"),
            original_filename="img.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@ccimg-out-nir")
        response = client.get(
            reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestClosedCaseDetailImageAttachmentLinks:
    """Tests that closed_case_detail.html mobile image link uses internal viewer (Slice 006)."""

    def test_closed_case_image_attachment_mobile_link_uses_internal_viewer(self, client) -> None:
        """Image attachment mobile link points to closed_case_attachment_image_viewer."""
        nir_user = User.objects.create_user(username="nir-tmpl-img@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Template Img", "age": 45, "gender": "M"}},
        )
        img_content = b"fake image for template link test"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="clinical_photo.jpg"),
            original_filename="clinical_photo.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@tmpl-img-nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
        assert viewer_url in content, (
            f"Mobile image attachment link should reference closed_case_attachment_image_viewer URL: {viewer_url}"
        )

    def test_closed_case_image_attachment_mobile_link_no_target_blank(self, client) -> None:
        """Image attachment mobile link does NOT use target='_blank'."""
        nir_user = User.objects.create_user(username="nir-tmpl-img2@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Template Img2", "age": 45, "gender": "M"}},
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="clinical_photo.jpg"),
            original_filename="clinical_photo.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@tmpl-img2-nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("intake:closed_case_attachment_image_viewer", args=[case.case_id, att.attachment_id])
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

    def test_closed_case_image_attachment_desktop_inline_img_preserved(self, client) -> None:
        """Desktop image attachment still uses <img> with closed_case_attachment."""
        nir_user = User.objects.create_user(username="nir-tmpl-img3@test.test", password="testpass123")
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Template Img3", "age": 45, "gender": "M"}},
        )
        img_content = b"fake image"
        att = CaseAttachment.objects.create(
            case=case,
            file=ContentFile(img_content, name="clinical_photo.jpg"),
            original_filename="clinical_photo.jpg",
            content_type="image/jpeg",
            size_bytes=len(img_content),
            uploaded_by=nir_user,
            upload_phase="initial",
        )
        _login_as(client, "nir", "@tmpl-img3-nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        att_url = reverse("intake:closed_case_attachment", args=[case.case_id, att.attachment_id])
        assert "<img" in content and att_url in content, (
            "Desktop should still have <img> for image attachments using historical binary route"
        )


class TestOperationalServeAttachmentBlocksCleaned:
    """Tests that intake:serve_attachment (operational) still blocks CLEANED cases."""

    def test_serve_attachment_blocks_cleaned_case(self, client) -> None:
        """intake:serve_attachment returns 404 for CLEANED case."""
        case, att = _create_cleaned_case_with_pdf_and_attachment()
        _login_as(client, "nir", "@ca-sa-cl")
        response = client.get(reverse("intake:serve_attachment", args=[case.case_id, att.attachment_id]))
        assert response.status_code == 404, "Operational serve_attachment should block CLEANED cases"
