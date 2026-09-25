"""Doctor report presenter — 7-block medical report without Matrix/Room coupling.

Ports the logic from legacy build_room2_case_summary_message and helpers
into a standalone Django presenter for the doctor decision screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from apps.cases.exam_profiles import get_exam_profile
from apps.cases.models import ProcedureType
from apps.cases.priority_signals import (
    PRIORITY_SIGNAL_VERSION,
    build_priority_signal_badges,
    build_priority_signal_context_fragments,
)
from apps.cases.procedures import PROCEDURE_LABELS, SUPPORTED_PROCEDURE_TYPES, is_procedure_neutral_structured_data
from apps.pipeline.infection_review import INFECTION_EVIDENCE_ARTIFACT_KEY

# Labels anatômicos do local informativo de EDA + Dilatação (D6/R6): a
# apresentação é do presenter, o valor técnico vem do pipeline.
_DILATION_SITE_LABELS: dict[str, str] = {
    "esophagus": "Esôfago",
    "pylorus": "Piloro",
    "duodenum": "Duodeno",
    "anastomosis": "Anastomose",
    "jejunum": "Jejuno",
    "other": "Outro local informado no laudo",
}
_DILATION_SITE_UNKNOWN_LABEL = "não informado no laudo"

# Revisão infecciosa consultiva de EDA + GTT (Slice 004, D7/D8/R4/R5): copy
# explícita de apoio à revisão humana — nunca diagnóstico nem critério
# automático. O destaque já vem derivado em código pelo verificador.
INFECTION_ALERT_COPY = (
    "Possível infecção sistêmica — revisar evidências; informação consultiva, não altera a sugestão automática."
)
INFECTION_NEUTRAL_COPY = (
    "Nenhum sinal de preocupação explicitamente documentado; informação consultiva, não altera a sugestão automática."
)

INFECTION_CATEGORY_LABELS: dict[str, str] = {
    "leukocytes": "Leucócitos",
    "crp": "PCR (proteína C reativa)",
    "procalcitonin": "Procalcitonina",
    "lactate": "Lactato",
    "culture": "Culturas",
    "temperature_or_fever": "Temperatura/febre",
    "infectious_disease": "Infectologia",
    "antibiotic": "Antibióticos",
}

INFECTION_ASSESSMENT_LABELS: dict[str, str] = {
    "normal_explicit": "normal (documentado)",
    "abnormal_explicit": "alterado (documentado)",
    "positive_explicit": "positivo (documentado)",
    "negative_explicit": "negativo (documentado)",
    "febrile_explicit": "febre documentada",
    "current_care_explicit": "avaliação de infectologia atual",
    "antibiotic_in_use": "antibiótico em uso",
    "antibiotic_started": "antibiótico iniciado",
    "antibiotic_escalated": "antibiótico escalonado",
    "unclassified": "sem interpretação documentada",
}

INFECTION_TEMPORAL_LABELS: dict[str, str] = {
    "current": "atual",
    "historical": "histórico",
    "unknown": "temporalidade não informada",
}


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


# ── Medication labels (Slice 001) ────────────────────────────────────────

_MEDICATION_CLASS_LABELS: dict[str, str] = {
    "anticoagulant": "anticoagulante",
    "antiplatelet": "antiagregante",
    "other": "outro",
    "unknown": "classe a confirmar",
}

_MEDICATION_USE_STATUS_LABELS: dict[str, str] = {
    "current": "uso atual",
    "recent": "uso recente",
    "historical": "uso prévio",
    "suspended": "suspenso",
    "unknown": "não informado",
}


def _format_medication_class(value: Any) -> str:
    """Map a medication_class enum value to its Portuguese label."""
    if isinstance(value, str):
        label = _MEDICATION_CLASS_LABELS.get(value)
        if label is not None:
            return label
    return "classe a confirmar"


def _format_medication_use_status(value: Any) -> str:
    """Map a use_status enum value to its Portuguese label."""
    if isinstance(value, str):
        label = _MEDICATION_USE_STATUS_LABELS.get(value)
        if label is not None:
            return label
    return "não informado"


def _format_unknown_with_evidence(value: Any) -> str:
    """Return clearer wording when scalar value is unknown in source evidence."""
    formatted = _format_value_or_fallback(value)
    if formatted in {"indeterminado"}:
        return "indeterminado (sem evidência no laudo)"
    return formatted


def _is_yes_precheck(value: Any) -> bool:
    """Return True when precheck enum-like value explicitly means yes."""
    return isinstance(value, str) and value.strip().lower() == "yes"


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
    priority_signals: list[dict[str, Any]] = field(default_factory=list)
    # Slice 003 (R6): declared exam type drives the canonical procedure name.
    # Never infer the type from the legacy ``eda`` envelope block.
    exam_type: str = "eda"
    # Slice 003 (R6/D10): seções de histórico anterior por procedimento,
    # preparadas por ``reporting.prepare_doctor_case_report`` (modo 2.0).
    prior_sections: list[dict[str, Any]] = field(default_factory=list)

    # ── Public API ───────────────────────────────────────────────────────

    def _is_v2(self) -> bool:
        """True quando o structured_data é contrato procedure-neutral (2.0 ou 3.0)."""
        return is_procedure_neutral_structured_data(self.structured_data)

    def build_report(self) -> dict[str, Any]:
        """Return the full report structure with blocks, context, and denial info.

        Returns a dict with:

        - ``blocks``: dict of 7 block names → list[str]
        - ``context``: dict with procedure, origin, transfusion_lines,
          tracked_exam_lines, pediatric
        - ``recent_denial``: dict | None with lines and display fields
        - ``notices``: avisos operacionais (ex.: limite técnico dos anexos em 3.0)
        """
        return {
            "blocks": self._build_all_blocks(),
            "context": self._build_context(),
            "recent_denial": self._build_recent_denial(),
            "priority_signal_badges": build_priority_signal_badges(self.priority_signals),
            "prior_sections": self._build_prior_sections(),
            "procedure_sections": self._build_procedure_sections(),
            "infection_review": self._build_infection_review(),
            "notices": self._build_notices(),
        }

    def _is_v3(self) -> bool:
        """True quando o artefato usa o contrato procedure-neutral gravável.

        R4 (cutover 4.0): reconhece 2.0/3.0 históricos e 4.0 (writer atual);
        1.1 permanece no caminho legado.
        """
        return is_procedure_neutral_structured_data(self.structured_data)

    def _build_notices(self) -> list[str]:
        """Avisos operacionais do relatório (design D9/D5).

        No contrato procedure-neutral (2.0/3.0/4.0) a sugestão automática usa
        SOMENTE o relatório principal: o aviso descreve o limite técnico (anexos
        disponíveis na tela não participaram), sem afirmar invalidade clínica e
        sem bloquear decisão.
        Quando a precedência especializada suprimiu EDA/Colonoscopia, um aviso
        informativo adicional identifica o procedimento priorizado.
        """
        if not self._is_v3():
            return []
        notices = [
            "Anexos disponíveis na tela não participaram da sugestão automática; "
            "o médico pode consultá-los e decidir de forma divergente."
        ]
        precedence_notice = self._build_precedence_notice()
        if precedence_notice is not None:
            notices.append(precedence_notice)
        return notices

    def _build_precedence_notice(self) -> str | None:
        """Aviso da redução de conjunto aplicada (D5/ADR-0008, D3/Slice 003).

        Informativo e não bloqueante: não altera policy, formulário, validação
        nem FSM. Existe somente quando ``suggested_action.procedure_precedence``
        registra uma supressão (especializado sobre convencionais ou variação
        atômica sobre a base) — singleton normal, conflito fail-closed e
        artefatos legados não geram aviso. Os labels vêm do catálogo/perfis,
        nunca de valores técnicos crus, e a copy acompanha a regra aplicada.
        """
        metadata = self.suggested_action.get("procedure_precedence")
        if not isinstance(metadata, dict):
            return None
        from apps.pipeline.procedure_reconciliation import VARIATION_PRECEDENCE_RULE

        selected = metadata.get("selected")
        suppressed = metadata.get("suppressed")
        if not isinstance(selected, str) or selected not in SUPPORTED_PROCEDURE_TYPES:
            return None
        if not isinstance(suppressed, list):
            return None
        suppressed_labels = [
            self._canonical_label_for_type(procedure_type)
            for procedure_type in suppressed
            if isinstance(procedure_type, str) and procedure_type in SUPPORTED_PROCEDURE_TYPES
        ]
        if not suppressed_labels:
            return None
        if metadata.get("rule") == VARIATION_PRECEDENCE_RULE:
            return (
                f"O relatório apresentou também solicitação de {'/'.join(suppressed_labels)}. "
                f"O sistema priorizou {self._canonical_label_for_type(selected)} porque a solicitação "
                "atual descreve o pacote atômico correspondente. Revise o texto original e ajuste a "
                "decisão se necessário."
            )
        return (
            f"O relatório apresentou também solicitação de {'/'.join(suppressed_labels)}. "
            f"O sistema priorizou {self._canonical_label_for_type(selected)} pela regra de "
            "precedência de procedimento especializado. Revise o texto original e ajuste a "
            "decisão se necessário."
        )

    def _detected_procedure_types(self) -> tuple[str, ...]:
        """Tipos reconciliados (detectados) na ordem do catálogo.

        D12: o relatório médico descreve o conjunto DETECTADO. A leitura vem das
        recomendações por componente do ``suggested_action``; sem elas, cai no
        ``requested_procedures`` do artefato.
        """
        recommendations = self.suggested_action.get("procedure_recommendations")
        types: list[str] = []
        if isinstance(recommendations, list):
            for recommendation in recommendations:
                if isinstance(recommendation, dict):
                    procedure_type = recommendation.get("procedure_type")
                    if isinstance(procedure_type, str) and procedure_type not in types:
                        types.append(procedure_type)
        if not types:
            from apps.pipeline.schemas.adapters import requested_procedure_types_v3

            types = list(requested_procedure_types_v3(self.structured_data))
        return tuple(procedure_type for procedure_type in SUPPORTED_PROCEDURE_TYPES if procedure_type in types)

    def _identity_label(self, procedure_type: str) -> str:
        """Label canônica da IDENTIDADE (D4) — nunca a label do profile/família.

        Um pacote é apresentado como sua identidade atômica (ex.: ``EDA +
        Cápsula``), e não como a label do profile clínico reutilizado.
        """
        return PROCEDURE_LABELS.get(procedure_type) or get_exam_profile(procedure_type).label

    def _canonical_label_for_type(self, procedure_type: str) -> str:
        """Label canônico do procedimento para a decisão por componente."""
        from apps.pipeline.schemas.adapters import requested_procedure_for_type

        if procedure_type != ProcedureType.EDA:
            return self._identity_label(procedure_type)
        procedure = requested_procedure_for_type(self.structured_data, "eda")
        subtype = procedure.get("subtype") or "standard"
        if subtype == "foreign_body":
            return "EDA para retirada de corpo estranho"
        if subtype == "gastrostomy":
            return "EDA para gastrostomia"
        if subtype == "esophageal_dilation":
            return "EDA para dilatação esofágica"
        return "EDA"

    # ── Priority signals (persisted — Slice 003) ────────────────────────

    # Procedural fragment order for the canonical procedure name: ecoendoscopia
    # → dilatação esofágica → gastrostomia (design D9).
    _PROCEDURE_FRAGMENT_ORDER: tuple[tuple[str, str], ...] = (
        ("echoendoscopy", "ecoendoscopia"),
        ("esophageal_dilation", "dilatação esofágica"),
        ("gastrostomy", "gastrostomia"),
    )

    def _get_signal(self, code: str) -> dict[str, Any] | None:
        """Return the compatible persisted signal for a code, or None."""
        if not isinstance(self.priority_signals, list):
            return None
        for item in self.priority_signals:
            if isinstance(item, dict) and item.get("code") == code and item.get("version") == PRIORITY_SIGNAL_VERSION:
                return item
        return None

    def _has_signal(self, code: str) -> bool:
        """True when a compatible persisted signal exists for the code."""
        return self._get_signal(code) is not None

    def _build_priority_contexts_line(self) -> str:
        """Build the deterministic single-line context for Resumo clínico."""
        fragments = build_priority_signal_context_fragments(self.priority_signals)
        if not fragments:
            return ""
        return "Contextos prioritários: " + "; ".join(fragments) + "."

    def _build_clinical_alert_lines_from_signals(self) -> list[str]:
        """Return foreign-body/caustic alert lines from persisted signals.

        Canonical order: foreign_body before caustic_ingestion (design D13).
        Informative tone only — no automatic urgency/denial assertion.
        """
        lines: list[str] = []
        foreign_body = self._get_signal("foreign_body")
        if foreign_body is not None:
            lines.append("- Suspeita de corpo estranho: avaliar retirada.")
        caustic = self._get_signal("caustic_ingestion")
        if caustic is not None:
            lines.append(self._build_caustic_alert_line(caustic))
        return lines

    @staticmethod
    def _build_caustic_alert_line(signal: dict[str, Any]) -> str:
        """Documental caustic line with time detail when persisted."""
        line = "- Ingestão cáustica/corrosiva relatada."
        detail = signal.get("detail")
        if isinstance(detail, str) and detail.strip():
            line += f" Tempo desde a ingestão: {detail.strip()}."
        return line

    # ── Block builders ───────────────────────────────────────────────────

    def _build_comorbidities_line(self) -> str:
        """Build the comorbidities display line from structured_data."""
        if self._is_v2():
            preop = _extract_nested(self.structured_data, "common_preop")
        else:
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
        if context.get("comorbidities_line"):
            lines.append(context["comorbidities_line"])
        lines.append("")

        # Medications (informational; alert lives in Achados críticos)
        medication_lines = context.get("medication_lines")
        if medication_lines:
            lines.append("Medicamentos descritos:")
            lines.extend(medication_lines)
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

        # Prior sections (per-procedure, Slice 003)
        prior_sections = report.get("prior_sections") or []
        if prior_sections:
            lines.append("## Histórico anterior por procedimento:")
            for section in prior_sections:
                lines.append(f"- {section['procedure_label']}: {section['decision_display']}.")
                lines.append(f"  Motivo: {section['reason_display']}")
                lines.append(f"  Data/hora: {section['decided_at_display']}")
                if section.get("prior_denial_count_7d"):
                    lines.append(f"  Total de negativas nos últimos 7 dias: {section['prior_denial_count_7d']}")
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
        """Normalize clinical summary into 2-4 line block, with the deterministic
        priority-context line first when persisted signals provide one."""
        stripped = [line.strip() for line in self.summary_text.splitlines() if line.strip()]
        if not stripped:
            lines = [
                "Resumo clínico não informado.",
                "Consulte o relatório original para contexto clínico.",
            ]
        elif len(stripped) >= 2:
            lines = stripped[:4]
        else:
            one_liner = stripped[0]
            words = one_liner.split()
            if len(words) >= 4:
                midpoint = len(words) // 2
                first_half = " ".join(words[:midpoint]).strip()
                second_half = " ".join(words[midpoint:]).strip()
                if first_half and second_half:
                    lines = [first_half, second_half]
                else:
                    lines = [one_liner, f"Base clínica: {one_liner}"]
            else:
                lines = [one_liner, f"Base clínica: {one_liner}"]

        context_line = self._build_priority_contexts_line()
        if context_line:
            return [context_line, *lines]
        return lines

    def _build_critical_findings(self) -> list[str]:
        if self._is_v2():
            labs = _extract_nested(self.structured_data, "common_preop", "labs") or {}
            ecg = _extract_nested(self.structured_data, "common_preop", "ecg") or {}
            hb = labs.get("hb_g_dl")
            platelets = labs.get("platelets_per_mm3")
            inr = labs.get("inr")
            ecg_present = ecg.get("report_present")
            ecg_alert = ecg.get("abnormal_flag")
        else:
            hb = _extract_nested(self.structured_data, "eda", "labs", "hb_g_dl")
            platelets = _extract_nested(self.structured_data, "eda", "labs", "platelets_per_mm3")
            inr = _extract_nested(self.structured_data, "eda", "labs", "inr")
            ecg_present = _extract_nested(self.structured_data, "eda", "ecg", "report_present")
            ecg_alert = _extract_nested(self.structured_data, "eda", "ecg", "abnormal_flag")
        lab_lines = [
            f"- Hb: {_format_value_or_fallback(hb)}",
            f"- Plaquetas: {_format_value_or_fallback(platelets)}",
            f"- INR: {_format_value_or_fallback(inr)}",
            f"- ECG presente: {_format_value_or_fallback(ecg_present)}",
            f"- ECG sinal de alerta: {_format_unknown_with_evidence(ecg_alert)}",
        ]
        return [
            *self._build_clinical_alert_lines_from_signals(),
            *self._build_medication_alert_lines(),
            *lab_lines,
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
        if self._is_v2():
            recommendations = self.suggested_action.get("procedure_recommendations")
            if not isinstance(recommendations, list) or not recommendations:
                return ["- não informado"]
            lines: list[str] = []
            for recommendation in recommendations:
                if not isinstance(recommendation, dict):
                    continue
                procedure_type = str(recommendation.get("procedure_type") or "")
                procedure_name = self._canonical_label_for_type(procedure_type) if procedure_type else "—"
                suggestion_text = (
                    _format_scalar(recommendation.get("suggestion")) if recommendation.get("suggestion") else ""
                )
                lines.append(f"- {procedure_name}: {suggestion_text}")
            return lines or ["- não informado"]
        suggestion = self.suggested_action.get("suggestion")
        if isinstance(suggestion, str):
            return [f"- {_format_scalar(suggestion)}"]
        return ["- não informado"]

    def _build_support(self) -> list[str]:
        if self._is_v2():
            support = self.suggested_action.get("global_support_recommendation")
            if isinstance(support, str):
                return [f"- {_format_scalar(support)}"]
            return ["- não informado"]
        support = self.suggested_action.get("support_recommendation")
        if isinstance(support, str):
            return [f"- {_format_scalar(support)}"]
        return ["- não informado"]

    def _build_asa(self) -> list[str]:
        if self._is_v2():
            asa_payload = _extract_nested(self.structured_data, "common_preop", "asa")
            if isinstance(asa_payload, dict):
                bucket = asa_payload.get("bucket")
                if isinstance(bucket, str) and bucket.strip():
                    return [f"- {self._format_asa_bucket(bucket.strip())}"]
            return ["- não informado"]
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

    def _iter_medications(self) -> list[dict[str, Any]]:
        """Return the structured medications_described items, ignoring malformed input."""
        if self._is_v2():
            preop = _extract_nested(self.structured_data, "common_preop")
        else:
            preop = _extract_nested(self.structured_data, "preop_screening")
        if not isinstance(preop, dict):
            return []
        items = preop.get("medications_described")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _build_medication_alert_lines(self) -> list[str]:
        """Informative alert lines for anticoagulants/antiplatelets.

        Prominent at the start of Achados críticos. Never recommends
        suspension, dose or pharmacological window — the doctor confirms
        peri-procedural management.
        """
        lines: list[str] = []
        for med in self._iter_medications():
            med_class = med.get("medication_class")
            if med_class not in {"anticoagulant", "antiplatelet"}:
                continue
            name = med.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            lines.append(f"Medicamento relevante: {name.strip()} — {_format_medication_class(med_class)}")
            lines.append(f"Uso descrito: {_format_medication_use_status(med.get('use_status'))}")
            lines.append("Conduta: confirmar manejo peri-procedimento.")
        return lines

    def _build_medication_lines(self) -> list[str]:
        """Build informational medication lines from structured_data.

        Lists every explicitly described medication with class, use status
        and, when available, last dose/schedule and textual evidence.
        """
        meds = self._iter_medications()
        if not meds:
            return []

        lines: list[str] = []
        seen: set[str] = set()
        for med in meds:
            name = med.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            normalized = name.strip()
            if normalized in seen:
                continue
            seen.add(normalized)

            line = (
                f"{normalized}: {_format_medication_class(med.get('medication_class'))}; "
                f"{_format_medication_use_status(med.get('use_status'))}"
            )
            last_dose = med.get("last_dose_or_schedule")
            if isinstance(last_dose, str) and last_dose.strip():
                line += f"; última dose/posologia: {last_dose.strip()}"
            evidence = med.get("source_text_hint")
            if isinstance(evidence, str) and evidence.strip():
                line += f" (evidência: {evidence.strip()})"
            lines.append(line)
        return lines

    def _build_context(self) -> dict[str, Any]:
        return {
            "procedure": f"procedimento solicitado: {self._resolve_canonical_procedure_name()}",
            "origin": self._build_origin_line(),
            "transfusion_lines": self._build_transfusion_lines(),
            "tracked_exam_lines": self._build_tracked_exam_lines(),
            "pediatric": "paciente pediátrico: sim" if self._is_pediatric() else "",
            "comorbidities_line": self._build_comorbidities_line(),
            "medication_lines": self._build_medication_lines(),
        }

    def _resolve_canonical_procedure_name(self) -> str:
        """Resolve the canonical procedure name for the report context.

        Contrato 2.0/3.0 (Slice 002): o nome vem do conjunto DETECTADO, lido das
        recomendações por componente — nunca inferido do envelope legado. Assim
        Ecoendoscopia/CPRE singleton não caem em "EDA".
        Contrato 1.1: comportamento legado preservado (``exam_type`` + sinais).
        """
        if self._is_v2():
            types = self._detected_procedure_types()
            if not types:
                return "procedimento não identificado no laudo"
            if len(types) == 1:
                return self._canonical_label_for_type(types[0])
            return " + ".join(self._identity_label(procedure_type) for procedure_type in types)
        if self.exam_type == "colonoscopy":
            return "Colonoscopia"
        if not self.exam_type:
            # Slice 009 (R2): tipo 1.1 ambíguo/ausente é fail-closed neutro —
            # nunca default EDA. O reporting só passa "" quando não deriva.
            return "procedimento não identificado no laudo"
        subtype = self._extract_eda_subtype()
        if subtype == "foreign_body":
            return "EDA para retirada de corpo estranho"

        procedural_codes = [code for code, _ in self._PROCEDURE_FRAGMENT_ORDER if self._has_signal(code)]
        if procedural_codes:
            if len(procedural_codes) == 1:
                code = procedural_codes[0]
                if code == "echoendoscopy":
                    return "EDA com ecoendoscopia"
                if code == "esophageal_dilation":
                    return "EDA para dilatação esofágica"
                if code == "gastrostomy":
                    return "EDA para gastrostomia"
            fragment_names = [fragment for code, fragment in self._PROCEDURE_FRAGMENT_ORDER if code in procedural_codes]
            return "EDA com " + ", ".join(fragment_names[:-1]) + f" e {fragment_names[-1]}"
        if self._has_signal("foreign_body"):
            return "EDA para retirada de corpo estranho"
        if subtype == "gastrostomy":
            return "EDA para gastrostomia"
        if subtype == "esophageal_dilation":
            return "EDA para dilatação esofágica"
        if subtype == "echoendoscopy":
            return "EDA com ecoendoscopia"
        return "EDA"

    def _extract_eda_subtype(self) -> str:
        requested = _extract_nested(self.structured_data, "eda", "requested_procedure", "subtype")
        if requested in {"standard", "gastrostomy", "esophageal_dilation", "foreign_body", "echoendoscopy"}:
            return str(requested)

        rulebook = _extract_nested(self.structured_data, "preop_screening", "rulebook_signals", "eda_subtype")
        if rulebook in {"standard", "gastrostomy", "esophageal_dilation", "foreign_body", "echoendoscopy"}:
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
            if self._is_v2():
                return _extract_nested(self.structured_data, "policy_precheck", "pediatric_flag") is True
            is_pediatric = _extract_nested(self.structured_data, "eda", "is_pediatric")
            return is_pediatric is True

        if self._is_v2():
            return _extract_nested(self.structured_data, "policy_precheck", "pediatric_flag") is True
        is_pediatric = _extract_nested(self.structured_data, "eda", "is_pediatric")
        return is_pediatric is True

    # ── Prior sections (Slice 003, R6/D10) ───────────────────────────────

    def _build_prior_sections(self) -> list[dict[str, Any]]:
        """Renderiza as seções de histórico anterior por procedimento.

        Cada seção usa a decisão/razão da própria row do caso anterior
        (``doctor_denied`` | ``appointment_denied`` | ``doctor_approved``),
        preservando a ordem D10 e a janela de sete dias já aplicada no
        lookup (``reporting._build_prior_sections``).
        """
        sections: list[dict[str, Any]] = []
        for section in self.prior_sections:
            decision = section.get("decision_display") or section.get("decision") or "—"
            sections.append(
                {
                    "procedure_label": section.get("procedure_label") or "—",
                    "decision_display": decision,
                    "reason_display": self._format_denial_reason(section.get("reason")),
                    "decided_at_display": self._format_denial_decided_at(section.get("decided_at")),
                    "decided_by": section.get("decided_by") or "—",
                    "prior_case_id": section.get("prior_case_id") or "",
                    "prior_denial_count_7d": section.get("prior_denial_count_7d", 0),
                }
            )
        return sections

    # ── Procedure sections (R6/D11) ──────────────────────────────────────

    def _build_procedure_sections(self) -> list[dict[str, Any]]:
        """Uma seção por procedimento DETECTADO (R6/D11).

        Um pacote atômico ocupa uma única seção; EDA + Colonoscopia mantém duas
        rows e, portanto, duas seções. O local traduzido da dilatação é
        exclusivo de ``eda_dilation`` (nunca herdado por outro procedimento da
        família) e vem da projeção ancorada pelo pipeline.
        """
        sections: list[dict[str, Any]] = []
        for procedure_type in self._detected_procedure_types():
            section: dict[str, Any] = {
                "procedure_type": procedure_type,
                "label": self._canonical_label_for_type(procedure_type),
            }
            if procedure_type == ProcedureType.EDA_DILATION:
                section["dilation_site_label"] = self._dilation_site_label(procedure_type)
            sections.append(section)
        return sections

    def _dilation_site_label(self, procedure_type: str) -> str:
        """Local informativo da dilatação projetado pelo pipeline (D6/R6).

        Sem projeção ancorada (artefato legado, destino incluído pelo médico ou
        pacote de outra família) o texto é neutro: nunca inventa local nem cria
        pendência.
        """
        detail = self._recommendation_detail(procedure_type, "dilation_detail")
        if not isinstance(detail, dict):
            return _DILATION_SITE_UNKNOWN_LABEL
        site = detail.get("anatomical_site")
        if not isinstance(site, str):
            return _DILATION_SITE_UNKNOWN_LABEL
        return _DILATION_SITE_LABELS.get(site, _DILATION_SITE_UNKNOWN_LABEL)

    def _build_infection_review(self) -> dict[str, Any] | None:
        """Painel consultivo ancorado de EDA + GTT (Slice 004, R4/R5/D8).

        O painel existe SOMENTE quando a identidade detectada é exatamente
        ``eda_gastrostomy`` (nunca por herança de família/sinal legado). Artefato
        ausente/vazio ou sem filtro confirmado produz a MESMA seção neutra da
        identidade exata (título + copy "informação consultiva"), com grupos
        vazios: ausência/falha de extração nunca vira pendência nem bloqueio —
        o médico segue com a análise normal do procedimento.
        Todo o destaque vem derivado em código pelo verificador determinístico;
        nenhum limiar clínico é calculado aqui.
        """
        if ProcedureType.EDA_GASTROSTOMY not in self._detected_procedure_types():
            return None
        artifact = self.suggested_action.get(INFECTION_EVIDENCE_ARTIFACT_KEY)
        raw_groups = artifact.get("groups") if isinstance(artifact, dict) else None

        groups: list[dict[str, Any]] = []
        if isinstance(raw_groups, list):
            for raw_group in raw_groups:
                if not isinstance(raw_group, dict):
                    continue
                category = str(raw_group.get("category") or "")
                raw_items = raw_group.get("items")
                if category not in INFECTION_CATEGORY_LABELS or not isinstance(raw_items, list):
                    continue
                items: list[dict[str, Any]] = []
                for raw_item in raw_items:
                    if not isinstance(raw_item, dict):
                        continue
                    assessment = str(raw_item.get("assessment") or "")
                    if assessment not in INFECTION_ASSESSMENT_LABELS:
                        continue
                    items.append(
                        {
                            "assessment_label": INFECTION_ASSESSMENT_LABELS[assessment],
                            "temporal_label": INFECTION_TEMPORAL_LABELS.get(
                                str(raw_item.get("temporal_status") or ""), ""
                            ),
                            "value_text": raw_item.get("value_text") or "",
                            "evidence_excerpt": raw_item.get("evidence_excerpt") or "",
                            "concerning": bool(raw_item.get("concerning")),
                        }
                    )
                if not items:
                    continue
                groups.append({"category_label": INFECTION_CATEGORY_LABELS[category], "items": items})

        if not groups:
            # D7/D8: seção neutra (sem grupos, sem alerta), nunca pendência.
            return {"concerning": False, "alert_message": INFECTION_NEUTRAL_COPY, "groups": []}

        concerning = bool(artifact.get("concerning")) if isinstance(artifact, dict) else False
        return {
            "concerning": concerning,
            "alert_message": INFECTION_ALERT_COPY if concerning else INFECTION_NEUTRAL_COPY,
            "groups": groups,
        }

    def _recommendation_detail(self, procedure_type: str, key: str) -> Any:
        """Campo consultivo da recomendação daquele procedimento, se existir."""
        recommendations = self.suggested_action.get("procedure_recommendations")
        if not isinstance(recommendations, list):
            return None
        for recommendation in recommendations:
            if isinstance(recommendation, dict) and recommendation.get("procedure_type") == procedure_type:
                return recommendation.get(key)
        return None

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
