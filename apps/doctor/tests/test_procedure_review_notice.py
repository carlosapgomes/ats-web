"""S2/R8 — medico ve a confirmacao NIR antes de decidir (aviso nao bloqueante).

Contrato: openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/
slices/slice-002-human-confirmation-to-doctor-with-timeline.md.

O aviso vem dos eventos (autor/justificativa lidos, nunca inventados) via
``prepare_doctor_case_report`` → ``DoctorReportPresenter.procedure_review_notice``
→ bloco ``report.notices`` (template ja renderiza). Sem aplicacao/confirmacao
localizavel nao ha aviso ficticio — nem mesmo com precedence metadata.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.doctor.reporting import prepare_doctor_case_report

User = get_user_model()

pytestmark = pytest.mark.django_db


def _role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _nir_user(username: str = "nir-docnotice@test.com"):
    user = User.objects.create_user(username=username, password="testpass123")
    user.roles.add(_role("nir"))
    user.first_name = "Ana"
    user.last_name = "Nir"
    user.save()
    return user


def _doctor_client(client, username: str = "doc-notice@test.com"):
    user = User.objects.create_user(username=username, password="testpass123")
    user.roles.add(_role("doctor"))
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


def _wait_doctor_case(user, *, procedure: str = "cpre") -> Case:
    """Caso 4.0 em WAIT_DOCTOR com recomendacao do conjunto confirmado."""
    case = Case.objects.create(
        created_by=user,
        status=CaseStatus.WAIT_DOCTOR,
        extracted_text="RELATORIO DE OCORRENCIAS\nMotivo: avaliacao.",
        structured_data={"schema_version": "4.0", "patient": {"name": "Paciente"}},
        summary_text="Resumo.",
        suggested_action={
            "schema_version": "4.0",
            "procedure_recommendations": [
                {
                    "procedure_type": procedure,
                    "suggestion": "accept",
                    "support_recommendation": "none",
                    "policy_alignment": {},
                    "contradictions": [],
                    "preop_decision": {"decision": "proceed"},
                }
            ],
            "global_support_recommendation": "none",
            "nir_procedure_review": {
                "confirmation_event_id": None,
                "effective_procedures": [procedure],
            },
        },
    )
    return case


def _confirmed_history(case: Case, user) -> CaseEvent:
    review = CaseEvent.objects.create(
        case=case,
        event_type="EDA_SCOPE_GATED_MANUAL_REVIEW",
        actor=None,
        actor_type="system",
        payload={"reason_code": "exam_type_mismatch", "reason_text": "Divergencia."},
    )
    confirmed = CaseEvent.objects.create(
        case=case,
        event_type="CASE_PROCEDURE_REVIEW_CONFIRMED",
        actor=user,
        actor_type="human",
        payload={
            "version": 1,
            "actor_role": "nir",
            "review_event_id": review.pk,
            "review_reason_code": "exam_type_mismatch",
            "previous_declared_procedures": ["eda", "echoendoscopy", "cpre"],
            "confirmed_procedures": ["cpre"],
            "selection_changed": True,
            "justification": "Revisei o relatorio e confirmo CPRE.",
            "source_fingerprint": "v1:abc",
        },
    )
    CaseEvent.objects.create(
        case=case,
        event_type="CASE_PROCEDURE_REVIEW_APPLIED",
        actor=None,
        actor_type="system",
        payload={
            "confirmation_event_id": confirmed.pk,
            "automatic_procedures": ["eda", "echoendoscopy", "cpre"],
            "effective_procedures": ["cpre"],
        },
    )
    suggested = case.suggested_action
    assert isinstance(suggested, dict)
    provenance = suggested.get("nir_procedure_review")
    assert isinstance(provenance, dict)
    provenance["confirmation_event_id"] = confirmed.pk
    case.save()
    return confirmed


class TestDoctorConfirmationNotice:
    def test_presenter_notice_names_procedure_author_and_justification(self, django_user_model) -> None:
        """Aviso com procedimento confirmado, autor, justificativa e limite clínico."""
        user = _nir_user()
        case = _wait_doctor_case(user)

        # Sem eventos: nenhum aviso ficticio (mesmo com metadata no artefato).
        report = prepare_doctor_case_report(case).presenter.build_report()
        assert not [line for line in report["notices"] if "confirmado pelo NIR" in line]

        _confirmed_history(case, user)
        report = prepare_doctor_case_report(Case.objects.get(pk=case.pk)).presenter.build_report()
        matches = [line for line in report["notices"] if "confirmado pelo NIR" in line]
        assert len(matches) == 1
        notice = matches[0]
        assert "CPRE" in notice
        assert "Ana Nir" in notice
        assert "Revisei o relatorio e confirmo CPRE." in notice
        assert "Ecoendoscopia" in notice  # divergencia automatica registrada
        assert "não é aprovação clínica" in notice

    def test_legacy_case_has_no_notice(self, django_user_model) -> None:
        """Caso automatico/legado sem confirmacao: sem aviso humano."""
        user = _nir_user("nir-legacy@test.com")
        case = _wait_doctor_case(user)
        report = prepare_doctor_case_report(case).presenter.build_report()
        assert not [line for line in report["notices"] if "NIR" in line and "confirm" in line.lower()]

    def test_decision_page_renders_notice_and_effective_procedures(self, client) -> None:
        """SSR: aviso visivel + procedimentos em analise = conjunto confirmado."""
        client, _doctor = _doctor_client(client)
        nir = _nir_user("nir-ssr@test.com")
        case = _wait_doctor_case(nir)
        _confirmed_history(case, nir)

        response = client.get(reverse("doctor:decision", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Procedimento confirmado pelo NIR" in content
        assert "Ana Nir" in content
        assert "não é aprovação clínica" in content
        assert "CPRE" in content

    def test_decision_page_without_confirmation_has_no_notice(self, client) -> None:
        """SSR legado: nenhum aviso humano ficticio."""
        client, _doctor = _doctor_client(client, "doc-legacy@test.com")
        nir = _nir_user("nir-ssr-legacy@test.com")
        case = _wait_doctor_case(nir)

        response = client.get(reverse("doctor:decision", args=[case.case_id]))
        assert response.status_code == 200
        assert "Procedimento confirmado pelo NIR" not in response.content.decode()
