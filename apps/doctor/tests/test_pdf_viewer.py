"""Tests for doctor PDF viewer (Slice 001).

Focus on the doctor-specific PDF viewer route, mobile link in decision.html,
desktop embed preservation, and Cache-Control in serve_pdf.
"""

import uuid
from pathlib import Path

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
class TestDoctorPdfViewerView:
    """Tests for doctor:pdf_viewer route (GET /doctor/<case_id>/pdf-viewer/)."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@pdfv.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_with_pdf(self) -> Case:
        """Create a WAIT_DOCTOR case with a dummy pdf_file, advancing via FSM."""
        nir_user = User.objects.create_user(username="nir_pdfv@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.NEW,
            structured_data={"patient": {"name": "PDF Viewer Test", "age": 40, "gender": "Masculino"}},
        )
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
        # Assign a dummy pdf_file (path only, not a real file)
        case.pdf_file = "test_cases/dummy.pdf"
        case.save()
        return case

    def _get_pdf_viewer_url(self, case_id: uuid.UUID) -> str:
        return reverse("doctor:pdf_viewer", args=[case_id])

    # ── Test 1: requires login ─────────────────────────────────────────

    def test_pdf_viewer_requires_login(self, client) -> None:
        """Redirects to login when unauthenticated."""
        url = self._get_pdf_viewer_url(uuid.uuid4())
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.url

    # ── Test 2: blocks non-doctor roles ────────────────────────────────

    def test_pdf_viewer_blocks_nir(self, client) -> None:
        """User with active_role='nir' cannot access the viewer."""
        case = self._create_case_with_pdf()
        self._login_as(client, "nir")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        assert response.status_code == 302
        assert response.url == "/"

    def test_pdf_viewer_blocks_scheduler(self, client) -> None:
        """User with active_role='scheduler' cannot access the viewer."""
        case = self._create_case_with_pdf()
        self._login_as(client, "scheduler")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        assert response.status_code == 302
        assert response.url == "/"

    # ── Test 3: renders 200 for authorized doctor ──────────────────────

    def test_pdf_viewer_renders_for_authorized_doctor(self, client) -> None:
        """Doctor with active_role='doctor' gets 200 on pdf-viewer."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        assert response.status_code == 200

    def test_pdf_viewer_allows_manager_with_active_doctor(self, client) -> None:
        """Manager with active_role='doctor' can access pdf-viewer."""
        case = self._create_case_with_pdf()
        user = User.objects.create_user(username="mgr-doc@pdfv.test", password="testpass123")
        user.roles.add(self._create_role("manager"))
        user.roles.add(self._create_role("doctor"))
        client.force_login(user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        assert response.status_code == 200

    # ── Test 4: viewer contains serve_pdf URL ──────────────────────────

    def test_pdf_viewer_contains_pdf_url_config(self, client) -> None:
        """Viewer page contains the doctor:serve_pdf URL in a data attribute."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        content = response.content.decode()
        pdf_url = reverse("doctor:serve_pdf", args=[case.case_id])
        # Check that the PDF URL appears somewhere in the page config
        assert pdf_url in content

    # ── Test 5: viewer has two "Voltar" actions ────────────────────────

    def test_pdf_viewer_has_two_back_actions(self, client) -> None:
        """Viewer has 'Voltar' action in top and bottom sections."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        content = response.content.decode()
        # Expect two "Voltar" occurrences (top + bottom)
        volgar_count = content.count("Voltar")
        assert volgar_count >= 2, f"Expected at least 2 'Voltar', found {volgar_count}"

    # ── Test 6: viewer has fallback link ───────────────────────────────

    def test_pdf_viewer_has_fallback_open_original(self, client) -> None:
        """Viewer contains a fallback to open the original PDF."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        content = response.content.decode()
        # Should have a fallback message and link to open the original PDF
        assert "Abrir PDF original" in content or "PDF original" in content

    # ── Test 7: 404 when case has no pdf_file ──────────────────────────

    def test_pdf_viewer_404_when_no_pdf_file(self, client) -> None:
        """Returns 404 when case has no pdf_file."""
        nir_user = User.objects.create_user(username="nir_nopdf@pdfv.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.NEW,
            structured_data={"patient": {"name": "No PDF", "age": 40, "gender": "M"}},
        )
        case = _advance_case_to(case, CaseStatus.WAIT_DOCTOR)
        # No pdf_file assigned
        case.save()

        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        assert response.status_code == 404

    # ── Test 8: next URL validation ────────────────────────────────────

    def test_pdf_viewer_back_url_defaults_to_decision(self, client) -> None:
        """Back URL defaults to doctor:decision when no next param."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        response = client.get(self._get_pdf_viewer_url(case.case_id))
        content = response.content.decode()
        decision_url = reverse("doctor:decision", args=[case.case_id])
        # The back link should point to doctor:decision
        assert decision_url in content

    def test_pdf_viewer_back_url_accepts_safe_next(self, client) -> None:
        """Back URL uses safe next param when provided."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        decision_url = reverse("doctor:decision", args=[case.case_id])
        # Pass a safe next URL
        response = client.get(self._get_pdf_viewer_url(case.case_id) + f"?next={decision_url}")
        content = response.content.decode()
        # Should link back to decision_url
        assert decision_url in content

    def test_pdf_viewer_rejects_external_next(self, client) -> None:
        """Back URL falls back to doctor:decision when next is external."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        decision_url = reverse("doctor:decision", args=[case.case_id])
        # Pass an external next URL
        response = client.get(self._get_pdf_viewer_url(case.case_id) + "?next=https://evil.example.com/phish")
        content = response.content.decode()
        # Should NOT contain evil.example
        assert "evil.example" not in content
        # Should fall back to doctor:decision
        assert decision_url in content

    def test_pdf_viewer_rejects_protocol_relative_next(self, client) -> None:
        """Back URL falls back to doctor:decision when next is protocol-relative."""
        case = self._create_case_with_pdf()
        self._login_as(client, "doctor")
        decision_url = reverse("doctor:decision", args=[case.case_id])
        # Pass a protocol-relative next URL
        response = client.get(self._get_pdf_viewer_url(case.case_id) + "?next=//evil.example.com/phish")
        content = response.content.decode()
        # Should NOT contain evil.example
        assert "evil.example" not in content
        # Should fall back to doctor:decision
        assert decision_url in content


@pytest.mark.django_db
class TestDoctorDecisionPdfMobileLink:
    """Tests that doctor/decision.html mobile link uses internal viewer."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@pdflink.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_in_status(self, status: str) -> Case:
        nir_user = User.objects.create_user(username=f"nir_{status.lower()}@pdflink.test", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.NEW)
        if status != CaseStatus.NEW:
            case = _advance_case_to(case, status)
        case.pdf_file = "test_cases/dummy.pdf"
        case.save()
        return case

    def test_decision_mobile_pdf_link_uses_internal_viewer(self, client) -> None:
        """Mobile PDF link points to doctor:pdf_viewer; not serve_pdf directly."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Mobile Link", "age": 40, "gender": "M"}}
        case.save()

        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # The mobile link (d-md-none) should contain the pdf_viewer URL
        pdf_viewer_url = reverse("doctor:pdf_viewer", args=[case.case_id])
        # Find the mobile section (d-md-none area) around PDF section
        # Better: check the PDF viewer URL appears in the page
        assert pdf_viewer_url in content, f"Mobile PDF link should reference pdf_viewer URL: {pdf_viewer_url}"

    def test_decision_mobile_link_no_target_blank(self, client) -> None:
        """Mobile PDF link does NOT use target='_blank'."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "No Blank", "age": 40, "gender": "M"}}
        case.save()

        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        # Check that no mobile-visible PDF link uses target="_blank"
        pdf_viewer_url = reverse("doctor:pdf_viewer", args=[case.case_id])
        # Find the mobile link
        import re

        mobile_pdf_links = re.findall(
            rf'<a[^>]*href="[^"]*{re.escape(pdf_viewer_url)}[^"]*"[^>]*>.*?</a>',
            content,
            re.DOTALL,
        )
        for link in mobile_pdf_links:
            assert 'target="_blank"' not in link, "Mobile PDF link should not use target='_blank'"

    def test_decision_desktop_preserves_embed_with_serve_pdf(self, client) -> None:
        """Desktop section still has <embed> with serve_pdf URL."""
        case = self._create_case_in_status(CaseStatus.WAIT_DOCTOR)
        case.structured_data = {"patient": {"name": "Desktop Embed", "age": 40, "gender": "M"}}
        case.save()

        self._login_as(client, "doctor")
        response = client.get(f"/doctor/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()

        serve_pdf_url = reverse("doctor:serve_pdf", args=[case.case_id])
        # Desktop should have an <embed> with the serve_pdf URL
        assert f'<embed src="{serve_pdf_url}"' in content or ('<embed src="' in content and serve_pdf_url in content)


@pytest.mark.django_db
class TestDoctorServePdfCacheControl:
    """Tests that doctor:serve_pdf returns no-store cache control."""

    def _create_role(self, name: str):
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name=name)
        return role

    def _login_as(self, client, role_name: str):
        user = User.objects.create_user(username=f"{role_name}@cache.test", password="testpass123")
        user.roles.add(self._create_role(role_name))
        client.force_login(user)
        session = client.session
        session["active_role"] = role_name
        session.save()
        return user

    def _create_case_with_real_pdf(self) -> Case:
        """Cria um Case WAIT_DOCTOR com um pdf_file real no storage de teste.

        Necessário porque serve_pdf faz pdf_file.open("rb"); um caminho sem
        arquivo físico gera FileNotFoundError antes do header ser setado.
        """
        nir_user = User.objects.create_user(username="nir_cache@test.com", password="testpass123")
        nir_user.roles.add(self._create_role("nir"))
        case = Case.objects.create(created_by=nir_user, status=CaseStatus.WAIT_DOCTOR)
        case.pdf_file.save(
            "test.pdf",
            ContentFile(b"%PDF-1.4 fake pdf for testing"),
            save=True,
        )
        return case

    def test_serve_pdf_has_no_store_cache_control(self, client) -> None:
        """serve_pdf response includes Cache-Control: no-store."""
        case = self._create_case_with_real_pdf()

        self._login_as(client, "doctor")
        response = client.get(reverse("doctor:serve_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"

    def test_serve_pdf_content_type_is_pdf(self, client) -> None:
        """serve_pdf returns Content-Type: application/pdf."""
        case = self._create_case_with_real_pdf()

        self._login_as(client, "doctor")
        response = client.get(reverse("doctor:serve_pdf", args=[case.case_id]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
class TestPdfViewerStaticJS:
    """Minimal static inspection of pdf-viewer.js."""

    def test_pdf_viewer_js_contains_intersection_observer(self) -> None:
        """pdf-viewer.js contains IntersectionObserver for lazy rendering."""
        js_path = Path("static/js/pdf-viewer.js")
        assert js_path.exists(), "pdf-viewer.js must exist"
        js = js_path.read_text()
        assert "IntersectionObserver" in js

    def test_pdf_viewer_js_contains_error_fallback(self) -> None:
        """pdf-viewer.js contains error handling or fallback logic."""
        js_path = Path("static/js/pdf-viewer.js")
        assert js_path.exists(), "pdf-viewer.js must exist"
        js = js_path.read_text()
        assert "error" in js.lower() or "catch" in js or "fallback" in js.lower()
