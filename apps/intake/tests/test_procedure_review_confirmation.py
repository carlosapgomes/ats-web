"""S2 RED — confirmacao NIR da revisao de procedimento (servico + POST + HTML).

Contrato: openspec/changes/confirm-nir-procedure-review-and-harden-pipeline/
slices/slice-002-human-confirmation-to-doctor-with-timeline.md (R1–R3, R7).

Estado RED (baseline S1): o CTA de correcao proibe manter a selecao
(option `disabled` + servico exige conjunto diferente) e o POST antigo
(exam_type + reason_code, sem consentimento) adquire mutacao sem leitura
explicita nem justificativa. Estes testes provam o gap comportamental com
APENAS imports pre-existentes; os testes do novo servico/helper (que exigem
`apps.cases.procedure_review`) vivem em `test_procedure_review.py` e nos
blocos marcados abaixo.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ProcedureType
from apps.cases.procedures import get_declared_procedure_types
from apps.cases.services import claim_case_lock
from apps.intake.services import is_exam_type_correction_eligible

pytestmark = pytest.mark.django_db

User = get_user_model()


# ── Helpers (so imports pre-existentes) ───────────────────────────────────


def _nir_client(client, username: str = "nir-confirm@test.com"):
    from apps.accounts.models import Role

    user = User.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _eligible_case(*, user, exam_type: str = ProcedureType.EDA) -> tuple[Case, CaseEvent]:
    case = Case.objects.create(
        created_by=user,
        status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        extracted_text="RELATORIO DE OCORRENCIAS\nMotivo da Solicitacao: EDA",
        agency_record_number="REC-CONF-001",
        structured_data={"patient": {"name": "Paciente de Teste"}},
        summary_text="Resumo antigo.",
        suggested_action={
            "decision": "manual_review_required",
            "suggestion": "manual_review_required",
            "reason_code": "exam_type_mismatch",
            "reason_text": "Tipo declarado difere do detectado.",
            "exam_type": "colonoscopy",
            "declared_exam_type": exam_type,
            "detected_exam_type": "colonoscopy",
            "declared_procedures": [exam_type],
            "detected_procedures": ["colonoscopy"],
        },
    )
    CaseProcedure.objects.create(case=case, procedure_type=exam_type, declared_by_nir=True)
    review = CaseEvent.objects.create(
        case=case,
        event_type="EDA_SCOPE_GATED_MANUAL_REVIEW",
        actor=None,
        actor_type="system",
        payload={"reason_code": "exam_type_mismatch", "reason_text": "Tipo declarado difere do detectado."},
    )
    case.save()
    return case, review


def _claim(case: Case, user) -> uuid.UUID:
    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        context="nir_receipt",
        role="nir",
    )
    assert result.acquired
    assert result.token is not None
    return result.token


def _post_confirmation(client, case: Case, token: object, **overrides: object) -> object:
    data: dict[str, object] = {
        "exam_type": ProcedureType.EDA,
        "review_acknowledged": "on",
        "review_justification": "Revisei o relatorio principal e confirmo EDA.",
        "lock_token": str(token),
    }
    data.update(overrides)
    return client.post(reverse("intake:exam_type_correction", args=[case.case_id]), data)


# ═══════════════════════════════════════════════════════════════════════════
# R1 — mesma selecao com consentimento e resolvida (RED comportamental)
# ═══════════════════════════════════════════════════════════════════════════


class TestSameSelectionConfirmationRed:
    def test_card_enables_current_selection(self, client) -> None:
        """A selecao vigente deve ser CONFIRMAVEL: option atual sem `disabled`.

        RED: o template atual marca a option vigente como `disabled`.
        """
        client, user = _nir_client(client, "nir-card@test.com")
        case, _review = _eligible_case(user=user)
        _claim(case, user)
        response = client.get(reverse("intake:case_detail", args=[case.case_id]))
        assert response.status_code == 200
        html = response.content.decode()
        current_line = next(line for line in html.splitlines() if 'value="eda"' in line and "(atual)" in line)
        assert "disabled" not in current_line

    def test_post_same_selection_with_consent_is_accepted(self, client) -> None:
        """POST com mesma selecao + leitura + justificativa resolve a revisao.

        RED: o backend atual rejeita igualdade ("deve ser diferente") e o caso
        permanece em revisao sem evento humano.
        """
        from apps.cases.procedure_review import source_fingerprint_for_case

        client, user = _nir_client(client, "nir-same@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        _post_confirmation(
            client,
            case,
            token,
            review_event_id=str(review.pk),
            source_fingerprint=fingerprint,
        )
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()

    def test_post_switch_selection_with_consent_is_accepted(self, client) -> None:
        """POST com troca + leitura + justificativa tambem resolve (R1).

        RED: exige o novo servico de confirmacao (import falha no baseline).
        """
        from apps.cases.procedure_review import source_fingerprint_for_case

        client, user = _nir_client(client, "nir-switch@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            _post_confirmation(
                client,
                case,
                token,
                exam_type=ProcedureType.COLONOSCOPY,
                review_event_id=str(review.pk),
                source_fingerprint=fingerprint,
            )
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert get_declared_procedure_types(reloaded) == (ProcedureType.COLONOSCOPY,)


# ═══════════════════════════════════════════════════════════════════════════
# R1/R2 — sem consentimento nao ha autoridade (caracterizacao + RED antigo)
# ═══════════════════════════════════════════════════════════════════════════


class TestNoImplicitConsent:
    def test_old_post_without_consent_acquires_no_authority(self, client) -> None:
        """POST antigo (exam_type + reason_code, sem leitura/justificativa).

        RED: no baseline ele SOFRE mutacao (corrige e reprocessa) sem nenhum
        consentimento explicito. Contrato S2: recusado sem mutacao/enqueue.
        """
        client, user = _nir_client(client, "nir-oldpost@test.com")
        case, _review = _eligible_case(user=user)
        token = _claim(case, user)
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "reason_code": "nir_identified_exam",
                    "lock_token": str(token),
                },
            )
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()

    def test_same_selection_without_consent_stays_in_review(self, client) -> None:
        """Mesma selecao SEM leitura continua recusada (caracterizacao)."""
        client, user = _nir_client(client, "nir-noconsent@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        _post_confirmation(
            client,
            case,
            token,
            review_acknowledged="",
            review_event_id=str(review.pk),
            source_fingerprint="v1:stale",
        )
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()

    def test_nul_justification_never_confirms(self, client) -> None:
        """Justificativa com U+0000 nao confirma e nao produz mutacao.

        RED: o campo e ignorado no baseline e a troca e aplicada.
        """
        client, user = _nir_client(client, "nir-nul@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            _post_confirmation(
                client,
                case,
                token,
                exam_type=ProcedureType.COLONOSCOPY,
                reason_code="nir_identified_exam",
                review_justification="texto com nul \x00 embutido",
                review_event_id=str(review.pk),
                source_fingerprint="v1:stale",
            )
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)

    def test_eligibility_unchanged_without_consent(self, django_user_model) -> None:
        """Elegibilidade/ator/reserva continuam exigidos (caracterizacao)."""
        from apps.accounts.models import Role

        user = django_user_model.objects.create_user(username="nir-elig@test.com", password="x")
        user.roles.add(Role.objects.get_or_create(name="nir")[0])
        case, _review = _eligible_case(user=user)
        assert is_exam_type_correction_eligible(case) is True


# ═══════════════════════════════════════════════════════════════════════════
# R7 — Linha do Tempo pós-encerramento (NIR encerrados conservam histórico)
# ═══════════════════════════════════════════════════════════════════════════


class TestClosedCaseConfirmationTimeline:
    def test_closed_detail_keeps_who_confirmed_which_selection(self, client) -> None:
        """Encerrado conserva autor, seleção, troca e justificativa (R7)."""
        from apps.cases.procedure_review import source_fingerprint_for_case

        client, user = _nir_client(client, "nir-closed@test.com")
        user.first_name = "Ana"
        user.save()
        case, review = _eligible_case(user=user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        CaseEvent.objects.create(
            case=case,
            event_type="CASE_PROCEDURE_REVIEW_CONFIRMED",
            actor=user,
            actor_type="human",
            payload={
                "version": 1,
                "actor_role": "nir",
                "review_event_id": review.pk,
                "review_reason_code": "exam_type_mismatch",
                "previous_declared_procedures": ["eda"],
                "confirmed_procedures": ["colonoscopy"],
                "selection_changed": True,
                "justification": "Revisei e troquei.",
                "source_fingerprint": fingerprint,
            },
        )
        # Atalho de fixture: CLEANED direto via update (FSM protegido no ORM).
        Case.objects.filter(pk=case.pk).update(status=CaseStatus.CLEANED)

        response = client.get(reverse("intake:closed_case_detail", args=[case.case_id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Procedimento confirmado pelo NIR: Colonoscopia" in content
        assert "Ana" in content
        assert "Revisei e troquei." in content


class TestConfirmationErrorRerender:
    def test_error_preserves_selection_and_justification_without_consent(self, client) -> None:
        """R1: erro preserva tentativa (seleção + justificativa), sem marcar leitura."""
        from apps.cases.procedure_review import source_fingerprint_for_case

        client, user = _nir_client(client, "nir-rerender@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_justification": "Minha justificativa parcial.",
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    "lock_token": str(token),
                    # sem review_acknowledged: recusado, sem consentimento implícito
                },
                follow=True,
            )

        assert response.status_code == 200
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        content = response.content.decode()
        assert "Minha justificativa parcial." in content
        # Seleção tentada preservada; checkbox nunca vem marcada.
        assert 'value="colonoscopy" selected' in content
        ack_tag = content.split('name="review_acknowledged"')[1].split(">")[0]
        assert "checked" not in ack_tag


# ═══════════════════════════════════════════════════════════════════════════
# P1-A — consentimento exige exatamente "on" ou True (sem truthiness)
# ═══════════════════════════════════════════════════════════════════════════


def _nir_service_user(django_user_model, username: str):
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    user.roles.add(Role.objects.get_or_create(name="nir")[0])
    return user


def _valid_confirm_kwargs(case: Case, review: CaseEvent, user, token):
    from apps.cases.procedure_review import source_fingerprint_for_case

    return {
        "case_id": case.case_id,
        "exam_type": ProcedureType.EDA,
        "user": user,
        "active_role": "nir",
        "lock_token": token,
        "review_justification": "Revisei o relatorio principal e confirmo EDA.",
        "review_event_id": review.pk,
        "source_fingerprint": source_fingerprint_for_case(Case.objects.get(pk=case.pk)),
    }


class TestNonCanonicalConsentRejected:
    """P1-A: valores truthy não-canônicos NÃO conferem autoridade humana.

    O checkbox envia exatamente ``"on"``; chamadas diretas de serviço usam o
    booleano ``True``. Qualquer outro valor não-vazio (``"false"``, ``"0"``,
    ``"off"``, ``1`` etc.) deve ser recusado sem nenhum efeito.
    """

    @pytest.mark.parametrize(
        "false_like",
        [
            "false",
            "False",
            "FALSE",
            "0",
            "off",
            "no",
            "n",
            "yes",
            "true",
            "True",
            "ON",
            " on",
            "on ",
            "checked",
            "1",
            1,
            0,
        ],
    )
    def test_false_like_consent_has_no_effects(self, django_user_model, monkeypatch, false_like) -> None:
        from apps.intake.services import confirm_case_procedure_review

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        user = _nir_service_user(django_user_model, f"nir-consent-{uuid.uuid4().hex[:8]}@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        before = Case.objects.get(pk=case.pk)
        before_events = CaseEvent.objects.filter(case=case).count()
        kwargs = _valid_confirm_kwargs(case, review, user, token)
        kwargs["review_acknowledged"] = false_like

        with pytest.raises(ValueError):
            confirm_case_procedure_review(**kwargs)

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data == before.structured_data
        assert reloaded.suggested_action == before.suggested_action
        assert reloaded.summary_text == before.summary_text
        # A recusa nao consome a reserva (o GET de re-render pode rotacionar
        # o token via heartbeat, sem transferir a titularidade).
        assert reloaded.lock_token is not None
        assert reloaded.lock_role == "nir"
        assert reloaded.lock_context == "nir_receipt"
        assert CaseEvent.objects.filter(case=case).count() == before_events
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert enqueue_calls == []

    @pytest.mark.parametrize("canonical", ["on", True])
    def test_canonical_consent_is_accepted(self, django_user_model, monkeypatch, canonical) -> None:
        from apps.intake.services import confirm_case_procedure_review

        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: None)
        user = _nir_service_user(django_user_model, f"nir-consent-ok-{uuid.uuid4().hex[:8]}@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        kwargs = _valid_confirm_kwargs(case, review, user, token)
        kwargs["review_acknowledged"] = canonical

        confirm_case_procedure_review(**kwargs)

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()

    def test_post_with_false_like_consent_is_refused(self, client, monkeypatch) -> None:
        """POST real com ``"false"`` é recusado sem mutação/enqueue."""
        from apps.cases.procedure_review import source_fingerprint_for_case

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        client, user = _nir_client(client, "nir-post-false@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        before_events = CaseEvent.objects.filter(case=case).count()

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_acknowledged": "false",
                    "review_justification": "Revisei o relatorio principal e confirmo.",
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    "lock_token": str(token),
                },
            )

        assert response.status_code == 302
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.lock_token == token
        assert CaseEvent.objects.filter(case=case).count() == before_events
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert enqueue_calls == []


# ═══════════════════════════════════════════════════════════════════════════
# P1-B — justificativa livre nunca viaja na URL
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionErrorRerenderPrivacy:
    def test_error_rerender_never_places_free_justification_in_url(self, client, monkeypatch) -> None:
        """P1-B: erro preserva a tentativa sem expor texto livre na URL.

        A justificativa com marcador sensível sintético deve reaparecer
        escapada no HTML (estado transitório server-side), com consentimento
        desmarcado, sem nenhum parâmetro de justificativa/marcador no
        redirect Location nem na URL final — sem mutação/enqueue.
        """
        from apps.cases.procedure_review import source_fingerprint_for_case

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        marker = "SENSIVEL-7f3a9c-justificativa"
        justification = f"{marker} revisei <b>negrito</b> & aspas"
        client, user = _nir_client(client, "nir-rerender-private@test.com")
        case, review = _eligible_case(user=user)
        token = _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        before = Case.objects.get(pk=case.pk)

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    "lock_token": str(token),
                    # sem review_acknowledged: recusado, sem consentimento implícito
                },
            )

        assert response.status_code == 302
        location = response["Location"]
        assert "correction_justification" not in location
        assert marker not in location

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            followed = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    "lock_token": str(token),
                },
                follow=True,
            )

        assert followed.status_code == 200
        final_url = followed.redirect_chain[-1][0]
        assert "correction_justification" not in final_url
        assert marker not in final_url
        content = followed.content.decode()
        assert marker in content
        assert "<b>negrito</b>" not in content
        assert "&lt;b&gt;negrito&lt;/b&gt;" in content
        assert 'value="colonoscopy" selected' in content
        ack_tag = content.split('name="review_acknowledged"')[1].split(">")[0]
        assert "checked" not in ack_tag
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data == before.structured_data
        assert reloaded.suggested_action == before.suggested_action
        assert reloaded.summary_text == before.summary_text
        # A recusa não consome a reserva (confirmação válida a limparia):
        # o lock segue retido (o GET de re-render pode rotacionar o token
        # via heartbeat, sem transferir a titularidade).
        assert reloaded.lock_token is not None
        assert reloaded.lock_role == "nir"
        assert reloaded.lock_context == "nir_receipt"
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []


# ═══════════════════════════════════════════════════════════════════════════
# P2 — lease/token: erro preserva a tentativa (mesmo contrato R1/P1-B)
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionLeaseTokenErrorRerender:
    """P2: falhas de lease/token preservam selecao+justificativa sem vazar na URL.

    Os ramos token-None (ausente/malformado) e PermissionError (reserva
    obsoleta/divergente) do POST de correcao devem seguir o mesmo contrato
    do ramo ValueError: selecao habilitada na query string limitada,
    justificativa limitada so na sessao server-side de uso unico, checkbox
    de consentimento nunca marcado — sem mutacao/enqueue.
    """

    def test_missing_lock_token_preserves_attempt(self, client, monkeypatch) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        marker = "P2-MISSING-TOKEN-4d2a1f"
        justification = f"{marker} revisei <b>negrito</b> & aspas"
        client, user = _nir_client(client, "nir-p2-missing@test.com")
        case, review = _eligible_case(user=user)
        _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        before = Case.objects.get(pk=case.pk)

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_acknowledged": "on",
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    # sem lock_token: reserva nao apresentada
                },
            )

        assert response.status_code == 302
        location = response["Location"]
        assert "correction_exam_type=colonoscopy" in location
        assert "correction_justification" not in location
        assert "review_acknowledged" not in location
        assert "consent" not in location
        assert marker not in location
        assert justification not in location

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            rerendered = client.get(location)
        assert rerendered.status_code == 200
        content = rerendered.content.decode()
        assert marker in content
        assert "<b>negrito</b>" not in content
        assert "&lt;b&gt;negrito&lt;/b&gt;" in content
        assert 'value="colonoscopy" selected' in content
        ack_tag = content.split('name="review_acknowledged"')[1].split(">")[0]
        assert "checked" not in ack_tag
        # Uso unico: segundo GET nao reexibe a justificativa.
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            reread = client.get(location)
        assert marker not in reread.content.decode()

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data == before.structured_data
        assert reloaded.suggested_action == before.suggested_action
        assert reloaded.summary_text == before.summary_text
        # A recusa nao consome a reserva (o GET de re-render pode rotacionar
        # o token via heartbeat, sem transferir a titularidade).
        assert reloaded.lock_token is not None
        assert reloaded.lock_role == "nir"
        assert reloaded.lock_context == "nir_receipt"
        # Sem evento de confirmacao/correcao: o POST recusado nao produz
        # auditoria de decisao (o GET de re-render pode emitir eventos de
        # reserva pre-existentes, fora do escopo desta correcao).
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []

    def test_malformed_lock_token_preserves_attempt(self, client, monkeypatch) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        marker = "P2-MALFORMED-TOKEN-9c7b3e"
        justification = f"{marker} revisei <i>italico</i> & aspas"
        client, user = _nir_client(client, "nir-p2-malformed@test.com")
        case, review = _eligible_case(user=user)
        _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        before = Case.objects.get(pk=case.pk)

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_acknowledged": "on",
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    "lock_token": "not-a-uuid",
                },
            )

        assert response.status_code == 302
        location = response["Location"]
        assert "correction_exam_type=colonoscopy" in location
        assert "correction_justification" not in location
        assert "review_acknowledged" not in location
        assert "consent" not in location
        assert marker not in location

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            rerendered = client.get(location)
        assert rerendered.status_code == 200
        content = rerendered.content.decode()
        assert marker in content
        assert "<i>italico</i>" not in content
        assert "&lt;i&gt;italico&lt;/i&gt;" in content
        assert 'value="colonoscopy" selected' in content
        ack_tag = content.split('name="review_acknowledged"')[1].split(">")[0]
        assert "checked" not in ack_tag
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            reread = client.get(location)
        assert marker not in reread.content.decode()

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data == before.structured_data
        assert reloaded.suggested_action == before.suggested_action
        assert reloaded.summary_text == before.summary_text
        # A recusa nao consome a reserva (o GET de re-render pode rotacionar
        # o token via heartbeat, sem transferir a titularidade).
        assert reloaded.lock_token is not None
        assert reloaded.lock_role == "nir"
        assert reloaded.lock_context == "nir_receipt"
        # Sem evento de confirmacao/correcao: o POST recusado nao produz
        # auditoria de decisao (o GET de re-render pode emitir eventos de
        # reserva pre-existentes, fora do escopo desta correcao).
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []

    def test_lease_mismatch_permission_error_preserves_attempt(self, client, monkeypatch) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        marker = "P2-LEASE-MISMATCH-51f0aa"
        justification = f"{marker} revisei <u>sublinhado</u> & aspas"
        client, user = _nir_client(client, "nir-p2-lease@test.com")
        case, review = _eligible_case(user=user)
        _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))
        before = Case.objects.get(pk=case.pk)

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_acknowledged": "on",
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    # UUID valido mas divergente da reserva retida -> PermissionError.
                    "lock_token": str(uuid.uuid4()),
                },
            )

        assert response.status_code == 302
        location = response["Location"]
        assert "correction_exam_type=colonoscopy" in location
        assert "correction_justification" not in location
        assert "review_acknowledged" not in location
        assert "consent" not in location
        assert marker not in location

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            rerendered = client.get(location)
        assert rerendered.status_code == 200
        content = rerendered.content.decode()
        assert marker in content
        assert "<u>sublinhado</u>" not in content
        assert "&lt;u&gt;sublinhado&lt;/u&gt;" in content
        assert 'value="colonoscopy" selected' in content
        ack_tag = content.split('name="review_acknowledged"')[1].split(">")[0]
        assert "checked" not in ack_tag
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            reread = client.get(location)
        assert marker not in reread.content.decode()

        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data == before.structured_data
        assert reloaded.suggested_action == before.suggested_action
        assert reloaded.summary_text == before.summary_text
        # A reserva obsoleta nao e consumida nem transferida (o GET de
        # re-render pode rotacionar o token via heartbeat).
        assert reloaded.lock_token is not None
        assert reloaded.lock_role == "nir"
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_REVIEW_CONFIRMED").exists()
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()
        assert enqueue_calls == []

    def test_nul_justification_discarded_on_missing_token(self, client) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        marker = "P2-NUL-77aa01"
        justification = f"prefixo {marker}\x00 sufixo descartado"
        client, user = _nir_client(client, "nir-p2-nul@test.com")
        case, review = _eligible_case(user=user)
        _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                },
            )

        assert response.status_code == 302
        location = response["Location"]
        assert "correction_exam_type=colonoscopy" in location
        assert marker not in location
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            rerendered = client.get(location)
        content = rerendered.content.decode()
        assert marker not in content
        assert "sufixo descartado" not in content
        assert 'value="colonoscopy" selected' in content

    def test_overlong_justification_discarded_on_missing_token(self, client, monkeypatch) -> None:
        from apps.cases.procedure_review import source_fingerprint_for_case

        enqueue_calls: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue_calls.append(case_id))
        marker = "P2-OVERLONG-3e9c55"
        justification = f"{marker} " + ("y" * 600)
        assert len(justification.strip()) > 500
        client, user = _nir_client(client, "nir-p2-overlong@test.com")
        case, review = _eligible_case(user=user)
        _claim(case, user)
        fingerprint = source_fingerprint_for_case(Case.objects.get(pk=case.pk))

        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {
                    "exam_type": ProcedureType.COLONOSCOPY,
                    "review_justification": justification,
                    "review_event_id": str(review.pk),
                    "source_fingerprint": fingerprint,
                    # sem lock_token: o servico nunca e chamado; o helper
                    # descarta a justificativa fora do limite (500).
                },
            )

        assert response.status_code == 302
        location = response["Location"]
        assert "correction_exam_type=colonoscopy" in location
        assert marker not in location
        with override_settings(COLONOSCOPY_INTAKE_ENABLED=True):
            rerendered = client.get(location)
        content = rerendered.content.decode()
        assert marker not in content
        assert 'value="colonoscopy" selected' in content
        assert enqueue_calls == []
