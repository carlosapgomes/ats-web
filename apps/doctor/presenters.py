"""Doctor report presenter — 7-block medical report without Matrix/Room coupling.

Ports the logic from legacy build_room2_case_summary_message and helpers
into a standalone Django presenter for the doctor decision screen.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _format_exam_datetime(value: Any) -> str:
    """Parse exam_datetime_iso and return formatted date string, or empty string if invalid.

    Accepts ISO formats:
    - ``2025-12-01`` (date only)       -> ``01/12/2025``
    - ``2025-12-01T10:00:00``          -> ``01/12/2025 10:00``
    - ``2025-12-01T10:00:00Z``         -> ``01/12/2025 10:00``
    - ``2025-12-01T10:00:00-03:00``    -> ``01/12/2025 10:00``

    Returns empty string if value is None, empty, or unparseable.
    Never raises ValueError.
    """
    if not isinstance(value, str) or not value.strip():
        return ""

    iso_str = value.strip()
    if iso_str.endswith("Z"):
        iso_str = f"{iso_str[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return ""

    # Check if the source had a time component (contains 'T' or ' ' after date)
    has_time = "T" in value.strip()

    if has_time:
        return parsed.strftime("%d/%m/%Y %H:%M")
    return parsed.strftime("%d/%m/%Y")


def _extract_nested(payload: dict[str, Any], *keys: str) -> Any:
    """Return nested dictionary value by key path, or None when missing."""
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _format_scalar(value: Any) -> str:
    """Format scalar value to Portuguese display text."""
    if value is None:
        return "(vazio)"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, str):
        if not value.strip():
            return "(vazio)"
        return _map_presentation_value(value)
    return str(value)


def _map_presentation_value(value: str) -> str:
    """Map internal enum-like values to Portuguese display labels."""
    mapping: dict[str, str] = {
        "accept": "aceitar",
        "deny": "negar",
        "none": "nenhum",
        "anesthesist": "anestesista",
        "anesthesist_icu": "anestesista_uti",
        "yes": "sim",
        "no": "não",
        "unknown": "indeterminado",
        "bleeding": "sangramento",
        "moderate": "moderado",
        "low": "baixo",
        "high": "alto",
    }
    return mapping.get(value, value)


def _format_value_or_fallback(value: Any) -> str:
    """Return human-readable value with 'não informado' fallback."""
    if value is None:
        return "não informado"
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return "não informado"
        return _map_presentation_value(normalized)
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _format_unknown_with_evidence(value: Any) -> str:
    """Return clearer wording when scalar value is unknown in source evidence."""
    formatted = _format_value_or_fallback(value)
    if formatted in {"indeterminado"}:
        return "indeterminado (sem evidência no laudo)"
    return formatted


def _is_yes_precheck(value: Any) -> bool:
    """Return True when precheck enum-like value explicitly means yes."""
    return isinstance(value, str) and value.strip().lower() == "yes"


# ── Caustic ingestion detection helpers ─────────────────────────────────


def _normalize_caustic_text(value: str) -> str:
    """Normalize text for caustic detection: remove accents, lowercase, collapse whitespace."""
    # Decompose (NFD) then remove combining characters (category Mn = Mark, Nonspacing)
    decomposed = unicodedata.normalize("NFD", value)
    stripped_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    normalized = stripped_accents.lower()
    # Collapse whitespace
    return " ".join(normalized.split())


_CAUSTIC_KEYWORDS: set[str] = {
    "caustic",
    "corrosiv",
    "soda caustica",
    "acido",
}

_INGESTION_VERBS: set[str] = {
    "ingeriu",
    "ingestao",
    "ingerir",
    "ingerido",
}

# Negation patterns: compiled on normalized (unaccented, lowercase) text
# Use unaccented terms since normalization removes accents before matching.
_CAUSTIC_NEGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"nega\s+ingestao\s+de\s+(caustic|corrosiv|soda\s+caustica|acido)", re.IGNORECASE),
    re.compile(r"sem\s+ingestao\s+de\s+(corrosiv|caustic)", re.IGNORECASE),
    re.compile(r"nao\s+ingeriu\s+(soda\s+caustica|caustic|corrosiv)", re.IGNORECASE),
    re.compile(r"nega\s+(ter\s+)?ingerid[oa]\s+(produto\s+)?(caustic|corrosiv|soda\s+caustica|acido)", re.IGNORECASE),
    # General "sem ingestao" or "sem relato de ingestao" near caustic context
    re.compile(r"sem\s+(relato\s+de\s+)?ingestao[\s,;.:!?]", re.IGNORECASE),
]

_CAUSTIC_TIME_PATTERNS: list[re.Pattern[str]] = [
    # Match both "há" and "ha" (accented and unaccented)
    re.compile(
        r"h[aá]\s+(cerca\s+de\s+|aproximadamente\s+)?[\w\s]+?(semanas?|dias?|meses?|anos?|minutos?|horas?)",
        re.IGNORECASE,
    ),
    re.compile(r"em\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", re.IGNORECASE),
    # Also match "ha ... atras" unaccented
    re.compile(
        r"h[aá]\s+(cerca\s+de\s+|aproximadamente\s+)?[\w\s]+?(semanas?|dias?|meses?|anos?|minutos?|horas?)\s+atr[aá]s",
        re.IGNORECASE,
    ),
]


def _detect_caustic_ingestion(text: str) -> list[str]:
    """Detect caustic/corrosive ingestion in source_text and return alert lines.

    Returns a list with:
    - Empty list when no ingestion detected or negation is explicit.
    - One or two lines with the alert header and time info when positive.

    Detection runs on normalized (unaccented, lowercase) text.
    Time extraction runs on original text but matches both accented and
    unaccented variants.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    normalized = _normalize_caustic_text(text)

    # Check for explicit negation first (on normalized text)
    for pattern in _CAUSTIC_NEGATION_PATTERNS:
        if pattern.search(normalized):
            return []

    # Detect caustic/corrosive ingestion (on normalized text)
    if not _has_caustic_keyword_near_ingestion(normalized):
        return []

    # Extract time expression from original text (for literal display)
    time_text = _extract_time_from_text(text)

    lines: list[str] = ["⚠️ ingestão cáustica/corrosiva relatada: sim"]
    if time_text:
        lines.append(f"tempo desde a ingestão: {time_text}")
    else:
        lines.append("tempo desde a ingestão: não informado no relatório")

    return lines


def _has_caustic_keyword_near_ingestion(normalized: str) -> bool:
    """Return True if text contains caustic/corrosive keyword near an ingestion verb.

    Input must already be normalized (unaccented, lowercase).
    All keywords and verbs are also unaccented.
    """
    # Check for keyword + ingestion verb proximity
    for keyword in _CAUSTIC_KEYWORDS:
        if keyword not in normalized:
            continue

        # Check if there's an ingestion verb near the keyword (within ~80 chars)
        for verb in _INGESTION_VERBS:
            for match in re.finditer(re.escape(verb), normalized):
                start = max(0, match.start() - 20)
                end = min(len(normalized), match.end() + 80)
                window = normalized[start:end]
                if keyword in window:
                    return True

    return False


def _extract_time_from_text(text: str) -> str:
    """Extract the first time expression from text, or empty string.

    Patterns match both accented and unaccented variants (e.g. "há" and "ha").
    Returns the matched text from the original source as-is.
    """
    for pattern in _CAUSTIC_TIME_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return ""


def _is_absent_exam_result(value: Any) -> bool:
    """Return True when result_value indicates absence of exam.

    Normalizes the value (lowercase, strip, remove accents) and compares
    against a conservative list of absence indicators.
    """
    if not isinstance(value, str) or not value.strip():
        return False

    normalized = value.strip().lower()
    # Remove acentos portugueses
    normalized = (
        normalized.replace("\u00e1", "a")  # á
        .replace("\u00e0", "a")  # à
        .replace("\u00e3", "a")  # ã
        .replace("\u00e2", "a")  # â
        .replace("\u00e9", "e")  # é
        .replace("\u00ea", "e")  # ê
        .replace("\u00ed", "i")  # í
        .replace("\u00f3", "o")  # ó
        .replace("\u00f4", "o")  # ô
        .replace("\u00f5", "o")  # õ
        .replace("\u00fa", "u")  # ú
        .replace("\u00e7", "c")  # ç
    )
    # Compact spaces
    normalized = " ".join(normalized.split())

    absence_values = {
        "sem exame",
        "sem exames",
        "nao realizado",
        "nao realizada",
        "nao consta",
        "ausente",
        "sem laudo",
        "sem resultado",
    }
    return normalized in absence_values


@dataclass
class DoctorReportPresenter:
    """Presenter that generates a 7-block medical report for the doctor decision screen.

    Inputs mirror the legacy build_room2_case_summary_* functions but use
    Django Case model fields directly — no Matrix/Room coupling.
    """

    structured_data: dict[str, Any] = field(default_factory=dict)
    summary_text: str = ""
    suggested_action: dict[str, Any] = field(default_factory=dict)
    recent_denial_context: dict[str, Any] | None = None
    source_text: str = ""

    # ── Public API ───────────────────────────────────────────────────────

    def build_report(self) -> dict[str, Any]:
        """Return the full report structure with blocks, context, and denial info.

        Returns a dict with:

        - ``blocks``: dict of 7 block names → list[str]
        - ``context``: dict with procedure, origin, transfusion_lines,
          tracked_exam_lines, pediatric
        - ``recent_denial``: dict | None with lines and display fields
        """
        return {
            "blocks": self._build_all_blocks(),
            "context": self._build_context(),
            "recent_denial": self._build_recent_denial(),
        }

    # ── Clinical alert lines ────────────────────────────────────────────

    def _build_clinical_alert_lines(self) -> list[str]:
        """Detect caustic/corrosive ingestion in source_text and return alert lines.

        Returns a list with:
        - Empty list when no ingestion detected or negation is explicit.
        - One or two lines with the alert header and time info when positive.
        """
        return _detect_caustic_ingestion(self.source_text)

    def _build_comorbidities_line(self) -> str:
        """Build the comorbidities display line from structured_data.

        Returns one of:
        - "Comorbidades descritas: <comma-separated names>" when items exist.
        - "Comorbidades descritas: sem comorbidades descritas no relatório" when
          the field is present but empty or all items are invalid.
        - "Comorbidades descritas: extração de comorbidades não disponível neste caso"
          when the field is absent (old case without extraction).
        """
        preop = _extract_nested(self.structured_data, "preop_screening")
        if not isinstance(preop, dict) or "comorbidities_described" not in preop:
            return "Comorbidades descritas: extração de comorbidades não disponível neste caso"

        items = preop.get("comorbidities_described")
        if not isinstance(items, list) or not items:
            return "Comorbidades descritas: sem comorbidades descritas no relatório"

        seen: set[str] = set()
        names: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            normalized = name.strip()
            if normalized not in seen:
                seen.add(normalized)
                names.append(normalized)

        if not names:
            return "Comorbidades descritas: sem comorbidades descritas no relatório"

        return f"Comorbidades descritas: {', '.join(names)}"

    def build_text_report(self) -> str:
        """Render the report as a markdown-like text block for audit/testing."""
        report = self.build_report()
        context = report["context"]
        blocks = report["blocks"]
        denial = report["recent_denial"]

        lines: list[str] = ["# Resumo técnico da regulação\n"]

        # Context
        lines.append(f"procedimento solicitado: {context['procedure']}")
        lines.append(context["origin"])
        lines.extend(context["transfusion_lines"])
        lines.extend(context["tracked_exam_lines"])
        if context["pediatric"]:
            lines.append(context["pediatric"])
        if context.get("clinical_alert_lines"):
            for alert_line in context["clinical_alert_lines"]:
                lines.append(alert_line)
        if context.get("comorbidities_line"):
            lines.append(context["comorbidities_line"])
        lines.append("")

        # Blocks
        block_labels = [
            ("resumo_clinico", "Resumo clínico"),
            ("achados_criticos", "Achados críticos"),
            ("pendencias_criticas", "Pendências críticas"),
            ("decisao_sugerida", "Decisão sugerida"),
            ("suporte_recomendado", "Suporte recomendado"),
            ("asa_estimado", "ASA estimado"),
            ("motivo_objetivo", "Motivo objetivo"),
        ]
        for key, label in block_labels:
            lines.append(f"## {label}:")
            lines.extend(blocks[key])
            lines.append("")

        # Recent denial
        if denial:
            lines.append("## Histórico de negativa recente:")
            lines.extend(denial["lines"])
            lines.append("")

        return "\n".join(lines)

    # ── Block builders ───────────────────────────────────────────────────

    def _build_all_blocks(self) -> dict[str, list[str]]:
        return {
            "resumo_clinico": self._build_clinical_summary(),
            "achados_criticos": self._build_critical_findings(),
            "pendencias_criticas": self._build_critical_pending(),
            "decisao_sugerida": self._build_decision(),
            "suporte_recomendado": self._build_support(),
            "asa_estimado": self._build_asa(),
            "motivo_objetivo": self._build_objective_reason(),
        }

    def _build_clinical_summary(self) -> list[str]:
        """Normalize clinical summary into 2-4 line block."""
        stripped = [line.strip() for line in self.summary_text.splitlines() if line.strip()]
        if not stripped:
            return [
                "Resumo clínico não informado.",
                "Consulte o relatório original para contexto clínico.",
            ]
        if len(stripped) >= 2:
            return stripped[:4]
        one_liner = stripped[0]
        words = one_liner.split()
        if len(words) >= 4:
            midpoint = len(words) // 2
            first_half = " ".join(words[:midpoint]).strip()
            second_half = " ".join(words[midpoint:]).strip()
            if first_half and second_half:
                return [first_half, second_half]
        return [one_liner, f"Base clínica: {one_liner}"]

    def _build_critical_findings(self) -> list[str]:
        hb = _extract_nested(self.structured_data, "eda", "labs", "hb_g_dl")
        platelets = _extract_nested(self.structured_data, "eda", "labs", "platelets_per_mm3")
        inr = _extract_nested(self.structured_data, "eda", "labs", "inr")
        ecg_present = _extract_nested(self.structured_data, "eda", "ecg", "report_present")
        ecg_alert = _extract_nested(self.structured_data, "eda", "ecg", "abnormal_flag")
        return [
            f"- Hb: {_format_value_or_fallback(hb)}",
            f"- Plaquetas: {_format_value_or_fallback(platelets)}",
            f"- INR: {_format_value_or_fallback(inr)}",
            f"- ECG presente: {_format_value_or_fallback(ecg_present)}",
            f"- ECG sinal de alerta: {_format_unknown_with_evidence(ecg_alert)}",
        ]

    def _build_critical_pending(self) -> list[str]:
        labs_pass = _extract_nested(self.structured_data, "policy_precheck", "labs_pass")
        ecg_present = _extract_nested(self.structured_data, "policy_precheck", "ecg_present")
        labs_failed = _extract_nested(self.structured_data, "policy_precheck", "labs_failed_items")

        failed_text = "não informado"
        if isinstance(labs_failed, list):
            normalized = [str(item).strip() for item in labs_failed if str(item).strip()]
            if normalized:
                failed_text = ", ".join(normalized)
            elif isinstance(labs_pass, str) and labs_pass.strip().lower() == "unknown":
                failed_text = "indeterminadas (sem evidência no laudo)"

        lab_status = _format_unknown_with_evidence(labs_pass)
        ecg_status = _format_unknown_with_evidence(ecg_present)

        return [
            f"- Laboratório obrigatório (pré-check): {lab_status}",
            f"- ECG obrigatório (pré-check): {ecg_status}",
            f"- Pendências de laboratório: {failed_text}",
        ]

    def _build_decision(self) -> list[str]:
        suggestion = self.suggested_action.get("suggestion")
        if isinstance(suggestion, str):
            return [f"- {_format_scalar(suggestion)}"]
        return ["- não informado"]

    def _build_support(self) -> list[str]:
        support = self.suggested_action.get("support_recommendation")
        if isinstance(support, str):
            return [f"- {_format_scalar(support)}"]
        return ["- não informado"]

    def _build_asa(self) -> list[str]:
        asa_payload = self.suggested_action.get("asa")
        if isinstance(asa_payload, dict):
            display_text = asa_payload.get("display_text")
            if isinstance(display_text, str) and display_text.strip():
                return [f"- {display_text.strip()}"]

            bucket = asa_payload.get("bucket")
            if isinstance(bucket, str) and bucket.strip():
                return [f"- {self._format_asa_bucket(bucket.strip())}"]

        structured_asa = _extract_nested(self.structured_data, "eda", "asa", "bucket")
        if isinstance(structured_asa, str) and structured_asa.strip():
            return [f"- {self._format_asa_bucket(structured_asa.strip())}"]

        return ["- não informado"]

    def _format_asa_bucket(self, value: str) -> str:
        if value == "insufficient_data":
            return "não foi possível estimar com os dados apresentados"
        return _map_presentation_value(value)

    def _build_objective_reason(self) -> list[str]:
        suggestion = self.suggested_action.get("suggestion")
        decision_label = _format_scalar(suggestion) if isinstance(suggestion, str) else "não informado"
        support = self.suggested_action.get("support_recommendation")
        support_label = _format_scalar(support) if isinstance(support, str) else "não informado"

        decision_key = suggestion.strip().lower() if isinstance(suggestion, str) else ""

        if decision_key == "deny":
            return self._build_deny_reason_lines()
        if decision_key == "accept":
            return self._build_accept_reason_lines(decision_label, support_label)
        return self._build_default_reason_lines(decision_label, support_label)

    def _build_accept_reason_lines(self, decision_label: str, support_label: str) -> list[str]:
        first_line = "- Aceito com suporte a definir."
        if support_label == "nenhum":
            first_line = "- Aceito sem suporte adicional."
        elif support_label in {"anestesista", "anestesista_uti"}:
            first_line = f"- Aceito com suporte de {support_label}."

        lines = [first_line]
        return lines

    def _build_deny_reason_lines(self) -> list[str]:
        causes = self._build_deny_causes()
        visible = causes[:2]
        cause_text = "; ".join(visible)
        if len(causes) > 2:
            cause_text = f"{cause_text}; e outras pendências críticas"
        return [f"- Negado por: {cause_text}."]

    def _build_deny_causes(self) -> list[str]:
        reason_code = self.suggested_action.get("reason_code")
        reason_text = self.suggested_action.get("reason_text")
        cause = self._map_reason_code_to_cause(reason_code, reason_text)
        if cause is not None:
            return [cause]

        causes: list[str] = []
        excluded_from_flow = _extract_nested(self.structured_data, "policy_precheck", "excluded_from_eda_flow")
        excluded_request = _extract_nested(self.suggested_action, "policy_alignment", "excluded_request")

        if excluded_from_flow is True or excluded_request is True:
            exclusion_reason = _extract_nested(self.structured_data, "policy_precheck", "exclusion_reason")
            if isinstance(exclusion_reason, str) and exclusion_reason.strip():
                causes.append(f"solicitação fora do escopo EDA ({' '.join(exclusion_reason.split())})")
            else:
                causes.append("solicitação fora do escopo EDA")

        labs_required = _extract_nested(self.structured_data, "policy_precheck", "labs_required")
        labs_pass = _extract_nested(self.structured_data, "policy_precheck", "labs_pass")
        if labs_required is True and not _is_yes_precheck(labs_pass):
            failed_items = _extract_nested(self.structured_data, "policy_precheck", "labs_failed_items")
            if isinstance(failed_items, list):
                normalized = [str(item).strip() for item in failed_items if str(item).strip()]
                if normalized:
                    causes.append(f"pendência laboratorial obrigatória ({', '.join(normalized)})")
                else:
                    causes.append("pendência laboratorial obrigatória")
            else:
                causes.append("pendência laboratorial obrigatória")

        ecg_required = _extract_nested(self.structured_data, "policy_precheck", "ecg_required")
        ecg_present = _extract_nested(self.structured_data, "policy_precheck", "ecg_present")
        if ecg_required is True and not _is_yes_precheck(ecg_present):
            causes.append("ECG obrigatório ausente")

        if not causes:
            causes.append("critérios mínimos de segurança não atendidos")
        return causes

    def _map_reason_code_to_cause(self, reason_code: Any, reason_text: Any) -> str | None:
        if not isinstance(reason_code, str) or not reason_code.strip():
            return None

        minimum_exam_labels = {
            "missing_minimum_exam_hb_or_ht": "Hb/Ht",
            "missing_minimum_exam_platelets": "plaquetas",
            "missing_minimum_exam_tp_inr_rni": "TP/INR/RNI",
            "missing_minimum_exam_ttpa": "TTPa",
            "missing_minimum_exam_urea": "ureia",
            "missing_minimum_exam_creatinine": "creatinina",
        }
        if reason_code in minimum_exam_labels:
            return f"exame mínimo obrigatório ausente: {minimum_exam_labels[reason_code]}"

        if reason_code == "missing_ecg_with_cardiovascular_disease":
            return "critério cardiovascular sem laudo mínimo de ECG"
        if reason_code == "missing_chest_xray_with_respiratory_risk":
            return "critério respiratório sem laudo mínimo de RX de tórax"
        if reason_code == "missing_echocardiogram_with_structural_heart_risk":
            return "critério cardíaco estrutural sem laudo mínimo de ecocardiograma"

        if reason_code in {"hb_below_threshold", "platelets_below_threshold", "inr_above_threshold"}:
            summarized = self._summarize_threshold_reason(reason_text)
            if summarized is not None:
                return f"contraindicação: {summarized}"
            return "contraindicação por limiar clínico excedido"
        return None

    def _summarize_threshold_reason(self, reason_text: Any) -> str | None:
        if not isinstance(reason_text, str) or not reason_text.strip():
            return None
        normalized = reason_text.split(" Sinalização pediátrica:", 1)[0].strip()
        normalized = normalized.removesuffix(".")
        normalized = normalized.replace(" do rulebook EDA", "")
        normalized = " ".join(normalized.split())
        if not normalized:
            return None
        return normalized

    def _build_default_reason_lines(self, decision_label: str, support_label: str) -> list[str]:
        return [f"- Decisão {decision_label} com suporte {support_label}."]

    # ── Context builders ─────────────────────────────────────────────────

    def _build_context(self) -> dict[str, Any]:
        return {
            "procedure": f"procedimento solicitado: {self._resolve_canonical_procedure_name()}",
            "origin": self._build_origin_line(),
            "transfusion_lines": self._build_transfusion_lines(),
            "tracked_exam_lines": self._build_tracked_exam_lines(),
            "pediatric": "paciente pediátrico: sim" if self._is_pediatric() else "",
            "clinical_alert_lines": self._build_clinical_alert_lines(),
            "comorbidities_line": self._build_comorbidities_line(),
        }

    def _resolve_canonical_procedure_name(self) -> str:
        subtype = self._extract_eda_subtype()
        if subtype == "gastrostomy":
            return "EDA para gastrostomia"
        if subtype == "esophageal_dilation":
            return "EDA para dilatação esofágica"
        if subtype == "foreign_body":
            return "EDA para retirada de corpo estranho"
        return "EDA"

    def _extract_eda_subtype(self) -> str:
        requested = _extract_nested(self.structured_data, "eda", "requested_procedure", "subtype")
        if requested in {"standard", "gastrostomy", "esophageal_dilation", "foreign_body"}:
            return str(requested)

        rulebook = _extract_nested(self.structured_data, "preop_screening", "rulebook_signals", "eda_subtype")
        if rulebook in {"standard", "gastrostomy", "esophageal_dilation", "foreign_body"}:
            return str(rulebook)
        return "standard"

    def _build_origin_line(self) -> str:
        origin = _extract_nested(self.structured_data, "origin_context")
        if not isinstance(origin, dict):
            return "origem: sem evidência no laudo"

        city = origin.get("city")
        hospital = origin.get("hospital")
        unit = origin.get("unit")
        state_uf = origin.get("state_uf")

        city_str = self._normalize_origin_field(city)
        uf_str = self._normalize_origin_field(state_uf)

        parts: list[str] = []
        if city_str:
            if uf_str:
                parts.append(f"{city_str} ({uf_str})")
            else:
                parts.append(city_str)

        hospital_str = self._normalize_origin_field(hospital)
        if hospital_str:
            parts.append(hospital_str)

        unit_str = self._normalize_origin_field(unit)
        if unit_str:
            parts.append(unit_str)

        if not parts:
            return "origem: sem evidência no laudo"
        return f"origem: {' - '.join(parts)}"

    @staticmethod
    def _normalize_origin_field(value: Any) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return ""

    def _build_transfusion_lines(self) -> list[str]:
        transfusion = _extract_nested(self.structured_data, "transfusion")
        had_value = None
        if isinstance(transfusion, dict):
            had_value = transfusion.get("had_transfusion")

        is_yes = isinstance(had_value, str) and had_value.strip().lower() == "yes"
        lines: list[str] = [f"Há relato de transfusão? {'sim' if is_yes else 'não'}"]

        if is_yes and isinstance(transfusion, dict):
            total_units = transfusion.get("total_units")
            hemocomponent = transfusion.get("hemocomponent")
            units_label = str(total_units) if isinstance(total_units, (int, float)) else "não informado"
            hemo_label = (
                str(hemocomponent).strip()
                if isinstance(hemocomponent, str) and hemocomponent.strip()
                else "não informado"
            )
            lines.append(f"Total de unidades transfundidas: {units_label}")
            lines.append(f"Hemocomponente: {hemo_label}")

        return lines

    def _build_tracked_exam_lines(self) -> list[str]:
        tracked_exams = self.structured_data.get("tracked_exams")
        if not isinstance(tracked_exams, list) or not tracked_exams:
            return []

        lines: list[str] = []
        for exam in tracked_exams:
            if not isinstance(exam, dict):
                continue

            result_value = exam.get("result_value")
            # Skip exams whose result indicates absence
            if _is_absent_exam_result(result_value):
                continue

            exam_label = exam.get("exam_label")
            is_most_recent = exam.get("is_most_recent")
            exam_datetime = exam.get("exam_datetime_iso")

            label_str = str(exam_label).strip() if isinstance(exam_label, str) and exam_label.strip() else "exame"
            value_str = (
                str(result_value).strip() if isinstance(result_value, str) and result_value.strip() else "não informado"
            )

            line = f"{label_str}: {value_str}"

            # Always show date when available, regardless of is_most_recent
            formatted_date = _format_exam_datetime(exam_datetime)
            if formatted_date:
                line += f" (data: {formatted_date}"
                if is_most_recent is True:
                    line += "; mais recente"
                line += ")"
            elif is_most_recent is True:
                # Recent but no valid date — use fallback
                line += " (recência indeterminada (sem data no laudo))"

            lines.append(line)
        return lines

    def _is_pediatric(self) -> bool:
        age = _extract_nested(self.structured_data, "patient", "age")
        if isinstance(age, int) and not isinstance(age, bool):
            if age < 16:
                return True
            # Age >= 16, but also check explicit pediatric flag
            is_pediatric = _extract_nested(self.structured_data, "eda", "is_pediatric")
            return is_pediatric is True

        is_pediatric = _extract_nested(self.structured_data, "eda", "is_pediatric")
        return is_pediatric is True

    # ── Recent denial ────────────────────────────────────────────────────

    def _build_recent_denial(self) -> dict[str, Any] | None:
        if self.recent_denial_context is None:
            return None

        lines = self._build_recent_denial_lines(self.recent_denial_context)
        decision = self.recent_denial_context.get("decision")
        reason = self.recent_denial_context.get("reason")
        decided_at = self.recent_denial_context.get("decided_at")
        count = self.recent_denial_context.get("prior_denial_count_7d")

        return {
            "lines": lines,
            "decision_display": self._format_denial_decision(decision),
            "reason_display": self._format_denial_reason(reason),
            "decided_at_display": self._format_denial_decided_at(decided_at),
            "prior_denial_count_7d": count if isinstance(count, int) else 0,
        }

    def _build_recent_denial_lines(self, ctx: dict[str, Any]) -> list[str]:
        decision = ctx.get("decision")
        reason = ctx.get("reason")
        decided_at = ctx.get("decided_at")

        decision_label = self._format_denial_decision(decision)
        reason_label = self._format_denial_reason(reason)
        decided_at_label = self._format_denial_decided_at(decided_at)

        lines = [
            f"- Tipo da negativa mais recente: {decision_label}.",
            f"- Motivo da negativa mais recente: {reason_label}",
            f"- Data/hora da negativa mais recente: {decided_at_label}",
        ]

        counter = ctx.get("prior_denial_count_7d")
        if isinstance(counter, int):
            lines.append(f"- Total de negativas nos últimos 7 dias: {counter}")

        return lines

    @staticmethod
    def _format_denial_decision(value: Any) -> str:
        if value == "deny_triage":
            return "negado na regulação"
        if value == "deny_appointment":
            return "negado no agendamento"
        return "negado"

    @staticmethod
    def _format_denial_reason(value: Any) -> str:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return "não informado"

    @staticmethod
    def _format_denial_decided_at(value: Any) -> str:
        parsed = DoctorReportPresenter._parse_denial_datetime(value)
        if parsed is None:
            return "não informado"
        return parsed.strftime("%d/%m/%Y %H:%M") + " BRT"

    @staticmethod
    def _parse_denial_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            iso_candidate = normalized
            if iso_candidate.endswith("Z"):
                iso_candidate = f"{iso_candidate[:-1]}+00:00"
            try:
                parsed = datetime.fromisoformat(iso_candidate)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed

        return None
