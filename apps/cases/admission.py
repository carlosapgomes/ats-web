"""Shared admission-flow labels and operational-notice helpers."""

from __future__ import annotations

SCHEDULED_ADMISSION_FLOW = "scheduled"

OPERATIONAL_NOTICE_FLOWS: tuple[str, ...] = (
    "immediate",
    "pre_icu",
    "ward_icu_backup",
    "pediatric_em",
)

ADMISSION_FLOW_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "---"),
    ("scheduled", "Agendamento"),
    ("immediate", "Vinda Imediata"),
    ("pre_icu", "Vinda prévia para UTI"),
    ("ward_icu_backup", "Vinda para enfermaria (para retaguarda em UTI)"),
    ("pediatric_em", "Compartilhar com EM pediátrica"),
)

ADMISSION_FLOW_MAP: dict[str, str] = dict(ADMISSION_FLOW_CHOICES[1:])

# Labels compactos para badges de apresentação (dashboard + detalhe)
# Preserva ADMISSION_FLOW_CHOICES completos para formulários médicos.
COMPACT_ADMISSION_FLOW_LABELS: dict[str, str] = {
    "immediate": "Vinda imediata",
    "pre_icu": "Pré-UTI",
    "ward_icu_backup": "Enfermaria + retaguarda UTI",
    "pediatric_em": "EM pediátrica",
}

SUPPORT_FLAG_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "---"),
    ("none", "Nenhum"),
    ("anesthesist", "Anestesista"),
)

SUPPORT_FLAG_MAP: dict[str, str] = {
    "none": "Nenhum",
    "anesthesist": "Anestesista",
    # Historical/pipeline recommendation compatibility only. New doctor
    # decisions must not post this value through DoctorDecisionForm.
    "anesthesist_icu": "Anestesista + UTI",
}

OPERATIONAL_NOTICE_EVENT_TYPES: tuple[str, str] = (
    "ADMISSION_FLOW_OPERATIONAL_NOTICE",
    "IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
)

OPERATIONAL_NOTICE_ACK_EVENT_TYPES: tuple[str, str, str] = (
    "SCHEDULER_OPERATIONAL_NOTICE_ACK",
    "SCHEDULER_IMMEDIATE_ACK",
    # Slice 003: POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED de contexto
    # operational_notice satisfaz o notice inicial. Queries ja filtram
    # por doctor_admission_flow__in=OPERATIONAL_NOTICE_FLOWS, impedindo
    # que ACKs scheduled afetem casos indevidos.
    "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED",
)

ADMISSION_FLOW_NOTICE_COPY: dict[str, dict[str, str]] = {
    "immediate": {
        "scheduler_title": "⚡ Vinda imediata autorizada — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. Comunicação apenas para ciência operacional.",
        "nir_badge": "✓ Vinda Imediata Autorizada",
        "nir_body": "Caso aceito para vinda imediata. Não abrir agendamento para este caso.",
    },
    "pre_icu": {
        "scheduler_title": "🏥 Vinda prévia para UTI — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. O NIR providenciará a reserva de UTI antes de qualquer ação do CHD.",
        "nir_badge": "✓ Vinda prévia para UTI",
        "nir_body": "Caso aceito para vinda prévia para UTI. Providenciar reserva de UTI antes de acionar o CHD.",
    },
    "ward_icu_backup": {
        "scheduler_title": "🏥 Enfermaria com retaguarda em UTI — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. O NIR providenciará leito de enfermaria e retaguarda em UTI antes de qualquer ação do CHD.",
        "nir_badge": "✓ Vinda para enfermaria com retaguarda em UTI",
        "nir_body": "Caso aceito para vinda para enfermaria com retaguarda em UTI. Providenciar leito/enfermaria e retaguarda em UTI conforme fluxo institucional.",
    },
    "pediatric_em": {
        "scheduler_title": "👶 Compartilhar com EM pediátrica — ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. O NIR acionará o coordenador da EM Pediátrica; comunicação ao CHD é apenas para ciência operacional.",
        "nir_badge": "✓ Compartilhar com EM pediátrica",
        "nir_body": "Caso aceito para compartilhamento com EM pediátrica. Acionar o coordenador da EM Pediátrica; não há integração desta equipe no sistema.",
    },
}


def is_operational_notice_flow(flow: str | None) -> bool:
    """Return True when an accepted case does not open CHD scheduling."""
    return bool(flow) and flow in OPERATIONAL_NOTICE_FLOWS


def get_admission_flow_display(flow: str | None) -> str:
    """Return the Portuguese display label for an admission flow."""
    if not flow:
        return ""
    return ADMISSION_FLOW_MAP.get(flow, flow)


def get_support_flag_display(flag: str | None) -> str:
    """Return the Portuguese display label for a support flag."""
    if not flag:
        return ""
    return SUPPORT_FLAG_MAP.get(flag, flag)


def get_admission_flow_notice_copy(flow: str | None) -> dict[str, str]:
    """Return flow-specific copy for operational notices and NIR result."""
    if flow in ADMISSION_FLOW_NOTICE_COPY:
        return ADMISSION_FLOW_NOTICE_COPY[flow]
    label = get_admission_flow_display(flow)
    return {
        "scheduler_title": f"{label} — ciência operacional" if label else "Ciência operacional",
        "scheduler_body": "Não abrir agendamento para este caso. Comunicação apenas para ciência operacional.",
        "nir_badge": f"✓ {label}" if label else "✓ Ciência operacional",
        "nir_body": "Caso aceito sem abertura de agendamento. O NIR dará seguimento ao fluxo escolhido.",
    }
