"""Canonical EDA priority signals: pure resolver and badge projection.

This module is the single runtime source for deriving the six canonical
priority signals from LLM1 structured data plus the extracted source text,
and for projecting them into Bootstrap badges consumed by the shared SSR
partial (``templates/cases/_priority_signals.html``).

No ORM, no LLM, no I/O — deterministic and testable in isolation.

Persisted payload contract (version 1):

    [{"code": str, "category": str, "detail": str, "version": 1}, ...]

Only known codes are persisted; labels/CSS are a presentation projection and
are never stored. Signals are deduplicated by ``code`` and ordered canonically.

Textual fallbacks are conservative and per-occurrence: a negation or
historical qualifier cancels only the occurrence it qualifies, a current
request occurrence survives, and terms are matched with word boundaries
(never bare substring). Request context is anchored to the occurrence
(before-patterns end at the prefix, after-patterns start at the suffix)
and is never borrowed from another procedure in the same clause.
"""

from __future__ import annotations

import re
import unicodedata

PRIORITY_SIGNAL_VERSION = 1

# Canonical presentation order: clinical alert, population, procedure.
CANONICAL_ORDER: tuple[str, ...] = (
    "foreign_body",
    "caustic_ingestion",
    "pediatric",
    "echoendoscopy",
    "esophageal_dilation",
    "gastrostomy",
)

CATEGORY_BY_CODE: dict[str, str] = {
    "foreign_body": "clinical_alert",
    "caustic_ingestion": "clinical_alert",
    "pediatric": "special_population",
    "echoendoscopy": "special_procedure",
    "esophageal_dilation": "special_procedure",
    "gastrostomy": "special_procedure",
}

KNOWN_CODES = frozenset(CATEGORY_BY_CODE)

_SUPPORTED_SUBTYPES: frozenset[str] = frozenset({"foreign_body", "echoendoscopy", "esophageal_dilation", "gastrostomy"})


# ── Normalization / helpers ────────────────────────────────────────────────


def _normalize_text(value: str) -> str:
    """Strip diacritics, lowercase, and collapse whitespace."""
    decomposed = unicodedata.normalize("NFD", value)
    without_diacritics = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(without_diacritics.lower().split())


def _signal(code: str, *, detail: str = "") -> dict[str, object]:
    return {
        "code": code,
        "category": CATEGORY_BY_CODE[code],
        "detail": detail,
        "version": PRIORITY_SIGNAL_VERSION,
    }


def _get_dict(payload: object, key: str) -> dict[str, object]:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _get_str(payload: object, key: str) -> str:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _get_bool(payload: object, key: str) -> bool:
    if isinstance(payload, dict):
        return payload.get(key) is True
    return False


def _get_int(payload: object, key: str) -> int | None:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _eda_subtype(structured_data: dict[str, object]) -> str:
    """Return the supported subtype from requested procedure or rulebook."""
    eda = _get_dict(structured_data, "eda")
    requested = _get_dict(eda, "requested_procedure")
    subtype = _get_str(requested, "subtype").strip().lower()
    if subtype in _SUPPORTED_SUBTYPES:
        return subtype
    preop = _get_dict(structured_data, "preop_screening")
    rulebook = _get_dict(preop, "rulebook_signals")
    subtype = _get_str(rulebook, "eda_subtype").strip().lower()
    if subtype in _SUPPORTED_SUBTYPES:
        return subtype
    return ""


# ── Shared per-occurrence machinery (conservative, anchored) ────────────────
#
# Clause boundaries: '.', ';', '!', '?' or newline. ':' is intentionally NOT
# a boundary so immediate labels ('Exame: ecoendoscopia') stay in the local
# clause of the occurrence.
#
# Every qualifier below is ANCHORED to the occurrence: before-patterns end at
# the end of the prefix ('$'), after-patterns start at the beginning of the
# suffix ('^'). Context is never borrowed from another procedure in the same
# clause, and word boundaries protect against 'contraindicada'/'micro...'.

_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.;!?]|\n")

# Supported EDA procedure terms that may appear in a small requested chain
# ('Solicito EDA com ecoendoscopia e dilatação esofágica').
_PROCEDURE_TERM_SOURCE = (
    r"ecoendoscopia|eco\s+endoscopia|eco-endoscopia"
    r"|ultrassonografia\s+endoscopica|ultrassom\s+endoscopico"
    r"|dilatacao\s+esofagica|dilatacao\s+do\s+esofago|dilatacao\s+de\s+esofago"
    r"|dilatacao\s+endoscopica\s+esofagica"
    r"|gastrostomia|gastrostomy|gtt|peg"
)

# Request stem before the occurrence, with approved connectors and an
# optional small chain of supported EDA procedures ('... e ...' / ',').
_REQUEST_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:solicit|encaminh|indic|programar|confeccao)\w*\b"
    r"(?:\s+(?:realizacao\s+de|nova|atual\s+de|de|para))?"
    r"(?:\s+\beda\b\s+(?:com|para))?"
    r"(?:\s+(?:" + _PROCEDURE_TERM_SOURCE + r")\b(?:\s+(?:e\b|,))?)*"
    r"\s*$"
)

# Immediate labels before the occurrence: 'Exame: X', 'Procedimento: X',
# 'Motivo da Solicitação: X' — with an optional 'EDA com/para' chain after
# the label ('Motivo da Solicitação: EDA com ecoendoscopia').
_LABEL_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:exame|procedimento)\b\s*(?:de|para|:)?\s*$"
    r"|\bmotivo\s+da\s+solicitacao\b\s*:?\s*(?:eda\s+(?:com|para))?\s*$"
)

# Request stem immediately after the occurrence: 'X solicitado', 'X indicado'.
_REQUEST_AFTER_OCCURRENCE_PATTERN = re.compile(r"^\s*(?:solicit|indic|encaminh)\w*\b")

# Historical qualifiers attached to this occurrence (after or before).
_HISTORICAL_AFTER_OCCURRENCE_PATTERN = re.compile(
    r"^\s*(?:foi\s+)?realizad[oa]\b"
    r"|^\s*(?:previo|previa|anterior|previamente)\b"
    r"|^\s*no\s+historico\b"
)
_HISTORICAL_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:realizou)\b\s+$"
    r"|\b(?:previo|previa|anterior|previamente)\b\s*(?:de\s*)?:?\s*$"
    r"|\bhistorico\s+de\b\s*$"
)

# Negation qualifiers attached to this occurrence (after or before).
_NEGATION_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\bsem\s+indicacao\s+de\b\s*$"
    r"|\bsem\s+evidencia\s+de\b\s*$"
    r"|\bsem\b\s*$"
    r"|\bnega\s+indicacao\s+de\b\s*$"
    r"|\bnega\s+(?:a\s+)?ingestao\s+de\b\s*$"
    r"|\bnega\b\s*$"
    r"|\bnao\s+solicit\w*\b\s*$"
    r"|\bnao\s+foi\s+identificad[oa]\b\s*$"
    r"|\bnao\s+ha\b\s*$"
    r"|\bausencia\s+de\b\s*$"
)
_NEGATION_AFTER_OCCURRENCE_PATTERN = re.compile(
    r"^\s*(?:descartad[oa]|negad[oa]|ausente|contraindicad[oa])\b"
    r"|^\s*nao\s+(?:foi\s+)?(?:indicad[oa]|recomendad[oa]|solicitad[oa])\b"
    r"|^\s*sem\s+indicac\w*\b"
)


def _occurrence_contexts(normalized_text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    """Return (prefix, suffix) local clause contexts for each boundary-safe match."""
    contexts: list[tuple[str, str]] = []
    for match in pattern.finditer(normalized_text):
        left_boundaries = list(_CLAUSE_BOUNDARY_PATTERN.finditer(normalized_text, 0, match.start()))
        clause_start = left_boundaries[-1].end() if left_boundaries else 0
        right_boundary = _CLAUSE_BOUNDARY_PATTERN.search(normalized_text, match.end())
        clause_end = right_boundary.start() if right_boundary else len(normalized_text)
        contexts.append((normalized_text[clause_start : match.start()], normalized_text[match.end() : clause_end]))
    return contexts


def _is_historical_occurrence(prefix: str, suffix: str) -> bool:
    return (
        _HISTORICAL_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
        or _HISTORICAL_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
    )


def _is_negated_occurrence(prefix: str, suffix: str) -> bool:
    return (
        _NEGATION_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _NEGATION_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
    )


def _is_current_request_occurrence(prefix: str, suffix: str) -> bool:
    """True when the occurrence is directly anchored to request/exam/procedure intent.

    Before-patterns are anchored at the end of the prefix and after-patterns
    at the start of the suffix; context is never borrowed from another
    procedure elsewhere in the clause.
    """
    return (
        _REQUEST_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _LABEL_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _REQUEST_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
    )


# ── Pediatric ──────────────────────────────────────────────────────────────


def _resolve_pediatric(structured_data: dict[str, object]) -> list[dict[str, object]]:
    patient = _get_dict(structured_data, "patient")
    age = _get_int(patient, "age")
    if age is not None:
        if age < 16:
            return [_signal("pediatric", detail=f"{age} anos")]
        # Age present and >= 16: the validated contract keeps the flag
        # aligned, so no pediatric signal.
        return []
    # Fallback for legacy payloads without an age: explicit pediatric flag.
    eda = _get_dict(structured_data, "eda")
    if _get_bool(eda, "is_pediatric"):
        return [_signal("pediatric")]
    return []


# ── Foreign body ───────────────────────────────────────────────────────────


_FOREIGN_BODY_TERM_PATTERN = re.compile(r"\bcorpo\s+estranho\b")


def _has_structured_foreign_body(structured_data: dict[str, object]) -> bool:
    if _eda_subtype(structured_data) == "foreign_body":
        return True
    eda = _get_dict(structured_data, "eda")
    if _get_str(eda, "indication_category").strip().lower() == "foreign_body":
        return True
    if _get_bool(eda, "foreign_body_suspected"):
        return True
    return False


def _has_positive_foreign_body_occurrence(normalized_text: str) -> bool:
    """True when at least one body-foreign occurrence is a current positive.

    A negation or historical qualifier cancels only its own occurrence; a
    distinct current mention (suspeita/solicitação/achado) survives.
    """
    for prefix, suffix in _occurrence_contexts(normalized_text, _FOREIGN_BODY_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix):
            continue
        if _is_negated_occurrence(prefix, suffix):
            continue
        return True
    return False


def _resolve_foreign_body(
    structured_data: dict[str, object],
    normalized_text: str,
) -> list[dict[str, object]]:
    # Precedence: a structured positive signal validated by LLM1 represents
    # the current request and prevails over any negated/historical textual
    # fallback mention.
    if _has_structured_foreign_body(structured_data):
        return [_signal("foreign_body")]
    if _has_positive_foreign_body_occurrence(normalized_text):
        return [_signal("foreign_body")]
    return []


# ── Caustic ingestion (moved from the doctor presenter, single runtime copy) ──


_CAUSTIC_KEYWORDS: tuple[str, ...] = (
    "caustic",
    "corrosiv",
    "soda caustica",
    "acido",
)

_INGESTION_VERBS: tuple[str, ...] = (
    "ingeriu",
    "ingestao",
    "ingerir",
    "ingerido",
)

_CAUSTIC_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"nega\s+ingestao\s+de\s+(caustic|corrosiv|soda\s+caustica|acido)", re.IGNORECASE),
    re.compile(r"sem\s+ingestao\s+de\s+(corrosiv|caustic)", re.IGNORECASE),
    re.compile(r"nao\s+ingeriu\s+(soda\s+caustica|caustic|corrosiv)", re.IGNORECASE),
    re.compile(r"nega\s+(ter\s+)?ingerid[oa]\s+(produto\s+)?(caustic|corrosiv|soda\s+caustica|acido)", re.IGNORECASE),
    re.compile(r"sem\s+(relato\s+de\s+)?ingestao[\s,;.:!?]", re.IGNORECASE),
)

_CAUSTIC_TIME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"h[aá]\s+(cerca\s+de\s+|aproximadamente\s+)?[\w\s]+?(semanas?|dias?|meses?|anos?|minutos?|horas?)",
        re.IGNORECASE,
    ),
    re.compile(r"em\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", re.IGNORECASE),
    re.compile(
        r"h[aá]\s+(cerca\s+de\s+|aproximadamente\s+)?[\w\s]+?(semanas?|dias?|meses?|anos?|minutos?|horas?)\s+atr[aá]s",
        re.IGNORECASE,
    ),
)


def _has_caustic_keyword_near_ingestion(normalized: str) -> bool:
    """Return True when a caustic keyword appears near an ingestion verb."""
    for keyword in _CAUSTIC_KEYWORDS:
        if keyword not in normalized:
            continue
        for verb in _INGESTION_VERBS:
            for match in re.finditer(re.escape(verb), normalized):
                start = max(0, match.start() - 20)
                end = min(len(normalized), match.end() + 80)
                if keyword in normalized[start:end]:
                    return True
    return False


def _extract_time_from_text(text: str) -> str:
    """Extract the first relative/date time expression, or empty string."""
    for pattern in _CAUSTIC_TIME_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return ""


def resolve_caustic_ingestion(source_text: str) -> dict[str, object] | None:
    """Return the caustic ingestion signal dict, or None.

    Preserves the legacy presenter behavior: ingestion keyword near an
    ingestion verb, explicit negation first, and time extraction. Public so
    the doctor presenter can reuse it until Slice 003 consumes persistence.
    """
    if not isinstance(source_text, str) or not source_text.strip():
        return None
    normalized = _normalize_text(source_text)
    for pattern in _CAUSTIC_NEGATION_PATTERNS:
        if pattern.search(normalized):
            return None
    if not _has_caustic_keyword_near_ingestion(normalized):
        return None
    return _signal("caustic_ingestion", detail=_extract_time_from_text(source_text))


# ── Echoendoscopy ─────────────────────────────────────────────────────────


_ECHOENDOSCOPY_TERM_PATTERN = re.compile(
    r"\becoendoscopia\b"
    r"|\beco\s+endoscopia\b"
    r"|\beco-endoscopia\b"
    r"|\bultrassonografia\s+endoscopica\b"
    r"|\bultrassom\s+endoscopico\b"
)

# Conservative per-occurrence local context for the EUS acronym (Slice 001
# contract). Mirrors the scope detector; kept here because apps.cases must
# not import from apps.pipeline (layering: pipeline depends on cases).
_EUS_PATTERN = re.compile(r"\beus\b")
_EUS_REQUEST_BEFORE_PATTERN = re.compile(r"\b(solicit|encaminh|indic)\w*\b\s*(?:realizacao\s+de|de|para|:)?\s*$")
_EUS_EXAM_BEFORE_PATTERN = re.compile(r"\b(exame|procedimento)\b\s*(?:de|para|:)?\s*$")
_EUS_REQUEST_AFTER_PATTERN = re.compile(r"^\s*(?:solicit|indic|encaminh)\w*\b")
_EUS_HISTORICAL_AFTER_PATTERN = re.compile(r"^\s*(realizad[oa]|previo|previa|anterior)\b")
_EUS_HISTORICAL_BEFORE_PATTERN = re.compile(r"\b(?:realizou)\b\s+$|\b(?:previo|previa|anterior)\b\s+(?:de\s+)?$")


def _contains_eus_with_request_context(normalized: str) -> bool:
    """Return True when at least one EUS occurrence is an explicit request.

    Each occurrence is classified independently against its own bounded
    clause; a historical occurrence cancels only itself.
    """
    for prefix, suffix in _occurrence_contexts(normalized, _EUS_PATTERN):
        if _EUS_HISTORICAL_AFTER_PATTERN.match(suffix) is not None:
            continue
        if _EUS_HISTORICAL_BEFORE_PATTERN.search(prefix) is not None:
            continue
        if (
            _EUS_REQUEST_BEFORE_PATTERN.search(prefix) is not None
            or _EUS_EXAM_BEFORE_PATTERN.search(prefix) is not None
            or _EUS_REQUEST_AFTER_PATTERN.match(suffix) is not None
        ):
            return True
    return False


def _resolve_echoendoscopy(
    structured_data: dict[str, object],
    normalized_text: str,
) -> list[dict[str, object]]:
    if _eda_subtype(structured_data) == "echoendoscopy":
        return [_signal("echoendoscopy")]
    # Full names require a current request/exam/procedure context and are
    # matched with word boundaries; historical/negated mentions are ignored.
    for prefix, suffix in _occurrence_contexts(normalized_text, _ECHOENDOSCOPY_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix) or _is_negated_occurrence(prefix, suffix):
            continue
        if _is_current_request_occurrence(prefix, suffix):
            return [_signal("echoendoscopy")]
    if _contains_eus_with_request_context(normalized_text):
        return [_signal("echoendoscopy")]
    return []


# ── Esophageal dilation ───────────────────────────────────────────────────


_ESOPHAGEAL_DILATION_TERM_PATTERN = re.compile(
    r"\bdilatacao\s+esofagica\b"
    r"|\bdilatacao\s+do\s+esofago\b"
    r"|\bdilatacao\s+de\s+esofago\b"
    r"|\bdilatacao\s+endoscopica\s+esofagica\b"
)


def _resolve_esophageal_dilation(
    structured_data: dict[str, object],
    normalized_text: str,
) -> list[dict[str, object]]:
    if _eda_subtype(structured_data) == "esophageal_dilation":
        return [_signal("esophageal_dilation")]
    # Conservative: never accept the isolated word "dilatação" nor substring
    # matches; current-request context required per occurrence.
    for prefix, suffix in _occurrence_contexts(normalized_text, _ESOPHAGEAL_DILATION_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix) or _is_negated_occurrence(prefix, suffix):
            continue
        if _is_current_request_occurrence(prefix, suffix):
            return [_signal("esophageal_dilation")]
    return []


# ── Gastrostomy ───────────────────────────────────────────────────────────


_GASTROSTOMY_TERM_PATTERN = re.compile(r"\b(?:gtt|gastrostomia|gastrostomy|peg)\b")

# A clearly pre-existing/historical gastrostomy is not a current signal.
_GASTROSTOMY_HISTORICAL_PATTERN = re.compile(
    r"\b(previo|previa|anterior|portador\w*|realizou|realizad[oa]|em\s+uso|ja\s+(tem|possui))\b"
)


def _resolve_gastrostomy(
    structured_data: dict[str, object],
    normalized_text: str,
) -> list[dict[str, object]]:
    if _eda_subtype(structured_data) == "gastrostomy":
        return [_signal("gastrostomy")]
    for prefix, suffix in _occurrence_contexts(normalized_text, _GASTROSTOMY_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix):
            continue
        if _GASTROSTOMY_HISTORICAL_PATTERN.search(prefix + " " + suffix):
            continue
        # Current request anchored to the occurrence (shared anchored context).
        if _is_current_request_occurrence(prefix, suffix):
            return [_signal("gastrostomy")]
    return []


# ── Public resolver ────────────────────────────────────────────────────────


def resolve_priority_signals(
    *,
    structured_data: dict[str, object],
    source_text: str,
) -> list[dict[str, object]]:
    """Resolve the six canonical priority signals deterministically.

    Signals are deduplicated by code and returned in canonical order.
    No LLM, no ORM, no I/O.
    """
    normalized_text = _normalize_text(source_text or "")

    signals: list[dict[str, object]] = []
    signals.extend(_resolve_pediatric(structured_data))
    signals.extend(_resolve_foreign_body(structured_data, normalized_text))
    caustic = resolve_caustic_ingestion(source_text or "")
    if caustic is not None:
        signals.append(caustic)
    signals.extend(_resolve_echoendoscopy(structured_data, normalized_text))
    signals.extend(_resolve_esophageal_dilation(structured_data, normalized_text))
    signals.extend(_resolve_gastrostomy(structured_data, normalized_text))

    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for signal in signals:
        code = str(signal["code"])
        if code in seen:
            continue
        seen.add(code)
        deduped.append(signal)
    deduped.sort(key=lambda s: CANONICAL_ORDER.index(str(s["code"])))
    return deduped


# ── Badge projection (presentation metadata, single mapping) ──────────────


_BADGE_METADATA: dict[str, dict[str, str]] = {
    "foreign_body": {
        "label": "⚠ Suspeita de corpo estranho",
        "css_class": "bg-warning text-dark",
        "emphasis": "warning",
    },
    "caustic_ingestion": {
        "label": "⚠ Ingestão cáustica/corrosiva",
        "css_class": "bg-warning text-dark",
        "emphasis": "warning",
    },
    "pediatric": {
        "label": "Pediatria",
        "css_class": "bg-info text-dark",
        "emphasis": "attention",
    },
    "echoendoscopy": {
        "label": "Ecoendoscopia",
        "css_class": "bg-primary text-white",
        "emphasis": "operational",
    },
    "esophageal_dilation": {
        "label": "Dilatação esofágica",
        "css_class": "bg-primary text-white",
        "emphasis": "operational",
    },
    "gastrostomy": {
        "label": "Gastrostomia",
        "css_class": "bg-primary text-white",
        "emphasis": "operational",
    },
}


def build_priority_signal_badges(priority_signals: object) -> list[dict[str, str]]:
    """Project persisted signals into presentation badges.

    Tolerates any payload shape: non-list payloads, non-dict items, unknown
    codes, duplicates and incompatible versions are ignored. Order is
    canonical. Detail (age/time) is appended when present and safe.
    Never runs detection and never touches raw text.
    """
    if not isinstance(priority_signals, list):
        return []

    badges: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in priority_signals:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        version = item.get("version")
        if not isinstance(code, str) or code not in _BADGE_METADATA:
            continue
        if version != PRIORITY_SIGNAL_VERSION:
            continue
        if code in seen:
            continue
        seen.add(code)
        meta = _BADGE_METADATA[code]
        label = meta["label"]
        detail = item.get("detail")
        if isinstance(detail, str) and detail.strip():
            label = f"{label} ({detail.strip()})"
        badges.append(
            {
                "code": code,
                "label": label,
                "css_class": meta["css_class"],
                "emphasis": meta["emphasis"],
            }
        )

    badges.sort(key=lambda b: CANONICAL_ORDER.index(b["code"]))
    return badges
