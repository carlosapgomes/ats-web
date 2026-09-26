"""Pistas de procedimentos no corpo do relatório.

Slice 001 — `Justificativa da Transferência` como contexto de solicitação:
spans da seção no texto normalizado (R1), coleta de ocorrências com offsets
absolutos por cláusula em vez de ``str.find`` (R1b), promoção de menção dentro
da seção para solicitação atual (R2), não-promoção de histórico/negação e de
ocorrências fora da seção (R3), rótulo de proveniência ``section`` (R4) e
direção de falha da reconciliação (R5b).

Slice 002 — conectores instrumentais no vínculo variação↔base: `via`, `por`,
`através de` e `com uso de` (além de `com`/`e`) vinculam o termo ambíguo à base
da família na mesma cláusula (R1–R3), sem afetar a demotion do termo sem vínculo
nem o bloqueio de anatomia dilatada (R4), com a detecção v4 do texto-exemplo
completo (R5).

Slice 003 — precedência de família sobre o guarda-chuva do Motivo: exatamente
uma identidade atual da família Retossigmoidoscopia absorve a `colonoscopy`
cujo conjunto só se sustenta pelo alias guarda-chuva `Endoscopia Digestiva
Baixa` marcado em `motivo_da_solicitacao` (R1–R5), com metadado de regra
própria no dict único e na lista aditiva (R2/R6b).

Slice 004 — gate de conflito do item estruturado: o item estruturado do LLM1
contraditado por ocorrência não-atual do termo passa a sinalizar `conflicting`
no dict de detecção (por tipo, default `False` — R1) e a reconciliação devolve
`nir_review`/`conflicting_procedure_evidence` em vez de prosseguir em silêncio
(R2/R5); o wiring do orchestrator (R3) e o reason code elegível no intake (R4)
fecham a falha aberta. Sem item estruturado, a menção isolada segue inerte (R6).

Item 1.0 (change ``followup-body-clue-detection-hardening``) — o motivo da
revisão NIR informa a ORIGEM da detecção (seções das ocorrências atuais do
conjunto detectado) e a listagem de pistas deixa de ser renderizada na UI; a
projeção/payload ``detected_body_clues`` permanece para auditoria.
"""

from __future__ import annotations

import pytest

from apps.cases.models import Case, CaseEvent, CaseStatus, ProcedureType
from apps.pipeline.procedure_reconciliation import (
    ProcedureReconciliationResult,
    build_v2_review_payload,
    project_body_clues,
    reconcile_detected_procedures,
    serialize_procedure_precedence,
    serialize_procedure_precedence_rules,
)
from apps.pipeline.scope_detection import (
    ProcedureOccurrence,
    _justificativa_section_spans,
    _labelled_section_spans,
    _normalize_scope_keyword_text,
    detect_procedure_occurrences,
    detect_requested_procedures_v4,
)
from apps.pipeline.tests.test_rectosigmoidoscopy_pipeline_v4 import (
    _recto_procedure,
    _run,
    _suggested_action,
)
from apps.pipeline.tests.test_slice_002_pipeline import _llm1_json, _single_procedure_recommendation

JUSTIFICATIVA_SECTION = "justificativa_da_transferencia"
MOTIVO_SECTION = "motivo_da_solicitacao"

JUSTIFICATIVA_LABEL = "justificativa da transferencia"
MOTIVO_LABEL = "motivo da solicitacao"

# Relatório-exemplo real: cabeçalho de página, Motivo com o guarda-chuva
# `Endoscopia Digestiva Baixa - Colonoscopia` terminado por `Unid. Origem:`
# (layout real da SUREM: Motivo → Unid. Origem → ... → Justificativa) e a
# Justificativa com oração intermediária terminada em `.` antes do nome do
# procedimento, encerrada pelo cabeçalho da página seguinte.
REGULATION_REPORT_TEXT = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Governo do Estado da Bahia\n"
    "Código: 12345\n"
    "Abertura: 01/02/2026\n"
    "Motivo da Solicitação: Endoscopia Digestiva Baixa - Colonoscopia\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferência: Paciente com quadro de constipação intestinal crônica. "
    "Refere sangramento retal há dois meses. Retossigmoidoscopia para investigação.\n"
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Informado por: Dra. Fulana\n"
)

# Boilerplate repetido entre páginas: a MESMA cláusula aparece dentro da
# Justificativa e depois do cabeçalho da página seguinte.
REPEATED_CLAUSE_TEXT = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Motivo da Solicitação: Endoscopia Digestiva Baixa.\n"
    "Justificativa da Transferência: Paciente com síndrome dispéptica. Retossigmoidoscopia.\n"
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Informado por: Dra. Fulana. Retossigmoidoscopia.\n"
)

# Seção operacional que não é Justificativa nem Motivo: ocorrência ali é mera
# menção e não recebe rótulo de seção.
OUTSIDE_SECTION_TEXT = (
    "Motivo da Solicitação: Endoscopia Digestiva Baixa.\n"
    "Complemento da Solicitação: paciente aguardando vaga. Retossigmoidoscopia.\n"
    "Unid. Origem: Hospital Central\n"
)

TERMINATORS: tuple[str, ...] = (
    "RELATÓRIO DE OCORRÊNCIAS",
    "Informado por: Dr. Silva",
    "Motivo da Solicitação: EDA",
    "Complemento da Solicitação: sem complemento",
    "Resumo Clínico: anemia",
    "Hipótese do Diagnóstico: neoplasia",
    "Encaminhamento: ambulatório de proctologia",
    "Mot. Solicit.: colonoscopia",
    "Unid. Origem: Hospital Central",
)


def _normalized(text: str) -> str:
    return _normalize_scope_keyword_text(value=text)


def _occurrences(text: str) -> tuple[ProcedureOccurrence, ...]:
    return detect_procedure_occurrences(llm1_structured_data={}, cleaned_text=text)


def _occurrence(
    *,
    occurrences: tuple[ProcedureOccurrence, ...],
    procedure_type: str,
    excerpt: str | None = None,
) -> ProcedureOccurrence:
    matches = [
        occurrence
        for occurrence in occurrences
        if occurrence.procedure_type == procedure_type and (excerpt is None or occurrence.excerpt == excerpt)
    ]
    assert len(matches) == 1, (procedure_type, excerpt, matches)
    return matches[0]


def _justificativa_span(*, normalized_text: str) -> tuple[int, int]:
    spans = _justificativa_section_spans(normalized_text=normalized_text)
    assert len(spans) == 1, spans
    start, end = spans[0]
    assert start == normalized_text.find(JUSTIFICATIVA_LABEL)
    return start, end


def _motivo_span(*, normalized_text: str) -> tuple[int, int]:
    spans = _labelled_section_spans(normalized_text=normalized_text, label=MOTIVO_LABEL)
    assert len(spans) == 1, spans
    start, end = spans[0]
    assert start == normalized_text.find(MOTIVO_LABEL)
    return start, end


# ── R1: spans da seção `Justificativa da Transferência` ─────────────────────


@pytest.mark.parametrize("terminator", TERMINATORS)
def test_justificativa_span_stops_at_known_terminator(terminator: str) -> None:
    text = f"Justificativa da Transferência: Retossigmoidoscopia para investigação.\n{terminator}"
    normalized = _normalized(text)
    start, end = _justificativa_span(normalized_text=normalized)
    assert normalized[start:end].rstrip() == "justificativa da transferencia: retossigmoidoscopia para investigacao."
    assert end == normalized.find(_normalized(terminator))


def test_justificativa_span_without_terminator_runs_to_end_of_text() -> None:
    text = "Justificativa da Transferência: Retossigmoidoscopia para investigação."
    normalized = _normalized(text)
    assert _justificativa_section_spans(normalized_text=normalized) == (
        (normalized.find(JUSTIFICATIVA_LABEL), len(normalized)),
    )


def test_justificativa_span_absent_label_returns_empty() -> None:
    normalized = _normalized("Motivo da Solicitação: Colonoscopia.\nInformado por: Dra. Fulana")
    assert _justificativa_section_spans(normalized_text=normalized) == ()


def test_justificativa_span_ignores_terminators_before_the_label() -> None:
    text = "Informado por: Dra. Fulana. Justificativa da Transferência: Retossigmoidoscopia."
    normalized = _normalized(text)
    assert _justificativa_section_spans(normalized_text=normalized) == (
        (normalized.find(JUSTIFICATIVA_LABEL), len(normalized)),
    )


# ── R1b: offsets absolutos por cláusula ─────────────────────────────────────


def test_repeated_clause_offsets_are_distinct_and_sections_do_not_leak() -> None:
    normalized = _normalized(REPEATED_CLAUSE_TEXT)
    recto = tuple(
        occurrence
        for occurrence in _occurrences(REPEATED_CLAUSE_TEXT)
        if occurrence.procedure_type == "rectosigmoidoscopy"
    )
    assert len(recto) == 2
    assert len({occurrence.start for occurrence in recto}) == 2
    assert len({occurrence.evidence_id for occurrence in recto}) == 2
    for occurrence in recto:
        assert normalized[occurrence.start : occurrence.end] == occurrence.excerpt
    assert sorted((occurrence.section, occurrence.qualification) for occurrence in recto) == [
        ("", "mention"),
        (JUSTIFICATIVA_SECTION, "current_request"),
    ]
    assert recto[0].start < recto[1].start


# ── R2/R3: a seção qualifica menção como solicitação atual ──────────────────


def test_mention_inside_justificativa_becomes_current() -> None:
    occurrences = _occurrences(REGULATION_REPORT_TEXT)
    occurrence = _occurrence(occurrences=occurrences, procedure_type="rectosigmoidoscopy")
    assert occurrence.qualification == "current_request"
    assert occurrence.excerpt == "retossigmoidoscopia"
    assert occurrence.section == JUSTIFICATIVA_SECTION
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=REGULATION_REPORT_TEXT)
    assert detection["rectosigmoidoscopy"] == {"strong": True, "any": True, "conflicting": False}


def test_historical_and_negated_inside_section_not_promoted() -> None:
    text = "Justificativa da Transferência: Retossigmoidoscopia realizada em 2022. Paciente nega colonoscopia."
    occurrences = _occurrences(text)
    historical = _occurrence(occurrences=occurrences, procedure_type="rectosigmoidoscopy")
    assert historical.qualification == "historical"
    assert historical.section == JUSTIFICATIVA_SECTION
    negated = _occurrence(occurrences=occurrences, procedure_type="colonoscopy")
    assert negated.qualification == "negated"
    assert negated.section == JUSTIFICATIVA_SECTION
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=text)
    assert detection["rectosigmoidoscopy"] == {"strong": False, "any": False, "conflicting": False}
    assert detection["colonoscopy"] == {"strong": False, "any": False, "conflicting": False}


def test_outside_section_stays_mention() -> None:
    occurrence = _occurrence(
        occurrences=_occurrences(OUTSIDE_SECTION_TEXT),
        procedure_type="rectosigmoidoscopy",
    )
    assert occurrence.qualification == "mention"
    assert occurrence.section == ""


def test_promoted_base_extends_the_link_to_the_variation_in_the_same_clause() -> None:
    """A promoção acontece ANTES do passe de vínculo (R2/D1)."""
    text = (
        "Justificativa da Transferência: Paciente com quadro de constipação. "
        "Retossigmoidoscopia com dilatação de anastomose colorretal."
    )
    occurrences = _occurrences(text)
    for procedure_type in ("rectosigmoidoscopy", "rectosigmoidoscopy_dilation"):
        occurrence = _occurrence(occurrences=occurrences, procedure_type=procedure_type)
        assert occurrence.qualification == "current_request", procedure_type
        assert occurrence.linked_base is True, procedure_type
        assert occurrence.section == JUSTIFICATIVA_SECTION, procedure_type


# ── R4: proveniência da seção em cada ocorrência ────────────────────────────


def test_occurrence_carries_section_label() -> None:
    occurrences = _occurrences(REGULATION_REPORT_TEXT)
    umbrella = _occurrence(occurrences=occurrences, procedure_type="colonoscopy", excerpt="endoscopia digestiva baixa")
    assert umbrella.qualification == "current_request"
    assert umbrella.section == MOTIVO_SECTION
    explicit = _occurrence(occurrences=occurrences, procedure_type="colonoscopy", excerpt="colonoscopia")
    assert explicit.qualification == "mention"
    assert explicit.section == MOTIVO_SECTION
    assert {occurrence.section for occurrence in occurrences} == {MOTIVO_SECTION, JUSTIFICATIVA_SECTION}


# R5 exige o fixture fiel ao layout real: o Motivo da Solicitação é seguido do
# valor e então do rótulo `Unid. Origem:`, que encerra a seção. Estes testes
# provam o endpoint do span do Motivo tanto no nível da função quanto no da
# ocorrência após o terminador.


def test_motivo_span_stops_at_unid_origem_terminator() -> None:
    normalized = _normalized(REGULATION_REPORT_TEXT)
    start, end = _motivo_span(normalized_text=normalized)
    assert normalized[start:end].rstrip() == "motivo da solicitacao: endoscopia digestiva baixa - colonoscopia"
    assert end == normalized.find("unid. origem: hospital central")
    assert end < normalized.find(JUSTIFICATIVA_LABEL)


def test_occurrence_after_unid_origem_is_not_marked_as_motivo() -> None:
    text = (
        "Motivo da Solicitação: Endoscopia Digestiva Baixa.\n"
        "Unid. Origem: Hospital Central. Colonoscopia para investigação.\n"
    )
    occurrence = _occurrence(
        occurrences=_occurrences(text),
        procedure_type="colonoscopy",
        excerpt="colonoscopia",
    )
    assert occurrence.section == ""
    assert occurrence.qualification == "mention"


def test_occurrence_section_defaults_to_empty() -> None:
    occurrence = ProcedureOccurrence(
        procedure_type="rectosigmoidoscopy",
        qualification="mention",
        excerpt="retossigmoidoscopia",
        start=3,
        end=22,
    )
    assert occurrence.section == ""
    assert occurrence.evidence_id == "rectosigmoidoscopy:3-22"


# ── R5b: direção de falha da reconciliação (D6) ─────────────────────────────


def _reconcile(*, declared: tuple[str, ...], cleaned_text: str) -> ProcedureReconciliationResult:
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=cleaned_text)
    return reconcile_detected_procedures(
        declared=declared,
        strong=tuple(procedure_type for procedure_type, flags in detection.items() if flags["strong"]),
        any_evidence=tuple(procedure_type for procedure_type, flags in detection.items() if flags["any"]),
        occurrences=_occurrences(cleaned_text),
    )


def test_justificativa_naming_a_divergent_family_fails_closed() -> None:
    """Slice 003: a família absorve o guarda-chuva; a divergência segue fail-closed.

    Antes do Slice 003 a colonoscopia do Motivo sobrevivia e o conflito era o da
    matriz (``unsupported_procedure_combination``); agora o alias guarda-chuva é
    absorvido pela família e o desfecho é o mismatch limpo — declarado divergente
    NUNCA prossegue.
    """
    result = _reconcile(declared=("colonoscopy",), cleaned_text=REGULATION_REPORT_TEXT)
    assert result.action == "nir_review"
    assert result.reason_code == "exam_type_mismatch"
    assert result.detected_procedure_types == ("rectosigmoidoscopy",)
    assert result.family_umbrella_precedence_applied is True
    assert result.suppressed_umbrella_types == ("colonoscopy",)


def test_justificativa_naming_the_declared_family_is_detected_as_current_request() -> None:
    text = "Justificativa da Transferência: Retossigmoidoscopia para investigação de sangramento."
    occurrence = _occurrence(occurrences=_occurrences(text), procedure_type="rectosigmoidoscopy")
    assert occurrence.qualification == "current_request"
    assert occurrence.section == JUSTIFICATIVA_SECTION
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=text)
    assert detection["rectosigmoidoscopy"] == {"strong": True, "any": True, "conflicting": False}


# ── Slice 002 (R1–R5): conectores instrumentais no vínculo ──────────────────

# Trecho fiel do relatório-exemplo: a Justificativa traz a cláusula
# `DILATAÇÃO DE ANASTOMOSE COLORRETAL VIA RETOSSIGMOIDOSCOPIA FLEXIVEL` — a
# variação AMBÍGUA vem ANTES da base, unida pelo conector `via`.
VIA_LINK_REPORT_TEXT = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Governo do Estado da Bahia\n"
    "Motivo da Solicitação: Endoscopia Digestiva Baixa - Colonoscopia\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferência: Paciente com quadro de constipação intestinal crônica "
    "refratária a tratamento clínico. DILATAÇÃO DE ANASTOMOSE COLORRETAL VIA "
    "RETOSSIGMOIDOSCOPIA FLEXIVEL\n"
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Informado por: Dra. Fulana\n"
)

# `com`/`e` são os conectores históricos; `via`/`por`/`através de`/`com uso de`
# são os instrumentais acrescentados no Slice 002 (R1).
INSTRUMENTAL_CONNECTORS: tuple[str, ...] = ("via", "por", "através de", "com uso de", "com", "e")


def test_via_link_in_justificativa_example() -> None:
    """A base promovida pela seção estende o vínculo à variação via `via` (R2)."""
    occurrences = _occurrences(VIA_LINK_REPORT_TEXT)
    dilation = _occurrence(occurrences=occurrences, procedure_type="rectosigmoidoscopy_dilation")
    assert dilation.qualification == "current_request"
    assert dilation.linked_base is True
    assert dilation.section == JUSTIFICATIVA_SECTION
    base = _occurrence(occurrences=occurrences, procedure_type="rectosigmoidoscopy")
    assert base.qualification == "current_request"
    assert base.linked_base is True
    # Mesmo termo na família EDA: sem base EDA na cláusula, segue mera menção.
    eda_dilation = _occurrence(occurrences=occurrences, procedure_type="eda_dilation")
    assert eda_dilation.qualification == "mention"
    assert eda_dilation.linked_base is False
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=VIA_LINK_REPORT_TEXT)
    assert detection["rectosigmoidoscopy_dilation"] == {"strong": True, "any": True, "conflicting": False}


@pytest.mark.parametrize("connector", INSTRUMENTAL_CONNECTORS)
def test_via_link_without_section(connector: str) -> None:
    """Ordem invertida sem seção: verbo de solicitação + conector une o termo (R3)."""
    text = f"Solicito dilatação de estenose {connector} retossigmoidoscopia."
    occurrences = _occurrences(text)
    dilation = _occurrence(occurrences=occurrences, procedure_type="rectosigmoidoscopy_dilation")
    assert dilation.qualification == "current_request"
    assert dilation.linked_base is True
    assert dilation.section == ""
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=text)
    assert detection["rectosigmoidoscopy_dilation"] == {"strong": True, "any": True, "conflicting": False}


@pytest.mark.parametrize("connector", ("via", "por", "através de", "com uso de"))
def test_unlinked_and_blocked_terms_stay_mention(connector: str) -> None:
    """Conector novo não substitui o vínculo com a base nem vence o sítio bloqueado (R4)."""
    unlinked_text = (
        f"Relatório de imagem descreve dilatação de anastomose {connector} tomografia. Solicito retossigmoidoscopia."
    )
    for procedure_type in ("eda_dilation", "rectosigmoidoscopy_dilation"):
        occurrence = _occurrence(occurrences=_occurrences(unlinked_text), procedure_type=procedure_type)
        assert occurrence.qualification == "mention", (procedure_type, connector)
        assert occurrence.linked_base is False, (procedure_type, connector)
    unlinked_detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=unlinked_text)
    assert unlinked_detection["rectosigmoidoscopy_dilation"] == {"strong": False, "any": False, "conflicting": False}

    blocked_text = f"Solicito dilatação de colédoco {connector} retossigmoidoscopia."
    blocked = _occurrence(occurrences=_occurrences(blocked_text), procedure_type="rectosigmoidoscopy_dilation")
    assert blocked.qualification == "mention"
    assert blocked.linked_base is False
    blocked_detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=blocked_text)
    assert blocked_detection["rectosigmoidoscopy_dilation"] == {"strong": False, "any": False, "conflicting": False}


def test_v4_detection_detects_combined_example() -> None:
    """O texto-exemplo completo resolve a variação sem item estruturado do LLM1 (R5)."""
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=VIA_LINK_REPORT_TEXT)
    assert detection["rectosigmoidoscopy_dilation"] == {"strong": True, "any": True, "conflicting": False}
    assert detection["rectosigmoidoscopy"] == {"strong": True, "any": True, "conflicting": False}


# ── Slice 003 (R1–R6b): precedência de família sobre o guarda-chuva ─────────

# Justificativa nomeando a família BASE + Motivo com o alias guarda-chuva: a
# família tem exatamente UMA identidade atual e a colonoscopia do conjunto vem
# SÓ do guarda-chuva do Motivo (R1).
FAMILY_MOTIVE_UMBRELLA_TEXT = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Motivo da Solicitação: Endoscopia Digestiva Baixa - Colonoscopia\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferência: Paciente com sangramento retal há dois meses. "
    "Solicito Retossigmoidoscopia para investigação.\n"
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Informado por: Dra. Fulana\n"
)

BASE_ONLY_TEXT = "Justificativa da Transferência: Solicito Retossigmoidoscopia para investigação."


def test_family_umbrella_absorbs_motive_colonoscopy() -> None:
    """A família atual absorve a colonoscopia que só existe pelo guarda-chuva (R1)."""
    result = _reconcile(declared=("rectosigmoidoscopy",), cleaned_text=FAMILY_MOTIVE_UMBRELLA_TEXT)
    assert result.action == "proceed"
    assert result.detected_procedure_types == ("rectosigmoidoscopy",)
    assert result.family_umbrella_precedence_applied is True
    assert result.selected_family_type == "rectosigmoidoscopy"
    assert result.suppressed_umbrella_types == ("colonoscopy",)
    assert result.variation_precedence_applied is False
    assert serialize_procedure_precedence(result) == {
        "rule": "family_umbrella_over_colonoscopy",
        "selected": "rectosigmoidoscopy",
        "suppressed": ["colonoscopy"],
    }


# ── R3: o relatório-exemplo real deixa de alternar com o NIR ────────────────


def test_corrected_family_case_proceeds() -> None:
    """NIR declarou a variação: variação + família reduzem ao declarado (R3)."""
    result = _reconcile(declared=("rectosigmoidoscopy_dilation",), cleaned_text=VIA_LINK_REPORT_TEXT)
    assert result.action == "proceed"
    assert result.detected_procedure_types == ("rectosigmoidoscopy_dilation",)
    assert result.variation_precedence_applied is True
    assert result.family_umbrella_precedence_applied is True
    assert result.selected_family_type == "rectosigmoidoscopy_dilation"
    assert result.suppressed_umbrella_types == ("colonoscopy",)


def test_declared_colonoscopy_mismatches_cleanly() -> None:
    """NIR declarou Colonoscopia: mismatch limpo, sem conflito genérico (R3)."""
    result = _reconcile(declared=("colonoscopy",), cleaned_text=VIA_LINK_REPORT_TEXT)
    assert result.action == "nir_review"
    assert result.reason_code == "exam_type_mismatch"
    assert result.detected_procedure_types == ("rectosigmoidoscopy_dilation",)
    assert result.family_umbrella_precedence_applied is True
    assert result.suppressed_umbrella_types == ("colonoscopy",)


# ── R2: metadado compatível (dict único + lista aditiva) ────────────────────


def test_family_umbrella_precedence_metadata() -> None:
    """Dict único preserva a regra mais significativa; a lista traz todas (R2)."""
    result = _reconcile(declared=("rectosigmoidoscopy_dilation",), cleaned_text=VIA_LINK_REPORT_TEXT)
    assert serialize_procedure_precedence(result) == {
        "rule": "variation_over_base",
        "selected": "rectosigmoidoscopy_dilation",
        "suppressed": ["rectosigmoidoscopy"],
    }
    assert serialize_procedure_precedence_rules(result) == [
        {
            "rule": "variation_over_base",
            "selected": "rectosigmoidoscopy_dilation",
            "suppressed": ["rectosigmoidoscopy"],
        },
        {
            "rule": "family_umbrella_over_colonoscopy",
            "selected": "rectosigmoidoscopy_dilation",
            "suppressed": ["colonoscopy"],
        },
    ]


def test_precedence_rules_list_is_empty_without_reduction() -> None:
    """Sem redução o dict é ``None`` e a lista é vazia (R2, compatibilidade)."""
    result = _reconcile(declared=("rectosigmoidoscopy",), cleaned_text=BASE_ONLY_TEXT)
    assert result.action == "proceed"
    assert serialize_procedure_precedence(result) is None
    assert serialize_procedure_precedence_rules(result) == []


# ── R4: proveniência — só o guarda-chuva do MOTIVO autoriza ─────────────────


def test_explicit_colonoscopy_current_not_absorbed() -> None:
    """R4-i: ocorrência ATUAL do termo explícito não é guarda-chuva."""
    text = (
        "Motivo da Solicitação: Colonoscopia.\n"
        "Justificativa da Transferência: Solicito Retossigmoidoscopia para investigação.\n"
    )
    explicit = _occurrence(occurrences=_occurrences(text), procedure_type="colonoscopy")
    assert explicit.qualification == "current_request"
    assert explicit.excerpt == "colonoscopia"

    result = _reconcile(declared=("rectosigmoidoscopy",), cleaned_text=text)

    assert result.family_umbrella_precedence_applied is False
    assert result.action == "nir_review"
    assert result.reason_code == "unsupported_procedure_combination"
    assert set(result.detected_procedure_types) == {"rectosigmoidoscopy", "colonoscopy"}


def test_body_umbrella_current_not_absorbed() -> None:
    """R4-ii: guarda-chuva ATUAL citado no corpo (seção ≠ Motivo) não autoriza."""
    text = (
        "Motivo da Solicitação: Endoscopia Digestiva Baixa - Colonoscopia\n"
        "Unid. Origem: Hospital Central\n"
        "Justificativa da Transferência: Paciente com anemia. "
        "Solicito Retossigmoidoscopia e Endoscopia Digestiva Baixa para investigação.\n"
    )
    body_umbrella = [
        occurrence
        for occurrence in _occurrences(text)
        if occurrence.procedure_type == "colonoscopy" and occurrence.section == JUSTIFICATIVA_SECTION
    ]
    assert len(body_umbrella) == 1
    assert body_umbrella[0].qualification == "current_request"
    assert body_umbrella[0].excerpt == "endoscopia digestiva baixa"

    result = _reconcile(declared=("rectosigmoidoscopy",), cleaned_text=text)

    assert result.family_umbrella_precedence_applied is False
    assert result.reason_code == "unsupported_procedure_combination"
    assert set(result.detected_procedure_types) == {"rectosigmoidoscopy", "colonoscopy"}


# ── R5: regime de proveniência da família ───────────────────────────────────


def test_family_mention_does_not_absorb() -> None:
    """Sem ocorrência ATUAL da família, a colonoscopia do Motivo permanece (R5)."""
    text = (
        "Motivo da Solicitação: Endoscopia Digestiva Baixa - Colonoscopia\n"
        "Unid. Origem: Hospital Central\n"
        "Complemento da Solicitação: paciente aguardando vaga. Retossigmoidoscopia.\n"
    )
    occurrences = _occurrences(text)
    mention = _occurrence(occurrences=occurrences, procedure_type="rectosigmoidoscopy")
    assert mention.qualification == "mention"

    result = reconcile_detected_procedures(
        declared=("rectosigmoidoscopy",),
        strong=(),
        any_evidence=("rectosigmoidoscopy", "colonoscopy"),
        occurrences=occurrences,
    )

    assert result.family_umbrella_precedence_applied is False
    assert result.reason_code == "unsupported_procedure_combination"
    assert set(result.detected_procedure_types) == {"rectosigmoidoscopy", "colonoscopy"}


# ── R6b: wiring do campo aditivo nos três destinos do orchestrator ──────────

FAMILY_RULES_METADATA: list[dict[str, object]] = [
    {
        "rule": "variation_over_base",
        "selected": "rectosigmoidoscopy_dilation",
        "suppressed": ["rectosigmoidoscopy"],
    },
    {
        "rule": "family_umbrella_over_colonoscopy",
        "selected": "rectosigmoidoscopy_dilation",
        "suppressed": ["colonoscopy"],
    },
]


@pytest.mark.django_db
class TestFamilyUmbrellaPipelineWiring:
    """O dict legado segue sozinho; a lista aditiva acompanha os três destinos."""

    def _target_case(self, user, *, declared_type: str) -> tuple[Case, int]:
        case, client = _run(
            user,
            procedure_types=(declared_type,),
            extracted_text=VIA_LINK_REPORT_TEXT,
            llm1=_llm1_json(
                procedures=[
                    _recto_procedure(
                        "rectosigmoidoscopy_dilation",
                        excerpt="DILATAÇÃO DE ANASTOMOSE COLORRETAL VIA RETOSSIGMOIDOSCOPIA FLEXIVEL",
                    )
                ],
                one_liner="Retossigmoidoscopia + Dilatação indicada.",
            ),
            recommendations=_single_procedure_recommendation("rectosigmoidoscopy_dilation"),
        )
        return case, len(client.calls)

    def test_precedence_rules_wired_in_three_destinations(self, django_user_model) -> None:
        user = django_user_model.objects.create_user(username="nir-family-wiring")
        # (i) evento de detecção + (iii) sugestão final: NIR declarou a família.
        case, calls = self._target_case(user, declared_type="rectosigmoidoscopy_dilation")
        assert calls == 2
        assert case.status == CaseStatus.WAIT_DOCTOR
        detection_payload = (
            CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp").payload
        )
        assert detection_payload["procedure_precedence"] == FAMILY_RULES_METADATA[0]
        assert detection_payload["procedure_precedence_rules"] == FAMILY_RULES_METADATA
        suggested = _suggested_action(case)
        assert suggested["procedure_precedence"] == FAMILY_RULES_METADATA[0]
        assert suggested["procedure_precedence_rules"] == FAMILY_RULES_METADATA

        # (i) evento de detecção + (ii) payload de revisão: NIR declarou Colonoscopia.
        review_case, review_calls = self._target_case(user, declared_type="colonoscopy")
        assert review_calls == 1
        assert review_case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
        review_event = CaseEvent.objects.filter(case=review_case, event_type="CASE_PROCEDURES_DETECTED").latest(
            "timestamp"
        )
        assert review_event.payload["procedure_precedence"] == FAMILY_RULES_METADATA[0]
        assert review_event.payload["procedure_precedence_rules"] == FAMILY_RULES_METADATA
        review_payload = _suggested_action(review_case)
        assert review_payload["reason_code"] == "exam_type_mismatch"
        assert review_payload["procedure_precedence"] == FAMILY_RULES_METADATA[0]
        assert review_payload["procedure_precedence_rules"] == FAMILY_RULES_METADATA


# ── Slice 004 (R1–R6): gate de conflito do item estruturado ─────────────────

# Relatório-exemplo da FALHA ABERTA: o Motivo dá colonoscopia ATUAL (coincide
# com o declarado → prosseguia em silêncio) e o LLM1 reporta
# `rectosigmoidoscopy_dilation` com evidence span, mas o corpo só traz MENÇÃO do
# termo, fora das seções de solicitação (Complemento, não Justificativa/Motivo).
CONFLICT_REPORT_TEXT = (
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Governo do Estado da Bahia\n"
    "Motivo da Solicitação: Colonoscopia\n"
    "Unid. Origem: Hospital Central\n"
    "Justificativa da Transferência: Paciente com constipação intestinal crônica.\n"
    "Complemento da Solicitação: paciente aguardando vaga. Dilatação de anastomose colorretal.\n"
    "RELATÓRIO DE OCORRÊNCIAS\n"
    "Informado por: Dra. Fulana\n"
)

CONFLICT_STRUCTURED: dict[str, object] = {"requested_procedures": [_recto_procedure("rectosigmoidoscopy_dilation")]}


def _signals(detection: dict[str, dict[str, bool]]) -> dict[str, tuple[str, ...]]:
    """Projeta strong/any/conflicting do dict de detecção para a reconciliação."""
    return {
        "strong": tuple(procedure_type for procedure_type, flags in detection.items() if flags["strong"]),
        "any_evidence": tuple(procedure_type for procedure_type, flags in detection.items() if flags["any"]),
        "conflicting": tuple(procedure_type for procedure_type, flags in detection.items() if flags["conflicting"]),
    }


# R1 — o sinal `conflicting` por tipo do dict de detecção


def test_structured_item_vs_mention_flags_conflict() -> None:
    """Item estruturado + ocorrência não-atual do termo ⇒ conflicting=True (R1)."""
    detection = detect_requested_procedures_v4(
        llm1_structured_data=CONFLICT_STRUCTURED,
        cleaned_text=CONFLICT_REPORT_TEXT,
    )
    assert detection["rectosigmoidoscopy_dilation"] == {"strong": False, "any": False, "conflicting": True}
    # Demais tipos carregam o sinal default False (inclusive os derivados de v3).
    assert all(
        flags["conflicting"] is False
        for procedure_type, flags in detection.items()
        if procedure_type != "rectosigmoidoscopy_dilation"
    )


def test_conflicting_defaults_false_without_contradiction() -> None:
    """Sem item estruturado ou sem ocorrência, `conflicting` é False em todo tipo (R1)."""
    current = detect_requested_procedures_v4(
        llm1_structured_data={},
        cleaned_text="Solicito EDA com dilatação esofágica.",
    )
    assert current["eda_dilation"] == {"strong": True, "any": True, "conflicting": False}
    candidate = detect_requested_procedures_v4(
        llm1_structured_data=CONFLICT_STRUCTURED,
        cleaned_text="Relatorio clinico sem mencao ao procedimento.",
    )
    assert candidate["rectosigmoidoscopy_dilation"] == {"strong": True, "any": True, "conflicting": False}
    assert all(flags["conflicting"] is False for flags in candidate.values())


# R2 — a reconciliação vira `nir_review` antes de qualquer proceed


def test_conflicting_evidence_forces_nir_review() -> None:
    """Tipo conhecido em `conflicting` força nir_review/conflicting_procedure_evidence (R2)."""
    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=("colonoscopy",),
        any_evidence=("colonoscopy",),
        occurrences=(),
        conflicting=("rectosigmoidoscopy_dilation",),
    )
    assert result.action == "nir_review"
    assert result.reason_code == "conflicting_procedure_evidence"
    assert result.detected_procedure_types == ("colonoscopy", "rectosigmoidoscopy_dilation")


def test_reconciliation_without_conflicting_is_unchanged() -> None:
    """Sem o parâmetro (default ()) o desfecho é o de hoje — retrocompatível (R2)."""
    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=("colonoscopy",),
        any_evidence=("colonoscopy",),
    )
    assert result.action == "proceed"


# R5 — a falha aberta do relatório-exemplo agora falha fechado


def test_fail_open_scenario_now_fail_closed() -> None:
    """Declarado == Motivo + item estruturado contraditado ⇒ nir_review, não proceed (R5)."""
    detection = detect_requested_procedures_v4(
        llm1_structured_data=CONFLICT_STRUCTURED,
        cleaned_text=CONFLICT_REPORT_TEXT,
    )
    assert detection["rectosigmoidoscopy_dilation"] == {"strong": False, "any": False, "conflicting": True}
    signals = _signals(detection)
    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=signals["strong"],
        any_evidence=signals["any_evidence"],
        occurrences=_occurrences(CONFLICT_REPORT_TEXT),
        conflicting=signals["conflicting"],
    )
    assert result.action == "nir_review"
    assert result.reason_code == "conflicting_procedure_evidence"
    assert set(result.detected_procedure_types) == {"colonoscopy", "rectosigmoidoscopy_dilation"}


# R6 — sem item estruturado, a menção isolada continua inerte


def test_mention_alone_still_inert() -> None:
    """Sem item estruturado, a menção não cria identidade nem conflito (R6)."""
    detection = detect_requested_procedures_v4(
        llm1_structured_data={},
        cleaned_text=CONFLICT_REPORT_TEXT,
    )
    assert detection["rectosigmoidoscopy_dilation"] == {"strong": False, "any": False, "conflicting": False}
    signals = _signals(detection)
    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=signals["strong"],
        any_evidence=signals["any_evidence"],
        occurrences=_occurrences(CONFLICT_REPORT_TEXT),
        conflicting=signals["conflicting"],
    )
    assert result.action == "proceed"


# R3 — o orchestrator repassa o sinal à reconciliação (teste de contrato)


@pytest.mark.django_db
def test_orchestrator_passes_conflicting(django_user_model) -> None:
    """Pipeline real do relatório-exemplo termina em revisão por conflito (R3/R5)."""
    user = django_user_model.objects.create_user(username="nir-conflict-wiring")
    case, client = _run(
        user,
        procedure_types=("colonoscopy",),
        extracted_text=CONFLICT_REPORT_TEXT,
        llm1=_llm1_json(
            procedures=[_recto_procedure("rectosigmoidoscopy_dilation")],
            one_liner="Retossigmoidoscopia + Dilatação indicada.",
        ),
        recommendations=_single_procedure_recommendation("rectosigmoidoscopy_dilation"),
    )
    assert len(client.calls) == 1
    assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
    payload = _suggested_action(case)
    assert payload["reason_code"] == "conflicting_procedure_evidence"
    assert set(payload["detected_procedures"]) == {"colonoscopy", "rectosigmoidoscopy_dilation"}
    detection_event = CaseEvent.objects.filter(case=case, event_type="CASE_PROCEDURES_DETECTED").latest("timestamp")
    assert detection_event.payload["reason_code"] == "conflicting_procedure_evidence"


# ── Slice 005 (R1/R2/R6/R9): pistas do corpo na revisão NIR ─────────────────

# Ordem canônica do catálogo (``apps.cases.procedures``) para o teto de 8.
ALL_PROCEDURE_TYPES: tuple[str, ...] = tuple(procedure_type.value for procedure_type in ProcedureType)


def _occurrence_at(
    procedure_type: str,
    qualification: str,
    *,
    excerpt: str,
    start: int,
    section: str = "",
) -> ProcedureOccurrence:
    """Ocorrência construída à mão para isolar a projeção de R1."""
    return ProcedureOccurrence(
        procedure_type=procedure_type,
        qualification=qualification,
        excerpt=excerpt,
        start=start,
        end=start + len(excerpt),
        section=section,
    )


# R1 — projeção pura das ocorrências do corpo


def test_project_body_clues_shape_and_labels() -> None:
    """A pista carrega tipo, label do catálogo, seção e excerpt (R1)."""
    occurrence = _occurrence_at(
        "rectosigmoidoscopy_dilation",
        "current_request",
        excerpt="retossigmoidoscopia com dilatacao",
        start=10,
        section=JUSTIFICATIVA_SECTION,
    )
    assert project_body_clues((occurrence,)) == [
        {
            "procedure_type": "rectosigmoidoscopy_dilation",
            "procedure_label": "Retossigmoidoscopia + Dilatação",
            "qualification": "current_request",
            "qualification_label": "Solicitação atual",
            "section": JUSTIFICATIVA_SECTION,
            "excerpt": "retossigmoidoscopia com dilatacao",
        }
    ]


@pytest.mark.parametrize(
    ("qualification", "label"),
    [
        ("current_request", "Solicitação atual"),
        ("mention", "Menção"),
        ("historical", "Histórico"),
        ("negated", "Negado"),
    ],
)
def test_project_body_clues_translates_qualification(qualification: str, label: str) -> None:
    """Qualificações são traduzidas para pt-BR (R1)."""
    occurrence = _occurrence_at("eda", qualification, excerpt="eda", start=0)
    assert project_body_clues((occurrence,))[0]["qualification_label"] == label


def test_project_body_clues_orders_current_request_first_then_canonical() -> None:
    """``current_request`` primeiro; restante na ordem canônica do tipo (R1)."""
    occurrences = (
        _occurrence_at("colonoscopy", "mention", excerpt="colonoscopia", start=0),
        _occurrence_at("cpre", "current_request", excerpt="cpre", start=20),
        _occurrence_at("eda", "current_request", excerpt="eda", start=30),
    )
    assert [clue["procedure_type"] for clue in project_body_clues(occurrences)] == ["eda", "cpre", "colonoscopy"]


def test_project_body_clues_caps_at_eight_entries() -> None:
    """Tetô de 8 entradas, cortando pela ordem canônica do tipo (R1)."""
    occurrences = tuple(
        _occurrence_at(procedure_type, "mention", excerpt=procedure_type, start=index)
        for index, procedure_type in enumerate(reversed(ALL_PROCEDURE_TYPES))
    )
    clues = project_body_clues(occurrences)
    assert len(clues) == 8
    assert [clue["procedure_type"] for clue in clues] == list(ALL_PROCEDURE_TYPES[:8])


def test_project_body_clues_truncates_excerpt_to_200_chars() -> None:
    """``excerpt`` limitado a 200 chars (R1)."""
    excerpt = "d" * 250
    clue = project_body_clues((_occurrence_at("eda", "current_request", excerpt=excerpt, start=0),))[0]
    assert clue["excerpt"] == "d" * 200


def test_project_body_clues_excludes_motivo_section() -> None:
    """Ocorrências do Motivo não são pistas do corpo (R1/D5)."""
    clues = project_body_clues(_occurrences(REGULATION_REPORT_TEXT))
    assert [clue["procedure_type"] for clue in clues] == ["rectosigmoidoscopy"]
    assert clues[0]["section"] == JUSTIFICATIVA_SECTION
    assert all(clue["section"] != MOTIVO_SECTION for clue in clues)


def test_project_body_clues_empty_without_occurrences() -> None:
    """Sem ocorrências a projeção é vazia (R1)."""
    assert project_body_clues(()) == []


# R2/R6 — o payload de revisão carrega as pistas (schema 2.1, aditivo)


def test_review_payload_2_1_carries_clues() -> None:
    """Schema 2.1 preserva os campos existentes e agrega ``detected_body_clues`` (R2/R6)."""
    clues = project_body_clues(_occurrences(VIA_LINK_REPORT_TEXT))
    payload = build_v2_review_payload(
        case_id="case-1",
        agency_record_number="12345",
        reason_code="exam_type_mismatch",
        reason_text="Tipo declarado difere do detectado.",
        declared=("colonoscopy",),
        detected=("rectosigmoidoscopy_dilation",),
        evidence_spans=[{"field_path": "requested_procedures.0", "excerpt": "solicitacao"}],
        body_clues=clues,
    )
    assert payload["schema_version"] == "2.1"
    # Campos existentes permanecem (compatibilidade aditiva).
    assert payload["language"] == "pt-BR"
    assert payload["case_id"] == "case-1"
    assert payload["agency_record_number"] == "12345"
    assert payload["decision"] == "manual_review_required"
    assert payload["suggestion"] == "manual_review_required"
    assert payload["reason_code"] == "exam_type_mismatch"
    assert payload["reason_text"] == "Tipo declarado difere do detectado."
    assert payload["declared_procedures"] == ["colonoscopy"]
    assert payload["detected_procedures"] == ["rectosigmoidoscopy_dilation"]
    assert payload["exam_type"] == "rectosigmoidoscopy_dilation"
    assert payload["declared_exam_type"] == "colonoscopy"
    assert payload["detected_exam_type"] == "rectosigmoidoscopy_dilation"
    assert payload["evidence_spans"] == [{"field_path": "requested_procedures.0", "excerpt": "solicitacao"}]
    assert payload["detected_body_clues"] == clues

    dilation = [clue for clue in clues if clue["procedure_type"] == "rectosigmoidoscopy_dilation"]
    assert len(dilation) == 1
    assert dilation[0]["qualification"] == "current_request"
    assert dilation[0]["qualification_label"] == "Solicitação atual"
    assert dilation[0]["section"] == JUSTIFICATIVA_SECTION
    assert dilation[0]["excerpt"] == "dilatacao"
    assert all(clue["section"] != MOTIVO_SECTION for clue in clues)


def test_review_payload_without_clues_keeps_empty_list() -> None:
    """Default ``body_clues=None`` mantém o formato aditivo (lista vazia) (R2)."""
    payload = build_v2_review_payload(
        case_id="case-1",
        agency_record_number="12345",
        reason_code="exam_type_mismatch",
        reason_text="Tipo declarado difere do detectado.",
        declared=("eda",),
        detected=("colonoscopy",),
        evidence_spans=[],
    )
    assert payload["schema_version"] == "2.1"
    assert payload["detected_body_clues"] == []


# R3 — o orchestrator repassa as pistas ao payload do gate NIR


@pytest.mark.django_db
def test_orchestrator_review_payload_has_clues(django_user_model) -> None:
    """O gate de revisão NIR do pipeline real publica as pistas do corpo (R3)."""
    user = django_user_model.objects.create_user(username="nir-body-clues-wiring")
    case, client = _run(
        user,
        procedure_types=("colonoscopy",),
        extracted_text=VIA_LINK_REPORT_TEXT,
        llm1=_llm1_json(
            procedures=[
                _recto_procedure(
                    "rectosigmoidoscopy_dilation",
                    excerpt="DILATAÇÃO DE ANASTOMOSE COLORRETAL VIA RETOSSIGMOIDOSCOPIA FLEXIVEL",
                )
            ],
            one_liner="Retossigmoidoscopia + Dilatação indicada.",
        ),
        recommendations=_single_procedure_recommendation("rectosigmoidoscopy_dilation"),
    )
    assert len(client.calls) == 1
    assert case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
    payload = _suggested_action(case)
    assert payload["reason_code"] == "exam_type_mismatch"
    assert payload["schema_version"] == "2.1"

    clues = payload["detected_body_clues"]
    dilation = [clue for clue in clues if clue["procedure_type"] == "rectosigmoidoscopy_dilation"]
    assert len(dilation) == 1
    assert dilation[0]["qualification"] == "current_request"
    assert dilation[0]["section"] == JUSTIFICATIVA_SECTION
    assert all(clue["section"] != MOTIVO_SECTION for clue in clues)


# R9 — cadeia pura ponta a ponta sobre o texto-exemplo real


def test_end_to_end_example_flow() -> None:
    """detect → reconcile → project → payload sem LLM/banco sobre o exemplo real (R9)."""
    occurrences = _occurrences(VIA_LINK_REPORT_TEXT)
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=VIA_LINK_REPORT_TEXT)
    signals = _signals(detection)

    mismatch = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=signals["strong"],
        any_evidence=signals["any_evidence"],
        occurrences=occurrences,
        conflicting=signals["conflicting"],
    )
    assert mismatch.action == "nir_review"
    assert mismatch.reason_code == "exam_type_mismatch"

    proceed = reconcile_detected_procedures(
        declared=("rectosigmoidoscopy_dilation",),
        strong=signals["strong"],
        any_evidence=signals["any_evidence"],
        occurrences=occurrences,
        conflicting=signals["conflicting"],
    )
    assert proceed.action == "proceed"
    assert proceed.detected_procedure_types == ("rectosigmoidoscopy_dilation",)

    clues = project_body_clues(occurrences)
    payload = build_v2_review_payload(
        case_id="case-1",
        agency_record_number="12345",
        reason_code=mismatch.reason_code,
        reason_text=mismatch.reason_text,
        declared=("colonoscopy",),
        detected=mismatch.detected_procedure_types,
        evidence_spans=[],
        body_clues=clues,
    )
    assert payload["schema_version"] == "2.1"
    assert payload["detected_procedures"] == ["rectosigmoidoscopy_dilation"]
    assert payload["detected_body_clues"] == clues

    dilation = [clue for clue in clues if clue["procedure_type"] == "rectosigmoidoscopy_dilation"]
    assert len(dilation) == 1
    assert dilation[0]["section"] == JUSTIFICATIVA_SECTION
    assert dilation[0]["excerpt"] == "dilatacao"
    assert all(clue["section"] != MOTIVO_SECTION for clue in clues)


# ═══════════════════════════════════════════════════════════════════════════
# Item 1.0 — origem da detecção no motivo da revisão NIR
# ═══════════════════════════════════════════════════════════════════════════

MISMATCH_REASON_TEXT = (
    "Tipo de procedimento declarado difere do detectado na solicitação atual; revisão manual obrigatória."
)
CONFLICTING_REASON_TEXT = (
    "Item estruturado do LLM contradiz o corpo do relatório (ocorrência não-atual do termo); "
    "revisão manual obrigatória."
)
ORIGIN_JUSTIFICATIVA = "Origem da detecção: Justificativa da Transferência"
ORIGIN_MOTIVO = "Origem da detecção: Motivo da Solicitação"


def test_mismatch_reason_text_reports_justificativa_origin() -> None:
    """Ocorrência atual do detectado na Justificativa vira origem no motivo (R1)."""
    text = (
        "Justificativa da Transferência: Paciente com sangramento retal há dois meses. "
        "Solicito retossigmoidoscopia para investigação.\n"
    )
    occurrence = _occurrence(occurrences=_occurrences(text), procedure_type="rectosigmoidoscopy")
    assert occurrence.qualification == "current_request"
    assert occurrence.section == JUSTIFICATIVA_SECTION

    result = _reconcile(declared=("colonoscopy",), cleaned_text=text)

    assert result.action == "nir_review"
    assert result.reason_code == "exam_type_mismatch"
    assert result.detected_procedure_types == ("rectosigmoidoscopy",)
    assert result.reason_text == f"{MISMATCH_REASON_TEXT} {ORIGIN_JUSTIFICATIVA}."


def test_reason_text_is_unchanged_without_identified_section() -> None:
    """Sem seção elegível o motivo permanece o texto atual, byte a byte (R1)."""
    text = "Solicito retossigmoidoscopia para investigação."
    occurrence = _occurrence(occurrences=_occurrences(text), procedure_type="rectosigmoidoscopy")
    assert occurrence.qualification == "current_request"
    assert occurrence.section == ""

    result = _reconcile(declared=("colonoscopy",), cleaned_text=text)

    assert result.action == "nir_review"
    assert result.reason_code == "exam_type_mismatch"
    assert result.reason_text == MISMATCH_REASON_TEXT


def test_proceed_reason_text_has_no_origin_suffix() -> None:
    """``proceed`` não ganha sufixo de origem (R1)."""
    text = "Justificativa da Transferência: Solicito retossigmoidoscopia para investigação."

    result = _reconcile(declared=("rectosigmoidoscopy",), cleaned_text=text)

    assert result.action == "proceed"
    assert result.reason_text == ""


def test_auto_upgrade_reason_text_has_no_origin_suffix() -> None:
    """``auto_upgrade`` não ganha sufixo de origem (R1)."""
    occurrence = _occurrence_at(
        "eda",
        "current_request",
        excerpt="eda",
        start=0,
        section=JUSTIFICATIVA_SECTION,
    )

    result = reconcile_detected_procedures(
        declared=("eda",),
        strong=("eda", "colonoscopy"),
        any_evidence=("eda", "colonoscopy"),
        occurrences=(occurrence,),
    )

    assert result.action == "auto_upgrade"
    assert result.reason_text == (
        "Solicitações atuais de EDA e Colonoscopia com evidência forte; upgrade automático auditado."
    )


def test_mismatch_reason_text_reports_motivo_origin() -> None:
    """Ocorrência atual do detectado no Motivo vira origem no motivo (R1)."""
    text = "Motivo da Solicitação: Retossigmoidoscopia para investigação.\nUnid. Origem: Hospital Central\n"
    occurrence = _occurrence(occurrences=_occurrences(text), procedure_type="rectosigmoidoscopy")
    assert occurrence.qualification == "current_request"
    assert occurrence.section == MOTIVO_SECTION

    result = _reconcile(declared=("colonoscopy",), cleaned_text=text)

    assert result.action == "nir_review"
    assert result.reason_code == "exam_type_mismatch"
    assert result.reason_text == f"{MISMATCH_REASON_TEXT} {ORIGIN_MOTIVO}."


def test_origin_labels_are_deduplicated_in_canonical_order() -> None:
    """Várias ocorrências por seção viram um rótulo; Justificativa antes do Motivo (R1)."""
    text = (
        "Motivo da Solicitação: Retossigmoidoscopia para investigação.\n"
        "Unid. Origem: Hospital Central\n"
        "Justificativa da Transferência: Paciente com sangramento retal. "
        "Solicito retossigmoidoscopia para investigação. Retossigmoidoscopia com sedação.\n"
    )
    sections = [
        occurrence.section
        for occurrence in _occurrences(text)
        if occurrence.procedure_type == "rectosigmoidoscopy" and occurrence.qualification == "current_request"
    ]
    assert sections == [MOTIVO_SECTION, JUSTIFICATIVA_SECTION, JUSTIFICATIVA_SECTION]

    result = _reconcile(declared=("colonoscopy",), cleaned_text=text)

    assert result.action == "nir_review"
    assert result.reason_text == (
        f"{MISMATCH_REASON_TEXT} Origem da detecção: Justificativa da Transferência, Motivo da Solicitação."
    )


def test_reason_text_ignores_unknown_section() -> None:
    """Seção sem rótulo estável é ignorada e não vira origem (R1)."""
    occurrence = _occurrence_at(
        "rectosigmoidoscopy",
        "current_request",
        excerpt="retossigmoidoscopia",
        start=0,
        section="complemento_da_solicitacao",
    )

    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=(),
        any_evidence=("rectosigmoidoscopy",),
        occurrences=(occurrence,),
    )

    assert result.action == "nir_review"
    assert result.reason_code == "exam_type_mismatch"
    assert result.reason_text == MISMATCH_REASON_TEXT


def test_conflicting_reason_text_ignores_non_current_and_undetected_occurrences() -> None:
    """Menção com seção e tipo fora do detectado não viram origem no conflito (R4-vi)."""
    mention = _occurrence_at(
        "rectosigmoidoscopy_dilation",
        "mention",
        excerpt="dilatacao",
        start=0,
        section=JUSTIFICATIVA_SECTION,
    )
    undetected = _occurrence_at(
        "eda_dilation",
        "current_request",
        excerpt="dilatacao esofagica",
        start=0,
        section=JUSTIFICATIVA_SECTION,
    )

    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=("colonoscopy",),
        any_evidence=("colonoscopy",),
        occurrences=(mention, undetected),
        conflicting=("rectosigmoidoscopy_dilation",),
    )

    assert result.action == "nir_review"
    assert result.reason_code == "conflicting_procedure_evidence"
    assert result.reason_text == CONFLICTING_REASON_TEXT


def test_conflicting_reason_text_reports_current_origin_of_detected_set() -> None:
    """Ocorrência ATUAL de tipo do conjunto detectado vira origem no conflito (R4-vi)."""
    current = _occurrence_at(
        "rectosigmoidoscopy_dilation",
        "current_request",
        excerpt="dilatacao",
        start=0,
        section=JUSTIFICATIVA_SECTION,
    )

    result = reconcile_detected_procedures(
        declared=("colonoscopy",),
        strong=("colonoscopy",),
        any_evidence=("colonoscopy", "rectosigmoidoscopy_dilation"),
        occurrences=(current,),
        conflicting=("rectosigmoidoscopy_dilation",),
    )

    assert result.action == "nir_review"
    assert result.reason_code == "conflicting_procedure_evidence"
    assert result.reason_text == f"{CONFLICTING_REASON_TEXT} {ORIGIN_JUSTIFICATIVA}."
