"""Tests for scope detection: EDA vs non-EDA/unknown classification.

Ported faithfully from the legacy augmented-triage-system:
  tests/integration/test_process_pdf_case_llm2.py  (scope-gating scenarios)
  tests/integration/test_room1_final_reply_jobs.py  (scope-gate manual-review routing)

Every test case and assertion preserved. Only the import path changed.
"""

from __future__ import annotations

import importlib
from typing import cast

import pytest


def _classify(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str = "",
    case_id: str = "test-case-id",
    agency_record_number: str = "test-agency-record",
) -> dict[str, object] | None:
    """Dynamically import and invoke classify_exam_scope."""

    module = importlib.import_module("apps.pipeline.scope_detection")
    classify_exam_scope = getattr(module, "classify_exam_scope")
    result = classify_exam_scope(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
        case_id=case_id,
        agency_record_number=agency_record_number,
    )
    if result is None:
        return None
    return cast(dict[str, object], result)


# ── Gastrostomy keyword ──────────────────────────────────────────────


def test_gastrostomy_keyword_in_cleaned_text_returns_none_eda() -> None:
    """Gastrostomy keyword (gtt) in cleaned_text → EDA, return None (proceed LLM2)."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente para programar GTT. Exames laboratoriais ok.",
    )
    assert result is None


def test_gastrostomia_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito gastrostomia para o paciente.",
    )
    assert result is None


def test_gastrostomy_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Patient needs gastrostomy. Labs ok.",
    )
    assert result is None


def test_confeccao_de_gtt_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito confeccao de GTT para este paciente.",
    )
    assert result is None


# ── Esophageal dilation keyword ──────────────────────────────────────


def test_dilatacao_esofagica_keyword_in_cleaned_text_returns_none_eda() -> None:
    """Dilatação esofágica keyword → EDA, return None (proceed LLM2)."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente encaminhado para dilatação esofágica.",
    )
    assert result is None


def test_dilatacao_de_esofago_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Indicada dilatacao de esofago por estenose.",
    )
    assert result is None


def test_dilatacao_do_esofago_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente necessita de dilatação do esofago.",
    )
    assert result is None


# ── Echoendoscopy keyword (Slice 001) ───────────────────────────────


def test_ecoendoscopia_keyword_returns_none_eda() -> None:
    """'ecoendoscopia' na solicitação → EDA, return None."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente encaminhado para ecoendoscopia.",
    )
    assert result is None


def test_eco_endoscopia_hyphen_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito eco-endoscopia para avaliação de lesão subepitelial.",
    )
    assert result is None


def test_eco_endoscopia_space_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Indicada eco endoscopia com punção.",
    )
    assert result is None


def test_ultrassonografia_endoscopica_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito ultrassonografia endoscópica para estadiamento.",
    )
    assert result is None


def test_ultrassom_endoscopico_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente para ultrassom endoscópico.",
    )
    assert result is None


def test_eus_with_request_context_returns_none_eda() -> None:
    """EUS com contexto de solicitação → EDA."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito EUS para avaliação de lesão pancreática.",
    )
    assert result is None


def test_eus_isolated_without_context_returns_manual_review() -> None:
    """EUS sem contexto de solicitação/exame/procedimento → não basta."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente realizou EUS em 2024, sem intercorrências.",
    )
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


# ── EUS provenance corrections (Slice 001 corrective) ────────────────


def test_motivo_bare_eus_overrides_non_eda() -> None:
    """'Motivo da Solicitação: EUS ...' é solicitação atual mesmo com LLM1 non_eda."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Motivo da Solicitacao: EUS para avaliar lesao. Unid. X.",
    )
    assert result is None


def test_historical_eus_with_unrelated_context_stays_manual() -> None:
    """EUS histórico no Complemento não vira EDA por 'Motivo' longe no relatório."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    cleaned_text = (
        "Motivo da Solicitacao: Avaliacao de lesao pancreatica. Unid. X. "
        "Complemento da Solicitacao: EUS realizado em 2024."
    )
    result = _classify(llm1_structured_data=llm1, cleaned_text=cleaned_text)
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


def test_structured_name_bare_eus_is_procedural_context() -> None:
    """requested_procedure.name='EUS' fornece contexto procedimental por si só."""

    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "eda": {"requested_procedure": {"name": "EUS", "subtype": "unknown"}},
    }
    result = _classify(llm1_structured_data=llm1, cleaned_text="")
    assert result is None


# ── EUS natural local phrases (Slice 001, second corrective) ──────────


@pytest.mark.parametrize(
    "request_text",
    [
        "Encaminhamento para EUS para avaliar lesao.",
        "Encaminhado para EUS para avaliar lesao.",
        "Solicitacao de EUS para avaliar lesao.",
        "Procedimento de EUS indicado.",
        "Exame de EUS indicado.",
        "Solicito realizacao de EUS para avaliar lesao.",
        "Solicito EUS para avaliar lesao.",
        "EUS solicitado para avaliar lesao.",
    ],
)
def test_eus_natural_local_request_phrases_follow_eda(request_text: str) -> None:
    """C4: frases locais naturais de solicitação/exame/procedimento → EDA."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1, cleaned_text=request_text)
    assert result is None


@pytest.mark.parametrize(
    "historical_text",
    [
        "Exame anterior: EUS realizado em 2024.",
        "Procedimento realizado: EUS em 2024.",
        "Solicitacao previa de EUS foi cancelada.",
        "Paciente realizou EUS em 2024, sem intercorrencias.",
    ],
)
def test_eus_historical_qualifying_phrases_stay_manual(historical_text: str) -> None:
    """C5: construções que qualificam EUS como histórico → revisão manual."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1, cleaned_text=historical_text)
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


@pytest.mark.parametrize(
    "mixed_text",
    [
        "Solicito EUS; exame anterior sem alteracoes.",
        "Solicito EUS para controle de procedimento realizado em 2024.",
        "EUS solicitado para comparar com exame anterior.",
    ],
)
def test_eus_unrelated_historical_wording_does_not_cancel_request(mixed_text: str) -> None:
    """C5: histórico não relacionado em outra cláusula não cancela pedido atual."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1, cleaned_text=mixed_text)
    assert result is None


# ── EUS occurrence-specific + colon labels (Slice 001, third corrective) ──


@pytest.mark.parametrize(
    "mixed_text",
    [
        "Paciente realizou EUS em 2023 e solicita EUS agora.",
        "Solicito EUS agora e paciente realizou EUS em 2023.",
        "EUS realizado em 2023 e EUS solicitado agora.",
    ],
)
def test_eus_mixed_historical_and_current_occurrences_follow_eda(mixed_text: str) -> None:
    """C7: uma ocorrência histórica não cancela pedido atual distinto na mesma cláusula."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1, cleaned_text=mixed_text)
    assert result is None


@pytest.mark.parametrize(
    "label_text",
    [
        "Procedimento: EUS",
        "Exame: EUS",
        "Solicitacao: EUS",
    ],
)
def test_eus_immediate_colon_labels_follow_eda(label_text: str) -> None:
    """C8: rótulos imediatos antes de ':' fornecem contexto local positivo."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1, cleaned_text=label_text)
    assert result is None


@pytest.mark.parametrize(
    "historical_text",
    [
        "EUS realizado em 2022 e EUS previo em 2023.",
        "Exame anterior: EUS realizado em 2024.",
        "Procedimento realizado: EUS em 2024.",
        "Solicitacao previa: EUS cancelado.",
    ],
)
def test_eus_all_historical_occurrences_stay_manual(historical_text: str) -> None:
    """C9: ocorrências todas históricas/rotuladas-históricas → revisão manual."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1, cleaned_text=historical_text)
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


def test_requested_procedure_name_echoendoscopy_with_puncture_returns_none_eda() -> None:
    """Nome estruturado ecoendoscopia com punção → EDA; modificador não muda subtipo."""

    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "eda": {"requested_procedure": {"name": "Ecoendoscopia com punção e PAAF"}},
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is None


def test_structured_subtype_echoendoscopy_rulebook_returns_none_eda() -> None:
    """Subtipo estruturado echoendoscopy (rulebook) → EDA."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "unknown",
            "rulebook_signals": {"eda_subtype": "echoendoscopy"},
        },
    }
    result = _classify(llm1_structured_data=llm1, cleaned_text="Relatório sem termo explícito.")
    assert result is None


def test_structured_subtype_echoendoscopy_requested_returns_none_eda() -> None:
    """Subtipo estruturado echoendoscopy (requested_procedure) → EDA."""

    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "eda": {"requested_procedure": {"subtype": "echoendoscopy", "name": "EUS"}},
    }
    result = _classify(llm1_structured_data=llm1, cleaned_text="")
    assert result is None


# ── EDA/echo precedence in mixed requests (R4) ───────────────────────


def test_ecoendoscopia_and_cpre_follows_eda() -> None:
    """Motivo com ecoendoscopia + CPRE → EDA mesmo com LLM1 non_eda."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    cleaned_text = """
    Motivo da Solicitação:
    Ecoendoscopia e CPRE para avaliação de via biliar
    Unid. Origem:
    HSA - HOSPITAL SANTO ANTONIO
    """
    result = _classify(llm1_structured_data=llm1, cleaned_text=cleaned_text)
    assert result is None


def test_ecoendoscopia_and_cpre_follows_eda_via_structured_subtype() -> None:
    """Subtipo estruturado echoendoscopy prevalece sobre LLM1 non_eda."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "non_eda",
            "rulebook_signals": {"eda_subtype": "echoendoscopy"},
        },
        "eda": {"requested_procedure": {"subtype": "echoendoscopy", "name": "Ecoendoscopia"}},
    }
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Relatório menciona CPRE em avaliação de via biliar.",
    )
    assert result is None


def test_eda_and_colonoscopia_follows_eda() -> None:
    """Motivo com EDA + colonoscopia → EDA (EDA suportada prevalece)."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    cleaned_text = """
    Motivo da Solicitação:
    EDA diagnóstica e colonoscopia de rastreamento
    Unid. Origem:
    HSA - HOSPITAL SANTO ANTONIO
    """
    result = _classify(llm1_structured_data=llm1, cleaned_text=cleaned_text)
    assert result is None


def test_only_colonoscopy_with_historical_eda_mention_preserves_manual_review() -> None:
    """Motivo somente colonoscopia + menção histórica de EDA → revisão manual."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    cleaned_text = """
    Motivo da Solicitação:
    Colonoscopia de rastreamento
    Unid. Origem:
    HSA - HOSPITAL SANTO ANTONIO
    Complemento da Solicitação:
    Paciente com EDA prévia em 2023 sem alterações.
    """
    result = _classify(llm1_structured_data=llm1, cleaned_text=cleaned_text)
    assert result is not None
    assert result["decision"] == "manual_review_required"
    assert result["reason_code"] == "non_eda_request"


def test_only_cpre_preserves_manual_review() -> None:
    """Somente CPRE sem EDA/eco atual → revisão manual."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito CPRE para avaliação de via biliar.",
    )
    assert result is not None
    assert result["reason_code"] == "non_eda_request"


# ── Foreign body keyword ─────────────────────────────────────────────


def test_corpo_estranho_keyword_in_cleaned_text_returns_none_eda() -> None:
    """Corpo estranho keyword → foreign_body EDA, return None (proceed LLM2)."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente com corpo estranho no esôfago. EDA urgente.",
    )
    assert result is None


def test_retirada_de_corpo_estranho_keyword_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito retirada de corpo estranho via EDA.",
    )
    assert result is None


# ── Explicit EDA terms ───────────────────────────────────────────────


def test_full_eda_text_returns_none_eda() -> None:
    """Full 'endoscopia digestiva alta' text → EDA, return None."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito endoscopia digestiva alta para avaliação de dispepsia.",
    )
    assert result is None


def test_videoendoscopia_digestiva_alta_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito videoendoscopia digestiva alta.",
    )
    assert result is None


def test_endoscopia_digestiva_superior_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Endoscopia digestiva superior solicitada.",
    )
    assert result is None


def test_solicitacao_de_eda_explicit_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicitacao de endoscopia digestiva alta para o paciente.",
    )
    assert result is None


def test_eda_with_hyphen_explicit_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Endoscopia Digestiva Alta - EDA. Paciente com dispepsia.",
    )
    assert result is None


# ── EDA acronym with request context ─────────────────────────────────


def test_eda_acronym_with_motivo_context_returns_none_eda() -> None:
    """EDA acronym + 'motivo' context → EDA, return None."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Motivo: EDA para este paciente.",
    )
    assert result is None


def test_eda_acronym_with_motivo_word_context_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Motivo EDA: dispepsia persistente.",
    )
    assert result is None


def test_eda_acronym_with_exame_context_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Exame EDA solicitado.",
    )
    assert result is None


def test_eda_acronym_with_encaminhamento_context_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Encaminhamento para EDA.",
    )
    assert result is None


def test_eda_acronym_with_procedimento_context_returns_none_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Procedimento: EDA.",
    )
    assert result is None


# ── Non-EDA explicit ─────────────────────────────────────────────────


def test_non_eda_exam_type_returns_manual_review() -> None:
    """LLM1 declares non_eda → manual_review_required payload."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    result = _classify(llm1_structured_data=llm1)

    assert result is not None
    assert result["decision"] == "manual_review_required"
    assert result["suggestion"] == "manual_review_required"
    assert result["reason_code"] == "non_eda_request"
    assert result["exam_type"] == "non_eda"


def test_non_eda_exam_type_wins_over_default_eda_subtype() -> None:
    """Colonoscopia classified as non_eda must not reach doctor due to subtype noise.

    Real OpenAI runs may correctly set preop_screening.exam_type=non_eda while
    still leaving requested_procedure.subtype or rulebook eda_subtype as a
    default EDA subtype. The explicit non_eda classification is authoritative.
    """

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "non_eda",
            "evidence_spans": [{"field_path": "preop_screening.exam_type", "excerpt": "colonoscopia"}],
            "rulebook_signals": {"eda_subtype": "standard"},
        },
        "eda": {"requested_procedure": {"name": "Colonoscopia", "subtype": "standard"}},
        "summary": {"one_liner": "Colonoscopia solicitada.", "bullet_points": ["Exame fora de escopo EDA."]},
    }
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito colonoscopia para investigação.",
    )

    assert result is not None
    assert result["decision"] == "manual_review_required"
    assert result["reason_code"] == "non_eda_request"
    assert result["exam_type"] == "non_eda"


def test_motivo_endoscopia_digestiva_baixa_wins_over_later_eda_mentions() -> None:
    """Top-level colonoscopy motive must not be overridden by later EDA text."""

    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "eda", "rulebook_signals": {"eda_subtype": "standard"}},
        "eda": {"requested_procedure": {"name": "EDA", "subtype": "standard"}},
    }
    cleaned_text = """
    Motivo da Solicitação:
    Endoscopia Digestiva Baixa - Colonoscopia
    Unid. Origem:
    HSA - HOSPITAL SANTO ANTONIO
    Complemento da Solicitação:
    SOLICITO REGULAÇÃO PARA COLONOSCOPIA DIAGNÓSTICA E EDA DIAGNÓSTICA E TERAPÊUTICA
    Resumo Clínico:
    EDA prévia com gastrite erosiva.
    """

    result = _classify(llm1_structured_data=llm1, cleaned_text=cleaned_text)

    assert result is not None
    assert result["decision"] == "manual_review_required"
    assert result["reason_code"] == "non_eda_request"
    assert result["exam_type"] == "non_eda"


def test_cpre_non_eda_returns_manual_review() -> None:
    """CPRE text without EDA keywords → still requires LLM1 to detect non_eda."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito CPRE para avaliacao de via biliar.",
    )
    assert result is not None
    assert result["decision"] == "manual_review_required"
    assert result["reason_code"] == "non_eda_request"


def test_colonoscopia_non_eda_returns_manual_review() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Colonoscopia de rastreamento.",
    )
    assert result is not None
    assert result["decision"] == "manual_review_required"


# ── Unknown exam type ────────────────────────────────────────────────


def test_unknown_exam_type_returns_manual_review() -> None:
    """LLM1 declares unknown → manual_review_required payload."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1)

    assert result is not None
    assert result["decision"] == "manual_review_required"
    assert result["suggestion"] == "manual_review_required"
    assert result["reason_code"] == "unknown_exam_type"
    assert result["exam_type"] == "unknown"


def test_unknown_without_any_eda_evidence_returns_manual_review() -> None:
    """Unknown exam type with no EDA evidence anywhere → manual review."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Relatório médico genérico sem menção a exame específico.",
    )
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


# ── LLM1 subtype fallback ────────────────────────────────────────────


def test_llm1_subtype_standard_used_as_fallback() -> None:
    """LLM1 provides standard subtype via eda.requested_procedure.subtype → EDA."""

    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "eda": {
            "requested_procedure": {"subtype": "standard", "name": "EDA"},
            "indication_category": "dyspepsia",
        },
    }
    result = _classify(llm1_structured_data=llm1, cleaned_text="Relatório sem EDA explícito.")
    assert result is None


def test_llm1_subtype_gastrostomy_from_rulebook_signals() -> None:
    """LLM1 subtype from rulebook_signals → EDA."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "unknown",
            "rulebook_signals": {"eda_subtype": "gastrostomy"},
        },
    }
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente para GTT.",
    )
    assert result is None


def test_llm1_subtype_esophageal_dilation_from_rulebook_signals() -> None:
    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "unknown",
            "rulebook_signals": {"eda_subtype": "esophageal_dilation"},
        },
    }
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente para dilatacao.",
    )
    assert result is None


def test_llm1_subtype_foreign_body_from_rulebook_signals() -> None:
    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "unknown",
            "rulebook_signals": {"eda_subtype": "foreign_body"},
        },
    }
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Corpo estranho no esofago.",
    )
    assert result is None


# ── Normalization (diacritics, case) ──────────────────────────────────


def test_accented_eda_detected_after_normalization() -> None:
    """Accented EDA text normalized to ascii for matching."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito endoscopía digestíva altá para avaliação.",
    )
    assert result is None


def test_uppercase_eda_detected_after_normalization() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="ENDOSCOPIA DIGESTIVA ALTA - EDA.",
    )
    assert result is None


def test_mixed_case_eda_acronym_with_context() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="ExAmE: EdA pArA pAcIeNtE.",
    )
    assert result is None


def test_accented_gastrostomia_detected_after_normalization() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito gastrostomía para paciente.",
    )
    assert result is None


def test_accented_dilatacao_esofagica_detected() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente para dilatação esofágica.",
    )
    assert result is None


def test_accented_corpo_estranho_detected() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Paciente com corpo estranho no esôfago.",
    )
    assert result is None


# ── Partial word not matching ────────────────────────────────────────


def test_edac_word_boundary_does_not_match_eda() -> None:
    """'edac' should NOT match 'eda' because word boundary prevents partial match."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Solicito EDAC para paciente.",  # EDAC is not EDA
    )
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


def test_edam_word_boundary_does_not_match_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Exame EDAM solicitado.",
    )
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


def test_partial_eda_without_request_context_does_not_match() -> None:
    """EDA without request context keywords → no EDA detection."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="O paciente realizou EDA previamente.",
    )
    # "realizou" is not a request context keyword → no EDA match
    assert result is not None
    assert result["reason_code"] == "unknown_exam_type"


# ── Evidence spans in payload ────────────────────────────────────────


def test_non_eda_payload_includes_evidence_spans() -> None:
    """Manual review payload preserves evidence spans from LLM1."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "non_eda",
            "evidence_spans": [
                {
                    "field_path": "preop_screening.exam_type",
                    "excerpt": "CPRE solicitado",
                }
            ],
        }
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is not None
    assert result["evidence_spans"] == [{"field_path": "preop_screening.exam_type", "excerpt": "CPRE solicitado"}]


def test_unknown_payload_includes_evidence_spans() -> None:
    """Unknown manual review payload preserves evidence spans from LLM1."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "unknown",
            "evidence_spans": [
                {
                    "field_path": "preop_screening.exam_type",
                    "excerpt": "Tipo de exame nao identificado",
                }
            ],
        }
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is not None
    assert result["evidence_spans"] == [
        {
            "field_path": "preop_screening.exam_type",
            "excerpt": "Tipo de exame nao identificado",
        }
    ]


# ── EDA exam_type from LLM1 bypasses scope gate ──────────────────────


def test_eda_exam_type_from_llm1_returns_none_directly() -> None:
    """LLM1 declares eda → return None immediately."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "eda"}}
    result = _classify(llm1_structured_data=llm1)
    assert result is None


# ── Keyword in summary.one_liner or summary.bullet_points ─────────────


def test_keyword_in_summary_one_liner_triggers_detection() -> None:
    """Gastrostomy keyword in summary.one_liner → EDA detection."""

    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "summary": {"one_liner": "Paciente aguardando programar GTT."},
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is None


def test_keyword_in_summary_bullet_points_triggers_detection() -> None:
    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "summary": {
            "bullet_points": [
                "Paciente com dispepsia",
                "Exame: EDA para avaliacao de dispepsia",
            ]
        },
    }
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="",
    )
    assert result is None


# ── Keyword in eda.requested_procedure.name ───────────────────────────


def test_keyword_in_requested_procedure_name_triggers_detection() -> None:
    llm1: dict[str, object] = {
        "preop_screening": {"exam_type": "unknown"},
        "eda": {"requested_procedure": {"name": "Endoscopia Digestiva Alta para gastrostomia"}},
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is None


# ── Payload structure validation ─────────────────────────────────────


def test_payload_has_required_fields_for_non_eda() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "non_eda"}}
    result = _classify(
        llm1_structured_data=llm1,
        case_id="case-123",
        agency_record_number="ARN-456",
    )
    assert result is not None
    assert result["schema_version"] == "1.1"
    assert result["language"] == "pt-BR"
    assert result["case_id"] == "case-123"
    assert result["agency_record_number"] == "ARN-456"
    assert result["decision"] == "manual_review_required"
    assert result["suggestion"] == "manual_review_required"
    assert result["reason_code"] == "non_eda_request"
    assert result["exam_type"] == "non_eda"


def test_payload_has_required_fields_for_unknown() -> None:
    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(llm1_structured_data=llm1)
    assert result is not None
    assert result["schema_version"] == "1.1"
    assert result["language"] == "pt-BR"
    assert result["decision"] == "manual_review_required"
    assert result["suggestion"] == "manual_review_required"
    assert result["reason_code"] == "unknown_exam_type"
    assert result["exam_type"] == "unknown"


# ── Edge cases ───────────────────────────────────────────────────────


def test_empty_llm1_data_returns_none_pass_through() -> None:
    """Totally empty LLM1 data → no exam_type → defaults to pass-through (None).

    This matches the legacy behaviour: when preop_screening is absent entirely,
    _extract_preop_exam_type returns None, and None ∉ {non_eda, unknown} → None.
    In practice LLM1 always sets exam_type, so this edge case never triggers.
    """

    llm1: dict[str, object] = {}
    result = _classify(llm1_structured_data=llm1)
    assert result is None


def test_missing_preop_screening_returns_none_pass_through() -> None:
    """No preop_screening → no exam_type → defaults to pass-through (None).

    Faithful to legacy: when preop_screening is absent, exam_type remains None
    and the function returns None (proceed to LLM2). In real flows LLM1 always
    populates preop_screening.exam_type.
    """

    llm1: dict[str, object] = {"eda": {"indication_category": "dyspepsia"}}
    result = _classify(llm1_structured_data=llm1)
    assert result is None


def test_explicit_eda_in_evidence_span_triggers_detection() -> None:
    """EDA keyword inside evidence_span excerpt → EDA detection."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "unknown",
            "evidence_spans": [
                {
                    "field_path": "preop_screening.exam_type",
                    "excerpt": "Endoscopia digestiva alta solicitada",
                }
            ],
        }
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is None


def test_dotted_eda_abbreviation_with_request_context() -> None:
    """'e.d.a' dotted abbreviation with 'exame' context → EDA."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Exame: e.d.a para o paciente.",
    )
    assert result is None


def test_hyphenated_eda_abbreviation_with_context() -> None:
    """'e-d-a' hyphenated abbreviation with motive context → EDA."""

    llm1: dict[str, object] = {"preop_screening": {"exam_type": "unknown"}}
    result = _classify(
        llm1_structured_data=llm1,
        cleaned_text="Motivo: e-d-a para investigacao.",
    )
    assert result is None


def test_evidence_spans_with_invalid_items_are_filtered() -> None:
    """Invalid entries in evidence_spans are silently dropped."""

    llm1: dict[str, object] = {
        "preop_screening": {
            "exam_type": "non_eda",
            "evidence_spans": [
                {"field_path": "valid", "excerpt": "valid"},
                "not_a_dict",
                {"no_excerpt": "missing"},
                {"field_path": "", "excerpt": ""},
            ],
        }
    }
    result = _classify(llm1_structured_data=llm1)
    assert result is not None
    assert result["evidence_spans"] == [{"field_path": "valid", "excerpt": "valid"}]
