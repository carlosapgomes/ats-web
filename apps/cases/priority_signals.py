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


_FOREIGN_BODY_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsem\s+corpo\s+estranho\b"),
    re.compile(r"\bcorpo\s+estranho\s+descartad[oa]\b"),
    re.compile(r"\bnega\s+(?:a\s+)?ingestao\s+de\s+corpo\s+estranho\b"),
    re.compile(r"\bnao\s+ha\s+corpo\s+estranho\b"),
)


def _has_structured_foreign_body(structured_data: dict[str, object]) -> bool:
    if _eda_subtype(structured_data) == "foreign_body":
        return True
    eda = _get_dict(structured_data, "eda")
    if _get_str(eda, "indication_category").strip().lower() == "foreign_body":
        return True
    if _get_bool(eda, "foreign_body_suspected"):
        return True
    return False


def _resolve_foreign_body(
    structured_data: dict[str, object],
    normalized_text: str,
) -> list[dict[str, object]]:
    # Precedence: a structured positive signal validated by LLM1 represents
    # the current request and prevails over a negated textual fallback
    # (e.g. a historical mention). The textual fallback alone never fires
    # when an explicit negation is present.
    if _has_structured_foreign_body(structured_data):
        return [_signal("foreign_body")]
    for pattern in _FOREIGN_BODY_NEGATION_PATTERNS:
        if pattern.search(normalized_text):
            return []
    if re.search(r"\bcorpo\s+estranho\b", normalized_text):
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


_ECHOENDOSCOPY_TERMS: tuple[str, ...] = (
    "ecoendoscopia",
    "eco endoscopia",
    "eco-endoscopia",
    "ultrassonografia endoscopica",
    "ultrassom endoscopico",
)

# Conservative per-occurrence local context for the EUS acronym. Mirrors the
# scope detector's contract; kept here because apps.cases must not import
# from apps.pipeline (layering: pipeline depends on cases).
_EUS_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.;!?]|\n")
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
    if re.search(r"\beus\b", normalized) is None:
        return False
    for eus_match in re.finditer(r"\beus\b", normalized):
        left_boundaries = list(_EUS_CLAUSE_BOUNDARY_PATTERN.finditer(normalized, 0, eus_match.start()))
        clause_start = left_boundaries[-1].end() if left_boundaries else 0
        right_boundary = _EUS_CLAUSE_BOUNDARY_PATTERN.search(normalized, eus_match.end())
        clause_end = right_boundary.start() if right_boundary else len(normalized)
        prefix = normalized[clause_start : eus_match.start()]
        suffix = normalized[eus_match.end() : clause_end]
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
    for term in _ECHOENDOSCOPY_TERMS:
        if term in normalized_text:
            return [_signal("echoendoscopy")]
    if _contains_eus_with_request_context(normalized_text):
        return [_signal("echoendoscopy")]
    return []


# ── Esophageal dilation ───────────────────────────────────────────────────


_ESOPHAGEAL_DILATION_TERMS: tuple[str, ...] = (
    "dilatacao esofagica",
    "dilatacao do esofago",
    "dilatacao de esofago",
    "dilatacao endoscopica esofagica",
)


def _resolve_esophageal_dilation(
    structured_data: dict[str, object],
    normalized_text: str,
) -> list[dict[str, object]]:
    if _eda_subtype(structured_data) == "esophageal_dilation":
        return [_signal("esophageal_dilation")]
    # Conservative: never accept the isolated word "dilatação".
    for term in _ESOPHAGEAL_DILATION_TERMS:
        if term in normalized_text:
            return [_signal("esophageal_dilation")]
    return []


# ── Gastrostomy ───────────────────────────────────────────────────────────


_GASTROSTOMY_TERMS: tuple[str, ...] = (
    "gtt",
    "gastrostomia",
    "gastrostomy",
    "peg",
)

# Request/exam/procedure intent near the gastrostomy term.
_GASTROSTOMY_CONTEXT_PATTERN = re.compile(
    r"\b(solicit\w*|indic\w*|exame\w*|procedimento\w*|\beda\b|endoscopi\w*|confeccao\w*|programar\w*|realizac\w*)\b"
)

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
    for term in _GASTROSTOMY_TERMS:
        for match in re.finditer(rf"\b{re.escape(term)}\b", normalized_text):
            window = normalized_text[max(0, match.start() - 40) : match.end() + 40]
            if _GASTROSTOMY_HISTORICAL_PATTERN.search(window):
                continue
            if _GASTROSTOMY_CONTEXT_PATTERN.search(window):
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
