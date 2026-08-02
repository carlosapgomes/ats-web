# Generated manually for Slice 002 — AddField priority_signals + backfill de abertos.

"""Add Case.priority_signals (versioned canonical projection) and backfill
open cases deterministically.

Snapshot note (historical stability): migrations must be self-contained, so
this module carries a copy of the v1 resolver from
``apps/cases/priority_signals.py``. The copy is covered by an equivalence
test (``test_priority_signals_migration.py``) against the runtime resolver
for the six canonical codes — comparing full payloads (code, category,
detail, version, order), not only codes. When the resolver evolves (v2+),
this snapshot stays frozen so historical backfills remain reproducible.
"""

import re
import unicodedata

from django.db import migrations, models

PRIORITY_SIGNAL_VERSION = 1

CANONICAL_ORDER = (
    "foreign_body",
    "caustic_ingestion",
    "pediatric",
    "echoendoscopy",
    "esophageal_dilation",
    "gastrostomy",
)

CATEGORY_BY_CODE = {
    "foreign_body": "clinical_alert",
    "caustic_ingestion": "clinical_alert",
    "pediatric": "special_population",
    "echoendoscopy": "special_procedure",
    "esophageal_dilation": "special_procedure",
    "gastrostomy": "special_procedure",
}

_SUPPORTED_SUBTYPES = frozenset({"foreign_body", "echoendoscopy", "esophageal_dilation", "gastrostomy"})

# ── Shared per-occurrence machinery (mirror of apps/cases/priority_signals.py) ──
# Anchored: before-patterns end at the prefix ('$'), after-patterns start at
# the suffix ('^'); context is never borrowed from another procedure in the
# clause.

_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.;!?]|\n")

# Terms accepted as items in a small requested list. EDA procedures resolve
# as signals; 'cpre' and 'colonoscopia' are CONTEXT tokens only (the list
# remains a current request) and never produce signals themselves.
_REQUEST_LIST_TERM_SOURCE = (
    r"ecoendoscopia|eco\s+endoscopia|eco-endoscopia"
    r"|ultrassonografia\s+endoscopica|ultrassom\s+endoscopico"
    r"|dilatacao\s+esofagica|dilatacao\s+do\s+esofago|dilatacao\s+de\s+esofago"
    r"|dilatacao\s+endoscopica\s+esofagica"
    r"|gastrostomia|gastrostomy|gtt|peg"
    r"|eus"
    r"|cpre|colonoscopia"
)

# Zero or more requested-list items ('CPRE e', 'colonoscopia,') preceding the
# target occurrence. ONE shared grammar: request, negation and history all
# span the same closed chain, so a qualifier can never be short-circuited by
# an internal request stem ('indicação de CPRE e …' stays negated/historical).
_REQUEST_LIST_PREFIX_SOURCE = r"(?:\s+(?:" + _REQUEST_LIST_TERM_SOURCE + r")\b(?:\s+(?:e\b|,))?)*"

# Request stem before the occurrence, with approved connectors (fully
# optional, so 'Solicitação: EUS' and 'Solicito EUS' both anchor), an
# optional ':' and the shared closed list chain
# ('Solicito EDA com ecoendoscopia e dilatação esofágica',
# 'Solicito CPRE e ecoendoscopia').
_REQUEST_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:solicit|encaminh|indic|programar|confeccao)\w*\b"
    r"(?:\s*:?\s*(?:realizacao\s+de|nov[oa]|atual\s+de|de|para)?)"
    r"(?:\s+\beda\b\s+(?:com|para))?" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
)

_LABEL_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:exame|procedimento)\b\s*(?:de|para|:)?\s*$"
    r"|\bmotivo\s+da\s+solicitacao\b\s*:?\s*(?:eda\s+(?:com|para))?\s*$"
)

_REQUEST_AFTER_OCCURRENCE_PATTERN = re.compile(r"^\s*(?:solicit|indic|encaminh)\w*\b")

_HISTORICAL_AFTER_OCCURRENCE_PATTERN = re.compile(
    r"^\s*(?:ja\s+)?(?:foi\s+)?realizad[oa]\b"
    r"|^\s*(?:previo|previa|anterior|previamente)\b"
    r"|^\s*no\s+historico\b"
)
# 'histórico de solicitação/indicação de' e 'histórico de encaminhamento
# para' abrangem a mesma cadeia fechada (C22).
_HISTORICAL_BEFORE_OCCURRENCE_PATTERN = re.compile(
    r"\b(?:realizou)\b\s+$"
    r"|\b(?:previo|previa|anterior|previamente)\b\s*(?:de\s*)?:?\s*$"
    r"|\bhistorico\s+de\b\s*$"
    r"|\bhistorico\s+de\b\s+(?:solicitacao|indicacao)\s+de\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
    r"|\bhistorico\s+de\b\s+encaminhamento\s+para\b" + _REQUEST_LIST_PREFIX_SOURCE + r"\s*$"
)

# Negation qualifiers attached to this occurrence (after or before).
# As formas 'indicação de' / 'não solicito' abrangem a MESMA cadeia fechada
# do pedido (C21), ancoradas no final do prefixo.
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

_FOREIGN_BODY_TERM_PATTERN = re.compile(r"\bcorpo\s+estranho\b")

_ECHOENDOSCOPY_TERM_PATTERN = re.compile(
    r"\becoendoscopia\b"
    r"|\beco\s+endoscopia\b"
    r"|\beco-endoscopia\b"
    r"|\bultrassonografia\s+endoscopica\b"
    r"|\bultrassom\s+endoscopico\b"
)

_ESOPHAGEAL_DILATION_TERM_PATTERN = re.compile(
    r"\bdilatacao\s+esofagica\b"
    r"|\bdilatacao\s+do\s+esofago\b"
    r"|\bdilatacao\s+de\s+esofago\b"
    r"|\bdilatacao\s+endoscopica\s+esofagica\b"
)

_GASTROSTOMY_TERM_PATTERN = re.compile(r"\b(?:gtt|gastrostomia|gastrostomy|peg)\b")
_GASTROSTOMY_HISTORICAL_PATTERN = re.compile(
    r"\b(previo|previa|anterior|portador\w*|realizou|realizad[oa]|em\s+uso|ja\s+(tem|possui))\b"
)

_EUS_PATTERN = re.compile(r"\beus\b")

_CAUSTIC_KEYWORDS = ("caustic", "corrosiv", "soda caustica", "acido")
_INGESTION_VERBS = ("ingeriu", "ingestao", "ingerir", "ingerido")

_CAUSTIC_NEGATION_PATTERNS = (
    re.compile(r"nega\s+ingestao\s+de\s+(caustic|corrosiv|soda\s+caustica|acido)", re.IGNORECASE),
    re.compile(r"sem\s+ingestao\s+de\s+(corrosiv|caustic)", re.IGNORECASE),
    re.compile(r"nao\s+ingeriu\s+(soda\s+caustica|caustic|corrosiv)", re.IGNORECASE),
    re.compile(r"nega\s+(ter\s+)?ingerid[oa]\s+(produto\s+)?(caustic|corrosiv|soda\s+caustica|acido)", re.IGNORECASE),
    re.compile(r"sem\s+(relato\s+de\s+)?ingestao[\s,;.:!?]", re.IGNORECASE),
)

_CAUSTIC_TIME_PATTERNS = (
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


def _normalize_text(value):
    decomposed = unicodedata.normalize("NFD", value)
    without_diacritics = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(without_diacritics.lower().split())


def _get_dict(payload, key):
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _get_str(payload, key):
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _get_bool(payload, key):
    if isinstance(payload, dict):
        return payload.get(key) is True
    return False


def _get_int(payload, key):
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _signal(code, detail=""):
    return {
        "code": code,
        "category": CATEGORY_BY_CODE[code],
        "detail": detail,
        "version": PRIORITY_SIGNAL_VERSION,
    }


def _eda_subtype(structured_data):
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


def _occurrence_contexts(normalized_text, pattern):
    """Return (prefix, suffix) local clause contexts for each boundary-safe match."""
    contexts = []
    for match in pattern.finditer(normalized_text):
        left_boundaries = list(_CLAUSE_BOUNDARY_PATTERN.finditer(normalized_text, 0, match.start()))
        clause_start = left_boundaries[-1].end() if left_boundaries else 0
        right_boundary = _CLAUSE_BOUNDARY_PATTERN.search(normalized_text, match.end())
        clause_end = right_boundary.start() if right_boundary else len(normalized_text)
        contexts.append((normalized_text[clause_start : match.start()], normalized_text[match.end() : clause_end]))
    return contexts


def _is_historical_occurrence(prefix, suffix):
    return (
        _HISTORICAL_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
        or _HISTORICAL_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
    )


def _is_negated_occurrence(prefix, suffix):
    return (
        _NEGATION_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _NEGATION_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
    )


def _is_current_request_occurrence(prefix, suffix):
    return (
        _REQUEST_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _LABEL_BEFORE_OCCURRENCE_PATTERN.search(prefix) is not None
        or _REQUEST_AFTER_OCCURRENCE_PATTERN.match(suffix) is not None
    )


def _resolve_pediatric(structured_data):
    patient = _get_dict(structured_data, "patient")
    age = _get_int(patient, "age")
    if age is not None:
        if age < 16:
            return [_signal("pediatric", detail="%d anos" % age)]
        return []
    eda = _get_dict(structured_data, "eda")
    if _get_bool(eda, "is_pediatric"):
        return [_signal("pediatric")]
    return []


def _has_structured_foreign_body(structured_data):
    if _eda_subtype(structured_data) == "foreign_body":
        return True
    eda = _get_dict(structured_data, "eda")
    if _get_str(eda, "indication_category").strip().lower() == "foreign_body":
        return True
    if _get_bool(eda, "foreign_body_suspected"):
        return True
    return False


def _has_positive_foreign_body_occurrence(normalized_text):
    for prefix, suffix in _occurrence_contexts(normalized_text, _FOREIGN_BODY_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix):
            continue
        if _is_negated_occurrence(prefix, suffix):
            continue
        return True
    return False


def _resolve_foreign_body(structured_data, normalized_text):
    if _has_structured_foreign_body(structured_data):
        return [_signal("foreign_body")]
    if _has_positive_foreign_body_occurrence(normalized_text):
        return [_signal("foreign_body")]
    return []


def _has_caustic_keyword_near_ingestion(normalized):
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


def _extract_time_from_text(text):
    for pattern in _CAUSTIC_TIME_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return ""


def _resolve_caustic(source_text):
    if not isinstance(source_text, str) or not source_text.strip():
        return []
    normalized = _normalize_text(source_text)
    for pattern in _CAUSTIC_NEGATION_PATTERNS:
        if pattern.search(normalized):
            return []
    if not _has_caustic_keyword_near_ingestion(normalized):
        return []
    return [_signal("caustic_ingestion", detail=_extract_time_from_text(source_text))]


def _contains_eus_with_request_context(normalized):
    """EUS usa as mesmas guardas por ocorrência (C15): histórico, negação,
    depois contexto de pedido/label ancorado."""
    for prefix, suffix in _occurrence_contexts(normalized, _EUS_PATTERN):
        if _is_historical_occurrence(prefix, suffix):
            continue
        if _is_negated_occurrence(prefix, suffix):
            continue
        if _is_current_request_occurrence(prefix, suffix):
            return True
    return False


def _resolve_echoendoscopy(structured_data, normalized_text):
    if _eda_subtype(structured_data) == "echoendoscopy":
        return [_signal("echoendoscopy")]
    for prefix, suffix in _occurrence_contexts(normalized_text, _ECHOENDOSCOPY_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix) or _is_negated_occurrence(prefix, suffix):
            continue
        if _is_current_request_occurrence(prefix, suffix):
            return [_signal("echoendoscopy")]
    if _contains_eus_with_request_context(normalized_text):
        return [_signal("echoendoscopy")]
    return []


def _resolve_esophageal_dilation(structured_data, normalized_text):
    if _eda_subtype(structured_data) == "esophageal_dilation":
        return [_signal("esophageal_dilation")]
    for prefix, suffix in _occurrence_contexts(normalized_text, _ESOPHAGEAL_DILATION_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix) or _is_negated_occurrence(prefix, suffix):
            continue
        if _is_current_request_occurrence(prefix, suffix):
            return [_signal("esophageal_dilation")]
    return []


def _resolve_gastrostomy(structured_data, normalized_text):
    if _eda_subtype(structured_data) == "gastrostomy":
        return [_signal("gastrostomy")]
    for prefix, suffix in _occurrence_contexts(normalized_text, _GASTROSTOMY_TERM_PATTERN):
        if _is_historical_occurrence(prefix, suffix):
            continue
        if _is_negated_occurrence(prefix, suffix):
            continue
        if _GASTROSTOMY_HISTORICAL_PATTERN.search(prefix + " " + suffix):
            continue
        if _is_current_request_occurrence(prefix, suffix):
            return [_signal("gastrostomy")]
    return []


def _snapshot_resolve_priority_signals(structured_data, source_text):
    """Snapshot v1 — payload equivalente ao resolvedor runtime (teste dedicado)."""
    normalized_text = _normalize_text(source_text or "")
    signals = []
    signals.extend(_resolve_pediatric(structured_data))
    signals.extend(_resolve_foreign_body(structured_data, normalized_text))
    signals.extend(_resolve_caustic(source_text or ""))
    signals.extend(_resolve_echoendoscopy(structured_data, normalized_text))
    signals.extend(_resolve_esophageal_dilation(structured_data, normalized_text))
    signals.extend(_resolve_gastrostomy(structured_data, normalized_text))

    seen = set()
    deduped = []
    for signal in signals:
        code = signal["code"]
        if code in seen:
            continue
        seen.add(code)
        deduped.append(signal)
    deduped.sort(key=lambda s: CANONICAL_ORDER.index(s["code"]))
    return deduped


def backfill_priority_signals(apps, schema_editor):
    """Preenche priority_signals apenas para casos abertos com lista vazia.

    - status != CLEANED;
    - lista ainda vazia (não sobrescreve valores existentes);
    - structured_data ausente/malformado vira {} e o texto é resolvido;
    - sem LLM, sem eventos, sem mudança de status/decisão/agenda;
    - idempotente (chunks razoáveis).
    """
    Case = apps.get_model("cases", "Case")
    db_alias = schema_editor.connection.alias

    qs = (
        Case.objects.using(db_alias)
        .exclude(status="CLEANED")
        .filter(priority_signals=[])
        .only("case_id", "structured_data", "extracted_text")
    )

    for case in qs.iterator(chunk_size=500):
        structured_data = case.structured_data
        if not isinstance(structured_data, dict):
            structured_data = {}
        signals = _snapshot_resolve_priority_signals(
            structured_data=structured_data,
            source_text=case.extracted_text or "",
        )
        if not signals:
            continue
        Case.objects.using(db_alias).filter(case_id=case.case_id).update(priority_signals=signals)


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0012_post_acceptance_issue_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="priority_signals",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            code=backfill_priority_signals,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
