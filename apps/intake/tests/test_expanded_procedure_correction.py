"""Slice 007 — correção/reenvio NIR pelo catálogo (R1–R3).

Cobre:

- R1: correção e reenvio usam o MESMO combobox/chaves de seleção do catálogo
  do upload, preservam a seleção em erro de re-render e rejeitam alias, label,
  texto livre e conjunto proibido sem persistência parcial;
- R2: correção elegível mantém UUID/PDF/texto/extracted, invalida derivados,
  registra anterior/novo e agenda EXATAMENTE um reprocessamento 4.0 sem
  anexos; ``WAIT_DOCTOR``+ continua bloqueado;
- R3: reenvio cria novo caso somente com a seleção escolhida (nunca herdada)
  e não altera os procedimentos/artefatos do original.

A cobertura canônica do combobox é Django-side (contrato HTML/POST, re-render,
fallback SSR e validação backend); o teste Node é complementar.
"""

from __future__ import annotations

import re
import uuid
from io import BytesIO

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseAttachment,
    CaseEvent,
    CaseProcedure,
    CaseStatus,
    ProcedureType,
)
from apps.cases.procedures import (
    ALLOWED_PROCEDURE_SETS,
    get_declared_procedure_types,
    procedure_types_for_selection,
)
from apps.cases.services import claim_case_lock
from apps.intake.services import (
    correct_case_exam_type,
    create_corrected_resubmission,
    intake_selection_options,
    is_exam_type_correction_eligible,
)
from apps.pipeline.llm import RecordingLlmClient
from apps.pipeline.orchestrator import run_pipeline
from apps.pipeline.tests.test_eda_package_pipeline_v4 import _capsule_procedure
from apps.pipeline.tests.test_slice_002_pipeline import (
    _llm1_json,
    _llm2_json,
    _single_procedure_recommendation,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

ALL_FLAGS_ON = {
    "COLONOSCOPY_INTAKE_ENABLED": True,
    "ECHOENDOSCOPY_INTAKE_ENABLED": True,
    "CPRE_INTAKE_ENABLED": True,
}

CAPSULE_REPORT = "Solicito EDA com cápsula endoscópica para investigação."

# Todos os valores publicados no intake (mesma ordem do catálogo/jornada).
PUBLISHED_SELECTION_KEYS = tuple(option.key for option in intake_selection_options())

# Pacotes e família Retossigmoidoscopia sem gate de flag (Slices 003/004/005).
FLAGLESS_SELECTION_KEYS = (
    ProcedureType.EDA,
    ProcedureType.EDA_GASTROSTOMY,
    ProcedureType.EDA_CAPSULE,
    ProcedureType.EDA_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
)

# Identidades com gate de flag por jornada (D10) e a flag que as habilita.
GATED_SELECTIONS = (
    (ProcedureType.COLONOSCOPY, "COLONOSCOPY_INTAKE_ENABLED"),
    (EDA_COLONOSCOPY, "COLONOSCOPY_INTAKE_ENABLED"),
    (ProcedureType.ECHOENDOSCOPY, "ECHOENDOSCOPY_INTAKE_ENABLED"),
    (ProcedureType.CPRE, "CPRE_INTAKE_ENABLED"),
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_pdf_bytes(text: str = "Paciente: Maria\nRegistro: 2026-0505-001") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _simple_pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("test.pdf", _create_test_pdf_bytes(), content_type="application/pdf")


def _nir_user(django_user_model, username: str = "nir-catalog@test.com"):
    from apps.accounts.models import Role

    user = django_user_model.objects.create_user(username=username, password="testpass123")
    role, _ = Role.objects.get_or_create(name="nir")
    user.roles.add(role)
    return user


def _nir_client(client, username: str = "nir-catalog-view@test.com"):
    user = _nir_user(User, username)
    client.force_login(user)
    session = client.session
    session["active_role"] = "nir"
    session.save()
    return client, user


def _make_eligible_case(
    user,
    *,
    declared: str = ProcedureType.EDA,
    status: str = CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    reason_code: str = "exam_type_mismatch",
    detected: str = ProcedureType.EDA_CAPSULE,
    extracted_text: str = CAPSULE_REPORT,
) -> Case:
    """Caso em revisão manual elegível à correção (projeção declarada por rows)."""
    case = Case.objects.create(
        created_by=user,
        status=status,
        agency_record_number="12345",
        extracted_text=extracted_text,
        structured_data={
            "schema_version": "3.0",
            "eda": {"requested_procedure": {"subtype": "standard"}},
        },
        summary_text="Resumo do perfil anterior (derivado).",
        suggested_action={
            "decision": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": "Conjunto declarado difere da solicitação atual.",
            "declared_procedures": [declared],
            "detected_procedures": [detected],
        },
        priority_signals=[{"code": "foreign_body", "label": "Corpo estranho"}],
    )
    for procedure_type in procedure_types_for_selection(declared):
        CaseProcedure.objects.create(case=case, procedure_type=procedure_type, declared_by_nir=True)
    return case


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


def _select_block(html: str) -> str:
    match = re.search(r"<select[^>]*name=\"exam_type\"[^>]*>.*?</select>", html, re.DOTALL)
    assert match is not None, "select canônico de exam_type ausente"
    return match.group(0)


def _select_tag(block: str) -> str:
    match = re.search(r"<select[^>]*>", block)
    assert match is not None, "tag select ausente"
    return match.group(0)


def _option_tags(block: str) -> list[str]:
    return re.findall(r"<option[^>]*>", block)


def _option_tag(block: str, value: str) -> str:
    for tag in _option_tags(block):
        if f'value="{value}"' in tag:
            return tag
    raise AssertionError(f"Opção {value!r} ausente: {_option_tags(block)}")


def _option_values(block: str) -> list[str]:
    values: list[str] = []
    for tag in _option_tags(block):
        match = re.search(r'value="([^"]*)"', tag)
        if match and match.group(1):
            values.append(match.group(1))
    return values


def _correction_select(html: str, case_id) -> str:
    """Select canônico dentro do formulário de correção daquele caso."""
    url = reverse("intake:exam_type_correction", args=[case_id])
    form = re.search(r"<form[^>]*action=\"" + re.escape(url) + r"\"[^>]*>.*?</form>", html, re.DOTALL)
    assert form is not None, "formulário de correção ausente"
    assert not re.search(r"<input[^>]*name=[\"']exam_type[\"']", form.group(0)), "radios de exam_type persistidos"
    return _select_block(form.group(0))


# ═══════════════════════════════════════════════════════════════════════════
# R1 — correção usa o combobox do catálogo
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionCatalogSelection:
    def test_correction_uses_the_same_catalog_combobox_as_upload(self, client) -> None:
        """R1: select canônico com todas as identidades habilitadas, sem radios."""
        with override_settings(**ALL_FLAGS_ON):
            client, user = _nir_client(client, "nir-cor-select@test.com")
            case = _make_eligible_case(user)
            html = client.get(reverse("intake:case_detail", args=[case.case_id])).content.decode()

        block = _correction_select(html, case.case_id)
        select = _select_tag(block)
        assert 'name="exam_type"' in select
        assert "data-procedure-combobox" in select
        assert "procedure_combobox.js" in html, "combobox progressivo não carregado"
        assert _option_values(block) == list(PUBLISHED_SELECTION_KEYS)
        assert ProcedureType.EDA_CAPSULE.label in block
        assert ProcedureType.EDA_GASTROSTOMY.label in block

    def test_correction_offers_only_flag_enabled_identities(self, client) -> None:
        """R1/D10: só o que a jornada permite — flags preexistentes continuam gate."""
        client, user = _nir_client(client, "nir-cor-flag@test.com")
        case = _make_eligible_case(user)

        content = client.get(reverse("intake:case_detail", args=[case.case_id])).content.decode()
        block = _correction_select(content, case.case_id)
        values = _option_values(block)
        assert ProcedureType.ECHOENDOSCOPY not in values
        assert ProcedureType.CPRE not in values
        for key in FLAGLESS_SELECTION_KEYS:
            assert key in values, key
            if key == ProcedureType.EDA:  # seleção atual: marcada e desabilitada
                continue
            assert "disabled" not in _option_tag(block, key), key
        assert "disabled" in _option_tag(block, ProcedureType.EDA)

    def test_correction_marks_the_declared_selection_as_current(self, client) -> None:
        """A seleção atual aparece marcada (e não pode ser reescolhida)."""
        client, user = _nir_client(client, "nir-cor-current@test.com")
        case = _make_eligible_case(user)

        content = client.get(reverse("intake:case_detail", args=[case.case_id])).content.decode()
        block = _correction_select(content, case.case_id)
        declared_tag = _option_tag(block, ProcedureType.EDA)
        assert "selected" in declared_tag
        assert "disabled" in declared_tag
        assert f"{ProcedureType.EDA.label}(atual)" in block.replace(" ", "")

    def test_correction_error_rerender_preserves_the_attempted_selection(self, client, monkeypatch) -> None:
        """R1: POST rejeitado por outro campo re-renderiza com a escolha válida."""
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        client, user = _nir_client(client, "nir-cor-preserve@test.com")
        case = _make_eligible_case(user)
        token = _claim(case, user)

        with override_settings(**ALL_FLAGS_ON):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {"exam_type": ProcedureType.EDA_CAPSULE, "reason_code": "", "lock_token": token},
                follow=True,
            )

        assert response.status_code == 200
        content = response.content.decode()
        block = _correction_select(content, case.case_id)
        attempted = _option_tag(block, ProcedureType.EDA_CAPSULE)
        assert "selected" in attempted
        assert "selected" not in _option_tag(block, ProcedureType.COLONOSCOPY)
        # Nada foi corrigido nem enfileirado.
        assert enqueue == []
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)


# ═══════════════════════════════════════════════════════════════════════════
# R1 — backend rejeita alias/texto livre/conjunto proibido
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionBackendValidation:
    @pytest.mark.parametrize(
        "value",
        ["GTT", "gtt", "cápsula", "Cápsula", "EDA + Cápsula", "EDA + Colonoscopia", "eda_unknown"],
    )
    def test_alias_label_or_free_text_is_rejected_without_partial_persistence(
        self, client, monkeypatch, value: str
    ) -> None:
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        client, user = _nir_client(client, f"nir-cor-alias-{uuid.uuid4().hex[:8]}@test.com")
        case = _make_eligible_case(user)
        token = _claim(case, user)

        client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": value, "reason_code": "nir_identified_exam", "lock_token": token},
        )

        assert enqueue == []
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data is not None
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()

    @pytest.mark.parametrize(
        "duplicated",
        [
            [ProcedureType.EDA_DILATION, ProcedureType.COLONOSCOPY],
            [ProcedureType.COLONOSCOPY, ProcedureType.EDA_DILATION],
            [ProcedureType.EDA_GASTROSTOMY, ProcedureType.COLONOSCOPY],
        ],
    )
    def test_manipulated_post_never_persists_a_prohibited_pair(self, client, monkeypatch, duplicated) -> None:
        """R1: POST manipulado com duas identidades não persiste conjunto proibido."""
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        client, user = _nir_client(client, f"nir-cor-dup-{duplicated[0]}@test.com")
        case = _make_eligible_case(user)
        token = _claim(case, user)

        client.post(
            reverse("intake:exam_type_correction", args=[case.case_id]),
            {"exam_type": duplicated, "reason_code": "nir_identified_exam", "lock_token": token},
        )

        reloaded = Case.objects.get(pk=case.pk)
        declared = get_declared_procedure_types(reloaded)
        # No máximo o último valor submetido: nunca um par proibido persistido.
        assert frozenset(declared) in ALLOWED_PROCEDURE_SETS
        assert len(declared) <= 1


# ═══════════════════════════════════════════════════════════════════════════
# D10 (fix round 1) — correção só aceita o que a jornada expõe
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionJourneyPermittedSelection:
    """D10: POST manipulado nunca alcança opção que a jornada de correção exclui.

    A mesma derivação por jornada do combobox (``intake_selection_options``) é
    aplicada no backend: identidade com flag de intake desligada é rejeitada
    sem persistência, sem evento e sem reprocessamento agendado.
    """

    @pytest.mark.parametrize(("selection", "flag_name"), GATED_SELECTIONS)
    def test_gated_selection_rejected_with_flag_off_without_side_effects(
        self, django_user_model, monkeypatch, selection: str, flag_name: str
    ) -> None:
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        user = _nir_user(django_user_model, f"nir-journey-off-{selection}@test.com")
        case = _make_eligible_case(user)
        case.pdf_file = "pdfs/2025/01/original.pdf"
        case.save()
        original_id = case.case_id
        token = _claim(case, user)

        with override_settings(**{flag_name: False}), pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=selection,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        assert enqueue == []
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.case_id == original_id
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data is not None
        assert reloaded.summary_text == "Resumo do perfil anterior (derivado)."
        assert reloaded.pdf_file.name == "pdfs/2025/01/original.pdf"
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()

    @pytest.mark.parametrize(
        "selection",
        [ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY, ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE],
    )
    def test_manipulated_post_to_unavailable_selection_is_rejected(self, client, monkeypatch, selection: str) -> None:
        """POST cru com flag desligada não persiste nem agenda reprocessamento."""
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        client, user = _nir_client(client, f"nir-journey-post-{selection}@test.com")
        case = _make_eligible_case(user)
        token = _claim(case, user)

        with override_settings(
            COLONOSCOPY_INTAKE_ENABLED=False,
            ECHOENDOSCOPY_INTAKE_ENABLED=False,
            CPRE_INTAKE_ENABLED=False,
        ):
            response = client.post(
                reverse("intake:exam_type_correction", args=[case.case_id]),
                {"exam_type": selection, "reason_code": "nir_identified_exam", "lock_token": token},
                follow=True,
            )

        assert response.status_code == 200
        assert enqueue == []
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data is not None
        assert not CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED").exists()

    @pytest.mark.parametrize(("selection", "flag_name"), GATED_SELECTIONS)
    def test_gated_selection_accepted_with_flag_on(
        self, django_user_model, monkeypatch, selection: str, flag_name: str
    ) -> None:
        """Regressão: com a flag ligada a correção segue aceitando a identidade."""
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        user = _nir_user(django_user_model, f"nir-journey-on-{selection}@test.com")
        case = _make_eligible_case(user)
        token = _claim(case, user)

        with override_settings(**{flag_name: True}):
            result = correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=selection,
                user=user,
                active_role="nir",
                lock_token=token,
                reason_code="nir_identified_exam",
            )

        assert result.status == CaseStatus.LLM_STRUCT
        assert get_declared_procedure_types(Case.objects.get(pk=case.pk)) == procedure_types_for_selection(selection)
        assert enqueue == [case.case_id]


# ═══════════════════════════════════════════════════════════════════════════
# R2 — correção 3.0 → 4.0, um único reprocessamento, sem anexos
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrectionReprocessing:
    def test_3_0_case_corrected_to_package_reprocesses_once_in_4_0(self, django_user_model, monkeypatch) -> None:
        """R2: 3.0 → 4.0 no MESMO UUID, derivados invalidados, um enqueue, sem PDF."""
        pipeline_calls: list[object] = []
        pdf_calls: list[object] = []
        monkeypatch.setattr(
            "apps.pipeline.tasks.enqueue_pipeline",
            lambda case_id: pipeline_calls.append(case_id),
        )
        monkeypatch.setattr(
            "apps.intake.tasks.enqueue_pdf_extraction",
            lambda case_id: pdf_calls.append(case_id),
        )
        user = _nir_user(django_user_model, "nir-cor-3to4@test.com")
        case = _make_eligible_case(user)
        case.pdf_file = "pdfs/2025/01/original.pdf"
        case.save()
        attachment = CaseAttachment.objects.create(
            case=case,
            file="attachments/keep.pdf",
            original_filename="keep.pdf",
            stored_filename=f"{case.case_id}.pdf",
            content_type="application/pdf",
            size_bytes=10,
            sha256="0" * 64,
            uploaded_by=user,
        )
        original_id = case.case_id
        extracted_text = case.extracted_text
        token = _claim(case, user)

        result = correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=ProcedureType.EDA_CAPSULE,
            user=user,
            active_role="nir",
            lock_token=token,
            reason_code="nir_identified_exam",
        )

        assert result.case_id == original_id
        assert pipeline_calls == [original_id]
        assert pdf_calls == []
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == CaseStatus.LLM_STRUCT
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA_CAPSULE,)
        # R2: fontes preservadas.
        assert reloaded.extracted_text == extracted_text
        assert reloaded.pdf_file.name == "pdfs/2025/01/original.pdf"
        assert CaseAttachment.objects.filter(pk=attachment.pk, case=reloaded).exists()
        # R2: derivados 3.0 invalidados (o próximo write é o contrato atual).
        assert reloaded.structured_data is None
        assert reloaded.summary_text == ""
        assert reloaded.suggested_action is None
        assert reloaded.priority_signals == []
        # R2: anterior/novo auditados.
        corrected = CaseEvent.objects.get(case=case, event_type="CASE_PROCEDURE_DECLARATION_CORRECTED")
        assert corrected.payload["old_procedures"] == [ProcedureType.EDA]
        assert corrected.payload["new_procedures"] == [ProcedureType.EDA_CAPSULE]

        # R2: o reprocessamento escreve o artefato 4.0 (pipeline do branch é 4.0).
        client = RecordingLlmClient(
            responses=[
                _llm1_json(procedures=[_capsule_procedure()], one_liner="EDA + Cápsula indicada."),
                _llm2_json(str(case.case_id), recommendations=_single_procedure_recommendation("eda_capsule")),
            ]
        )
        run_pipeline(case.case_id, llm_client=client)

        reprocessed = Case.objects.get(pk=case.pk)
        assert reprocessed.status == CaseStatus.WAIT_DOCTOR
        assert isinstance(reprocessed.structured_data, dict)
        assert reprocessed.structured_data["schema_version"] == "4.0"

    @pytest.mark.parametrize(
        "status",
        [
            CaseStatus.WAIT_DOCTOR,
            CaseStatus.DOCTOR_ACCEPTED,
            CaseStatus.APPT_CONFIRMED,
            CaseStatus.CLEANED,
        ],
    )
    def test_wait_doctor_and_later_block_correction_without_side_effects(
        self, django_user_model, monkeypatch, status: str
    ) -> None:
        """R2: ``WAIT_DOCTOR``+ bloqueia a correção (nenhuma mutação/enqueue)."""
        enqueue: list[object] = []
        monkeypatch.setattr("apps.pipeline.tasks.enqueue_pipeline", lambda case_id: enqueue.append(case_id))
        user = _nir_user(django_user_model, f"nir-cor-blocked-{status}@test.com")
        case = _make_eligible_case(user, status=status)
        assert is_exam_type_correction_eligible(case) is False

        with pytest.raises(ValueError):
            correct_case_exam_type(
                case_id=case.case_id,
                new_exam_type=ProcedureType.EDA_CAPSULE,
                user=user,
                active_role="nir",
                lock_token=uuid.uuid4(),
                reason_code="nir_identified_exam",
            )

        assert enqueue == []
        reloaded = Case.objects.get(pk=case.pk)
        assert reloaded.status == status
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.structured_data is not None


# ═══════════════════════════════════════════════════════════════════════════
# R1/R3 — reenvio corrigido
# ═══════════════════════════════════════════════════════════════════════════


class TestResubmissionCatalogSelection:
    def test_resubmission_uses_the_same_catalog_combobox_as_upload(self, client) -> None:
        client, user = _nir_client(client, "nir-resub-combobox@test.com")
        original = Case.objects.create(created_by=user)

        with override_settings(**ALL_FLAGS_ON):
            html = client.get(reverse("intake:corrected_resubmission", args=[original.case_id])).content.decode()

        assert not re.search(r"<input[^>]*name=[\"']exam_type[\"']", html), "radios de exam_type persistidos"
        block = _select_block(html)
        assert "data-procedure-combobox" in _select_tag(block)
        assert "procedure_combobox.js" in html
        assert _option_values(block) == list(PUBLISHED_SELECTION_KEYS)

    def test_resubmission_marks_flag_disabled_identities_as_unavailable(self, client) -> None:
        client, user = _nir_client(client, "nir-resub-flags@test.com")
        original = Case.objects.create(created_by=user)
        html = client.get(reverse("intake:corrected_resubmission", args=[original.case_id])).content.decode()

        block = _select_block(html)
        for key in (ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY, ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE):
            assert "disabled" in _option_tag(block, key), key
        for key in FLAGLESS_SELECTION_KEYS:
            assert "disabled" not in _option_tag(block, key), key
        assert "indisponível para novos envios" in html

    def test_resubmission_error_rerender_preserves_the_attempted_selection(self, client) -> None:
        client, user = _nir_client(client, "nir-resub-preserve@test.com")
        original = Case.objects.create(created_by=user)

        response = client.post(
            reverse("intake:corrected_resubmission", args=[original.case_id]),
            {"correction_reason": "Corrige laudo", "exam_type": ProcedureType.EDA_DILATION, "confirmation": "on"},
        )

        assert response.status_code == 200
        html = response.content.decode()
        assert "Selecione um novo PDF principal" in html or "PDF" in html
        block = _select_block(html)
        assert "selected" in _option_tag(block, ProcedureType.EDA_DILATION)
        assert Case.objects.count() == 1

    @pytest.mark.parametrize(
        "selection",
        [
            ProcedureType.EDA_GASTROSTOMY,
            ProcedureType.EDA_CAPSULE,
            ProcedureType.EDA_DILATION,
            ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
            ProcedureType.CPRE,
            EDA_COLONOSCOPY,
        ],
    )
    def test_resubmission_persists_only_the_chosen_selection(self, django_user_model, selection: str) -> None:
        """R3: o novo caso declara somente a escolha; o original não é alterado."""
        user = _nir_user(django_user_model, f"nir-resub-{selection}@test.com")
        original = Case.objects.create(
            created_by=user,
            agency_record_number="2026-EDA-ORIG",
            structured_data={"schema_version": "3.0"},
            extracted_text="Relatório do original.",
        )
        CaseProcedure.objects.create(case=original, procedure_type=ProcedureType.EDA, declared_by_nir=True)

        with override_settings(**ALL_FLAGS_ON):
            new_case = create_corrected_resubmission(
                original_case=original,
                pdf_file=_simple_pdf(),
                user=user,
                correction_reason="Corrige classificação do relatório.",
                exam_type=selection,
            )

        assert get_declared_procedure_types(new_case) == procedure_types_for_selection(selection)
        # R3: o original mantém procedimentos e artefatos intactos.
        original = Case.objects.get(pk=original.pk)
        assert get_declared_procedure_types(original) == (ProcedureType.EDA,)
        assert original.structured_data == {"schema_version": "3.0"}
        assert original.extracted_text == "Relatório do original."
        assert not CaseProcedure.objects.filter(case=original).exclude(procedure_type=ProcedureType.EDA).exists()

    def test_resubmission_rejects_alias_without_creating_a_case(self, client) -> None:
        client, user = _nir_client(client, "nir-resub-alias@test.com")
        original = Case.objects.create(created_by=user)

        response = client.post(
            reverse("intake:corrected_resubmission", args=[original.case_id]),
            {
                "correction_reason": "Corrige laudo",
                "pdf_file": _simple_pdf(),
                "confirmation": "on",
                "exam_type": "GTT",
            },
        )

        assert response.status_code == 200
        assert Case.objects.count() == 1
        assert CaseProcedure.objects.filter(case=original).count() == 0


class TestResubmissionJourneyPermittedSelection:
    """D10 (fix round 1): o reenvio já recusa identidade fora da jornada.

    O reenvio passa por ``ensure_exam_type_allowed`` (choice + colonscopia/
    combinado + especializados), então o gap da correção NÃO existe aqui. Estes
    testes fixam essa paridade para o backend de reenvio.
    """

    @pytest.mark.parametrize(("selection", "flag_name"), GATED_SELECTIONS)
    def test_gated_selection_rejected_with_flag_off_without_creating_a_case(
        self, django_user_model, selection: str, flag_name: str
    ) -> None:
        user = _nir_user(django_user_model, f"nir-resub-journey-{selection}@test.com")
        original = Case.objects.create(
            created_by=user,
            agency_record_number="2026-EDA-ORIG",
            structured_data={"schema_version": "3.0"},
            extracted_text="Relatório do original.",
        )
        CaseProcedure.objects.create(case=original, procedure_type=ProcedureType.EDA, declared_by_nir=True)

        with override_settings(**{flag_name: False}), pytest.raises(ValueError):
            create_corrected_resubmission(
                original_case=original,
                pdf_file=_simple_pdf(),
                user=user,
                correction_reason="Corrige classificação do relatório.",
                exam_type=selection,
            )

        assert Case.objects.count() == 1
        assert not Case.objects.filter(corrects_case=original).exists()
        reloaded = Case.objects.get(pk=original.pk)
        assert get_declared_procedure_types(reloaded) == (ProcedureType.EDA,)
        assert reloaded.extracted_text == "Relatório do original."
        assert not CaseEvent.objects.filter(case=original, event_type="CASE_MARKED_SUPERSEDED").exists()

    @pytest.mark.parametrize(
        "selection",
        [ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY, ProcedureType.ECHOENDOSCOPY],
    )
    def test_gated_selection_accepted_with_flag_on(self, django_user_model, selection: str) -> None:
        """Regressão: com a flag ligada o reenvio segue criando o novo caso."""
        user = _nir_user(django_user_model, f"nir-resub-on-{selection}@test.com")
        original = Case.objects.create(created_by=user, agency_record_number="2026-EDA-ORIG")
        CaseProcedure.objects.create(case=original, procedure_type=ProcedureType.EDA, declared_by_nir=True)

        with override_settings(**ALL_FLAGS_ON):
            new_case = create_corrected_resubmission(
                original_case=original,
                pdf_file=_simple_pdf(),
                user=user,
                correction_reason="Corrige classificação do relatório.",
                exam_type=selection,
            )

        assert get_declared_procedure_types(new_case) == procedure_types_for_selection(selection)
        assert Case.objects.count() == 2
