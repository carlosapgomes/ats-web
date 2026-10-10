"""Revisao humana de procedimento — dominio (S2/D3, ADR-0012).

``CaseEvent`` e a autoridade duravel; nenhum JSON mutavel no ``Case`` e
segunda autoridade (D3). Este modulo e coeso e puro em I/O exceto onde
marcado: fingerprint, consulta da confirmacao mais recente, validacao de
vigencia (revisao/fonte/declaracao) e formatacao compartilhada de
Linha do Tempo/aviso medico.

Evento ``CASE_PROCEDURE_REVIEW_CONFIRMED`` (humano, actor obrigatorio),
payload versionado::

    version: 1
    actor_role: nir
    review_event_id: ID do EDA_SCOPE_GATED_MANUAL_REVIEW revisado
    review_reason_code: reason daquele evento
    previous_declared_procedures: codigos em ordem canonica
    confirmed_procedures: codigos em ordem canonica
    selection_changed: booleano (false e confirmacao valida)
    justification: texto breve validado (1–500, sem U+0000)
    source_fingerprint: fingerprint v1 da fonte principal

Fingerprint v1 (D3): ``"v1:" + sha256("v1\\n" + pdf_hex + "\\n" + text_hex)``,
onde ``pdf_hex`` e o sha256 dos bytes do PDF principal (``b""`` quando o
arquivo ainda nao existe, ex.: fixtures) e ``text_hex`` o sha256 do texto
extraido em UTF-8. Nome de arquivo e anexos NAO entram: a analise automatica
permanece do documento principal. O hash nao autentica humano — permissoes
e lease continuam obrigatorios no servico.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from apps.cases.models import Case, CaseEvent, ProcedureType
from apps.cases.procedures import (
    ALLOWED_PROCEDURE_SETS,
    PROCEDURE_ORDER,
    get_declared_procedure_types,
)

REVIEW_CONFIRMED_EVENT = "CASE_PROCEDURE_REVIEW_CONFIRMED"
REVIEW_APPLIED_EVENT = "CASE_PROCEDURE_REVIEW_APPLIED"
REVIEW_INVALIDATED_EVENT = "CASE_PROCEDURE_REVIEW_INVALIDATED"
REVIEW_EVENT_TYPE = "EDA_SCOPE_GATED_MANUAL_REVIEW"

SOURCE_FINGERPRINT_VERSION = 1
SOURCE_FINGERPRINT_PREFIX = f"v{SOURCE_FINGERPRINT_VERSION}:"


def compute_source_fingerprint(*, pdf_bytes: bytes, extracted_text: str) -> str:
    """Fingerprint v1 deterministico/versionado da fonte principal (D3)."""
    pdf_hex = hashlib.sha256(pdf_bytes or b"").hexdigest()
    text_hex = hashlib.sha256((extracted_text or "").encode("utf-8")).hexdigest()
    combined = hashlib.sha256(f"v{SOURCE_FINGERPRINT_VERSION}\n{pdf_hex}\n{text_hex}".encode()).hexdigest()
    return f"{SOURCE_FINGERPRINT_PREFIX}{combined}"


def _read_pdf_bytes(case: Case) -> bytes | None:
    """Bytes do PDF principal; ``None`` quando ilegivel/ausente-com-erro.

    Arquivo ainda nao anexado (fixtures/casos sem PDF) equivale a ``b""`` —
    deterministico. Erro de leitura do storage devolve ``None`` para que a
    validacao falhe como fonte nao verificavel em vez de validar uma fonte
    que mudou mas nao pode ser lida.
    """
    field = getattr(case, "pdf_file", None)
    if field is None or not getattr(field, "name", ""):
        return b""
    try:
        field.open("rb")
        try:
            return field.read() or b""
        finally:
            field.close()
    except Exception:
        return None


def source_fingerprint_for_case(case: Case) -> str | None:
    """Fingerprint v1 da fonte atual do caso; ``None`` se o PDF for ilegivel."""
    pdf_bytes = _read_pdf_bytes(case)
    if pdf_bytes is None:
        return None
    return compute_source_fingerprint(pdf_bytes=pdf_bytes, extracted_text=getattr(case, "extracted_text", None) or "")


def latest_review_event(case: Case) -> CaseEvent | None:
    """Revisao manual mais recente (ordem timestamp/id)."""

    return CaseEvent.objects.filter(case=case, event_type=REVIEW_EVENT_TYPE).order_by("-timestamp", "-id").first()


def latest_confirmation_event(case: Case) -> CaseEvent | None:
    """Confirmacao humana mais recente (ordem timestamp/id)."""

    return CaseEvent.objects.filter(case=case, event_type=REVIEW_CONFIRMED_EVENT).order_by("-timestamp", "-id").first()


@dataclass(frozen=True)
class ConfirmationValidity:
    """Resultado da validacao de vigencia de uma confirmacao."""

    valid: bool
    reason: str  # "ok" | codigo tecnico enxuto


def validate_confirmation(case: Case, event: CaseEvent) -> ConfirmationValidity:
    """Valida a vigencia de uma confirmacao contra a fonte atual (D3).

    Nao escolhe retrospectivamente confirmacao antiga: o chamador passa a
    mais recente; aqui cada dimensao (payload, ator, revisao, declaracao,
    fingerprint, matriz) invalida o uso sem efeitos colaterais.
    """

    payload = getattr(event, "payload", None)
    if not isinstance(payload, dict):
        return ConfirmationValidity(valid=False, reason="payload_invalid")
    if payload.get("version") != SOURCE_FINGERPRINT_VERSION:
        return ConfirmationValidity(valid=False, reason="payload_invalid")
    if payload.get("actor_role") != "nir":
        return ConfirmationValidity(valid=False, reason="actor_invalid")
    if getattr(event, "actor_id", None) is None:
        return ConfirmationValidity(valid=False, reason="actor_invalid")

    confirmed = payload.get("confirmed_procedures")
    if not isinstance(confirmed, list) or not confirmed:
        return ConfirmationValidity(valid=False, reason="payload_invalid")
    if any(not isinstance(code, str) or code not in PROCEDURE_ORDER for code in confirmed):
        return ConfirmationValidity(valid=False, reason="unsupported_set")
    if frozenset(confirmed) not in ALLOWED_PROCEDURE_SETS:
        return ConfirmationValidity(valid=False, reason="unsupported_set")

    review = latest_review_event(case)
    if review is None or review.pk != payload.get("review_event_id"):
        # Sem revisao ou revisao mais recente: resolucao anterior invalidada.
        return ConfirmationValidity(
            valid=False,
            reason="review_not_found" if review is None else "review_superseded",
        )

    declared = list(get_declared_procedure_types(case))
    if declared != sorted(confirmed, key=lambda code: PROCEDURE_ORDER[code]):
        return ConfirmationValidity(valid=False, reason="declaration_changed")

    current = source_fingerprint_for_case(case)
    if current is None or current != payload.get("source_fingerprint"):
        return ConfirmationValidity(valid=False, reason="source_changed")
    return ConfirmationValidity(valid=True, reason="ok")


def record_review_invalidated(case: Case, confirmation_event: CaseEvent, reason: str) -> CaseEvent:
    """Emite ``CASE_PROCEDURE_REVIEW_INVALIDATED`` enxuto, uma vez por confirmacao.

    Idempotente por ``confirmation_event_id``: re-execucoes do job nao
    entopem a auditoria com invalidacoes repetidas da mesma confirmacao.
    """
    existing = CaseEvent.objects.filter(
        case=case,
        event_type=REVIEW_INVALIDATED_EVENT,
        payload__confirmation_event_id=confirmation_event.pk,
    ).first()
    if existing is not None:
        return existing
    return CaseEvent.objects.create(
        case=case,
        event_type=REVIEW_INVALIDATED_EVENT,
        actor=None,
        actor_type="system",
        payload={
            "confirmation_event_id": confirmation_event.pk,
            "reason": reason,
        },
    )


def consume_valid_confirmation(case: Case) -> tuple[tuple[str, ...] | None, CaseEvent | None]:
    """Devolve ``(conjunto_efetivo, evento)`` quando a confirmacao vige (D4).

    - Sem confirmacao: ``(None, None)`` sem efeitos (caminho automatico).
    - Confirmacao mais recente valida: conjunto confirmado em ordem canonica.
    - Mais recente invalida: NAO tenta confirmacao antiga; audita a
      invalidacao uma vez e devolve ``(None, evento)`` para o caminho
      automatico. Evento legado ``CASE_PROCEDURE_DECLARATION_CORRECTED``
      nunca e lido aqui (sem autoridade retroativa, D8).
    """

    event = latest_confirmation_event(case)
    if event is None:
        return None, None
    validity = validate_confirmation(case, event)
    if not validity.valid:
        record_review_invalidated(case, event, validity.reason)
        return None, event
    ordered = tuple(sorted(event.payload["confirmed_procedures"], key=lambda code: PROCEDURE_ORDER[code]))
    return ordered, event


# ── Apresentacao compartilhada (D6) ────────────────────────────────────────
# Formatadores puros: recebem o evento e devolvem titulo/linhas com labels
# canonicos do catalogo — nunca codigo cru. Templates escapam o texto livre
# (autoescape do Django); regra de negocio NAO vive no template.


def _procedure_labels(procedure_types: Any) -> list[str]:

    labels: list[str] = []
    for raw in procedure_types or ():
        code = str(raw)
        labels.append(ProcedureType(code).label if code in ProcedureType.values else code)
    return labels


def _ordered_labels(procedure_types: Any) -> str:

    ordered = sorted(
        (str(raw) for raw in (procedure_types or ())),
        key=lambda code: PROCEDURE_ORDER.get(code, len(PROCEDURE_ORDER)),
    )
    return " + ".join(_procedure_labels(ordered))


def format_confirmation_title(event: CaseEvent) -> str:
    """``Procedimento confirmado pelo NIR: <label canonico>`` (R7)."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    return f"Procedimento confirmado pelo NIR: {_ordered_labels(payload.get('confirmed_procedures'))}"


def confirmation_timeline_lines(event: CaseEvent) -> list[str]:
    """Linhas da Linha do Tempo: manutencao/troca + justificativa (R7)."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    previous = _ordered_labels(payload.get("previous_declared_procedures"))
    confirmed = _ordered_labels(payload.get("confirmed_procedures"))
    lines: list[str] = []
    if payload.get("selection_changed"):
        lines.append(f"Seleção alterada: {previous} → {confirmed}.")
    else:
        lines.append(f"Seleção mantida: {confirmed}.")
    justification = str(payload.get("justification") or "").strip()
    if justification:
        lines.append(f"Justificativa: {justification}")
    return lines


def format_applied_lines(event: CaseEvent) -> list[str]:
    """Linhas do evento sistemico de aplicacao (R7/D4)."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    lines = [f"Conjunto em análise: {_ordered_labels(payload.get('effective_procedures'))}."]
    automatic = payload.get("automatic_procedures") or []
    if automatic:
        lines.append(f"Detecção automática registrada: {_ordered_labels(automatic)}.")
    return lines


_INVALIDATED_REASON_LABELS: dict[str, str] = {
    "source_changed": "a fonte principal mudou após a revisão",
    "review_superseded": "há revisão manual mais recente",
    "review_not_found": "a revisão de origem não foi localizada",
    "declaration_changed": "a seleção declarada mudou após a confirmação",
    "payload_invalid": "o registro da confirmação está inválido",
    "unsupported_set": "o conjunto confirmado saiu da matriz suportada",
    "actor_invalid": "a autoria da confirmação está inválida",
}


def format_invalidated_lines(event: CaseEvent) -> list[str]:
    """Linhas do evento sistemico de invalidacao (R7/D3)."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    reason = str(payload.get("reason") or "")
    label = _INVALIDATED_REASON_LABELS.get(reason, reason or "motivo técnico")
    return [f"Confirmação desconsiderada: {label}. A análise segue as regras automáticas."]


def timeline_detail_lines(event: CaseEvent) -> list[str]:
    """Despacho unico para as timelines: detalhe dos 3 eventos novos (D6).

    Devolve ``[]`` para qualquer outro tipo — leitores existentes passam
    todos os eventos por aqui sem ramificar por tipo na view.
    """
    event_type = getattr(event, "event_type", "")
    if event_type == REVIEW_CONFIRMED_EVENT:
        return confirmation_timeline_lines(event)
    if event_type == REVIEW_APPLIED_EVENT:
        return format_applied_lines(event)
    if event_type == REVIEW_INVALIDATED_EVENT:
        return format_invalidated_lines(event)
    return []


def timeline_title_override(event: CaseEvent) -> str | None:
    """Titulo dinamico da confirmacao (com selecao); ``None`` p/ demais."""
    if getattr(event, "event_type", "") == REVIEW_CONFIRMED_EVENT:
        return format_confirmation_title(event)
    return None


def build_doctor_confirmation_notice(case: Case) -> str | None:
    """Aviso nao bloqueante a avaliacao medica (R8/D6).

    Fonte: evento sistemico ``CASE_PROCEDURE_REVIEW_APPLIED`` mais recente +
    confirmacao referenciada (autor/justificativa lidos do evento, nunca
    inventados). Sem aplicacao/confirmacao localizavel: ``None`` (legados
    e automaticos continuam sem aviso ficticio). Nao depende de metadata
    de precedencia: selecao mantida tambem gera aviso.
    """
    applied = CaseEvent.objects.filter(case=case, event_type=REVIEW_APPLIED_EVENT).order_by("-timestamp", "-id").first()
    if applied is None or not isinstance(applied.payload, dict):
        return None
    confirmation_id = applied.payload.get("confirmation_event_id")
    if not isinstance(confirmation_id, int):
        return None
    confirmation = CaseEvent.objects.filter(
        case=case,
        event_type=REVIEW_CONFIRMED_EVENT,
        pk=confirmation_id,
    ).first()
    if confirmation is None or not isinstance(confirmation.payload, dict):
        return None
    author = confirmation.actor
    if author is None:
        return None
    author_display = author.get_full_name() or author.username
    confirmed = _ordered_labels(confirmation.payload.get("confirmed_procedures"))
    automatic = _ordered_labels(applied.payload.get("automatic_procedures"))
    when = confirmation.timestamp.strftime("%d/%m/%Y %H:%M") if confirmation.timestamp else ""
    justification = str(confirmation.payload.get("justification") or "").strip()
    parts = [f"Procedimento confirmado pelo NIR: {confirmed} — {author_display}" + (f" em {when}." if when else ".")]
    if automatic:
        parts.append(f"Divergência automática registrada: {automatic}.")
    if justification:
        parts.append(f"Justificativa do NIR: {justification}")
    parts.append("A confirmação do NIR não é aprovação clínica; a decisão permanece com o médico.")
    return " ".join(parts)
