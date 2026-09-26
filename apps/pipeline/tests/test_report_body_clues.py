"""Slice 001 — `Justificativa da Transferência` como contexto de solicitação.

Prova R1–R5b do slice: spans da seção no texto normalizado (R1), coleta de
ocorrências com offsets absolutos por cláusula em vez de ``str.find`` (R1b),
promoção de menção dentro da seção para solicitação atual (R2), não-promoção de
histórico/negação e de ocorrências fora da seção (R3), rótulo de proveniência
``section`` (R4) e direção de falha da reconciliação (R5b).
"""

from __future__ import annotations

import pytest

from apps.pipeline.procedure_reconciliation import ProcedureReconciliationResult, reconcile_detected_procedures
from apps.pipeline.scope_detection import (
    ProcedureOccurrence,
    _justificativa_section_spans,
    _labelled_section_spans,
    _normalize_scope_keyword_text,
    detect_procedure_occurrences,
    detect_requested_procedures_v4,
)

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
    assert detection["rectosigmoidoscopy"] == {"strong": True, "any": True}


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
    assert detection["rectosigmoidoscopy"] == {"strong": False, "any": False}
    assert detection["colonoscopy"] == {"strong": False, "any": False}


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
    result = _reconcile(declared=("colonoscopy",), cleaned_text=REGULATION_REPORT_TEXT)
    assert result.action == "nir_review"
    assert result.reason_code == "unsupported_procedure_combination"
    assert "colonoscopy" in result.detected_procedure_types
    assert "rectosigmoidoscopy" in result.detected_procedure_types


def test_justificativa_naming_the_declared_family_is_detected_as_current_request() -> None:
    text = "Justificativa da Transferência: Retossigmoidoscopia para investigação de sangramento."
    occurrence = _occurrence(occurrences=_occurrences(text), procedure_type="rectosigmoidoscopy")
    assert occurrence.qualification == "current_request"
    assert occurrence.section == JUSTIFICATIVA_SECTION
    detection = detect_requested_procedures_v4(llm1_structured_data={}, cleaned_text=text)
    assert detection["rectosigmoidoscopy"] == {"strong": True, "any": True}
