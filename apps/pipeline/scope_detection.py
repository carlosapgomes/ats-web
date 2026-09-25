"""Deterministic scope detection: classify exam as EDA vs colonoscopy vs mixed/unknown.

Ported faithfully from the legacy augmented-triage-system:
  triage_automation/application/services/process_pdf_case_service.py

Slice 003 rework (R3): colonoscopy is a supported type when declared and
confirmed. Approved aliases are recognized; EDB only with boundary and local
request/exam/procedure context; history/negation of the other exam never
creates mixed; two CURRENT requests EDA+colonoscopy → manual review with
``mixed_exam_request``; declared/detected mismatch and unknown also return to
NIR with a generic payload carrying ``declared_exam_type``,
``detected_exam_type`` and ``reason_code``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from apps.cases.exam_profiles import COLONOSCOPY_PROFILE, CPRE_PROFILE

_SUPPORTED_EDA_SUBTYPES: frozenset[str] = frozenset(
    {"standard", "gastrostomy", "esophageal_dilation", "foreign_body", "echoendoscopy"}
)

_SCOPE_GASTROSTOMY_TERMS: tuple[str, ...] = (
    "gtt",
    "gastrostomia",
    "gastrostomy",
    "confeccao de gtt",
    "programar gtt",
)

_SCOPE_ESOPHAGEAL_DILATION_TERMS: tuple[str, ...] = (
    "dilatacao esofagica",
    "dilatacao de esofago",
    "dilatacao do esofago",
)

_SCOPE_ECHOENDOSCOPY_TERMS: tuple[str, ...] = (
    "ecoendoscopia",
    "eco endoscopia",
    "eco-endoscopia",
    "ultrassonografia endoscopica",
    "ultrassom endoscopico",
)

_SCOPE_FOREIGN_BODY_TERMS: tuple[str, ...] = (
    "corpo estranho",
    "retirada de corpo estranho",
)

_SCOPE_EXPLICIT_EDA_TERMS: tuple[str, ...] = (
    "endoscopia digestiva alta",
    "solicitacao de endoscopia digestiva alta",
    "endoscopia digestiva alta - eda",
    "videoendoscopia digestiva alta",
    "endoscopia digestiva superior",
)

# Approved colonoscopy aliases come from the exam profile (R1/R3). EDB is
# handled separately with boundary + local request/exam/procedure context.
_SCOPE_EXPLICIT_COLONOSCOPY_TERMS: tuple[str, ...] = tuple(COLONOSCOPY_PROFILE.scope_aliases)


def _normalize_scope_keyword_text(*, value: str) -> str:
    """Strip diacritics, lowercase, and collapse whitespace for keyword matching."""

    normalized = unicodedata.normalize("NFD", value)
    without_diacritics = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    collapsed_whitespace = " ".join(without_diacritics.lower().split())
    return collapsed_whitespace


def _contains_scope_term(*, normalized_text: str, term: str) -> bool:
    """Multi-word term: exact substring match. Single-word term: word-boundary match."""

    if " " in term:
        return term in normalized_text
    return re.search(rf"\b{re.escape(term)}\b", normalized_text) is not None


def _extract_preop_evidence_spans(
    *,
    llm1_structured_data: dict[str, object],
) -> list[dict[str, str]]:
    """Extract validated evidence spans from preop_screening payload."""

    preop_screening = llm1_structured_data.get("preop_screening")
    if not isinstance(preop_screening, dict):
        return []

    evidence_spans_raw = preop_screening.get("evidence_spans")
    if not isinstance(evidence_spans_raw, list):
        return []

    evidence_spans: list[dict[str, str]] = []
    for item in evidence_spans_raw:
        if not isinstance(item, dict):
            continue
        field_path = item.get("field_path")
        excerpt = item.get("excerpt")
        if not isinstance(field_path, str) or not isinstance(excerpt, str):
            continue
        normalized_field_path = field_path.strip()
        normalized_excerpt = excerpt.strip()
        if not normalized_field_path or not normalized_excerpt:
            continue
        evidence_spans.append({"field_path": normalized_field_path, "excerpt": normalized_excerpt})
    return evidence_spans


def _extract_preop_exam_type(
    *,
    llm1_structured_data: dict[str, object],
) -> str | None:
    """Extract exam_type from LLM1 preop_screening if valid.

    Slice 003: ``colonoscopy`` is now a valid LLM1 classification.
    """

    preop_screening = llm1_structured_data.get("preop_screening")
    if not isinstance(preop_screening, dict):
        return None
    exam_type = preop_screening.get("exam_type")
    if isinstance(exam_type, str):
        normalized = exam_type.strip().lower()
        if normalized in {"eda", "colonoscopy", "non_eda", "unknown"}:
            return normalized
    return None


def _extract_supported_eda_subtype_from_llm1(
    *,
    llm1_structured_data: dict[str, object],
) -> str | None:
    """Try to extract a supported EDA subtype from LLM1 structured data."""

    eda_payload = llm1_structured_data.get("eda")
    if isinstance(eda_payload, dict):
        requested_procedure = eda_payload.get("requested_procedure")
        if isinstance(requested_procedure, dict):
            subtype = requested_procedure.get("subtype")
            if isinstance(subtype, str):
                normalized = subtype.strip().lower()
                if normalized in _SUPPORTED_EDA_SUBTYPES:
                    return normalized

    preop_screening = llm1_structured_data.get("preop_screening")
    if not isinstance(preop_screening, dict):
        return None
    rulebook_signals = preop_screening.get("rulebook_signals")
    if not isinstance(rulebook_signals, dict):
        return None
    subtype = rulebook_signals.get("eda_subtype")
    if not isinstance(subtype, str):
        return None
    normalized = subtype.strip().lower()
    if normalized in _SUPPORTED_EDA_SUBTYPES:
        return normalized
    return None


def _extract_scope_keyword_candidate_texts(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> list[str]:
    """Collect all candidate texts where scope keywords may appear."""

    candidate_texts: list[str] = [cleaned_text]

    eda_payload = llm1_structured_data.get("eda")
    if isinstance(eda_payload, dict):
        requested_procedure = eda_payload.get("requested_procedure")
        if isinstance(requested_procedure, dict):
            requested_name = requested_procedure.get("name")
            if isinstance(requested_name, str) and requested_name.strip():
                candidate_texts.append(requested_name)

    summary_payload = llm1_structured_data.get("summary")
    if isinstance(summary_payload, dict):
        one_liner = summary_payload.get("one_liner")
        if isinstance(one_liner, str) and one_liner.strip():
            candidate_texts.append(one_liner)
        bullet_points = summary_payload.get("bullet_points")
        if isinstance(bullet_points, list):
            candidate_texts.extend(point for point in bullet_points if isinstance(point, str) and point.strip())

    for span in _extract_preop_evidence_spans(llm1_structured_data=llm1_structured_data):
        excerpt = span.get("excerpt")
        if isinstance(excerpt, str) and excerpt.strip():
            candidate_texts.append(excerpt)

    return candidate_texts


def _contains_boundary_safe_eus(*, normalized_text: str) -> bool:
    """Return True when the EUS acronym appears as a standalone word."""

    return re.search(r"\beus\b", normalized_text) is not None


# Sentence/clause boundaries that bound the local context of an occurrence.
# ':' is intentionally NOT a boundary so an immediate label such as
# 'Procedimento: EDB' stays in the local context of the occurrence.
_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.;!?]|\n")


def _clause_context(normalized_text: str, start: int, end: int) -> tuple[str, str]:
    """Return (prefix, suffix) local clause context for an occurrence span."""
    left_boundaries = list(_CLAUSE_BOUNDARY_PATTERN.finditer(normalized_text, 0, start))
    clause_start = left_boundaries[-1].end() if left_boundaries else 0
    right_boundary = _CLAUSE_BOUNDARY_PATTERN.search(normalized_text, end)
    clause_end = right_boundary.start() if right_boundary else len(normalized_text)
    return normalized_text[clause_start:start], normalized_text[end:clause_end]


# ── Shared per-occurrence machinery (current-request detection) ─────────────
#
# Every qualifier below is ANCHORED to the occurrence: before-patterns end at
# the end of the prefix ('$'), after-patterns start at the beginning of the
# suffix ('^'). Context is never borrowed from another procedure in the same
# clause, and word boundaries protect against partial matches.
#
# The request-before pattern accepts a closed list chain of exam terms so that
# 'Solicito EDA e colonoscopia' marks both occurrences as current while
# 'Solicitacao previa de EUS foi cancelada' stays historical.

_REQUEST_LIST_TERM_SOURCE = (
    r"colonoscopia\s+diagnostica|colonoscopia\s+terapeutica|colonoscopia"
    r"|endoscopia\s+digestiva\s+baixa|videocolonoendoscopia"
    r"|endoscopia\s+digestiva\s+alta|videoendoscopia\s+digestiva\s+alta|endoscopia\s+digestiva\s+superior"
    r"|ecoendoscopia|eco\s+endoscopia|eco-endoscopia|ultrassonografia\s+endoscopica|ultrassom\s+endoscopico"
    r"|gastrostomia|gastrostomy|gtt|peg"
    r"|dilatacao\s+esofagica|dilatacao\s+do\s+esofago|dilatacao\s+de\s+esofago|dilatacao\s+endoscopica\s+esofagica"
    r"|corpo\s+estranho|eda"
)

_REQUEST_LIST_PREFIX_SOURCE = r"(?:\s+(?:" + _REQUEST_LIST_TERM_SOURCE + r")\b(?:\s+(?:e\b|,))?)*"

_REQUEST_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:solicit|encaminh|indic|programar|confeccao|regulac)\w*\b"
    r"(?:\s*:?\s*(?:realizacao\s+de|regulacao\s+para|regulacao\s+de|nov[oa]|atual\s+de|de|para)?)"
    + _REQUEST_LIST_PREFIX_SOURCE
    + r"\s*$"
)

_LABEL_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:exame|procedimento)\b\s*(?:de|para|:)?\s*$"
    r"|\bmotivo\s+da\s+solicitacao\b\s*:?\s*$"
    r"|\bmotivo\b\s*:?\s*$"
)

_REQUEST_AFTER_OCCURRENCE_PATTERN = re.compile(r"^\s*(?:solicit|indic|encaminh|regulac)\w*\b")

_HISTORICAL_AFTER_OCCURRENCE_PATTERN = re.compile(
    r"^\s*(?:ja\s+)?(?:foi\s+)?realizad[oa]\b"
    r"|^\s*(?:previo|previa|anterior|previamente)\b"
    r"|^\s*no\s+historico\b"
)
# Histórico e request percorrem a MESMA cadeia fechada de procedimentos
# (_REQUEST_LIST_PREFIX_SOURCE), ancorada à ocorrência: 'histórico de
# solicitação/indicação de' e 'histórico de encaminhamento para' envolvem a
# cadeia, então um verbo de solicitação interno não vira pedido atual (F2/C22).
_HISTORICAL_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:realizou)\b\s+$"
    r"|\b(?:previo|previa|anterior|previamente)\b\s*(?:de\s*)?:?\s*$"
    r"|\bhistorico\s+de\b\s*$"
    r"|\bhistorico\s+de\b\s+(?:solicitacao|indicacao)\s+de\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
    r"|\bhistorico\s+de\b\s+encaminhamento\s+para\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
)

# Negação e request percorrem a MESMA cadeia fechada de procedimentos,
# ancorada à ocorrência (F3/C21): 'sem/nega/nao ha/ausencia de indicacao de'
# e 'nao solicito' envolvem a cadeia, então itens negados/ausentes listados
# antes da ocorrência não ressuscitam um request interno.
_NEGATION_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\bsem\s+indicacao\s+de\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
    r"|\bsem\s+evidencia\s+de\b\s*$"
    r"|\bsem\b\s*$"
    r"|\bnega\s+(?:a\s+)?indicacao\s+de\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
    r"|\bnega\s+(?:a\s+)?ingestao\s+de\b\s*$"
    r"|\bnega\b\s*$"
    r"|\bnao\s+ha\s+indicacao\s+de\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
    r"|\bnao\s+ha\s+evidencia\s+de\b\s*$"
    r"|\bnao\s+solicit\w*\b(?:\s*:?\s*(?:realizacao\s+de|nov[oa]|atual\s+de|de|para)?)"
    + _REQUEST_LIST_PREFIX_SOURCE
    + r"\s*:?\s*$"
    r"|\bnao\s+foi\s+identificad[oa]\b\s*$"
    r"|\bnao\s+ha\b\s*$"
    r"|\bausencia\s+de\s+indicacao\s+de\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
    r"|\bausencia\s+de\b\s*$"
)
_NEGATION_AFTER_OCCURRENCE_PATTERN = re.compile(
    r"^\s*(?:descartad[oa]|negad[oa]|ausente|contraindicad[oa])\b"
    r"|^\s*nao\s+(?:foi\s+)?(?:indicad[oa]|recomendad[oa]|solicitad[oa]|identificad[oa])\b"
    r"|^\s*sem\s+indicac\w*\b"
)


def _occurrence_is_current_request(*, normalized_text: str, pattern: re.Pattern[str]) -> bool:
    """True when at least one term occurrence is a current positive request.

    A historical/negated qualifier cancels only its own occurrence; a distinct
    current occurrence in the same or another clause survives (R3).
    """
    for match in pattern.finditer(normalized_text):
        prefix, suffix = _clause_context(normalized_text, match.start(), match.end())
        if _HISTORICAL_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _HISTORICAL_AFTER_OCCURRENCE_PATTERN.match(suffix):
            continue
        if _NEGATION_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _NEGATION_AFTER_OCCURRENCE_PATTERN.match(suffix):
            continue
        if (
            _REQUEST_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
            or _LABEL_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
            or _REQUEST_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
        ):
            return True
    return False


def _occurrence_has_unqualified_match(*, normalized_text: str, pattern: re.Pattern[str]) -> bool:
    """True when at least one occurrence is NOT historically/negatively qualified.

    Used for EDA full names in the fallback path: a plain mention is EDA
    evidence unless explicitly historical or negated (legacy behaviour).
    """
    for match in pattern.finditer(normalized_text):
        prefix, suffix = _clause_context(normalized_text, match.start(), match.end())
        if _HISTORICAL_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _HISTORICAL_AFTER_OCCURRENCE_PATTERN.match(suffix):
            continue
        if _NEGATION_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _NEGATION_AFTER_OCCURRENCE_PATTERN.match(suffix):
            continue
        return True
    return False


# ── EUS (Slice 001) — preserved exactly ──────────────────────────────────────


_EUS_REQUEST_BEFORE_PATTERN = re.compile(r"\b(solicit|encaminh|indic)\w*\b\s*(?:realizacao\s+de|de|para|:)?\s*$")
_EUS_EXAM_BEFORE_PATTERN = re.compile(r"\b(exame|procedimento)\b\s*(?:de|para|:)?\s*$")
_EUS_REQUEST_AFTER_PATTERN = re.compile(r"^\s*(?:solicit|indic|encaminh)\w*\b")
_EUS_HISTORICAL_AFTER_PATTERN = re.compile(r"^\s*(realizad[oa]|previo|previa|anterior)\b")
_EUS_HISTORICAL_BEFORE_PATTERN = re.compile(r"\b(?:realizou)\b\s+$|\b(?:previo|previa|anterior)\b\s+(?:de\s+)?$")


def _extract_eus_local_clause_bounds(
    *,
    normalized_text: str,
    eus_start: int,
    eus_end: int,
) -> tuple[int, int]:
    """Return (clause_start, clause_end) bounding the EUS occurrence."""

    left_boundaries = list(_CLAUSE_BOUNDARY_PATTERN.finditer(normalized_text, 0, eus_start))
    clause_start = left_boundaries[-1].end() if left_boundaries else 0
    right_boundary = _CLAUSE_BOUNDARY_PATTERN.search(normalized_text, eus_end)
    clause_end = right_boundary.start() if right_boundary else len(normalized_text)
    return clause_start, clause_end


def _is_historical_eus_occurrence(*, prefix: str, suffix: str) -> bool:
    return (
        _EUS_HISTORICAL_AFTER_PATTERN.match(suffix) is not None
        or _EUS_HISTORICAL_BEFORE_PATTERN.search(prefix) is not None
    )


def _is_explicit_eus_request_occurrence(*, prefix: str, suffix: str) -> bool:
    return (
        _EUS_REQUEST_BEFORE_PATTERN.search(prefix) is not None
        or _EUS_EXAM_BEFORE_PATTERN.search(prefix) is not None
        or _EUS_REQUEST_AFTER_PATTERN.match(suffix) is not None
    )


def _contains_eus_with_local_request_context(*, normalized_text: str) -> bool:
    """Return True when at least one EUS occurrence is an explicit request."""

    if not _contains_boundary_safe_eus(normalized_text=normalized_text):
        return False
    for eus_match in re.finditer(r"\beus\b", normalized_text):
        clause_start, clause_end = _extract_eus_local_clause_bounds(
            normalized_text=normalized_text,
            eus_start=eus_match.start(),
            eus_end=eus_match.end(),
        )
        prefix = normalized_text[clause_start : eus_match.start()]
        suffix = normalized_text[eus_match.end() : clause_end]
        if _is_historical_eus_occurrence(prefix=prefix, suffix=suffix):
            continue
        if _is_explicit_eus_request_occurrence(prefix=prefix, suffix=suffix):
            return True
    return False


def _detect_supported_eda_scope_keyword_in_text(
    *,
    normalized_text: str,
) -> tuple[str | None, str | None]:
    """Search one normalized text for supported EDA subtype keywords.

    Returns (subtype, matched_term) or (None, None). EUS is only accepted
    with local request-oriented context; full names need no extra context.
    """

    for term in _SCOPE_FOREIGN_BODY_TERMS:
        if _contains_scope_term(normalized_text=normalized_text, term=term):
            return "foreign_body", term
    for term in _SCOPE_GASTROSTOMY_TERMS:
        if _contains_scope_term(normalized_text=normalized_text, term=term):
            return "gastrostomy", term
    for term in _SCOPE_ESOPHAGEAL_DILATION_TERMS:
        if _contains_scope_term(normalized_text=normalized_text, term=term):
            return "esophageal_dilation", term
    for term in _SCOPE_ECHOENDOSCOPY_TERMS:
        if _contains_scope_term(normalized_text=normalized_text, term=term):
            return "echoendoscopy", term
    if _contains_eus_with_local_request_context(normalized_text=normalized_text):
        return "echoendoscopy", "EUS"
    return None, None


def _detect_supported_eda_scope_keyword(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> tuple[str | None, str | None]:
    """Search candidate texts for supported EDA subtype keywords.

    Returns (subtype, matched_term) or (None, None).
    """

    candidate_texts = _extract_scope_keyword_candidate_texts(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )

    for candidate in candidate_texts:
        normalized_candidate = _normalize_scope_keyword_text(value=candidate)
        subtype, matched_term = _detect_supported_eda_scope_keyword_in_text(
            normalized_text=normalized_candidate,
        )
        if subtype is not None:
            return subtype, matched_term

    return None, None


def _extract_motivo_solicitacao_text(*, cleaned_text: str) -> str | None:
    """Extract the top-level 'Motivo da Solicitação' value when present."""

    pattern = re.compile(
        r"motivo\s+da\s+solicitacao\s*:\s*(?P<motive>.+?)(?:\s+unid\.|\s+complemento\s+da\s+solicitacao\s*:)",
        re.IGNORECASE | re.DOTALL,
    )
    normalized_text = _normalize_scope_keyword_text(value=cleaned_text)
    match = pattern.search(normalized_text)
    if match is None:
        return None
    motive = match.group("motive").strip()
    return motive or None


def _motive_mentions_supported_eda(*, normalized_motive: str) -> bool:
    """Return True when the motive text asks for supported EDA/echoendoscopy.

    The extracted 'Motivo da Solicitação' value is current-request evidence
    by provenance, so a bare boundary-safe EUS counts as echoendoscopy here.
    """

    for term in _SCOPE_EXPLICIT_EDA_TERMS:
        if _contains_scope_term(normalized_text=normalized_motive, term=term):
            return True
    if _contains_eda_acronym(normalized_text=normalized_motive):
        return True
    if _contains_boundary_safe_eus(normalized_text=normalized_motive):
        return True
    subtype, _ = _detect_supported_eda_scope_keyword_in_text(normalized_text=normalized_motive)
    return subtype is not None


def _motive_mentions_colonoscopy(*, normalized_motive: str) -> bool:
    """Return True when the motive text asks for colonoscopy (approved aliases)."""

    for term in _SCOPE_EXPLICIT_COLONOSCOPY_TERMS:
        if _contains_scope_term(normalized_text=normalized_motive, term=term):
            return True
    if _occurrence_is_current_request(
        normalized_text=normalized_motive,
        pattern=_COLONOSCOPY_ACRONYM_PATTERN,
    ):
        return True
    return False


# ── Term patterns ────────────────────────────────────────────────────────────


_EDA_FULL_NAME_PATTERN = re.compile(
    r"\bendoscopia\s+digestiva\s+alta\b"
    r"|\bvideoendoscopia\s+digestiva\s+alta\b"
    r"|\bendoscopia\s+digestiva\s+superior\b"
)

_EDA_ACRONYM_PATTERN = re.compile(r"\beda\b|\be\s*[.\-]?\s*d\s*[.\-]?\s*a\b")

# Ocorrência EDA para precedência especializada: nome completo + sigla. Os
# termos de subtipo/alias de Ecoendoscopia pertencem a outro padrão e NÃO podem
# contar como ocorrência EDA (senão ``ecoendoscopia`` viraria EDA também).
_EDA_PROCEDURE_OCCURRENCE_PATTERN = re.compile(
    r"\bendoscopia\s+digestiva\s+alta\b"
    r"|\bvideoendoscopia\s+digestiva\s+alta\b"
    r"|\bendoscopia\s+digestiva\s+superior\b"
    r"|\beda\b|\be\s*[.\-]?\s*d\s*[.\-]?\s*a\b"
)

_EDA_TERM_PATTERN = re.compile(
    r"\bendoscopia\s+digestiva\s+alta\b"
    r"|\bvideoendoscopia\s+digestiva\s+alta\b"
    r"|\bendoscopia\s+digestiva\s+superior\b"
    r"|\beda\b|\be\s*[.\-]?\s*d\s*[.\-]?\s*a\b"
    r"|\becoendoscopia\b|\beco\s+endoscopia\b|\beco-endoscopia\b"
    r"|\bultrassonografia\s+endoscopica\b|\bultrassom\s+endoscopico\b"
    r"|\b(?:gtt|gastrostomia|gastrostomy|peg)\b"
    r"|\bdilatacao\s+esofagica\b|\bdilatacao\s+do\s+esofago\b|\bdilatacao\s+de\s+esofago\b"
    r"|\bdilatacao\s+endoscopica\s+esofagica\b"
    r"|\bcorpo\s+estranho\b"
)

_COLONOSCOPY_TERM_PATTERN = re.compile(
    r"\bcolonoscopia\s+diagnostica\b|\bcolonoscopia\s+terapeutica\b|\bcolonoscopia\b"
    r"|\bendoscopia\s+digestiva\s+baixa\b|\bvideocolonoendoscopia\b"
)

# EDB is only accepted with boundary + local request/exam/procedure context
# (R3). The shared per-occurrence machinery enforces exactly that.
_COLONOSCOPY_ACRONYM_PATTERN = re.compile(r"\bedb\b")


def _contains_eda_acronym(*, normalized_text: str) -> bool:
    """Return True when the EDA acronym (plain, dotted or hyphenated) is present."""

    return (
        re.search(r"\beda\b", normalized_text) is not None
        or re.search(r"\be\s*[.\-]?\s*d\s*[.\-]?\s*a\b", normalized_text) is not None
    )


# ── Current-request signals (R3) ─────────────────────────────────────────────


def _detect_current_request_eda_signal(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> bool:
    """Return True when the current request explicitly asks for EDA/echoendoscopy.

    Only the 'Motivo da Solicitação' field and structured procedure fields
    count as current-request evidence for EDA (legacy behaviour preserved).
    Mentions elsewhere in the clinical body (e.g. historical EDA) must not
    override a non-EDA classification.
    """

    motive_text = _extract_motivo_solicitacao_text(cleaned_text=cleaned_text)
    if motive_text is not None:
        normalized_motive = _normalize_scope_keyword_text(value=motive_text)
        if _motive_mentions_supported_eda(normalized_motive=normalized_motive):
            return True

    subtype = _extract_supported_eda_subtype_from_llm1(
        llm1_structured_data=llm1_structured_data,
    )
    if subtype is not None and subtype != "standard":
        return True

    eda_payload = llm1_structured_data.get("eda")
    if not isinstance(eda_payload, dict):
        return False
    requested_procedure = eda_payload.get("requested_procedure")
    if not isinstance(requested_procedure, dict):
        return False
    requested_name = requested_procedure.get("name")
    if not isinstance(requested_name, str) or not requested_name.strip():
        return False
    normalized_name = _normalize_scope_keyword_text(value=requested_name)
    if _contains_boundary_safe_eus(normalized_text=normalized_name):
        return True
    subtype_from_name, _ = _detect_supported_eda_scope_keyword_in_text(
        normalized_text=normalized_name,
    )
    return subtype_from_name is not None


def _detect_current_request_colonoscopy_signal(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> bool:
    """Return True when the current request explicitly asks for colonoscopy.

    Mirrors the EDA strong-signal provenance: 'Motivo da Solicitação' field
    and the structured procedure name carry current-request evidence.
    """

    motive_text = _extract_motivo_solicitacao_text(cleaned_text=cleaned_text)
    if motive_text is not None:
        normalized_motive = _normalize_scope_keyword_text(value=motive_text)
        if _motive_mentions_colonoscopy(normalized_motive=normalized_motive):
            return True

    eda_payload = llm1_structured_data.get("eda")
    if not isinstance(eda_payload, dict):
        return False
    requested_procedure = eda_payload.get("requested_procedure")
    if not isinstance(requested_procedure, dict):
        return False
    requested_name = requested_procedure.get("name")
    if not isinstance(requested_name, str) or not requested_name.strip():
        return False
    normalized_name = _normalize_scope_keyword_text(value=requested_name)
    # O campo estruturado de procedimento tem prioridade por proveniência (D7):
    # um alias aprovado no nome basta, sem exigir verbo de solicitação.
    for term in _SCOPE_EXPLICIT_COLONOSCOPY_TERMS:
        if _contains_scope_term(normalized_text=normalized_name, term=term):
            return True
    return _occurrence_is_current_request(
        normalized_text=normalized_name,
        pattern=_COLONOSCOPY_ACRONYM_PATTERN,
    )


def _detect_current_request_signals(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
    llm1_exam_type: str | None,
) -> tuple[bool, bool, bool]:
    """Return (has_eda_strong, has_eda_any, has_colon_any) per design D7.

    ``has_eda_any``/``has_colon_any`` são evidências de solicitação ATUAL
    incondicionais (strong OU textual): duas solicitações atuais devem produzir
    mixed independentemente da classificação LLM1 (F1). ``has_eda_strong`` é o
    subconjunto com proveniência (motivo/subtipo/nome estruturado) que mantém a
    regra de autoridade legada do LLM1 ``non_eda`` na resolução de UM ÚNICO
    tipo detectado, nunca na decisão de mixed.
    """

    has_eda_strong = _detect_current_request_eda_signal(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    has_colon_strong = _detect_current_request_colonoscopy_signal(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )

    normalized_text = _normalize_scope_keyword_text(value=cleaned_text)
    has_eda_textual = _occurrence_is_current_request(
        normalized_text=normalized_text,
        pattern=_EDA_TERM_PATTERN,
    ) or _contains_eus_with_local_request_context(normalized_text=normalized_text)
    has_colon_textual = _occurrence_is_current_request(
        normalized_text=normalized_text,
        pattern=_COLONOSCOPY_TERM_PATTERN,
    ) or _occurrence_is_current_request(
        normalized_text=normalized_text,
        pattern=_COLONOSCOPY_ACRONYM_PATTERN,
    )

    return has_eda_strong, has_eda_strong or has_eda_textual, has_colon_strong or has_colon_textual


# ── Fallback detection (legacy EDA rescue) ──────────────────────────────────


def _has_eda_anywhere_evidence(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> bool:
    """Return True when EDA evidence exists anywhere in candidate texts.

    Full names count anywhere unless historically/negatively qualified; the
    acronym requires per-occurrence request/label context (like EUS).
    """
    for candidate in _extract_scope_keyword_candidate_texts(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    ):
        normalized_candidate = _normalize_scope_keyword_text(value=candidate)
        if _occurrence_has_unqualified_match(
            normalized_text=normalized_candidate,
            pattern=_EDA_FULL_NAME_PATTERN,
        ):
            return True
        if _occurrence_is_current_request(
            normalized_text=normalized_candidate,
            pattern=_EDA_ACRONYM_PATTERN,
        ):
            return True
    return False


def _detect_fallback_type(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
    llm1_exam_type: str | None,
) -> str | None:
    """Determine the detected type when no current-request signal fired.

    Returns one of "eda", "colonoscopy", "non_eda", "unknown" or None
    (None = pass-through when preop_screening is entirely absent, legacy).
    """
    if llm1_exam_type in {"eda", "colonoscopy"}:
        return llm1_exam_type

    supported_subtype = _extract_supported_eda_subtype_from_llm1(
        llm1_structured_data=llm1_structured_data,
    )
    if supported_subtype is not None:
        return "eda"

    subtype, _ = _detect_supported_eda_scope_keyword(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    if subtype is not None:
        return "eda"

    if _has_eda_anywhere_evidence(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    ):
        return "eda"

    if llm1_exam_type == "non_eda":
        return "non_eda"
    if llm1_exam_type == "unknown":
        return "unknown"
    return None


# ── Manual review payload ────────────────────────────────────────────────────


# ── Manual review payload projection (D7/R8, F4) ─────────────────────────────
#
# O payload de scope é dado de auditoria, não armazenamento de texto clínico:
# os evidence_spans são projetados com limites explícitos de quantidade e
# comprimento para que um excerpt longo nunca chegue integral a
# suggested_action ou ao evento EDA_SCOPE_GATED_MANUAL_REVIEW.
MAX_MANUAL_REVIEW_SPANS = 5
MAX_MANUAL_REVIEW_FIELD_PATH_LENGTH = 120
MAX_MANUAL_REVIEW_EXCERPT_LENGTH = 200


def _project_manual_review_evidence_spans(evidence_spans: list[dict[str, str]]) -> list[dict[str, str]]:
    """Projeta spans validados para o payload de manual review (F4).

    Itens inválidos já são descartados a montante; aqui limitamos a quantidade
    e truncamos field_path/excerpt de forma determinística. Spans curtos
    passam intactos (contrato legado preservado).
    """
    projected: list[dict[str, str]] = []
    for span in evidence_spans[:MAX_MANUAL_REVIEW_SPANS]:
        projected.append(
            {
                "field_path": span["field_path"][:MAX_MANUAL_REVIEW_FIELD_PATH_LENGTH],
                "excerpt": span["excerpt"][:MAX_MANUAL_REVIEW_EXCERPT_LENGTH],
            }
        )
    return projected


def _build_manual_review_payload(
    *,
    case_id: str,
    agency_record_number: str,
    reason_code: str,
    reason_text: str,
    detected: str,
    declared: str,
    evidence_spans: list[dict[str, str]],
) -> dict[str, object]:
    """Generic manual-review payload with declared/detected types (R3/R8)."""
    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "decision": "manual_review_required",
        "suggestion": "manual_review_required",
        "reason_code": reason_code,
        "reason_text": reason_text,
        "exam_type": detected,
        "declared_exam_type": declared,
        "detected_exam_type": detected,
        "evidence_spans": _project_manual_review_evidence_spans(evidence_spans),
    }


def _normalize_expected_exam_type(expected_exam_type: str | None) -> str:
    """Normalize the declared exam type; unknown/absent defaults to EDA."""
    normalized = (expected_exam_type or "").strip().lower()
    if normalized in {"eda", "colonoscopy"}:
        return normalized
    return "eda"


# ── Public API ───────────────────────────────────────────────────────────────


def _extract_v3_structured_procedures(
    *,
    llm1_structured_data: dict[str, object],
) -> set[str]:
    """Procedimentos da lista estruturada v3 com evidence spans válidos.

    Cobre os quatro tipos do catálogo. Ecoendoscopia/CPRE também são
    detectados textualmente (occurrences + precedência ``EDA com/e``) em
    ``detect_requested_procedures_v3``; aqui entra apenas o campo estruturado.
    """
    raw = llm1_structured_data.get("requested_procedures")
    if not isinstance(raw, list):
        return set()
    result: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        procedure_type = item.get("procedure_type")
        spans = item.get("evidence_spans")
        if procedure_type not in {"eda", "colonoscopy", "echoendoscopy", "cpre"}:
            continue
        if not isinstance(spans, list) or not spans:
            continue
        result.add(procedure_type)
    return result


def detect_requested_procedures_v3(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> dict[str, dict[str, bool]]:
    """Detecta solicitações atuais para o contrato 3.0 (quatro tipos).

    EDA/Colonoscopia preservam a detecção textual já existente (contrato 2.0).
    Ecoendoscopia e CPRE combinam a lista estruturada v3 com as ocorrências
    textuais qualificadas (R2): um pedido atual textual (inclusive a expressão
    composta ``EDA com/e <especializado>``) já é evidência forte.
    Histórico/negação nunca criam componente.
    """
    detection = detect_requested_procedures_v2(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    structured = _extract_v3_structured_procedures(llm1_structured_data=llm1_structured_data)
    occurrences = detect_procedure_occurrences(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    textual_current = {
        occurrence.procedure_type for occurrence in occurrences if occurrence.qualification == _QUALIFICATION_CURRENT
    }

    # D5: em 3.0 Ecoendoscopia NÃO é subtipo/sinal de EDA. A detecção 2.0 (que
    # conta ``ecoendoscopia`` como evidência EDA) é corrigida quando não há
    # nenhuma evidência EDA própria — textual, estruturada ou no motivo.
    if "eda" not in structured and "eda" not in textual_current and not _motive_requires_eda_proper(cleaned_text):
        detection["eda"] = {"strong": False, "any": False}

    for procedure_type in ("echoendoscopy", "cpre"):
        present = procedure_type in structured or procedure_type in textual_current
        detection[procedure_type] = {"strong": present, "any": present}
    return detection


def _motive_requires_eda_proper(cleaned_text: str) -> bool:
    """Motivo da Solicitação pede EDA próprio (não apenas Ecoendoscopia)."""
    motive_text = _extract_motivo_solicitacao_text(cleaned_text=cleaned_text)
    if motive_text is None:
        return False
    normalized_motive = _normalize_scope_keyword_text(value=motive_text)
    return _EDA_PROCEDURE_OCCURRENCE_PATTERN.search(normalized_motive) is not None


def classify_exam_scope(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
    case_id: str,
    agency_record_number: str,
    expected_exam_type: str | None = None,
) -> dict[str, object] | None:
    """Classify exam scope and gate automatic recommendation.

    Args:
        expected_exam_type: Exam type declared at intake (``Case.exam_type``).
            Defaults to EDA for backward compatibility.

    Returns:
        None → the detected exam type matches the declared type; proceed.
        dict → manual_review_required payload with ``reason_code`` and
            declared/detected types (mixed, mismatch, non_eda or unknown).
    """

    expected = _normalize_expected_exam_type(expected_exam_type)
    llm1_exam_type = _extract_preop_exam_type(llm1_structured_data=llm1_structured_data)

    has_eda_strong, has_eda_any, has_colon_any = _detect_current_request_signals(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
        llm1_exam_type=llm1_exam_type,
    )

    evidence_spans = _extract_preop_evidence_spans(llm1_structured_data=llm1_structured_data)

    if has_eda_any and has_colon_any:
        return _build_manual_review_payload(
            case_id=case_id,
            agency_record_number=agency_record_number,
            reason_code="mixed_exam_request",
            reason_text=(
                "Documento solicita EDA e Colonoscopia como pedidos atuais no mesmo PDF; "
                "envie PDFs/casos separados por tipo de exame."
            ),
            detected="mixed",
            declared=expected,
            evidence_spans=evidence_spans,
        )

    if has_colon_any:
        detected: str | None = "colonoscopy"
    elif has_eda_any:
        # Solicitação única de EDA. O LLM1 non_eda mantém autoridade legada
        # SOMENTE quando a evidência é textual sem proveniência (motivo/
        # subtipo/nome estruturado) — nunca na decisão de mixed (F1).
        if llm1_exam_type == "non_eda" and not has_eda_strong:
            detected = _detect_fallback_type(
                llm1_structured_data=llm1_structured_data,
                cleaned_text=cleaned_text,
                llm1_exam_type=llm1_exam_type,
            )
        else:
            detected = "eda"
    else:
        detected = _detect_fallback_type(
            llm1_structured_data=llm1_structured_data,
            cleaned_text=cleaned_text,
            llm1_exam_type=llm1_exam_type,
        )

    if detected is None:
        # No preop_screening at all — legacy pass-through.
        return None

    if detected == expected:
        return None

    if detected in {"eda", "colonoscopy"}:
        return _build_manual_review_payload(
            case_id=case_id,
            agency_record_number=agency_record_number,
            reason_code="exam_type_mismatch",
            reason_text=(
                "Tipo de exame declarado difere da solicitacao atual do documento; revisao manual obrigatoria."
            ),
            detected=detected,
            declared=expected,
            evidence_spans=evidence_spans,
        )

    if detected == "non_eda":
        return _build_manual_review_payload(
            case_id=case_id,
            agency_record_number=agency_record_number,
            reason_code="non_eda_request",
            reason_text="Solicitacao fora do escopo dos tipos suportados; revisao manual obrigatoria.",
            detected="non_eda",
            declared=expected,
            evidence_spans=evidence_spans,
        )

    return _build_manual_review_payload(
        case_id=case_id,
        agency_record_number=agency_record_number,
        reason_code="unknown_exam_type",
        reason_text="Tipo de exame nao identificado; revisao manual obrigatoria.",
        detected="unknown",
        declared=expected,
        evidence_spans=evidence_spans,
    )


# ── Detecção v2 (Slice 002, D7) ──────────────────────────────────────────────
#
# Contrato 2.0 procedure-neutral: a detecção é por procedimento (EDA e/ou
# Colonoscopia) com dois níveis — ``strong`` (proveniência: lista estruturada
# v2 com evidence spans e/ou Motivo da Solicitação) e ``any`` (strong OU
# ocorrência textual de solicitação atual). Histórico/negação nunca criam
# componente (máquinas por ocorrência compartilhadas com o fluxo 1.1).


def _extract_v2_requested_procedures(
    *,
    llm1_structured_data: dict[str, object],
) -> set[str]:
    """Procedimentos da lista estruturada v2 com evidence spans válidos.

    O schema 2.0 exige evidence_spans por item; aqui apenas confirmamos que
    os spans sobreviveram à validação (proveniência estruturada).
    """
    raw = llm1_structured_data.get("requested_procedures")
    if not isinstance(raw, list):
        return set()
    result: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        procedure_type = item.get("procedure_type")
        spans = item.get("evidence_spans")
        if procedure_type not in {"eda", "colonoscopy"}:
            continue
        if not isinstance(spans, list) or not spans:
            continue
        result.add(procedure_type)
    return result


def _occurrence_has_qualifier(
    *,
    normalized_text: str,
    pattern: re.Pattern[str],
    historical: bool,
) -> bool:
    """True quando ao menos uma ocorrência do termo é negada/histórica (D7).

    Usado para cancelar uma afirmação estruturada do LLM contradita pelo texto:
    referência histórica/negação nunca adiciona componente, mesmo quando o
    LLM listou o procedimento em ``requested_procedures``.
    """
    for match in pattern.finditer(normalized_text):
        prefix, suffix = _clause_context(normalized_text, match.start(), match.end())
        if historical:
            if _HISTORICAL_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _HISTORICAL_AFTER_OCCURRENCE_PATTERN.match(
                suffix
            ):
                return True
        elif _NEGATION_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _NEGATION_AFTER_OCCURRENCE_PATTERN.match(suffix):
            return True
    return False


def detect_requested_procedures_v2(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> dict[str, dict[str, bool]]:
    """Detecta solicitações atuais por procedimento para o contrato 2.0 (D7).

    Returns:
        {"eda": {"strong": bool, "any": bool},
         "colonoscopy": {"strong": bool, "any": bool}}

    ``strong`` = proveniência de solicitação atual (lista estruturada v2 com
    spans OU Motivo da Solicitação). ``any`` = evidência textual de solicitação
    atual OU (``strong`` confirmado pelo texto: termo presente e sem negação/
    histórico exclusivo). Uma afirmação do LLM sem correspondência no texto
    (hallucination) ou contradita por negação/histórico nunca vira componente
    detectado (D7 — evidência forte exige proveniência suficiente).
    """
    structured_strong = _extract_v2_requested_procedures(
        llm1_structured_data=llm1_structured_data,
    )

    strong_eda = "eda" in structured_strong
    strong_colon = "colonoscopy" in structured_strong

    motive_text = _extract_motivo_solicitacao_text(cleaned_text=cleaned_text)
    if motive_text is not None:
        normalized_motive = _normalize_scope_keyword_text(value=motive_text)
        if _motive_mentions_supported_eda(normalized_motive=normalized_motive):
            strong_eda = True
        if _motive_mentions_colonoscopy(normalized_motive=normalized_motive):
            strong_colon = True

    normalized_text = _normalize_scope_keyword_text(value=cleaned_text)
    eda_current = _occurrence_is_current_request(
        normalized_text=normalized_text,
        pattern=_EDA_TERM_PATTERN,
    ) or _contains_eus_with_local_request_context(normalized_text=normalized_text)
    colon_current = _occurrence_is_current_request(
        normalized_text=normalized_text,
        pattern=_COLONOSCOPY_TERM_PATTERN,
    ) or _occurrence_is_current_request(
        normalized_text=normalized_text,
        pattern=_COLONOSCOPY_ACRONYM_PATTERN,
    )

    eda_mentions = _EDA_TERM_PATTERN.search(normalized_text) is not None
    colon_mentions = (
        _COLONOSCOPY_TERM_PATTERN.search(normalized_text) is not None
        or _COLONOSCOPY_ACRONYM_PATTERN.search(normalized_text) is not None
    )
    eda_neg_or_hist = _occurrence_has_qualifier(
        normalized_text=normalized_text,
        pattern=_EDA_TERM_PATTERN,
        historical=False,
    ) or _occurrence_has_qualifier(
        normalized_text=normalized_text,
        pattern=_EDA_TERM_PATTERN,
        historical=True,
    )
    colon_neg_or_hist = (
        _occurrence_has_qualifier(
            normalized_text=normalized_text,
            pattern=_COLONOSCOPY_TERM_PATTERN,
            historical=False,
        )
        or _occurrence_has_qualifier(
            normalized_text=normalized_text,
            pattern=_COLONOSCOPY_TERM_PATTERN,
            historical=True,
        )
        or _occurrence_has_qualifier(
            normalized_text=normalized_text,
            pattern=_COLONOSCOPY_ACRONYM_PATTERN,
            historical=False,
        )
        or _occurrence_has_qualifier(
            normalized_text=normalized_text,
            pattern=_COLONOSCOPY_ACRONYM_PATTERN,
            historical=True,
        )
    )

    def _any(strong: bool, current: bool, mentions: bool, neg_or_hist: bool) -> bool:
        if current:
            return True
        return strong and mentions and not neg_or_hist

    return {
        "eda": {"strong": strong_eda, "any": _any(strong_eda, eda_current, eda_mentions, eda_neg_or_hist)},
        "colonoscopy": {
            "strong": strong_colon,
            "any": _any(strong_colon, colon_current, colon_mentions, colon_neg_or_hist),
        },
    }


# ── Ocorrências qualificadas por procedimento (Slice 002, R2/D3) ─────────────
#
# D3: o contrato entre detecção e reconciliação não transporta apenas conjuntos
# ``strong/any``. Cada ocorrência relevante leva tipo, qualificação
# (``current_request|historical|negated|mention``), trecho/offsets (evidence id)
# e o vínculo textual ``com/e EDA`` quando a expressão é composta. Só assim a
# reconciliação distingue "EDA com Ecoendoscopia" (colapsa para Eco) de duas
# solicitações independentes incompatíveis (vão ao NIR).

_QUALIFICATION_CURRENT = "current_request"
_QUALIFICATION_HISTORICAL = "historical"
_QUALIFICATION_NEGATED = "negated"
_QUALIFICATION_MENTION = "mention"

_ECHOENDOSCOPY_TERM_PATTERN = re.compile(
    r"\becoendoscopia\b|\beco\s+endoscopia\b|\beco-endoscopia\b"
    r"|\bultrassonografia\s+endoscopica\b|\bultrassom\s+endoscopico\b|\beus\b"
)

# CPRE (nome completo + sigla): aliases aprovados no perfil do procedimento
# (D7) são a fonte única; o nome completo aparece nas duas ordens usadas na
# prática clínica.
_CPRE_TERM_PATTERN = re.compile("|".join(rf"\b{re.escape(alias)}\b" for alias in CPRE_PROFILE.scope_aliases))

# ── Pacotes EDA (Slice 003/004, D2/D3) ───────────────────────────────────────
#
# ``GTT``/``gastrostomia`` e ``cápsula`` são marcadores autoevidentes da família
# EDA (a ocorrência atual, mesmo isolada em trecho próprio, basta).
# ``dilatação`` é termo ambíguo: exige vínculo local com EDA solicitada na MESMA
# expressão e nunca aceita anatomia dilatada como achado (colédoco/via biliar).
# Nenhuma abreviação operacional nova é inventada (R2).
_EDA_GASTROSTOMY_TERM_PATTERN = re.compile(r"\bgtt\b|\bgastrostomia\b|\bgastrostomy\b")

_EDA_CAPSULE_TERM_PATTERN = re.compile(r"\bcapsula\b")

_EDA_DILATION_TERM_PATTERN = re.compile(r"\bdilatacao\b")

# ── Família Retossigmoidoscopia (Slice 005, D3) ───────────────────────────
#
# O nome canônico é a única ocorrência aceita (nenhuma sigla/alias inventado).
# ``dilatação`` e ``argônio`` são termos ambíguos e exigem vínculo local com
# Retossigmoidoscopia solicitada na MESMA expressão; ``dilatação de colédoco``
# segue bloqueada como achado anatômico.
_RETOSSIGMOIDOSCOPY_TERM_PATTERN = re.compile(r"\bretossigmoidoscopia\b")

_RECTOSIGMOIDOSCOPY_DILATION_TERM_PATTERN = re.compile(r"\bdilatacao\b")

_RECTOSIGMOIDOSCOPY_ARGON_TERM_PATTERN = re.compile(r"\bargonio\b")

# Anatomia dilatada como achado de imagem/relatório, nunca o pacote endoscópico.
_DILATION_BLOCKED_SITE_TERMS: tuple[str, ...] = ("coledoco", "via biliar", "vias biliares")

_V4_VARIATION_TYPES: tuple[str, ...] = (
    "eda_gastrostomy",
    "eda_capsule",
    "eda_dilation",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
)

# Identidades 4.0 cujo item estruturado é proveniência suficiente quando o texto
# não traz NENHUMA ocorrência do termo (D3).
_V4_STRUCTURED_CANDIDATE_TYPES: tuple[str, ...] = (*_V4_VARIATION_TYPES, "rectosigmoidoscopy")

# Termos que exigem vínculo local ``com/e`` com a base na mesma expressão.
_VARIATIONS_REQUIRING_LOCAL_LINK: frozenset[str] = frozenset(
    {"eda_dilation", "rectosigmoidoscopy_dilation", "rectosigmoidoscopy_argon"}
)

# Variações de dilatação (de qualquer família): únicas sujeitas ao bloqueio de
# anatomia dilatada como achado.
_DILATION_VARIATION_TYPES: frozenset[str] = frozenset({"eda_dilation", "rectosigmoidoscopy_dilation"})

# Base que a expressão composta de cada termo precisa conter (D3): as variações
# de Retossigmoidoscopia vinculam-se à própria Retossigmoidoscopia; todos os
# demais termos compostos (especializados e pacotes EDA) vinculam-se à EDA.
_VARIATION_BASE_PATTERNS: dict[str, re.Pattern[str]] = {
    "rectosigmoidoscopy_dilation": _RETOSSIGMOIDOSCOPY_TERM_PATTERN,
    "rectosigmoidoscopy_argon": _RETOSSIGMOIDOSCOPY_TERM_PATTERN,
}

# Identidades que funcionam como BASE de expressão composta (D3): nunca são
# resolvidas como termo vinculado, apenas marcadas como base quando o termo
# correspondente aparece ligado na mesma expressão.
_BASE_IDENTITY_TYPES: frozenset[str] = frozenset({"eda", "rectosigmoidoscopy"})

# Termos que expressam a MESMA ocorrência composta "<base> com/e <termo>".
_LINK_SEPARATOR_PATTERN = re.compile(r"\b(?:com|e)\b")


@dataclass(frozen=True)
class ProcedureOccurrence:
    """Ocorrência qualificada de um procedimento no texto da solicitação.

    ``start``/``end`` são offsets no texto normalizado e formam, com o tipo, o
    ``evidence_id`` determinístico da ocorrência (proveniência auditável).
    ``linked_base`` marca a expressão composta ``<base> com/e <termo>`` no mesmo
    contexto — ``EDA com <especializado>`` ou ``Retossigmoidoscopia com
    dilatação/argônio`` —, que a reconciliação colapsa (D3).
    """

    procedure_type: str
    qualification: str
    excerpt: str
    start: int
    end: int
    linked_base: bool = False

    @property
    def evidence_id(self) -> str:
        return f"{self.procedure_type}:{self.start}-{self.end}"


_PROCEDURE_OCCURRENCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("eda", _EDA_PROCEDURE_OCCURRENCE_PATTERN),
    ("colonoscopy", _COLONOSCOPY_TERM_PATTERN),
    ("echoendoscopy", _ECHOENDOSCOPY_TERM_PATTERN),
    ("cpre", _CPRE_TERM_PATTERN),
    ("eda_gastrostomy", _EDA_GASTROSTOMY_TERM_PATTERN),
    ("eda_capsule", _EDA_CAPSULE_TERM_PATTERN),
    ("eda_dilation", _EDA_DILATION_TERM_PATTERN),
    ("rectosigmoidoscopy", _RETOSSIGMOIDOSCOPY_TERM_PATTERN),
    ("rectosigmoidoscopy_dilation", _RECTOSIGMOIDOSCOPY_DILATION_TERM_PATTERN),
    ("rectosigmoidoscopy_argon", _RECTOSIGMOIDOSCOPY_ARGON_TERM_PATTERN),
)


def _classify_occurrence(*, prefix: str, suffix: str) -> str:
    """Qualifica a ocorrência ancorada no próprio contexto (D3)."""
    if _HISTORICAL_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _HISTORICAL_AFTER_OCCURRENCE_PATTERN.match(suffix):
        return _QUALIFICATION_HISTORICAL
    if _NEGATION_BEFORE_OCCURRENCE_PATTERN.search(prefix) or _NEGATION_AFTER_OCCURRENCE_PATTERN.match(suffix):
        return _QUALIFICATION_NEGATED
    if (
        _REQUEST_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _LABEL_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _REQUEST_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
    ):
        return _QUALIFICATION_CURRENT
    return _QUALIFICATION_MENTION


def _family_base_type(procedure_type: str) -> str:
    """Base exigida pela expressão composta de um termo (D3).

    As variações de Retossigmoidoscopia vinculam-se à própria
    Retossigmoidoscopia; qualquer outro termo composto (especializados e pacotes
    EDA) vincula-se à EDA.
    """
    return "rectosigmoidoscopy" if procedure_type in _VARIATION_BASE_PATTERNS else "eda"


def _linked_base_in_clause(*, clause: str, specialized: ProcedureOccurrence) -> bool:
    """True quando há ocorrência da BASE ligada ao termo por ``com``/``e``.

    O vínculo é textual e local: exige uma ocorrência da base da família no
    MESMO contexto e um separador ``com``/``e`` entre as duas ocorrências.
    Conjunto por si só nunca colapsa (D3).
    """
    base_pattern = _VARIATION_BASE_PATTERNS.get(specialized.procedure_type, _EDA_PROCEDURE_OCCURRENCE_PATTERN)
    for match in base_pattern.finditer(clause):
        base_start, base_end = match.start(), match.end()
        if base_end <= specialized.start:
            between = clause[base_end : specialized.start]
        elif specialized.end <= base_start:
            between = clause[specialized.end : base_start]
        else:
            return True
        if _LINK_SEPARATOR_PATTERN.search(between) is not None:
            return True
    return False


def detect_procedure_occurrences(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> tuple[ProcedureOccurrence, ...]:
    """Detecta ocorrências qualificadas dos procedimentos no relatório.

    Determinístico e puro (sem ORM/I-O). ``llm1_structured_data`` é aceito para
    paridade de assinatura com os demais detectores; a proveniência textual
    vem exclusivamente de ``cleaned_text`` (relatório principal).
    """
    del llm1_structured_data  # proveniência textual é a autoridade aqui
    normalized_text = _normalize_scope_keyword_text(value=cleaned_text or "")
    if not normalized_text:
        return ()

    clauses = [clause for clause in re.split(r"(?<=[.;!?])\s+|\n", normalized_text) if clause.strip()]
    occurrences: list[ProcedureOccurrence] = []
    seen: set[tuple[str, int, int]] = set()
    for clause in clauses:
        clause_start = normalized_text.find(clause)
        if clause_start < 0:
            continue
        for procedure_type, pattern in _PROCEDURE_OCCURRENCE_PATTERNS:
            for match in pattern.finditer(clause):
                start = clause_start + match.start()
                end = clause_start + match.end()
                key = (procedure_type, start, end)
                if key in seen:
                    continue
                seen.add(key)
                prefix, suffix = _clause_context(normalized_text, start, end)
                occurrences.append(
                    ProcedureOccurrence(
                        procedure_type=procedure_type,
                        qualification=_classify_occurrence(prefix=prefix, suffix=suffix),
                        excerpt=normalized_text[start:end],
                        start=start,
                        end=end,
                    )
                )

    # Vínculo ``com/e`` é avaliado por cláusula, após todas as ocorrências da
    # cláusula existirem (o separador pode preceder ou suceder o especializado).
    # Uma expressão composta cuja ocorrência da BASE é solicitação ATUAL é, por
    # definição, uma solicitação atual do termo composto (``EDA com Eco`` = Eco;
    # ``Retossigmoidoscopia com dilatação`` = Retossigmoidoscopia + Dilatação).
    clause_for = {
        occurrence.start: _clause_text_at(normalized_text=normalized_text, start=occurrence.start)
        for occurrence in occurrences
    }
    current_types_by_clause: dict[str, set[str]] = {}
    for occurrence in occurrences:
        if occurrence.qualification != _QUALIFICATION_CURRENT:
            continue
        clause = clause_for[occurrence.start]
        current_types_by_clause.setdefault(clause, set()).add(occurrence.procedure_type)

    linked: list[ProcedureOccurrence] = []
    linked_base_by_clause: dict[str, set[str]] = {}
    resolved: list[ProcedureOccurrence] = []
    for occurrence in occurrences:
        clause = clause_for[occurrence.start]
        if occurrence.procedure_type in _BASE_IDENTITY_TYPES:
            # A própria base é resolvida no final (vínculo simétrico).
            resolved.append(occurrence)
            continue
        base_type = _family_base_type(occurrence.procedure_type)
        clause_start = normalized_text.find(clause)
        local = replace_occurrence_offsets(occurrence=occurrence, clause_start=clause_start)
        if _linked_base_in_clause(clause=clause, specialized=local):
            linked_base_by_clause.setdefault(clause, set()).add(base_type)
            qualification = occurrence.qualification
            if base_type in current_types_by_clause.get(clause, set()) and qualification == _QUALIFICATION_MENTION:
                qualification = _QUALIFICATION_CURRENT
            resolved.append(replace_occurrence_link(occurrence=occurrence, linked=True, qualification=qualification))
        else:
            resolved.append(occurrence)

    # O vínculo é simétrico: a ocorrência da BASE da expressão composta também é
    # marcada, para que a reconciliação veja a proveniência de ambos os lados.
    for occurrence in resolved:
        if occurrence.procedure_type in linked_base_by_clause.get(clause_for[occurrence.start], set()):
            linked.append(replace_occurrence_link(occurrence=occurrence, linked=True))
        else:
            linked.append(occurrence)
    return tuple(_qualify_variation_occurrences(occurrences=linked, normalized_text=normalized_text))


def _qualify_variation_occurrences(
    *,
    occurrences: list[ProcedureOccurrence],
    normalized_text: str,
) -> list[ProcedureOccurrence]:
    """Aplica o regime dos termos ambíguos às ocorrências dos pacotes (D3).

    ``dilatação``/``argônio`` sem vínculo local com a base da família na mesma
    expressão — ou descrevendo anatomia dilatada como achado (``dilatação de
    colédoco``/via biliar) — permanece mera MENÇÃO: nem a detecção nem a
    reconciliação podem tratá-la como solicitação atual. ``cápsula``,
    ``GTT``/``gastrostomia`` e o nome canônico de Retossigmoidoscopia são
    marcadores autoevidentes e passam intactos.
    """
    qualified: list[ProcedureOccurrence] = []
    for occurrence in occurrences:
        if occurrence.procedure_type in _VARIATIONS_REQUIRING_LOCAL_LINK:
            prefix, suffix = _clause_context(normalized_text, occurrence.start, occurrence.end)
            local_context = f"{prefix} {suffix}"
            blocked_site = occurrence.procedure_type in _DILATION_VARIATION_TYPES and any(
                _contains_scope_term(normalized_text=local_context, term=term) for term in _DILATION_BLOCKED_SITE_TERMS
            )
            if blocked_site or not occurrence.linked_base:
                qualified.append(
                    replace_occurrence_link(
                        occurrence=occurrence,
                        linked=False,
                        qualification=_QUALIFICATION_MENTION,
                    )
                )
                continue
        qualified.append(occurrence)
    return qualified


def _clause_text_at(*, normalized_text: str, start: int) -> str:
    """Retorna a cláusula que contém a posição informada."""
    left = 0
    for boundary in re.finditer(r"[.;!?]\s+|\n", normalized_text):
        if boundary.end() > start:
            return normalized_text[left : boundary.start()]
        left = boundary.end()
    return normalized_text[left:]


def replace_occurrence_offsets(*, occurrence: ProcedureOccurrence, clause_start: int) -> ProcedureOccurrence:
    """Reprojeta os offsets da ocorrência no referencial da cláusula."""
    return ProcedureOccurrence(
        procedure_type=occurrence.procedure_type,
        qualification=occurrence.qualification,
        excerpt=occurrence.excerpt,
        start=occurrence.start - clause_start,
        end=occurrence.end - clause_start,
        linked_base=occurrence.linked_base,
    )


def replace_occurrence_link(
    *,
    occurrence: ProcedureOccurrence,
    linked: bool,
    qualification: str | None = None,
) -> ProcedureOccurrence:
    """Devolve a ocorrência com o vínculo ``com/e <base>`` e a qualificação resolvidos."""
    return ProcedureOccurrence(
        procedure_type=occurrence.procedure_type,
        qualification=qualification or occurrence.qualification,
        excerpt=occurrence.excerpt,
        start=occurrence.start,
        end=occurrence.end,
        linked_base=linked,
    )


# ── Detecção v4 (Slice 003/004/005, D3) ──────────────────────────────────────
#
# O contrato 4.0 preserva a detecção dos quatro tipos anteriores e acrescenta
# os pacotes atômicos (GTT, Cápsula e Dilatação) e a família
# Retossigmoidoscopia (nome canônico, Dilatação e Argônio). O item estruturado
# do LLM1 é proveniência suficiente para a identidade entrar como candidata
# detectada, EXCETO quando o texto traz alguma ocorrência do termo que não seja
# solicitação atual (histórica/negada/menção) — aí o texto contradiz o item e a
# identidade não é detectada. A supressão da base (EDA/Retossigmoidoscopia)
# depende de ocorrência textual ATUAL (decidida na reconciliação).


def _extract_v4_structured_candidates(
    *,
    llm1_structured_data: dict[str, object],
) -> set[str]:
    """Identidades 4.0 com item estruturado e evidence spans válidos (D3)."""
    raw = llm1_structured_data.get("requested_procedures")
    if not isinstance(raw, list):
        return set()
    result: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        procedure_type = item.get("procedure_type")
        spans = item.get("evidence_spans")
        if procedure_type not in _V4_STRUCTURED_CANDIDATE_TYPES:
            continue
        if not isinstance(spans, list) or not spans:
            continue
        result.add(str(procedure_type))
    return result


def detect_requested_procedures_v4(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> dict[str, dict[str, bool]]:
    """Detecta solicitações atuais do contrato 4.0 (D3).

    Preserva integralmente a detecção dos quatro tipos anteriores e acrescenta
    ``eda_gastrostomy``/``eda_capsule`` (marcadores autoevidentes),
    ``eda_dilation`` e a família Retossigmoidoscopia (``rectosigmoidoscopy``,
    ``rectosigmoidoscopy_dilation`` e ``rectosigmoidoscopy_argon``). Dilatação e
    argônio são termos ambíguos e já exigem vínculo local nas ocorrências;
    histórico, negação, achado anatômico e menção solta nunca criam identidade.

    O item estruturado do LLM1 só autoriza a identidade quando NENHUMA
    ocorrência do termo existe no texto: uma ocorrência não-atual (histórica,
    negada ou mera menção) contradiz o item e a identidade não é detectada — o
    caso falha fechado ao NIR em vez de prosseguir pela coincidência com a
    declaração (P1 review round 1). Sem qualquer ocorrência, o item estruturado
    permanece candidato (conjunto misto → fail-closed na matriz), comportamento
    preservado.
    """
    detection = detect_requested_procedures_v3(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    structured = _extract_v4_structured_candidates(llm1_structured_data=llm1_structured_data)
    occurrences = detect_procedure_occurrences(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    current_occurrences = {
        occurrence.procedure_type for occurrence in occurrences if occurrence.qualification == _QUALIFICATION_CURRENT
    }
    occurrence_types = {occurrence.procedure_type for occurrence in occurrences}
    for procedure_type in _V4_STRUCTURED_CANDIDATE_TYPES:
        present = procedure_type in current_occurrences or (
            procedure_type in structured and procedure_type not in occurrence_types
        )
        detection[procedure_type] = {"strong": present, "any": present}
    return detection
