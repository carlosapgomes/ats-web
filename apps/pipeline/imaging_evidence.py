"""Verificador determinístico de evidência de imagem abdominal (design D6).

A hard rule de imagem de Ecoendoscopia/CPRE **não** pode confiar em campos
declarados pelo LLM: um excerpt inventado, um trecho de solicitação rotulado
como achado ou um texto presente apenas em anexo jamais podem satisfazer o
requisito. Este módulo recebe exclusivamente ``Case.extracted_text`` (o
relatório principal) e valida, nesta ordem:

1. ``evidence_context_excerpt`` corresponde a trecho REAL e ÚNICO do relatório
   após normalização conservadora (Unicode/caixa/espaços);
2. o contexto é uma única oração/entrada (sem fronteira interna de frase);
3. ``finding_excerpt`` é substring do próprio contexto;
4. modalidade e anatomia são **rederivadas** do mesmo contexto por aliases
   versionados e devem coincidir com os enums declarados — aliases conflitantes
   ou mais de uma imagem no mesmo contexto são ambíguos (fail-closed);
5. o contexto contém predicado positivo de resultado ou está sob heading
   estrito de linha (``Conclusão:``/``Achados:``/``Laudo:``/``Resultado:``);
   substantivos isolados nunca são marcadores positivos;
6. marcador de intenção/estado futuro na MESMA oração domina e rejeita.

Evidência rejeitada é rebaixada a insuficiente: produz pendência/deny, nunca
aceite, e nunca é descartada em silêncio (o outcome carrega ``reason_code``).

A data do exame é apenas preservada; não há janela de validade.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# ── Alias catalog (versionado) ──────────────────────────────────────────────

_ALIAS_VERSION = "2026-09"

_MODALITY_ALIASES: tuple[tuple[str, str], ...] = (
    ("colangiopancreatografia por ressonancia", "mrcp"),
    ("colangiografia por ressonancia", "mrcp"),
    ("colangiorressonancia", "mrcp"),
    ("ressonancia magnetica", "mri"),
    ("tomografia computadorizada", "ct"),
    ("ultrassonografia", "ultrasound"),
    ("ressonancia", "mri"),
    ("tomografia", "ct"),
    ("ultrassom", "ultrasound"),
    ("ecografia", "ultrasound"),
    ("cprm", "mrcp"),
    ("usg", "ultrasound"),
    ("tc", "ct"),
    ("rm", "mri"),
)

_SITE_ALIASES: tuple[tuple[str, str], ...] = (
    ("andar superior do abdome", "upper_abdomen"),
    ("abdome superior", "upper_abdomen"),
    ("abdome alto", "upper_abdomen"),
    ("hepatobiliar", "hepatobiliary"),
    ("vias biliares", "hepatobiliary"),
    ("abdominal", "abdomen"),
    ("abdomen", "abdomen"),
    ("abdome", "abdomen"),
)

# Substantivos isolados NUNCA são marcadores positivos: apenas o heading
# estrito de linha (label + ':') ou um predicado de resultado qualificam.
_RESULT_PREDICATES: tuple[str, ...] = (
    "demonstrou",
    "demonstrada",
    "demonstrado",
    "evidenciou",
    "evidenciada",
    "evidenciado",
    "identificou",
    "identificada",
    "identificado",
    "revelou",
    "revelada",
    "revelado",
    "mostrou",
    "constatou",
    "observou",
    "visualizou",
    "apresentou",
)

_HEADING_LABELS: tuple[str, ...] = ("conclusao", "achados", "laudo", "resultado")

# Marcador de intenção/estado futuro domina qualquer palavra isolada
# (``laudo``/``resultado``) na mesma oração.
_INTENT_MARKERS: tuple[str, ...] = (
    "solicitacao",
    "solicitamos",
    "solicitado",
    "solicitada",
    "solicitante",
    "solicita",
    "solicito",
    "pedido",
    "pedida",
    "agendado",
    "agendada",
    "aguardando",
    "aguarda",
    "programado",
    "programada",
    "indicacao",
    "indicado",
    "indicada",
    "previsto",
    "prevista",
    "a realizar",
)

_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.;!?]")

REASON_CONTEXT_NOT_ANCHORED = "imaging_context_not_anchored"
REASON_FINDING_NOT_ANCHORED = "imaging_finding_excerpt_not_anchored"
REASON_MODALITY_MISMATCH = "imaging_modality_mismatch"
REASON_SITE_MISMATCH = "imaging_site_mismatch"
REASON_NO_RESULT_PREDICATE = "imaging_no_result_predicate"
REASON_INTENT_MARKER = "imaging_intent_marker"
REASON_AMBIGUOUS = "imaging_ambiguous_context"


@dataclass(frozen=True)
class ImagingEvidenceOutcome:
    """Desfecho determinístico de uma entrada de imagem abdominal."""

    modality: str
    anatomical_site: str
    report_finding_present: str
    verified: bool
    reason_code: str
    evidence_context_excerpt: str
    finding_excerpt: str | None = None
    exam_datetime_iso: str | None = None


@dataclass(frozen=True)
class ImagingVerificationReport:
    """Evidências verificadas + rejeitadas (rejeição nunca é silenciosa)."""

    outcomes: tuple[ImagingEvidenceOutcome, ...]

    @property
    def verified(self) -> tuple[ImagingEvidenceOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if outcome.verified)


def normalize_evidence_text(value: str) -> str:
    """Normalização conservadora: Unicode, caixa e espaços (sem fuzzy match)."""
    normalized = unicodedata.normalize("NFD", value)
    without_diacritics = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return " ".join(without_diacritics.lower().split())


def verify_abdominal_imaging_evidence(
    *,
    entries: Any,
    main_report_text: str,
) -> ImagingVerificationReport:
    """Valida as entradas declaradas contra o texto do relatório principal.

    Args:
        entries: ``common_preop.abdominal_imaging`` declarado pelo LLM1.
        main_report_text: ``Case.extracted_text`` (relatório principal). Nunca
            deve receber texto de anexo.

    Returns:
        ``ImagingVerificationReport`` com um outcome por entrada declarada.
    """
    if not isinstance(entries, (list, tuple)):
        return ImagingVerificationReport(outcomes=())

    normalized_report = normalize_evidence_text(main_report_text or "")
    # Preserva a estrutura de linhas para reconhecer headings estritos
    # (``Conclusão:``) sem depender de normalização que colapsa quebras.
    normalized_lines = "\n".join(normalize_evidence_text(line) for line in (main_report_text or "").splitlines())
    outcomes: list[ImagingEvidenceOutcome] = []
    for entry in entries:
        if isinstance(entry, dict):
            outcomes.append(
                _verify_entry(
                    entry=entry,
                    normalized_report=normalized_report,
                    normalized_lines=normalized_lines,
                )
            )
    return ImagingVerificationReport(outcomes=tuple(outcomes))


def _verify_entry(
    *,
    entry: dict[str, Any],
    normalized_report: str,
    normalized_lines: str,
) -> ImagingEvidenceOutcome:
    declared_modality = str(entry.get("modality") or "other")
    declared_site = str(entry.get("anatomical_site") or "unspecified")
    context_raw = str(entry.get("evidence_context_excerpt") or "")
    finding_raw = entry.get("finding_excerpt")
    finding_text = str(finding_raw) if isinstance(finding_raw, str) else None
    exam_datetime_iso = entry.get("exam_datetime_iso")
    exam_datetime = str(exam_datetime_iso) if isinstance(exam_datetime_iso, str) else None
    normalized_context = normalize_evidence_text(context_raw)

    def _outcome(
        *,
        verified: bool,
        reason_code: str,
        modality: str = declared_modality,
        site: str = declared_site,
    ) -> ImagingEvidenceOutcome:
        return ImagingEvidenceOutcome(
            modality=modality,
            anatomical_site=site,
            report_finding_present="yes" if verified else "no",
            verified=verified,
            reason_code=reason_code,
            evidence_context_excerpt=context_raw,
            finding_excerpt=finding_text,
            exam_datetime_iso=exam_datetime,
        )

    if not normalized_context or normalized_context not in normalized_report:
        return _outcome(verified=False, reason_code=REASON_CONTEXT_NOT_ANCHORED)

    # Contexto precisa ser delimitável a uma única oração/entrada.
    if _CLAUSE_BOUNDARY_PATTERN.search(normalized_context.rstrip(".")):
        return _outcome(verified=False, reason_code=REASON_AMBIGUOUS)

    # Contexto duplicado no relatório é ambíguo (não se sabe qual ocorrência).
    if normalized_report.count(normalized_context) > 1:
        return _outcome(verified=False, reason_code=REASON_AMBIGUOUS)

    modality_value = _rederive_value(text=normalized_context, aliases=_MODALITY_ALIASES)
    site_value = _rederive_value(text=normalized_context, aliases=_SITE_ALIASES)

    # Aliases conflitantes (mais de uma modalidade/anatomia no MESMO contexto)
    # são ambíguos. A ausência total de alias é mismatch: um trecho real não
    # relacionado não pode ancorar modalidade/anatomia inventadas.
    modality, modality_conflict = modality_value if modality_value is not None else (declared_modality, False)
    site, site_conflict = site_value if site_value is not None else (declared_site, False)
    if modality_conflict or site_conflict:
        # Sentinela determinística: aliases conflitantes nunca podem ser
        # coincidentemente aceitos por um perfil (``other``/``unspecified`` não
        # pertencem a nenhum ``accepted_imaging``).
        return _outcome(
            verified=False,
            reason_code=REASON_AMBIGUOUS,
            modality="other" if modality_conflict else modality,
            site="unspecified" if site_conflict else site,
        )
    if modality_value is None or modality != declared_modality:
        return _outcome(verified=False, reason_code=REASON_MODALITY_MISMATCH, modality=modality, site=site)
    if site_value is None or site != declared_site:
        return _outcome(verified=False, reason_code=REASON_SITE_MISMATCH, modality=modality, site=site)

    if not _context_has_result_form(normalized_lines=normalized_lines, normalized_context=normalized_context):
        return _outcome(
            verified=False,
            reason_code=REASON_NO_RESULT_PREDICATE,
            modality=modality,
            site=site,
        )
    if _has_intent_marker(normalized_context):
        return _outcome(verified=False, reason_code=REASON_INTENT_MARKER, modality=modality, site=site)

    normalized_finding = normalize_evidence_text(finding_text or "")
    if not normalized_finding or normalized_finding not in normalized_context:
        return _outcome(
            verified=False,
            reason_code=REASON_FINDING_NOT_ANCHORED,
            modality=modality,
            site=site,
        )

    return _outcome(verified=True, reason_code="", modality=modality, site=site)


def _rederive_value(
    *,
    text: str,
    aliases: tuple[tuple[str, str], ...],
) -> tuple[str, bool] | None:
    """Rederiva o valor do enum a partir do contexto, por aliases versionados.

    Aliases mais longos têm prioridade e mascaram o trecho já reconhecido, de
    modo que ``abdome superior`` não seja contado também como ``abdome``.

    Returns:
        ``(valor, conflito)`` ou ``None`` quando nenhum alias é reconhecido.
    """
    mask = [False] * len(text)
    found: set[str] = set()
    for alias, value in sorted(aliases, key=lambda item: -len(item[0])):
        pattern = re.compile(re.escape(alias)) if " " in alias else re.compile(rf"\b{re.escape(alias)}\b")
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            if any(mask[start:end]):
                continue
            for index in range(start, end):
                mask[index] = True
            found.add(value)
    if not found:
        return None
    return next(iter(found)), len(found) > 1


def _context_has_result_form(*, normalized_lines: str, normalized_context: str) -> bool:
    """True quando o contexto tem predicado de resultado ou heading estrito.

    Heading é reconhecido apenas por forma estrita de linha
    (``Conclusão:``/``Achados:``/``Laudo:``/``Resultado:``) — os substantivos
    isolados nunca são marcadores positivos (D6).
    """
    if _has_result_predicate(normalized_context):
        return True

    for line in normalized_lines.split("\n"):
        if normalized_context not in line:
            continue
        for label in _HEADING_LABELS:
            if line.startswith((f"{label}:", f"{label} :")):
                return True
    return False


def _has_result_predicate(normalized_context: str) -> bool:
    for predicate in _RESULT_PREDICATES:
        if re.search(rf"\b{predicate}\b", normalized_context) is not None:
            return True
    return False


def _has_intent_marker(normalized_context: str) -> bool:
    for marker in _INTENT_MARKERS:
        if " " in marker:
            if marker in normalized_context:
                return True
            continue
        if re.search(rf"\b{marker}\b", normalized_context) is not None:
            return True
    return False


__all__ = [
    "ImagingEvidenceOutcome",
    "ImagingVerificationReport",
    "normalize_evidence_text",
    "verify_abdominal_imaging_evidence",
]
