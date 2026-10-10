"""S2/R7 — Linha do Tempo da confirmacao no contexto CHD (leitor existente).

O ``scheduler_context_detail`` reutiliza o enriquecimento compartilhado
(``enrich_timeline_events``) e o partial ``cases/_event_detail.html``: quem
confirmou qual selecao aparece com manutencao/troca e justificativa escapada.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseCommunicationMessage, CaseEvent

User = get_user_model()

pytestmark = pytest.mark.django_db


def _role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _login_as(client, role_name: str, username: str):
    user = User.objects.create_user(username=username, password="testpass123")
    user.roles.add(_role(role_name))
    client.force_login(user)
    session = client.session
    session["active_role"] = role_name
    session.save()
    return user


def _create_notification(user, case):
    from apps.accounts.models import UserNotification

    msg = CaseCommunicationMessage.objects.create(
        case=case,
        author=user,
        author_role="nir",
        body="Teste de menção @scheduler",
    )
    return UserNotification.objects.create(
        recipient=user,
        case=case,
        communication_message=msg,
        triggered_by=user,
        notification_type="case_communication_mention",
        title="Você foi mencionado",
        body_preview="Teste de menção @scheduler",
    )


def _nir_user(username: str = "nir-chd@test.com"):
    user = User.objects.create_user(username=username, password="testpass123")
    user.roles.add(_role("nir"))
    user.first_name = "Ana"
    user.last_name = "Nir"
    user.save()
    return user


def _case_with_confirmation(nir) -> Case:
    case = Case.objects.create(
        created_by=nir,
        structured_data={"patient": {"name": "Paciente Teste", "age": 45, "gender": "M"}},
    )
    review = CaseEvent.objects.create(
        case=case,
        event_type="EDA_SCOPE_GATED_MANUAL_REVIEW",
        actor=None,
        actor_type="system",
        payload={"reason_code": "exam_type_mismatch", "reason_text": "Divergencia."},
    )
    CaseEvent.objects.create(
        case=case,
        event_type="CASE_PROCEDURE_REVIEW_CONFIRMED",
        actor=nir,
        actor_type="human",
        payload={
            "version": 1,
            "actor_role": "nir",
            "review_event_id": review.pk,
            "review_reason_code": "exam_type_mismatch",
            "previous_declared_procedures": ["eda"],
            "confirmed_procedures": ["rectosigmoidoscopy_argon"],
            "selection_changed": True,
            "justification": "Revisei <b>argonio</b> no relatorio.",
            "source_fingerprint": "v1:abc",
        },
    )
    return case


class TestSchedulerContextConfirmationTimeline:
    def test_context_shows_who_confirmed_which_selection(self, client) -> None:
        """CHD ve titulo dinamico, troca e justificativa escapada (R7)."""
        scheduler = _login_as(client, "scheduler", "sched_tl")
        nir = _nir_user()
        case = _case_with_confirmation(nir)
        _create_notification(scheduler, case)

        response = client.get(f"/scheduler/context/{case.case_id}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Procedimento confirmado pelo NIR: Retossigmoidoscopia + Argônio" in content
        assert "Ana Nir" in content
        assert "EDA" in content and "Retossigmoidoscopia + Argônio" in content
        assert "Revisei &lt;b&gt;argonio&lt;/b&gt; no relatorio." in content
        assert "<b>argonio</b>" not in content
