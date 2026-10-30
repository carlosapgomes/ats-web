"""Extração determinística e mascaramento da identidade do paciente (PI-01..PI-09).

Módulo puro (sem Django/DB): extrai ``Paciente``, ``Nome Social`` e ``CNS``
do cabeçalho padronizado do relatório de regulação já limpo
(``strip_watermark_and_extract_record``) e substitui os valores conhecidos
por placeholders em qualquer texto destinado a um LLM.

Isto é minimização por melhor esforço, não anonimização garantida:
identificadores desconhecidos (nomes citados sem cabeçalho, datas, origem)
podem permanecer. Falha/ambiguidade conhecida falha fechado — quem chama
deve bloquear o envio em vez de cair para o texto original (PI-09).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NAME_PLACEHOLDER = "[NOME_REMOVIDO]"
SOCIAL_NAME_PLACEHOLDER = "[NOME_SOCIAL_REMOVIDO]"
CNS_PLACEHOLDER = "[CNS_REMOVIDO]"

_KNOWN_LABEL_PREFIXES: tuple[str, ...] = (
    "relatorio",
    "governo",
    "secretaria",
    "central",
    "municipio",
    "motivo",
    "unid",
    "complemento",
    "resumo",
    "abertura",
    "codigo",
    "dias",
    "data",
    "hora",
    "pag",
    "paciente",
    "nome social",
    "cns",
)
_NAME_SUFFIX_PATTERN = re.compile(r"\s+-\s+Idade\b.*$", flags=re.IGNORECASE | re.DOTALL)
_CNS_LABEL_PATTERN = re.compile(r"\bCNS\s*:\s*([^\n]*)", flags=re.IGNORECASE)
_SOCIAL_LABEL_PATTERN = re.compile(r"\bNome\s+Social\s*:\s*([^\n]*)", flags=re.IGNORECASE)
_PACIENTE_LINE_PATTERN = re.compile(r"^Paciente\s*:\s*(.*)$", flags=re.IGNORECASE)
_NON_NAME_CHARS = re.compile(r"[^A-Za-zÀ-ÖØ-öø-ÿ'’\-\s]")

_ACCENT_CLASSES: dict[str, str] = {}
for _chars, _cls in (
    ("aáàâãä", "aáàâãä"),
    ("eéèêë", "eéèêë"),
    ("iíìîï", "iíìîï"),
    ("oóòôõö", "oóòôõö"),
    ("uúùûü", "uúùûü"),
    ("cç", "cç"),
    ("nñ", "nñ"),
):
    for _ch in _chars:
        _ACCENT_CLASSES[_ch] = _cls


@dataclass(frozen=True)
class PatientIdentity:
    """Identidade conhecida do paciente, extraída programaticamente."""

    name: str | None
    social_name: str | None
    cns: str | None
    status: str  # "extracted" | "absent" | "ambiguous"

    @property
    def has_known_identity(self) -> bool:
        return bool(self.name or self.social_name or self.cns)


class PatientIdentityError(RuntimeError):
    """Preparação da identidade falhou; envio ao LLM deve ser bloqueado."""


class PatientIdentityLeakError(PatientIdentityError):
    """Identificador conhecido ainda presente no texto destinado ao LLM."""


def extract_patient_identity(text: str) -> PatientIdentity:
    """Extrai nome, nome social e CNS do cabeçalho padronizado.

    Apenas a primeira ocorrência de ``Nome Social:`` é autoritativa (o
    cabeçalho repete por página e, nas páginas seguintes, a linha seguinte
    ao rótulo pode ser texto clínico). Divergências entre cabeçalhos
    repetidos tornam o resultado ``ambiguous`` (falha fechada).
    """
    ambiguous = False
    names: list[str] = []
    name, name_ambiguous = _extract_names(text)
    if name is not None:
        names.append(name)
    ambiguous = ambiguous or name_ambiguous

    cns, cns_ambiguous = _extract_cns(text)
    ambiguous = ambiguous or cns_ambiguous

    social_name = _extract_social_name(text)

    resolved_name = names[0] if names else None
    if ambiguous:
        status = "ambiguous"
    elif resolved_name is not None:
        status = "extracted"
    else:
        status = "absent"
    return PatientIdentity(
        name=resolved_name,
        social_name=social_name,
        cns=cns,
        status=status,
    )


def identity_from_stored_fields(
    *,
    name: str | None,
    social_name: str | None,
    cns: str | None,
    status: str | None,
) -> PatientIdentity | None:
    """Reconstrói a identidade persistida; ``None`` se nunca extraída."""
    if status not in ("extracted", "absent", "ambiguous", "failed"):
        return None
    return PatientIdentity(
        name=(name or None),
        social_name=(social_name or None),
        cns=(cns or None),
        status=status,
    )


def require_maskable(identity: PatientIdentity) -> None:
    """Falha fechado quando a identidade é ambígua ou a extração falhou (PI-09)."""
    if identity.status in ("ambiguous", "failed"):
        raise PatientIdentityError(
            f"Identidade do paciente não mascarável (status={identity.status}); envio ao LLM bloqueado."
        )


def mask_patient_identity(text: str, identity: PatientIdentity) -> str:
    """Substitui os valores conhecidos por placeholders em todo o texto."""
    if not text or not identity.has_known_identity:
        return text
    result = text
    for value, placeholder in _mask_pairs(identity):
        result = _value_pattern(value).sub(placeholder, result)
    return result


def mask_identity_in_value(value: object, identity: PatientIdentity) -> object:
    """Máscara recursiva em estruturas JSON-like (apenas valores string)."""
    if isinstance(value, str):
        return mask_patient_identity(value, identity)
    if isinstance(value, dict):
        return {key: mask_identity_in_value(item, identity) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_identity_in_value(item, identity) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_identity_in_value(item, identity) for item in value)
    return value


def count_identity_occurrences(text: str, identity: PatientIdentity) -> dict[str, int]:
    """Contagens por tipo para auditoria enxuta (sem valores, PI-10)."""
    counts: dict[str, int] = {}
    for kind, value in (("name", identity.name), ("social_name", identity.social_name), ("cns", identity.cns)):
        if value:
            counts[kind] = len(_value_pattern(value).findall(text or ""))
    return counts


def find_identity_leaks(text: str, identity: PatientIdentity) -> list[str]:
    """Tipos de identificador conhecido ainda presentes no texto."""
    leaks: list[str] = []
    for kind, value in (("name", identity.name), ("social_name", identity.social_name), ("cns", identity.cns)):
        if value and _value_pattern(value).search(text or ""):
            leaks.append(kind)
    return leaks


def assert_no_identity_leaks(text: str, identity: PatientIdentity) -> None:
    """Guarda final antes de qualquer chamada LLM (PI-09)."""
    leaks = find_identity_leaks(text, identity)
    if leaks:
        raise PatientIdentityLeakError(f"Identificador do paciente presente no texto do LLM: {', '.join(leaks)}.")


def _mask_pairs(identity: PatientIdentity) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if identity.social_name:
        pairs.append((identity.social_name, SOCIAL_NAME_PLACEHOLDER))
    if identity.name:
        pairs.append((identity.name, NAME_PLACEHOLDER))
    if identity.cns:
        pairs.append((identity.cns, CNS_PLACEHOLDER))
    pairs.sort(key=lambda pair: -len(pair[0]))
    return pairs


def _value_pattern(value: str) -> re.Pattern[str]:
    """Regex do valor completo: fronteiras, caixa/acentos/espaços flexíveis."""
    if value.isdigit():
        body = r"[ .]?".join(re.escape(digit) for digit in value)
        return re.compile(rf"(?<!\d){body}(?!\d)")
    tokens = value.split()
    body = r"\s+".join(_flexible_token(token) for token in tokens)
    return re.compile(rf"(?<!\w){body}(?!\w)", flags=re.IGNORECASE)


def _flexible_token(token: str) -> str:
    parts: list[str] = []
    for char in token:
        lower = char.lower()
        if lower in _ACCENT_CLASSES:
            parts.append(f"[{_ACCENT_CLASSES[lower]}]")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks).strip().lower()


def _is_name_like(value: str) -> bool:
    candidate = value.strip()
    if not candidate or len(candidate) < 2:
        return False
    if any(char.isdigit() for char in candidate):
        return False
    if ":" in candidate:
        return False
    if _NON_NAME_CHARS.search(candidate):
        return False
    normalized = _normalize(candidate)
    if any(normalized.startswith(prefix) for prefix in _KNOWN_LABEL_PREFIXES):
        return False
    return any(char.isalpha() for char in candidate)


def _clean_name_candidate(raw: str) -> str | None:
    candidate = _NAME_SUFFIX_PATTERN.sub("", raw or "").strip().strip("-").strip()
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate if _is_name_like(candidate) else None


def _extract_names(text: str) -> tuple[str | None, bool]:
    lines = (text or "").splitlines()
    candidates: list[str] = []
    saw_paciente_label = False
    for index, line in enumerate(lines):
        match = _PACIENTE_LINE_PATTERN.match(line.strip())
        if match is None:
            continue
        saw_paciente_label = True
        inline = _clean_name_candidate(match.group(1))
        if inline is not None:
            candidates.append(inline)
            continue
        if match.group(1).strip():
            continue  # valor após o rótulo que não é nome: não inventar
        if index > 0:
            before = _clean_name_candidate(lines[index - 1])
            if before is not None:
                candidates.append(before)
    if not candidates:
        return None, saw_paciente_label
    distinct = {_normalize(candidate) for candidate in candidates}
    if len(distinct) > 1:
        return None, True
    return candidates[0], False


def _extract_cns(text: str) -> tuple[str | None, bool]:
    values: set[str] = set()
    ambiguous = False
    for match in _CNS_LABEL_PATTERN.finditer(text or ""):
        raw = match.group(1).strip()
        if not raw or "cadastrado" in _normalize(raw):
            continue
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 15:
            values.add(digits)
        elif digits:
            ambiguous = True
    if len(values) > 1:
        return None, True
    return (next(iter(values)) if values else None), ambiguous


def _extract_social_name(text: str) -> str | None:
    match = _SOCIAL_LABEL_PATTERN.search(text or "")
    if match is None:
        return None
    inline = _clean_name_candidate(match.group(1))
    if inline is not None:
        return inline
    if match.group(1).strip():
        return None
    remainder = (text or "")[match.end() :]
    for line in remainder.splitlines():
        candidate_line = line.strip()
        if not candidate_line:
            continue
        if re.fullmatch(r"\d{3,}", candidate_line):
            return None  # token de watermark, não nome social
        return _clean_name_candidate(candidate_line)
    return None
