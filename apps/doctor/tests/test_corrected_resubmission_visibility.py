"""Testes de visibilidade de reenvio corrigido na tela médica — Slice 002.

RED: testes falham pois contexto/template não implementaram cards ainda.
GREEN: implementação mínima faz todos passarem.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import Case, CaseEvent, CaseStatus

User = get_user_model()


def _create_role(name: str):
    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name=name)
    return role


def _nir_user():
    user = User.objects.create_user(username="nir_doc_vis@test.com", password="testpass123")
    user.roles.add(_create_role("nir"))
    return user


def _doctor_user():
    user = User.objects.create_user(username="doc_vis@test.com", password="testpass123")
    user.roles.add(_create_role("doctor"))
    return user


def _advance_case_to(case: Case, target_status: str) -> Case:
    """Avança um caso através da FSM até o status desejado."""

    transitions = {
        CaseStatus.R1_ACK_PROCESSING: lambda c: c.start_processing(user=None),
        CaseStatus.EXTRACTING: lambda c: c.start_extraction(user=None),
        CaseStatus.LLM_STRUCT: lambda c: (c.extraction_complete(success=True, user=None), c.save()),
        CaseStatus.LLM_SUGGEST: lambda c: (c.llm1_complete(success=True, user=None), c.save()),
        CaseStatus.R2_POST_WIDGET: lambda c: (c.llm2_complete(success=True, user=None), c.save()),
        CaseStatus.WAIT_DOCTOR: lambda c: (c.ready_for_doctor(user=None), c.save()),
    }

    for status, apply in transitions.items():
        if case.status == target_status:
            break
        apply(case)
        case.save()
    return case


def _doctor_login(client):
    """Cria usuário doctor, faz login e retorna (cliente, usuário)."""
    user = _doctor_user()
    client.force_login(user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client, user


@pytest.mark.django_db
class TestDoctorDecisionCorrectionVisibility:
    """Testes de visibilidade do card de reenvio corrigido na tela médica."""

    def _claim_lock(self, client, case_id, user):
        """Adquire lock e retorna o token."""
        from apps.cases.services import claim_case_lock

        result = claim_case_lock(
            case_id=case_id,
            user=user,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        return str(result.token)

    def test_doctor_decision_shows_corrected_resubmission_card(self, client) -> None:
        """Card \"Reenvio corrigido\" aparece na tela de decisão médica."""
        client, doctor = _doctor_login(client)
        nir = _nir_user()

        original = Case.objects.create(
            created_by=nir,
            agency_record_number="ORIG-DOC-001",
            status=CaseStatus.DOCTOR_DENIED,
            doctor=doctor,
            doctor_decision="deny",
            doctor_reason="Sem indicação cirúrgica",
            doctor_decided_at=timezone.now(),
        )

        new_case = Case.objects.create(
            created_by=nir,
            corrects_case=original,
            correction_reason="Novo laudo com exames complementares",
            correction_created_by=nir,
            correction_created_at=timezone.now(),
            agency_record_number="NEW-DOC-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        new_case.structured_data = {"patient": {"name": "Maria Paciente", "age": 45, "gender": "Feminino"}}
        new_case.summary_text = "Paciente com indicação de EDA"
        new_case.suggested_action = {"suggestion": "accept", "support_recommendation": "none"}
        new_case.save()

        self._claim_lock(client, new_case.case_id, doctor)
        response = client.get(reverse("doctor:decision", args=[new_case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reenvio corrigido" in content
        assert "Novo laudo com exames complementares" in content

    def test_doctor_decision_card_warns_previous_documents_not_inherited(self, client) -> None:
        """Card médico contém aviso explícito de não herança de documentos/anexos."""
        client, doctor = _doctor_login(client)
        nir = _nir_user()

        original = Case.objects.create(
            created_by=nir,
            agency_record_number="ORIG-NOINH-001",
            status=CaseStatus.DOCTOR_DENIED,
            doctor=doctor,
            doctor_decision="deny",
            doctor_reason="Fora do perfil",
            doctor_decided_at=timezone.now(),
        )

        new_case = Case.objects.create(
            created_by=nir,
            corrects_case=original,
            correction_reason="Laudo corrigido",
            correction_created_by=nir,
            correction_created_at=timezone.now(),
            agency_record_number="NEW-NOINH-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        new_case.structured_data = {"patient": {"name": "João", "age": 60, "gender": "Masculino"}}
        new_case.summary_text = "Indicação de EDA"
        new_case.suggested_action = {"suggestion": "accept", "support_recommendation": "none"}
        new_case.save()

        self._claim_lock(client, new_case.case_id, doctor)
        response = client.get(reverse("doctor:decision", args=[new_case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "não foram herdados" in content or "não foram copiados" in content or "herdados" in content

    def test_doctor_decision_does_not_embed_previous_case_documents(self, client) -> None:
        """Tela médica do novo caso não contém PDF/anexos do caso anterior."""
        from django.core.files.base import ContentFile

        from apps.cases.models import CaseAttachment

        client, doctor = _doctor_login(client)
        nir = _nir_user()

        original = Case.objects.create(
            created_by=nir,
            agency_record_number="ORIG-EMBED-001",
            status=CaseStatus.DOCTOR_DENIED,
            doctor=doctor,
            doctor_decision="deny",
            doctor_reason="Sem condições",
            doctor_decided_at=timezone.now(),
        )
        # Criar PDF e anexo no caso original
        original.pdf_file.save("original.pdf", ContentFile(b"%PDF-1.4 original"), save=True)
        CaseAttachment.objects.create(
            case=original,
            file=ContentFile(b"attachment", name="orig_att.pdf"),
            original_filename="orig_att.pdf",
            stored_filename="orig_att.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="e" * 64,
            uploaded_by=nir,
        )

        new_case = Case.objects.create(
            created_by=nir,
            corrects_case=original,
            correction_reason="Novo relatório",
            correction_created_by=nir,
            correction_created_at=timezone.now(),
            agency_record_number="NEW-EMBED-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        new_case.structured_data = {"patient": {"name": "Ana", "age": 35, "gender": "Feminino"}}
        new_case.summary_text = "Indicação cirúrgica"
        new_case.suggested_action = {"suggestion": "accept", "support_recommendation": "none"}
        new_case.save()

        self._claim_lock(client, new_case.case_id, doctor)
        response = client.get(reverse("doctor:decision", args=[new_case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Não deve conter referência ao PDF do caso anterior
        assert "original.pdf" not in content
        assert "orig_att.pdf" not in content
        assert "ORIG-EMBED" not in content or "original.pdf" not in content

    def test_doctor_decision_hides_duplicate_prior_case_card_when_same_original(self, client) -> None:
        """Quando corrects_case aponta para o mesmo caso do prior lookup,
        apenas o card de reenvio corrigido aparece — sem duplicação do genérico."""
        client, doctor = _doctor_login(client)
        nir = _nir_user()

        original = Case.objects.create(
            created_by=nir,
            agency_record_number="DUP-001",
            status=CaseStatus.DOCTOR_DENIED,
            doctor=doctor,
            doctor_decision="deny",
            doctor_reason="Sem critérios",
            doctor_decided_at=timezone.now(),
        )

        new_case = Case.objects.create(
            created_by=nir,
            corrects_case=original,
            correction_reason="Laudo corrigido",
            correction_created_by=nir,
            correction_created_at=timezone.now(),
            agency_record_number="NEW-DUP-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        new_case.structured_data = {"patient": {"name": "Dup Paciente", "age": 50, "gender": "Masculino"}}
        new_case.summary_text = "Indicação de EDA"
        new_case.suggested_action = {"suggestion": "accept", "support_recommendation": "none"}
        new_case.save()

        # Criar evento PRIOR_CASE_LOOKUP que referencia o mesmo original
        CaseEvent.objects.create(
            case=new_case,
            event_type="PRIOR_CASE_LOOKUP",
            actor=None,
            actor_type="system",
            payload={
                "prior_case_id": str(original.case_id),
                "decision": "doctor_denied",
                "reason": "Sem critérios",
                "decided_at": original.doctor_decided_at.isoformat() if original.doctor_decided_at else "",
                "decided_by": doctor.display_name,
                "decided_by_role": "doctor",
                "prior_denial_count_7d": 1,
            },
        )

        self._claim_lock(client, new_case.case_id, doctor)
        response = client.get(reverse("doctor:decision", args=[new_case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()

        # Card de reenvio corrigido deve aparecer
        assert "Reenvio corrigido" in content
        # Card genérico "Caso Anterior — Negação Recente" não deve aparecer
        assert "Caso Anterior" not in content

    def test_doctor_decision_without_correction_keeps_prior_case_card(self, client) -> None:
        """Upload normal sem corrects_case mantém card genérico de prior-case lookup."""
        client, doctor = _doctor_login(client)
        nir = _nir_user()

        # Criar caso anterior "negado" que será detectado pelo prior lookup
        Case.objects.create(
            created_by=nir,
            agency_record_number="PRIOR-KEEP-001",
            status=CaseStatus.DOCTOR_DENIED,
            doctor=doctor,
            doctor_decision="deny",
            doctor_reason="Sem indicação",
            doctor_decided_at=timezone.now(),
        )

        # Novo caso SEM corrects_case, mas com mesmo agency_record_number
        new_case = Case.objects.create(
            created_by=nir,
            agency_record_number="PRIOR-KEEP-001",  # Mesmo número, prior lookup detecta
            status=CaseStatus.WAIT_DOCTOR,
        )
        new_case.structured_data = {"patient": {"name": "Prior Keep", "age": 40, "gender": "Feminino"}}
        new_case.summary_text = "Indicação de EDA"
        new_case.suggested_action = {"suggestion": "accept", "support_recommendation": "none"}
        new_case.save()

        self._claim_lock(client, new_case.case_id, doctor)
        response = client.get(reverse("doctor:decision", args=[new_case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        # Card genérico "Caso Anterior — Negação Recente" deve aparecer
        assert "Caso Anterior" in content
        assert "Negação Recente" in content or "Negada" in content
