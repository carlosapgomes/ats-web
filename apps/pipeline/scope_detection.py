"""Deterministic scope detection: classify exam as EDA vs non-EDA/unknown.

Ported faithfully from the legacy augmented-triage-system:
  triage_automation/application/services/process_pdf_case_service.py

Every keyword list, normalisation helper, and detection heuristic preserved exactly.
"""

from __future__ import annotations

import re
import unicodedata

_SUPPORTED_EDA_SUBTYPES: frozenset[str] = frozenset({"standard", "gastrostomy", "esophageal_dilation", "foreign_body"})

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

_SCOPE_EXPLICIT_NON_EDA_TERMS: tuple[str, ...] = (
    "endoscopia digestiva baixa",
    "endoscopia digestiva baixa - colonoscopia",
    "colonoscopia",
    "colonoscopia diagnostica",
    "colonoscopia terapeutica",
)


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
    """Extract exam_type from LLM1 preop_screening if valid."""

    preop_screening = llm1_structured_data.get("preop_screening")
    if not isinstance(preop_screening, dict):
        return None
    exam_type = preop_screening.get("exam_type")
    if isinstance(exam_type, str):
        normalized = exam_type.strip().lower()
        if normalized in {"eda", "non_eda", "unknown"}:
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
        for term in _SCOPE_FOREIGN_BODY_TERMS:
            if _contains_scope_term(normalized_text=normalized_candidate, term=term):
                return "foreign_body", term
        for term in _SCOPE_GASTROSTOMY_TERMS:
            if _contains_scope_term(normalized_text=normalized_candidate, term=term):
                return "gastrostomy", term
        for term in _SCOPE_ESOPHAGEAL_DILATION_TERMS:
            if _contains_scope_term(normalized_text=normalized_candidate, term=term):
                return "esophageal_dilation", term

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


def _detect_explicit_non_eda_scope_keyword(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> tuple[bool, str | None, str | None]:
    """Check if the request explicitly names a non-EDA exam.

    The top-level 'Motivo da Solicitação' field is authoritative because the
    clinical body may mention prior EDA reports or mixed historical context.

    Returns (is_non_eda, matched_term, source) or (False, None, None).
    """

    motive_text = _extract_motivo_solicitacao_text(cleaned_text=cleaned_text)
    if motive_text is not None:
        for term in _SCOPE_EXPLICIT_NON_EDA_TERMS:
            if _contains_scope_term(normalized_text=motive_text, term=term):
                return True, term, "motivo_da_solicitacao"

    candidate_texts = _extract_scope_keyword_candidate_texts(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    for candidate in candidate_texts:
        normalized_candidate = _normalize_scope_keyword_text(value=candidate)
        for term in _SCOPE_EXPLICIT_NON_EDA_TERMS:
            if _contains_scope_term(normalized_text=normalized_candidate, term=term):
                return True, term, "candidate_text"

    return False, None, None


def _detect_explicit_eda_scope_keyword(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
) -> tuple[bool, str | None]:
    """Check if the report explicitly mentions EDA.

    Returns (is_eda, matched_term) or (False, None).
    """

    candidate_texts = _extract_scope_keyword_candidate_texts(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )

    for candidate in candidate_texts:
        normalized_candidate = _normalize_scope_keyword_text(value=candidate)

        for term in _SCOPE_EXPLICIT_EDA_TERMS:
            if _contains_scope_term(normalized_text=normalized_candidate, term=term):
                return True, term

        has_eda_acronym = (
            re.search(r"\beda\b", normalized_candidate) is not None
            or re.search(r"\be\s*[.\-]?\s*d\s*[.\-]?\s*a\b", normalized_candidate) is not None
        )
        has_request_context = (
            re.search(
                r"\b(motivo|solicit|exame|encaminhamento|procedimento)\b",
                normalized_candidate,
            )
            is not None
        )
        if has_eda_acronym and has_request_context:
            return True, "eda"

    return False, None


def _append_scope_keyword_evidence_span(
    *,
    evidence_spans: list[dict[str, str]],
    scope_keyword_type: str,
    matched_term: str,
) -> list[dict[str, str]]:
    """Append a scope keyword evidence span, avoiding duplicates."""

    scope_label = "gastrostomia/GTT" if scope_keyword_type == "gastrostomy" else "dilatacao esofagica"
    keyword_span: dict[str, str] = {
        "field_path": "scope_detection.keyword",
        "excerpt": (f"Termo de escopo detectado no relatorio: {matched_term} ({scope_label})."),
    }
    if keyword_span in evidence_spans:
        return evidence_spans
    return [*evidence_spans, keyword_span]


def classify_exam_scope(
    *,
    llm1_structured_data: dict[str, object],
    cleaned_text: str,
    case_id: str,
    agency_record_number: str,
) -> dict[str, object] | None:
    """Classify exam scope and gate automatic recommendation.

    Returns:
        None → EDA confirmed; proceed with LLM2.
        dict → non_eda or unknown → manual_review_required payload.
    """

    exam_type = _extract_preop_exam_type(llm1_structured_data=llm1_structured_data)

    explicit_non_eda_detected, _, explicit_non_eda_source = _detect_explicit_non_eda_scope_keyword(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )
    if explicit_non_eda_detected and explicit_non_eda_source == "motivo_da_solicitacao":
        exam_type = "non_eda"

    explicit_eda_detected, _ = _detect_explicit_eda_scope_keyword(
        llm1_structured_data=llm1_structured_data,
        cleaned_text=cleaned_text,
    )

    # If LLM1 explicitly classified the request as non-EDA, keep that result
    # authoritative. Real strict-schema runs can still carry default EDA subtype
    # values (e.g. "standard") in nested fields, and those must not route
    # colonoscopy/CPRE/etc. to the doctor queue.
    if exam_type != "non_eda":
        supported_subtype = _extract_supported_eda_subtype_from_llm1(
            llm1_structured_data=llm1_structured_data,
        )
        if supported_subtype is None:
            supported_subtype, _ = _detect_supported_eda_scope_keyword(
                llm1_structured_data=llm1_structured_data,
                cleaned_text=cleaned_text,
            )

        if supported_subtype is not None or explicit_eda_detected:
            exam_type = "eda"

    if exam_type not in {"non_eda", "unknown"}:
        return None

    reason_code = "non_eda_request" if exam_type == "non_eda" else "unknown_exam_type"
    reason_text = (
        "Relatorio fora de escopo EDA; revisao manual obrigatoria."
        if exam_type == "non_eda"
        else "Tipo de exame nao identificado; revisao manual obrigatoria."
    )

    evidence_spans = _extract_preop_evidence_spans(llm1_structured_data=llm1_structured_data)

    return {
        "schema_version": "1.1",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "decision": "manual_review_required",
        "suggestion": "manual_review_required",
        "reason_code": reason_code,
        "reason_text": reason_text,
        "exam_type": exam_type,
        "evidence_spans": evidence_spans,
    }
