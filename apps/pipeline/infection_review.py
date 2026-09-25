"""Verificador determinístico da revisão infecciosa consultiva de EDA + GTT (D7/D8).

A revisão infecciosa **não** é regra: nada aqui entra em
``PolicyEvaluation.failed_requirements``, em ``priority_signals`` ou no
reconciliador LLM2. Este módulo recebe somente as entradas declaradas pelo LLM1
(schema 4.0, vocabulário fechado) e o relatório principal
(``Case.extracted_text``) e valida, nesta ordem:

1. a categoria pertence ao vocabulário fechado e o trecho é ÚNICO no relatório
   principal normalizado conservadoramente (Unicode/caixa/espaços);
2. a categoria é **rederivada** do próprio trecho por aliases versionados e
   deve coincidir com a declarada — aliases conflitantes são ambíguos e trecho
   real sem alias é mismatch (fail-closed);
3. ``normal/normal``, ``abnormal``, ``positive``, ``negative``, ``febrile`` e
   os estados de antibiótico só são aceitos com marcador textual explícito
   local e afirmativo; classificação não comprovada é rebaixada a
   ``unclassified`` preservando valor e trecho ancorados;
4. marcador histórico local domina a temporalidade declarada: a evidência é
   histórica e não pode acionar destaque;
5. itens são deduplicados por categoria + valor + trecho e ordenados pelo
   vocabulário canônico (categoria, classificação, valor, trecho).

O destaque (``concerning``) é derivado AQUI, em código, nunca confiado a
boolean do LLM: exige temporalidade não histórica E classificação no conjunto
preocupante (alterado/positivo/febril documentados, infectologia atual ou
antibiótico atual/iniciado/escalonado). Nenhum limiar, faixa de referência ou
unidade é inferido: um número sem interpretação explícita do laudo permanece
``unclassified`` e não alerta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from apps.pipeline.imaging_evidence import normalize_evidence_text

# Versão do catálogo de aliases/marcadores: mudanças de reconhecimento exigem
# nova versão (auditoria do que cada release considerava explícito).
ALIAS_VERSION = "2026-09"

# Campo do schema LLM1 4.0 que carrega a coleção infecciosa dentro do item
# ``eda_gastrostomy``. É consultivo: a visão efêmera do LLM2 o remove (D7/D8).
INFECTION_EVIDENCE_FIELD = "infection_evidence"

# Chave do artefato 4.0 onde o pipeline persiste a revisão verificada
# (``suggested_action``) para o presenter médico. Não é coluna de model.
INFECTION_EVIDENCE_ARTIFACT_KEY = "infection_review"

# ── Vocabulário fechado (design D7) ────────────────────────────────────────

INFECTION_CATEGORY_ORDER: tuple[str, ...] = (
    "leukocytes",
    "crp",
    "procalcitonin",
    "lactate",
    "culture",
    "temperature_or_fever",
    "infectious_disease",
    "antibiotic",
)

INFECTION_ASSESSMENT_ORDER: tuple[str, ...] = (
    "normal_explicit",
    "abnormal_explicit",
    "positive_explicit",
    "negative_explicit",
    "febrile_explicit",
    "current_care_explicit",
    "antibiotic_in_use",
    "antibiotic_started",
    "antibiotic_escalated",
    "unclassified",
)

UNCLASSIFIED_ASSESSMENT = "unclassified"

# Classificações que acionam o destaque consultivo quando a temporalidade não é
# histórica. ``unclassified``/normal/negativo aparecem sem alertar.
CONCERNING_ASSESSMENTS: frozenset[str] = frozenset(
    {
        "abnormal_explicit",
        "positive_explicit",
        "febrile_explicit",
        "current_care_explicit",
        "antibiotic_in_use",
        "antibiotic_started",
        "antibiotic_escalated",
    }
)

REASON_OUT_OF_VOCABULARY = "infection_evidence_not_in_vocabulary"
REASON_EXCERPT_NOT_ANCHORED = "infection_excerpt_not_anchored"
REASON_EXCERPT_AMBIGUOUS = "infection_excerpt_ambiguous"
REASON_CATEGORY_MISMATCH = "infection_category_mismatch"
REASON_CATEGORY_AMBIGUOUS = "infection_category_ambiguous"
REASON_DUPLICATE = "infection_evidence_duplicate"

# ── Aliases de categoria (versionados) ─────────────────────────────────────

_CATEGORY_ALIASES: tuple[tuple[str, str], ...] = (
    ("hemoculturas", "culture"),
    ("hemocultura", "culture"),
    ("uroculturas", "culture"),
    ("urocultura", "culture"),
    ("culturas", "culture"),
    ("cultura", "culture"),
    ("leucocitos", "leukocytes"),
    ("leucocitose", "leukocytes"),
    ("leucograma", "leukocytes"),
    ("proteina c reativa", "crp"),
    ("procalcitonina", "procalcitonin"),
    ("antibioticoterapia", "antibiotic"),
    ("antibioticos", "antibiotic"),
    ("antibiotico", "antibiotic"),
    ("antimicrobianos", "antibiotic"),
    ("antimicrobiano", "antibiotic"),
    ("infectologistas", "infectious_disease"),
    ("infectologista", "infectious_disease"),
    ("infectologia", "infectious_disease"),
    ("lactato", "lactate"),
    ("temperatura", "temperature_or_fever"),
    ("afebril", "temperature_or_fever"),
    ("febril", "temperature_or_fever"),
    ("febre", "temperature_or_fever"),
    ("crp", "crp"),
    ("pcr", "crp"),
)

# ── Marcadores explícitos de classificação (locais, afirmativos) ───────────
#
# Nenhum limiar/faixa de referência: a classificação só é aceita quando o
# PRÓPRIO LAUDO a documenta textualmente. Temperatura numérica isolada não é
# marcador (inferir febre por número seria threshold).

_ASSESSMENT_MARKERS: dict[str, tuple[str, ...]] = {
    "normal_explicit": (
        "normal",
        "normais",
        "normalidade",
        "sem alteracoes",
        "dentro da normalidade",
        "afebril",
    ),
    "abnormal_explicit": (
        "alterado",
        "alterada",
        "alterados",
        "alteradas",
        "elevado",
        "elevada",
        "elevados",
        "elevadas",
        "aumentado",
        "aumentada",
        "aumentados",
        "aumentadas",
        "leucocitose",
        "acima do valor de referencia",
        "acima da referencia",
        "elevacao",
    ),
    "positive_explicit": (
        "positivo",
        "positiva",
        "positivos",
        "positivas",
        "crescimento bacteriano",
        "crescimento de",
        "identificado crescimento",
    ),
    "negative_explicit": (
        "negativo",
        "negativa",
        "negativos",
        "negativas",
        "sem crescimento",
        "ausencia de crescimento",
        "nao houve crescimento",
    ),
    "febrile_explicit": ("febre", "febril", "hipertermia"),
    "current_care_explicit": (
        "infectologia",
        "infectologista",
        "parecer infectologico",
        "avaliacao infectologica",
    ),
    "antibiotic_in_use": (
        "em uso de",
        "faz uso de",
        "esta em uso",
        "em antibioticoterapia",
        "uso atual de",
        "uso de antibiotico",
        "uso de antimicrobiano",
    ),
    "antibiotic_started": (
        "iniciado",
        "iniciada",
        "inicio de",
        "iniciou",
        "introduzido",
        "introduzida",
        "introducao de",
    ),
    "antibiotic_escalated": (
        "escalonado",
        "escalonada",
        "escalonamento",
        "escalonou",
        "ampliacao do espectro",
        "ampliou o espectro",
    ),
}

# Marcadores de contexto histórico: quando presentes no trecho, DOMINAM a
# temporalidade declarada (evidência histórica nunca alerta).
_HISTORICAL_MARKERS: tuple[str, ...] = (
    "historico",
    "historia previa",
    "previamente",
    "previo",
    "previa",
    "pregresso",
    "pregressa",
    "anterior",
    "passado",
)

# Negação ancorada ao próprio marcador: "sem febre"/"não apresenta febre"/
# "nega febre" nunca afirmam o estado declarado (fail-safe: rebaixa a
# classificação em vez de rebaixar a evidência).
_NEGATION_BEFORE_MARKER_PATTERN = re.compile(
    r"\b(?:sem|nao|nega|negou|negad[oa]|ausencia\s+de|ausentes?|descartad[oa]|contraindicad[oa])\b"
    r"(?:\s+\w+){0,2}\s*$"
)

_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.;!?]|\n")


# ── DTOs ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InfectionEvidenceView:
    """Evidência ancorada e apresentável de uma categoria fechada (D7)."""

    category: str
    assessment: str
    temporal_status: str
    value_text: str
    evidence_excerpt: str
    concerning: bool


@dataclass(frozen=True)
class InfectionEvidenceRejection:
    """Entrada declarada não confirmada (rejeição nunca silenciosa)."""

    category: str
    reason_code: str
    evidence_excerpt: str


@dataclass(frozen=True)
class InfectionCategoryGroup:
    """Grupo de evidências de uma categoria, na ordem canônica."""

    category: str
    items: tuple[InfectionEvidenceView, ...]


@dataclass(frozen=True)
class InfectionReviewView:
    """Revisão consultiva verificada (apresentação, nunca regra de policy)."""

    groups: tuple[InfectionCategoryGroup, ...] = ()
    concerning: bool = False
    rejected: tuple[InfectionEvidenceRejection, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.groups


# ── Verificador ────────────────────────────────────────────────────────────


def verify_infection_evidence(*, entries: Any, main_report_text: str) -> InfectionReviewView:
    """Valida as entradas declaradas contra o relatório principal (D7/R2/R3).

    Args:
        entries: ``infection_evidence`` do item ``eda_gastrostomy`` (LLM1 4.0).
        main_report_text: ``Case.extracted_text`` — nunca texto de anexo.

    Returns:
        ``InfectionReviewView`` com os grupos confirmados (inclusive
        normal/negativo/``unclassified``), o destaque derivado em código e as
        rejeições com motivo técnico.
    """
    normalized_report = normalize_evidence_text(main_report_text or "")
    accepted: list[InfectionEvidenceView] = []
    rejected: list[InfectionEvidenceRejection] = []
    seen: set[tuple[str, str, str]] = set()

    for entry in entries if isinstance(entries, (list, tuple)) else ():
        if not isinstance(entry, dict):
            continue
        outcome = _verify_entry(entry=entry, normalized_report=normalized_report)
        if isinstance(outcome, InfectionEvidenceRejection):
            rejected.append(outcome)
            continue
        key = (outcome.category, outcome.value_text, outcome.evidence_excerpt)
        if key in seen:
            rejected.append(
                InfectionEvidenceRejection(
                    category=outcome.category,
                    reason_code=REASON_DUPLICATE,
                    evidence_excerpt=outcome.evidence_excerpt,
                )
            )
            continue
        seen.add(key)
        accepted.append(outcome)

    accepted.sort(key=_evidence_sort_key)
    groups = tuple(
        InfectionCategoryGroup(
            category=category,
            items=tuple(item for item in accepted if item.category == category),
        )
        for category in INFECTION_CATEGORY_ORDER
        if any(item.category == category for item in accepted)
    )
    return InfectionReviewView(
        groups=groups,
        concerning=any(item.concerning for item in accepted),
        rejected=tuple(rejected),
    )


def serialize_infection_review(view: InfectionReviewView) -> dict[str, object]:
    """Projeção JSON-serializável da revisão para o artefato 4.0 (D7).

    Somente evidências confirmadas são persistidas: trecho inventado/duplicado
    não chega ao relatório médico como fato. O destaque viaja derivado do
    verificador, nunca recalculado por heurística de apresentação.
    """
    return {
        "concerning": view.concerning,
        "groups": [
            {
                "category": group.category,
                "items": [
                    {
                        "assessment": item.assessment,
                        "temporal_status": item.temporal_status,
                        "value_text": item.value_text,
                        "evidence_excerpt": item.evidence_excerpt,
                        "concerning": item.concerning,
                    }
                    for item in group.items
                ],
            }
            for group in view.groups
        ],
    }


def _verify_entry(
    *,
    entry: dict[str, Any],
    normalized_report: str,
) -> InfectionEvidenceView | InfectionEvidenceRejection:
    category = str(entry.get("category") or "")
    assessment = str(entry.get("assessment") or "")
    raw_excerpt = entry.get("evidence_excerpt")
    excerpt = str(raw_excerpt) if isinstance(raw_excerpt, str) else ""
    value_text = entry.get("value_text")
    value = str(value_text) if isinstance(value_text, str) else ""
    temporal_status = str(entry.get("temporal_status") or "unknown")

    if category not in INFECTION_CATEGORY_ORDER or assessment not in INFECTION_ASSESSMENT_ORDER:
        return InfectionEvidenceRejection(
            category=category,
            reason_code=REASON_OUT_OF_VOCABULARY,
            evidence_excerpt=excerpt.strip(),
        )

    normalized_excerpt = normalize_evidence_text(excerpt)
    if not normalized_excerpt or normalized_excerpt not in normalized_report:
        return InfectionEvidenceRejection(
            category=category,
            reason_code=REASON_EXCERPT_NOT_ANCHORED,
            evidence_excerpt=excerpt.strip(),
        )
    if normalized_report.count(normalized_excerpt) > 1:
        return InfectionEvidenceRejection(
            category=category,
            reason_code=REASON_EXCERPT_AMBIGUOUS,
            evidence_excerpt=excerpt.strip(),
        )

    derived_category = _rederive_category(normalized_excerpt=normalized_excerpt)
    if derived_category is None:
        return InfectionEvidenceRejection(
            category=category,
            reason_code=REASON_CATEGORY_MISMATCH,
            evidence_excerpt=excerpt.strip(),
        )
    if derived_category[1]:
        return InfectionEvidenceRejection(
            category=category,
            reason_code=REASON_CATEGORY_AMBIGUOUS,
            evidence_excerpt=excerpt.strip(),
        )
    if derived_category[0] != category:
        return InfectionEvidenceRejection(
            category=category,
            reason_code=REASON_CATEGORY_MISMATCH,
            evidence_excerpt=excerpt.strip(),
        )

    resolved_assessment = _resolve_assessment(declared=assessment, normalized_excerpt=normalized_excerpt)
    resolved_temporal = _resolve_temporal_status(declared=temporal_status, normalized_excerpt=normalized_excerpt)
    return InfectionEvidenceView(
        category=category,
        assessment=resolved_assessment,
        temporal_status=resolved_temporal,
        value_text=value.strip(),
        evidence_excerpt=excerpt.strip(),
        concerning=resolved_temporal != "historical" and resolved_assessment in CONCERNING_ASSESSMENTS,
    )


def _resolve_assessment(*, declared: str, normalized_excerpt: str) -> str:
    """Classificação aceita somente com marcador explícito local (D7 passo 3/5)."""
    if declared == UNCLASSIFIED_ASSESSMENT:
        return UNCLASSIFIED_ASSESSMENT
    if _has_affirmative_marker(markers=_ASSESSMENT_MARKERS[declared], normalized_excerpt=normalized_excerpt):
        return declared
    return UNCLASSIFIED_ASSESSMENT


def _resolve_temporal_status(*, declared: str, normalized_excerpt: str) -> str:
    """Marcador histórico local domina a temporalidade declarada (D7 passo 4)."""
    if declared == "historical" or _has_any_marker(
        normalized_excerpt=normalized_excerpt,
        markers=_HISTORICAL_MARKERS,
    ):
        return "historical"
    return "current" if declared == "current" else "unknown"


def _has_affirmative_marker(*, markers: tuple[str, ...], normalized_excerpt: str) -> bool:
    """True quando há marcador explícito no trecho que NÃO está negado localmente."""
    for marker in markers:
        for match in _find_marker_occurrences(normalized_excerpt=normalized_excerpt, marker=marker):
            prefix, _suffix = _clause_context(normalized_excerpt, match.start(), match.end())
            if _NEGATION_BEFORE_MARKER_PATTERN.search(prefix) is None:
                return True
    return False


def _find_marker_occurrences(*, normalized_excerpt: str, marker: str) -> list[re.Match[str]]:
    pattern = re.compile(re.escape(marker)) if " " in marker else re.compile(rf"\b{re.escape(marker)}\b")
    return list(pattern.finditer(normalized_excerpt))


def _has_any_marker(*, markers: tuple[str, ...], normalized_excerpt: str) -> bool:
    """True quando qualquer marcador do conjunto ocorre no trecho."""
    return any(_find_marker_occurrences(normalized_excerpt=normalized_excerpt, marker=marker) for marker in markers)


def _rederive_category(*, normalized_excerpt: str) -> tuple[str, bool] | None:
    """Rederiva a categoria do próprio trecho por aliases versionados (D7 passo 2).

    Aliases mais longos mascaram o trecho já reconhecido (``hemoculturas`` não
    conta também como ``cultura``).

    Returns:
        ``(categoria, conflito)`` ou ``None`` quando nenhum alias é reconhecido.
    """
    mask = [False] * len(normalized_excerpt)
    found: set[str] = set()
    for alias, value in sorted(_CATEGORY_ALIASES, key=lambda item: -len(item[0])):
        for match in _find_marker_occurrences(normalized_excerpt=normalized_excerpt, marker=alias):
            start, end = match.start(), match.end()
            if any(mask[start:end]):
                continue
            for index in range(start, end):
                mask[index] = True
            found.add(value)
    if not found:
        return None
    return next(iter(found)), len(found) > 1


def _clause_context(normalized_excerpt: str, start: int, end: int) -> tuple[str, str]:
    """Contexto local (prefixo/sufixo na mesma oração) de uma ocorrência."""
    left_boundaries = list(_CLAUSE_BOUNDARY_PATTERN.finditer(normalized_excerpt, 0, start))
    clause_start = left_boundaries[-1].end() if left_boundaries else 0
    right_boundary = _CLAUSE_BOUNDARY_PATTERN.search(normalized_excerpt, end)
    clause_end = right_boundary.start() if right_boundary else len(normalized_excerpt)
    return normalized_excerpt[clause_start:start], normalized_excerpt[end:clause_end]


def _evidence_sort_key(item: InfectionEvidenceView) -> tuple[int, int, str, str]:
    return (
        INFECTION_CATEGORY_ORDER.index(item.category),
        INFECTION_ASSESSMENT_ORDER.index(item.assessment),
        item.value_text,
        item.evidence_excerpt,
    )
