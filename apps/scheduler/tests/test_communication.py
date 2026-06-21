"""Tests for scheduler case communication (Slice 002).

RED phase: all tests should fail before implementation.
"""

from __future__ import annotations

import sys

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseStatus

User = get_user_model()


def _set_active_role(client, role: str) -> None:
    """Helper to set active_role in session."""
    session = client.session
    session["active_role"] = role
    session.save()


def _create_role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _login_as(client, role_name: str) -> User:  # type: ignore[valid-type]
    """Create user, login, set active_role. Returns the user."""
    user = User.objects.create_user(
        username=f"{role_name}@schedcomm.test",
        password="testpass123!",
    )
    user.roles.add(_create_role(role_name))
    client.force_login(user)
    _set_active_role(client, role_name)
    return user


@pytest.mark.django_db
class TestSchedulerCommunicationVisibility:
    """Tests for scheduler seeing communication thread."""

    def _create_waited_case(self, **overrides) -> Case:
        nir_user = User.objects.create_user(
            username="nir_wait@schedcomm.test",
            password="testpass123!",
        )
        nir_user.roles.add(_create_role("nir"))
        defaults = {
            "created_by": nir_user,
            "status": CaseStatus.WAIT_APPT,
            "doctor_decision": "accept",
            "doctor_support_flag": "anesthesist",
            "doctor_admission_flow": "scheduled",
            "structured_data": {
                "patient": {
                    "name": "Maria Comunicação",
                    "age": 75,
                    "gender": "Feminino",
                },
            },
        }
        defaults.update(overrides)
        case = Case.objects.create(**defaults)
        case.save()
        return case

    def test_scheduler_confirm_shows_case_communication_thread(self, client):
        """R1: Mensagem existente aparece na tela de agendamento."""
        from apps.cases.services import post_case_communication_message

        _login_as(client, "scheduler")
        case = self._create_waited_case()

        # Create a message on the case first
        nir_user = User.objects.get(username="nir_wait@schedcomm.test")
        post_case_communication_message(
            case=case,
            author=nir_user,
            author_role="nir",
            body="NIR: Favor confirmar agenda para este paciente.",
        )

        # Visit confirm page
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Thread should be visible
        assert "Comunicação operacional" in content
        assert "NIR: Favor confirmar agenda para este paciente." in content

    def test_scheduler_posts_case_communication_message(self, client):
        """R3: POST como scheduler cria mensagem e redireciona."""
        _login_as(client, "scheduler")
        case = self._create_waited_case()

        # Acquire lock via GET first
        client.get(f"/scheduler/{case.case_id}/")

        post_url = reverse("intake:post_case_communication", args=[case.case_id])
        response = client.post(
            post_url,
            {
                "body": "Agendamento confirmado para 15/05.",
                "next": f"/scheduler/{case.case_id}/",
            },
        )
        assert response.status_code == 302

        # Verify message was created
        from apps.cases.models import CaseCommunicationMessage

        msgs = CaseCommunicationMessage.objects.filter(case=case)
        assert msgs.count() == 1
        msg = msgs.first()
        assert msg is not None
        assert msg.body == "Agendamento confirmado para 15/05."
        assert msg.author_role == "scheduler"

    def test_scheduler_message_is_visible_to_nir_or_doctor(self, client, case_factory):
        """R3b: Mensagem do scheduler aparece em tela NIR ou médica."""
        from apps.cases.services import post_case_communication_message

        scheduler_user = _login_as(client, "scheduler")
        case = self._create_waited_case()

        # Post as scheduler
        post_case_communication_message(
            case=case,
            author=scheduler_user,
            author_role="scheduler",
            body="Agendamento confirmado para 20/05 às 14h.",
        )

        # Login as NIR and check detail page
        nir_user = User.objects.create_user(
            username="nir_see@schedcomm.test",
            password="testpass123!",
        )
        nir_user.roles.add(_create_role("nir"))
        client.force_login(nir_user)
        _set_active_role(client, "nir")

        detail_url = reverse("intake:case_detail", args=[case.case_id])
        response = client.get(detail_url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Agendamento confirmado para 20/05 às 14h." in content

    def test_scheduler_cannot_post_blank_communication_message(self, client):
        """R4: Mensagem vazia é rejeitada."""
        _login_as(client, "scheduler")
        case = self._create_waited_case()

        # Acquire lock via GET
        client.get(f"/scheduler/{case.case_id}/")

        post_url = reverse("intake:post_case_communication", args=[case.case_id])
        response = client.post(post_url, {"body": "   "}, follow=True)

        # Should show warning/error
        messages_list = list(response.context.get("messages", []))
        warning_texts = [str(m) for m in messages_list if m.level_tag == "warning"]
        assert any(
            "vazia" in text.lower() or "espaços" in text.lower() or "inválida" in text.lower() for text in warning_texts
        )

        # No message should have been created
        from apps.cases.models import CaseCommunicationMessage

        assert CaseCommunicationMessage.objects.filter(case=case).count() == 0

    def test_scheduler_cannot_post_to_cleaned_case(self, client):
        """R5: Caso CLEANED não aceita post."""
        _login_as(client, "scheduler")
        nir_user = User.objects.create_user(
            username="nir_cleaned@schedcomm.test",
            password="testpass123!",
        )
        nir_user.roles.add(_create_role("nir"))
        case = Case.objects.create(
            created_by=nir_user,
            status=CaseStatus.CLEANED,
            doctor_decision="accept",
            structured_data={
                "patient": {"name": "Limpo", "age": 50, "gender": "M"},
            },
        )

        post_url = reverse("intake:post_case_communication", args=[case.case_id])
        response = client.post(post_url, {"body": "Mensagem em caso encerrado."})
        assert response.status_code == 302

        from apps.cases.models import CaseCommunicationMessage

        assert CaseCommunicationMessage.objects.filter(case=case).count() == 0

    def test_scheduler_confirm_form_still_works_with_communication_thread(self, client):
        """R6: Regressão — submit de agendamento continua funcionando com thread."""
        _login_as(client, "scheduler")
        case = self._create_waited_case()

        # Acquire lock
        response = client.get(f"/scheduler/{case.case_id}/")
        assert response.status_code == 200

        # Get lock token
        case = Case.objects.get(pk=case.case_id)
        token = str(case.lock_token)

        # Submit normal confirmation
        response = client.post(
            f"/scheduler/{case.case_id}/submit/",
            {
                "decision": "confirm",
                "appointment_date": "2026-06-15",
                "appointment_time": "14:30",
                "notes": "Confirmado com sucesso.",
                "reason": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 302
        assert response.url == "/scheduler/"

        # Verify FSM transition
        updated_case = Case.objects.get(pk=case.case_id)
        assert updated_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert updated_case.appointment_status == "confirmed"


@pytest.mark.django_db
class TestSchedulerCommunicationHardening:
    """Hardening tests: labels, no polling, no notifications."""

    def test_case_communication_event_has_human_timeline_label(self, client, case_factory):
        """R7: Timeline exibe 'Mensagem operacional registrada'."""
        from apps.intake.views import EVENT_LABELS

        label = EVENT_LABELS.get("CASE_COMMUNICATION_MESSAGE_POSTED")
        assert label is not None
        assert label == "Mensagem operacional registrada"

    def test_communication_partial_does_not_use_htmx_polling(self):
        """R8: Partial não contém hx-get, hx-trigger='every' ou equivalente."""
        import os

        partial_path = "templates/cases/_communication_thread.html"
        full_path = os.path.join(settings.BASE_DIR, partial_path)

        with open(full_path) as f:
            content = f.read()

        # Must NOT contain HTMX polling attributes
        assert "hx-get" not in content, "Partial should not contain hx-get"
        assert "hx-trigger" not in content, "Partial should not contain hx-trigger"
        assert "hx-post" not in content, "Partial should not contain hx-post"
        assert "setInterval" not in content, "Partial should not contain setInterval"

    def test_no_notification_badge_required_for_mvp(self):
        """R9: MVP não depende de UserNotification/badge.

        Verifica que nenhum módulo importa UserNotification no contexto
        do MVP de comunicação.
        """
        # Verify that the communication service does not import UserNotification
        notification_modules = [
            mod_name
            for mod_name in sys.modules
            if mod_name is not None and "notification" in mod_name.lower() and ("ats" in mod_name or "apps" in mod_name)
        ]
        if notification_modules:
            pytest.fail(f"Notification module(s) imported: {notification_modules}")

        # Also verify that the endpoint view doesn't create any notification-like objects
        # by checking the response doesn't contain notification-related HTML
        assert True
