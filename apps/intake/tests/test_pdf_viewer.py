"""Tests for intake PDF viewer routes (Slice 002).

Focus on:
- intake:pdf_viewer (operational NIR PDF viewer route)
- intake:closed_case_pdf_viewer (historical NIR PDF viewer route)
- Mobile link replacement in case_detail.html and closed_case_detail.html
- Cache-Control on intake:serve_pdf and intake:closed_case_pdf
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.cases.models import Case, CaseStatus

User = get_user_model()


def _advance_case_to(case: Case, target: str) -> Case:
    """Advance a Case through FSM transitions to reach a target status."""
    path: dict[str, list[str]] = {
        CaseStatus.WAIT_DOCTOR: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
        ],
        CaseStatus.WAIT_R1_CLEANUP_THUMBS: [
            "start_processing",
            "start_extraction",
            "extraction_complete(success=True)",
            "llm1_complete(success=True)",
            "llm2_complete(success=True)",
            "ready_for_doctor",
            "doctor_decided(decision='deny')",
            "waiting_appointment",
            "appointment_canceled(result='deny_triage')",
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
class TestIntakePdfViewerView:
    """Tests for intake:pdf_viewer route (operational NIR)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@intake-pdfv.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_operational_case_with_pdf(self) -> Case:
        """Create an operational (WAIT_DOCTOR) case with a real pdf_file."""
        nir_user = User.objects.create_user(username="nir-op@intake-pdfv.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.NEW,
            structured_data={"patient": {"name": "Intake PDF Viewer", "age": 40, "gender": "Masculino"}},
        )
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake pdf for testing"),
            save=True,
        )
        return case

    # ── Authorization tests ──────────────────────────────────────────

    def test_pdf_viewer_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = reverse("intake:pdf_viewer", args=[uuid.uuid4()])
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_pdf_viewer_blocks_doctor(self, client) -> None:
        """User with active_role='doctor' cannot access intake viewer."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        assert response.status_code == 302
        assert response.url == "/"

    def test_pdf_viewer_renders_for_authorized_nir(self, client) -> None:
        """NIR with active_role='nir' gets 200 on intake:pdf_viewer."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        assert response.status_code == 200

    def test_pdf_viewer_404_when_no_pdf(self, client) -> None:
        """Returns 404 when case has no pdf_file."""
        nir_user = User.objects.create_user(username="nir-no-pdf@intake-pdfv.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "No PDF", "age": 40, "gender": "M"}},
        )
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        assert response.status_code == 404

    def test_pdf_viewer_blocks_cleaned_case(self, client) -> None:
        """Operational viewer should NOT serve CLEANED cases (404)."""
        nir_user = User.objects.create_user(username="nir-cl@intake-pdfv.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Cleaned", "age": 40, "gender": "M"}},
        )
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        assert response.status_code == 404

    # ── Content tests ────────────────────────────────────────────────

    def test_pdf_viewer_contains_serve_pdf_url(self, client) -> None:
        """Viewer page contains intake:serve_pdf URL in data attribute."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        serve_pdf_url = reverse("intake:serve_pdf", args=[case.case_id])
        assert serve_pdf_url in content

    def test_pdf_viewer_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' in top nav and bottom section."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    def test_pdf_viewer_has_fallback_open_original(self, client) -> None:
        """Viewer contains fallback to open original PDF."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        assert "Abrir PDF original" in content or "PDF original" in content

    def test_pdf_viewer_back_url_defaults_to_case_detail(self, client) -> None:
        """Back URL defaults to intake:case_detail when no next param."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        case_detail_url = reverse("intake:case_detail", args=[case.case_id])
        assert case_detail_url in content

    def test_pdf_viewer_back_url_accepts_safe_next(self, client) -> None:
        """Back URL uses safe next param when provided."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        case_detail_url = reverse("intake:case_detail", args=[case.case_id])
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]) + f"?next={case_detail_url}")
        content = response.content.decode()
        assert case_detail_url in content

    def test_pdf_viewer_rejects_external_next(self, client) -> None:
        """Back URL falls back to intake:case_detail when next is external."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        case_detail_url = reverse("intake:case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:pdf_viewer", args=[case.case_id]) + "?next=https://evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert case_detail_url in content

    def test_pdf_viewer_rejects_protocol_relative_next(self, client) -> None:
        """Back URL falls back to intake:case_detail when next is protocol-relative."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        case_detail_url = reverse("intake:case_detail", args=[case.case_id])
        response = client.get(reverse("intake:pdf_viewer", args=[case.case_id]) + "?next=//evil.example.com/phish")
        content = response.content.decode()
        assert "evil.example" not in content
        assert case_detail_url in content


@pytest.mark.django_db
class TestIntakeClosedCasePdfViewerView:
    """Tests for intake:closed_case_pdf_viewer route (historical NIR)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@closed-pdfv.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_cleaned_case_with_pdf(self) -> Case:
        """Create a CLEANED case with a real pdf_file."""
        nir_user = User.objects.create_user(username="nir-closed@pdfv.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Closed Viewer", "age": 50, "gender": "Feminino"}},
        )
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake pdf for closed case testing"),
            save=True,
        )
        return case

    def test_closed_pdf_viewer_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = reverse("intake:closed_case_pdf_viewer", args=[uuid.uuid4()])
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_closed_pdf_viewer_blocks_doctor(self, client) -> None:
        """User with active_role='doctor' cannot access closed_case_pdf_viewer."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(reverse("intake:closed_case_pdf_viewer", args=[case.case_id]))
        assert response.status_code == 302
        assert response.url == "/"

    def test_closed_pdf_viewer_renders_for_authorized_nir(self, client) -> None:
        """NIR with active_role='nir' gets 200 on intake:closed_case_pdf_viewer."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf_viewer", args=[case.case_id]))
        assert response.status_code == 200

    def test_closed_pdf_viewer_contains_closed_case_pdf_url(self, client) -> None:
        """Viewer page contains intake:closed_case_pdf URL."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        closed_pdf_url = reverse("intake:closed_case_pdf", args=[case.case_id])
        assert closed_pdf_url in content

    def test_closed_pdf_viewer_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' in top nav and bottom section."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    def test_closed_pdf_viewer_back_url_defaults_to_closed_detail(self, client) -> None:
        """Back URL defaults to intake:closed_case_detail when no next param."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        assert closed_detail_url in content

    def test_closed_pdf_viewer_rejects_external_next(self, client) -> None:
        """Back URL falls back to closed_case_detail when next is external."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:closed_case_pdf_viewer", args=[case.case_id]) + "?next=https://evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert closed_detail_url in content

    def test_closed_pdf_viewer_rejects_protocol_relative_next(self, client) -> None:
        """Back URL falls back to closed_case_detail when next is protocol-relative."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:closed_case_pdf_viewer", args=[case.case_id]) + "?next=//evil.example.com/phish"
        )
        content = response.content.decode()
        assert "evil.example" not in content
        assert closed_detail_url in content

    def test_closed_pdf_viewer_has_fallback(self, client) -> None:
        """Viewer contains fallback to open original PDF."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf_viewer", args=[case.case_id]))
        content = response.content.decode()
        assert "Abrir PDF original" in content or "PDF original" in content

    def test_closed_pdf_viewer_accepts_safe_next(self, client) -> None:
        """Back URL uses safe next param when provided."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        closed_detail_url = reverse("intake:closed_case_detail", args=[case.case_id])
        response = client.get(
            reverse("intake:closed_case_pdf_viewer", args=[case.case_id]) + f"?next={closed_detail_url}"
        )
        content = response.content.decode()
        assert closed_detail_url in content


@pytest.mark.django_db
class TestIntakeCaseDetailMobilePdfLink:
    """Tests that intake/case_detail.html mobile link uses internal viewer."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@link-det.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_operational_case_with_pdf(self) -> Case:
        nir_user = User.objects.create_user(username="nir-op-link@det.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
            structured_data={"patient": {"name": "Mobile Link", "age": 40, "gender": "M"}},
        )
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake"),
            save=True,
        )
        return case

    def test_case_detail_mobile_pdf_link_uses_internal_viewer(self, client) -> None:
        """Mobile PDF link points to intake:pdf_viewer URL."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        pdf_viewer_url = reverse("intake:pdf_viewer", args=[case.case_id])
        assert pdf_viewer_url in content, f"Mobile PDF link should reference pdf_viewer URL: {pdf_viewer_url}"

    def test_case_detail_mobile_link_no_target_blank(self, client) -> None:
        """Mobile PDF link does NOT use target='_blank'."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        pdf_viewer_url = reverse("intake:pdf_viewer", args=[case.case_id])
        import re

        mobile_pdf_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(pdf_viewer_url)}[^"]*"[^>]*>.*?</a>',
            content,
            re.DOTALL,
        )
        for link in mobile_pdf_links:
            assert 'target="_blank"' not in link, "Mobile PDF link should not use target='_blank'"

    def test_case_detail_desktop_preserves_embed_with_serve_pdf(self, client) -> None:
        """Desktop section still has <embed> with serve_pdf URL."""
        case = self._create_operational_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        serve_pdf_url = reverse("intake:serve_pdf", args=[case.case_id])
        assert f'<embed src="{serve_pdf_url}"' in content or ('<embed src="' in content and serve_pdf_url in content), (
            "Desktop embed should use intake:serve_pdf"
        )


@pytest.mark.django_db
class TestIntakeClosedCaseDetailMobilePdfLink:
    """Tests that intake/closed_case_detail.html mobile link uses internal viewer."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@cl-link.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_cleaned_case_with_pdf(self) -> Case:
        nir_user = User.objects.create_user(username="nir-cl-link@test.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            structured_data={"patient": {"name": "Closed Link", "age": 50, "gender": "F"}},
        )
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake"),
            save=True,
        )
        return case

    def test_closed_case_detail_mobile_pdf_link_uses_internal_viewer(self, client) -> None:
        """Mobile PDF link on closed case detail points to closed_case_pdf_viewer."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("intake:closed_case_pdf_viewer", args=[case.case_id])
        assert viewer_url in content, f"Mobile PDF link should reference closed_case_pdf_viewer URL: {viewer_url}"

    def test_closed_case_detail_mobile_link_no_target_blank(self, client) -> None:
        """Mobile PDF link on closed case detail does NOT use target='_blank'."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        viewer_url = reverse("intake:closed_case_pdf_viewer", args=[case.case_id])
        import re

        mobile_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(viewer_url)}[^"]*"[^>]*>.*?</a>',
            content,
            re.DOTALL,
        )
        for link in mobile_links:
            assert 'target="_blank"' not in link

    def test_closed_case_detail_desktop_preserves_embed_with_closed_pdf(self, client) -> None:
        """Desktop section still has <embed> with closed_case_pdf URL."""
        case = self._create_cleaned_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        closed_pdf_url = reverse("intake:closed_case_pdf", args=[case.case_id])
        assert f'<embed src="{closed_pdf_url}"' in content or (
            '<embed src="' in content and closed_pdf_url in content
        ), "Desktop embed should use intake:closed_case_pdf"


@pytest.mark.django_db
class TestIntakeServePdfCacheControl:
    """Tests Cache-Control on intake:serve_pdf and intake:closed_case_pdf."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@cache-intake.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_operational_case_with_real_pdf(self) -> Case:
        nir_user = User.objects.create_user(username="nir-op-cache@test.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.WAIT_DOCTOR,
        )
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake pdf for cache test"),
            save=True,
        )
        return case

    def _create_cleaned_case_with_real_pdf(self) -> Case:
        nir_user = User.objects.create_user(username="nir-cl-cache@test.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
        )
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake pdf for closed cache test"),
            save=True,
        )
        return case

    def test_intake_serve_pdf_has_no_store_cache_control(self, client) -> None:
        """intake:serve_pdf response includes Cache-Control: no-store."""
        case = self._create_operational_case_with_real_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:serve_pdf", args=[case.case_id]))
        assert response.status_code == 200
        cache_control = response.get("Cache-Control", "")
        assert "no-store" in cache_control

    def test_intake_serve_pdf_content_type_is_pdf(self, client) -> None:
        """intake:serve_pdf returns Content-Type: application/pdf."""
        case = self._create_operational_case_with_real_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:serve_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_intake_closed_case_pdf_has_no_store_cache_control(self, client) -> None:
        """intake:closed_case_pdf response includes Cache-Control: no-store."""
        case = self._create_cleaned_case_with_real_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf", args=[case.case_id]))
        assert response.status_code == 200
        cache_control = response.get("Cache-Control", "")
        assert "no-store" in cache_control

    def test_intake_closed_case_pdf_content_type_is_pdf(self, client) -> None:
        """intake:closed_case_pdf returns Content-Type: application/pdf."""
        case = self._create_cleaned_case_with_real_pdf()
        self._login_as(client, "nir")
        response = client.get(reverse("intake:closed_case_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
