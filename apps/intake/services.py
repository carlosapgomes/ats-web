"""Business logic for intake file processing.

Separates file validation and Case creation from the view layer,
keeping the view thin and the logic testable in isolation.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.cases.models import (
    ACCEPTED_ATTACHMENT_CONTENT_TYPES,
    ACCEPTED_ATTACHMENT_EXTENSIONS,
    EDA_COLONOSCOPY,
    Case,
    CaseAttachment,
    CaseEvent,
    CaseStatus,
    ProcedureType,
)
from apps.cases.procedure_review import (
    REVIEW_CONFIRMED_EVENT,
    latest_review_event,
    source_fingerprint_for_case,
)
from apps.cases.procedures import (
    PROCEDURE_LABELS,
    PROCEDURE_ORDER,
    SELECTION_KEYS,
    get_declared_procedure_types,
    procedure_types_for_selection,
    reset_detection_and_doctor_statuses,
    set_declared_procedures,
    sync_declared_projection,
)

if TYPE_CHECKING:
    from apps.accounts.models import User as AccountsUser

logger = logging.getLogger(__name__)

# ── Exam type validation (centralized — R2/R3) ──────────────────────────


def is_colonoscopy_intake_enabled() -> bool:
    """Flag global de intake: permite novos uploads de colonoscopia.

    Consultada APENAS no intake (novos casos). Nenhum worker/pipeline/fila
    deve consultar esta flag para interromper casos existentes (R3).
    """
    return bool(getattr(settings, "COLONOSCOPY_INTAKE_ENABLED", False))


def is_echoendoscopy_intake_enabled() -> bool:
    """Flag independente de intake para Ecoendoscopia (Slice 002, R1/D4).

    Web-only: bloqueia novos uploads, correção e reenvio como Ecoendoscopia.
    Nenhum worker/pipeline consulta esta flag; caso existente sempre conclui.
    """
    return bool(getattr(settings, "ECHOENDOSCOPY_INTAKE_ENABLED", False))


def is_cpre_intake_enabled() -> bool:
    """Flag independente de intake para CPRE (Slice 004, R1/D4).

    Mesma fronteira da flag de Ecoendoscopia: web-only (upload, correção e
    reenvio) e independente dela. Nenhum worker/pipeline/fila/médico consulta
    esta flag; caso existente sempre conclui.
    """
    return bool(getattr(settings, "CPRE_INTAKE_ENABLED", False))


# Seleção declarada aceita no intake: derivada de ``SELECTION_KEYS`` do
# catálogo (design D10) — cada código atômico mais a chave derivada
# ``eda_colonoscopy``. O valor combinado NÃO é membro de
# ``ProcedureType.values``. Expor as chaves aqui NÃO expõe opções na UI: as
# flags de rollout continuam explicitamente em ``ensure_*_allowed`` e o helper
# de opções por jornada lista somente os códigos publicados.
_DECLARED_SELECTION_VALUES: frozenset[str] = frozenset(SELECTION_KEYS)


def _selection_label(key: str) -> str:
    """Label legível de uma chave de seleção, derivada das labels do catálogo."""
    return " + ".join(PROCEDURE_LABELS[code] for code in procedure_types_for_selection(key))


_SELECTION_CHOICES_LABEL: str = ", ".join(_selection_label(key) for key in SELECTION_KEYS)


# ── Opções de seleção por jornada (design D9/D10) ────────────────────────

# Lista ordenada explícita dos códigos publicados no intake (upload, reenvio
# corrigido e correção). Cada slice de identidade acrescenta SOMENTE o seu
# código aqui; nenhuma flag nova é criada. A ordem espelha o catálogo canônico
# (``PROCEDURE_CATALOG``): EDA e seus pacotes, depois Colonoscopia e o
# combinado, depois a família Retossigmoidoscopia, depois os especializados.
INTAKE_EXPOSED_SELECTION_KEYS: tuple[str, ...] = (
    ProcedureType.EDA,
    ProcedureType.EDA_GASTROSTOMY,
    ProcedureType.EDA_CAPSULE,
    ProcedureType.EDA_DILATION,
    ProcedureType.COLONOSCOPY,
    EDA_COLONOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
    ProcedureType.ECHOENDOSCOPY,
    ProcedureType.CPRE,
)

# Gate de flag por código exposto (D10): a referência é EXPLÍCITA — regra de
# rollout, não lista derivada do catálogo. Código sem gate é sempre
# habilitado (EDA).
_INTAKE_SELECTION_FLAG_GATES: dict[str, Callable[[], bool]] = {
    ProcedureType.COLONOSCOPY: is_colonoscopy_intake_enabled,
    EDA_COLONOSCOPY: is_colonoscopy_intake_enabled,
    ProcedureType.ECHOENDOSCOPY: is_echoendoscopy_intake_enabled,
    ProcedureType.CPRE: is_cpre_intake_enabled,
}


@dataclass(frozen=True)
class IntakeSelectionOption:
    """Opção de procedimento exposta na jornada de intake (design D9/D10)."""

    key: str
    label: str
    enabled: bool
    aliases: tuple[str, ...] = ()


def is_intake_selection_enabled(key: str) -> bool:
    """Flag de rollout de um código exposto (sempre habilitado sem gate)."""
    gate = _INTAKE_SELECTION_FLAG_GATES.get(key)
    return True if gate is None else gate()


def _selection_search_aliases(key: str) -> tuple[str, ...]:
    """Aliases pesquisáveis de uma chave, derivados do catálogo.

    Seleção composta (``eda_colonoscopy``) é encontrada também pelas labels dos
    componentes — nenhum alias é inventado localmente; identidade atômica usa
    somente a própria label.
    """
    components = procedure_types_for_selection(key)
    if len(components) == 1:
        return ()
    return tuple(PROCEDURE_LABELS[code] for code in components)


def intake_selection_options() -> tuple[IntakeSelectionOption, ...]:
    """Opções ordenadas de procedimento para as jornadas de intake (R1/D10).

    Compõe o catálogo (label/aliases) com as flags de rollout sobre a lista
    explícita de códigos publicados. O template SSR usa exatamente esta lista;
    ampliar a exposição é acrescentar o código em
    ``INTAKE_EXPOSED_SELECTION_KEYS``.
    """
    return tuple(
        IntakeSelectionOption(
            key=key,
            label=_selection_label(key),
            enabled=is_intake_selection_enabled(key),
            aliases=_selection_search_aliases(key),
        )
        for key in INTAKE_EXPOSED_SELECTION_KEYS
    )


@dataclass(frozen=True)
class NirProcedureFilterOption:
    """Opção de filtro por procedimento declarado das filas NIR (design D12)."""

    key: str
    label: str


def nir_procedure_filter_options() -> tuple[NirProcedureFilterOption, ...]:
    """Opções ordenadas de filtro declarado das filas NIR (R5/D12).

    Compõe "Todos os tipos" com as chaves de seleção publicadas no intake, na
    ordem canônica do catálogo. As flags de intake NÃO gateiam filtros: elas
    limitam somente novos intakes (R6); casos existentes de qualquer identidade
    continuam consultáveis, então nenhuma opção é omitida por flag.
    """
    return (
        NirProcedureFilterOption(key="all", label="Todos os tipos"),
        *(NirProcedureFilterOption(key=key, label=_selection_label(key)) for key in INTAKE_EXPOSED_SELECTION_KEYS),
    )


def validate_exam_type(exam_type: str | None) -> str:
    """Valida e normaliza a seleção declarada (intake e correção NIR).

    Levanta ``ValueError`` se ausente/inválida. Aceita as chaves canônicas do
    catálogo (``SELECTION_KEYS``) — nunca inferência por texto (R1). Desde o
    Slice 005 a correção NIR aceita as seleções, então esta validação é
    compartilhada por novos intakes/reenvios e pela correção; os gates de flag
    de intake ficam em ``ensure_exam_type_allowed`` (novo caso/reenvio) e
    ``ensure_intake_selection_permitted`` (correção, D10), não aqui.
    """
    value = (exam_type or "").strip()
    if value not in _DECLARED_SELECTION_VALUES:
        raise ValueError(f"Selecione o tipo de exame ({_SELECTION_CHOICES_LABEL}).")
    return value


def ensure_specialized_exam_type_allowed(exam_type: str | None) -> str:
    """Gate de choice + flag dos tipos ESPECIALIZADOS (Slice 007, R3).

    Exige a flag de intake do próprio tipo ligada para Ecoendoscopia/CPRE —
    fronteira compartilhada pelo intake (upload/reenvio), via
    ``ensure_exam_type_allowed``. EDA, Colonoscopia e EDA + Colonoscopia passam
    inalterados aqui; a flag de colonoscopia é aplicada por
    ``ensure_exam_type_allowed`` (novo caso) e por
    ``ensure_intake_selection_permitted`` (correção, D10).
    """
    value = validate_exam_type(exam_type)
    if value == ProcedureType.ECHOENDOSCOPY and not is_echoendoscopy_intake_enabled():
        raise ValueError(
            "Ecoendoscopia ainda não está habilitada para novos envios. "
            "Envie lotes apenas de EDA ou selecione um tipo disponível."
        )
    if value == ProcedureType.CPRE and not is_cpre_intake_enabled():
        raise ValueError(
            "CPRE ainda não está habilitada para novos envios. "
            "Envie lotes apenas de EDA ou selecione um tipo disponível."
        )
    return value


def ensure_exam_type_allowed(exam_type: str | None) -> str:
    """Validação central de choice + flag para criação de novo caso.

    - tipo ausente/inválido → ValueError;
    - colonoscopia ou combinação com flag de intake desligada → ValueError;
    - ecoendoscopia com a própria flag desligada → ValueError;
    - cpre com a própria flag desligada → ValueError (independente da de Eco);
    - EDA sempre permitido.

    Backend é a fonte de verdade; templates/JS apenas melhoram a UX.
    """
    value = ensure_specialized_exam_type_allowed(exam_type)
    if value in (ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY) and not is_colonoscopy_intake_enabled():
        raise ValueError(
            "Colonoscopia e EDA + Colonoscopia ainda não estão habilitadas para novos envios. "
            "Envie lotes apenas de EDA."
        )
    return value


def ensure_intake_selection_permitted(exam_type: str | None) -> str:
    """Gate de seleção pela jornada de intake (design D10, fix round 1).

    Fonte única da derivação por jornada: a MESMA lista habilitada que compõe o
    combobox (``intake_selection_options``, que aplica as flags de rollout sobre
    as chaves publicadas). Seleção publicada cuja flag de intake está desligada
    (Colonoscopia, ``eda_colonoscopy``, Ecoendoscopia, CPRE) é rejeitada; EDA e
    identidades sem gate sempre passam.

    Usado pela correção NIR: um POST manipulado não pode alcançar uma opção que
    a jornada de correção exclui.
    """
    value = validate_exam_type(exam_type)
    permitted = {option.key for option in intake_selection_options() if option.enabled}
    if value not in permitted:
        raise ValueError(f"{_selection_label(value)} ainda não está disponível para novos envios.")
    return value


# ── Correção de tipo e confirmação NIR serializadas (Slice 006) ───────────

# Reason codes do scope gate elegíveis para correção de tipo: o NIR vê
# declarado/detectado e corrige o tipo no MESMO caso (spec exam-type-correction).
# ``unsupported_procedure_combination`` entra no Slice 007 como "conjunto
# incompatível" da spec (ex.: ``Solicito EDA. Solicito CPRE.`` independentes
# chegam ao NIR sem falhar o pipeline). ``non_eda_request`` e
# ``invalid_regulation_report`` NÃO são elegíveis: não se resolvem trocando o
# tipo (fora do escopo suportado e falha de gate de regulação,
# respectivamente).
EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES: frozenset[str] = frozenset(
    {
        "exam_type_mismatch",
        "mixed_exam_request",
        "unknown_exam_type",
        "unsupported_procedure_combination",
        "conflicting_procedure_evidence",
    }
)

# Reserva NIR exigida por confirmação e recebimento (mesmo protocolo, C1/C3).
NIR_RECEIPT_CONTEXT: str = "nir_receipt"
NIR_RECEIPT_ROLE: str = "nir"

# Atraso do retry automático (Schedule ONCE) quando o enqueue pós-commit falha.
RECOVERY_SCHEDULE_DELAY_SECONDS: int = 60


class EnqueueAfterCommitError(RuntimeError):
    """Falha pós-commit ao enfileirar o reprocessamento LLM.

    A correção já foi commitada (caso em ``LLM_STRUCT``). ``recovery_scheduled``
    indica se um retry automático foi programado via ``Schedule`` ONCE.
    """

    def __init__(self, *, recovery_scheduled: bool, original: Exception) -> None:
        super().__init__("Falha pós-commit ao enfileirar o reprocessamento LLM.")
        self.recovery_scheduled = recovery_scheduled
        self.original = original


# Campos de reserva limpos após conclusão (o estado saiu de
# WAIT_R1_CLEANUP_THUMBS; a reserva nir_receipt perdeu o objeto).
_LOCK_CLEAR_FIELDS: tuple[str, ...] = (
    "locked_by",
    "locked_at",
    "locked_until",
    "lock_token",
    "lock_context",
    "lock_role",
)


def _validate_nir_actor(*, user: AccountsUser, active_role: str) -> None:
    """Valida o ator NIR explicitamente (C2).

    Exige ator autenticado, papel ativo NIR passado pela sessão e papel NIR
    atribuído ao usuário. Nunca deriva o papel ativo de papéis existentes de
    um usuário multi-role.
    """
    if user is None or not user.is_authenticated:
        raise PermissionError("Ator não autenticado.")
    if active_role != NIR_RECEIPT_ROLE:
        raise PermissionError("Papel ativo não é NIR; operação recusada.")
    if not user.roles.filter(name=NIR_RECEIPT_ROLE).exists():
        raise PermissionError("Usuário não possui o papel NIR atribuído.")


def _assert_receipt_lease(*, case: Case, user: AccountsUser, token: uuid.UUID) -> None:
    """Valida a reserva nir_receipt completa na instância bloqueada (C3).

    Owner correto, token exato, contexto ``nir_receipt``, papel ``nir`` e
    lease não expirada. Rejeita também lock do mesmo usuário quando token,
    contexto ou papel forem incompatíveis.
    """
    from apps.cases.services import assert_case_lock

    assert_case_lock(case=case, user=user, token=token, context=NIR_RECEIPT_CONTEXT)
    if case.lock_role != NIR_RECEIPT_ROLE:
        raise PermissionError(f"Papel da reserva inválido: esperado '{NIR_RECEIPT_ROLE}', obtido '{case.lock_role}'.")


def _clear_receipt_lease(case: Case) -> None:
    """Limpa os campos de reserva nir_receipt após conclusão."""
    for field in _LOCK_CLEAR_FIELDS:
        setattr(case, field, None if field not in ("lock_context", "lock_role") else "")
    case.save(update_fields=list(_LOCK_CLEAR_FIELDS))


def _acquire_locked_case(
    *,
    case_id: uuid.UUID,
    user: AccountsUser,
    active_role: str,
) -> Case:
    """Valida o ator NIR (C2) e retorna a instância bloqueada e atualizada.

    A linha é travada com ``select_for_update`` DENTRO da transação aberta
    pelo serviço; a instância retornada é a fonte de verdade para validação
    e mutação — nenhuma instância lida fora do lock é usada para salvar
    (C1/C4).
    """
    _validate_nir_actor(user=user, active_role=active_role)
    return Case.objects.select_for_update().get(pk=case_id)


def is_exam_type_correction_eligible(case: Case) -> bool:
    """Elegibilidade server-side para correção de tipo (R1).

    Estado estável pré-médico explicitamente enumerado: WAIT_R1_CLEANUP_THUMBS
    com manual review de mismatch/mixed/unknown. Estados transitórios de
    worker (R1_ACK_PROCESSING/EXTRACTING/LLM_STRUCT/LLM_SUGGEST/R2_POST_WIDGET)
    e qualquer decisão pós-WAIT_DOCTOR são recusados — nunca comparação
    textual frouxa de status.
    """
    if case.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        return False
    if case.doctor_decision:
        return False
    suggested = case.suggested_action
    if not isinstance(suggested, dict):
        return False
    if suggested.get("decision") != "manual_review_required":
        return False
    return suggested.get("reason_code") in EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES


# Justificativa breve da confirmação humana (D1): trim, 1–500 caracteres.
REVIEW_JUSTIFICATION_MAX_CHARS: int = 500


def _validate_review_acknowledgment(review_acknowledged: str | bool | None) -> None:
    """Valida o consentimento explícito de leitura da confirmação (D1/P1-A).

    Somente o valor documentado do checkbox (``"on"``) ou o booleano ``True``
    conferem autoridade — qualquer outro valor, inclusive strings não-vazias
    como ``"false"``/``"0"``/``"off"`` ou números, é recusado sem efeitos.
    Sem aliases, sem defaults verdadeiros e sem consentimento por truthiness.
    """
    if review_acknowledged is True or review_acknowledged == "on":
        return
    raise ValueError("Confirme que leu o relatório principal para validar o procedimento.")


def _validate_review_justification(review_justification: str | None) -> str:
    """Valida a justificativa livre da confirmação (D1).

    Devolve o texto com trim. Vazia, longa demais ou com U+0000 e recusada
    ANTES de qualquer efeito — sem sanitizacao silenciosa de conteudo.
    """
    text = (review_justification or "").strip()
    if not text:
        raise ValueError("Informe a justificativa da confirmação (1–500 caracteres).")
    if len(text) > REVIEW_JUSTIFICATION_MAX_CHARS:
        raise ValueError("Justificativa excede 500 caracteres.")
    if "\x00" in text:
        raise ValueError("Justificativa contém caractere inválido.")
    return text


def confirm_case_procedure_review(
    *,
    case_id: uuid.UUID,
    exam_type: str,
    user: AccountsUser,
    active_role: str,
    lock_token: uuid.UUID,
    review_acknowledged: str | bool | None,
    review_justification: str | None,
    review_event_id: int | str | None,
    source_fingerprint: str | None,
) -> Case:
    """Confirma o procedimento revisado no mesmo caso e reprocessa (S2/D1–D3).

    Substitui a correção operacional: aceita a seleção vigente OU outra
    seleção habilitada, com leitura confirmada e justificativa breve
    obrigatórias. POST antigo sem consentimento/justificativa e recusado
    sem mutação — nunca convertido em confirmação implícita (D8).

    Transacional com ``select_for_update``: nenhuma atualização parcial.
    Ator NIR e reserva completa validados sob o row lock. A revisão vista
    (``review_event_id``) deve ser a mais recente e o fingerprint da fonte
    deve coincidir com o atual; fonte/revisão que mudou desde o GET recusa
    sem efeitos. Preserva fontes e limpa derivados. Evento humano
    ``CASE_PROCEDURE_REVIEW_CONFIRMED`` (autoridade, D3) ANTES da transição
    FSM nomeada de volta a LLM_STRUCT. Após commit, enfileira o pipeline
    exatamente uma vez — nunca reextrai PDF; em falha de enqueue, agenda
    retry automático e levanta ``EnqueueAfterCommitError`` (confirmação
    commitada permanece durável, R9).

    Raises:
        ValueError: caso inelegível, seleção inválida/indisponível na
            jornada, consentimento/justificativa ausentes ou inválidos,
            revisão/fonte desatualizadas.
        PermissionError: ator sem papel NIR, papel ativo incorreto ou reserva
            incompatível/ausente/expirada.
        EnqueueAfterCommitError: enqueue pós-commit falhou (confirmação commitada).
    """
    validated_exam_type = ensure_intake_selection_permitted(exam_type)
    _validate_review_acknowledgment(review_acknowledged)
    justification = _validate_review_justification(review_justification)
    try:
        review_pk = int(review_event_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError("Revisão de origem inválida; reabra o caso e confirme novamente.") from None
    if not source_fingerprint:
        raise ValueError("Identificação da fonte ausente; reabra o caso e confirme novamente.")
    if lock_token is None:
        raise PermissionError("Token de reserva não fornecido.")

    with transaction.atomic():
        case = _acquire_locked_case(case_id=case_id, user=user, active_role=active_role)
        if not is_exam_type_correction_eligible(case):
            raise ValueError("Caso não está em revisão manual elegível para confirmação de procedimento.")
        # D3 — a revisão vista deve ser a mais recente; motivo codificado vem
        # do evento de revisão, nunca de input livre do cliente (D1).
        review = latest_review_event(case)
        if review is None or review.pk != review_pk:
            raise ValueError("A revisão mudou desde a abertura; reabra o caso e confirme novamente.")
        review_payload = review.payload if isinstance(review.payload, dict) else {}
        review_reason = str(review_payload.get("reason_code") or "")
        if review_reason not in EXAM_TYPE_CORRECTION_ELIGIBLE_REASON_CODES:
            raise ValueError("Revisão de origem inelegível para confirmação de procedimento.")
        # D3 — fingerprint revalidado sob o lock: fonte que mudou recusa.
        current_fingerprint = source_fingerprint_for_case(case)
        if current_fingerprint is None or current_fingerprint != source_fingerprint:
            raise ValueError("A fonte principal mudou desde a abertura; revise a fonte atual.")
        # S2 (D1): mesma seleção e confirmação válida — sem exigência de
        # diferença e sem reescrita do relatório. Conjuntos vêm das rows.
        new_procedures = list(procedure_types_for_selection(validated_exam_type))
        old_procedures = list(get_declared_procedure_types(case))
        _assert_receipt_lease(case=case, user=user, token=lock_token)

        # Invalida artefatos derivados do perfil anterior; fontes ficam.
        case.structured_data = None
        case.summary_text = ""
        case.suggested_action = None
        case.priority_signals = []

        # Detecção e disposições médicas voltam a pending (confirmação só é
        # permitida antes de qualquer decisão; nunca deixa projeção residual).
        reset_detection_and_doctor_statuses(case)

        # D3 — evento humano de autoridade com payload versionado (actor
        # obrigatório); a confirmação permanece durável na invalidação de
        # derivados para definir o conjunto efetivo no reprocessamento.
        case._record_event(
            REVIEW_CONFIRMED_EVENT,
            user=user,
            payload={
                "version": 1,
                "actor_role": "nir",
                "review_event_id": review.pk,
                "review_reason_code": review_reason,
                "previous_declared_procedures": old_procedures,
                "confirmed_procedures": sorted(new_procedures, key=lambda code: PROCEDURE_ORDER[code]),
                "selection_changed": set(new_procedures) != set(old_procedures),
                "justification": justification,
                "source_fingerprint": current_fingerprint,
            },
        )
        # Reroteamento pelo serviço único de declaração sob a MESMA
        # transação/lock; falha reverte tudo (incl. derivados/eventos/FSM).
        sync_declared_projection(case, new_procedures)
        case.save()

        # Transição FSM nomeada; CASE_REPROCESSING_REQUESTED é persistido no
        # save() seguinte, após o evento humano (ordem append-only, sem
        # sobrescrever _pending_event). Referencia a confirmação.
        confirmation_id = (
            CaseEvent.objects.filter(case=case, event_type=REVIEW_CONFIRMED_EVENT).order_by("-timestamp", "-id").first()
        )
        case.reprocess_after_exam_type_correction(
            user=user,
            payload={
                "reason_code": review_reason,
                "confirmation_event_id": confirmation_id.pk if confirmation_id else None,
            },
        )
        case.save()

        # A reserva nir_receipt perdeu o objeto (estado saiu de
        # WAIT_R1_CLEANUP_THUMBS): limpa para não vazar lock em LLM_STRUCT.
        _clear_receipt_lease(case)

    # Fora da transação: um único enqueue LLM pós-commit. Em falha, agenda
    # retry automático (Schedule ONCE) e levanta erro explícito.
    _enqueue_pipeline_or_schedule_recovery(case.case_id)
    return case


def confirm_case_receipt(
    *,
    case_id: uuid.UUID,
    user: AccountsUser,
    active_role: str,
    lock_token: uuid.UUID,
) -> Case:
    """Confirma recebimento do resultado final e conclui o caso (NIR).

    Mesmo protocolo de row lock da correção (C1): ``transaction.atomic`` +
    ``select_for_update`` no mesmo ``case_id``, ator NIR e reserva completa
    validados na instância bloqueada e atualizada, e somente então as
    transições FSM. Confirmação e correção nunca podem vencer juntas e
    nenhuma usa instância obsoleta para salvar.

    Preserva o fluxo legado: ciência de intercorrência pós-agendamento
    respondida (``acknowledge_scheduled_post_acceptance_issue``) ou limpeza
    comum (``cleanup_triggered`` → ``cleanup_completed``).

    Raises:
        ValueError: caso não está aguardando confirmação.
        PermissionError: ator ou reserva incompatíveis.
    """
    from apps.cases.services import (
        POST_SCHEDULE_ISSUE_STATUS_RESPONDED,
        acknowledge_scheduled_post_acceptance_issue,
    )

    if lock_token is None:
        raise PermissionError("Token de reserva não fornecido.")

    with transaction.atomic():
        case = _acquire_locked_case(case_id=case_id, user=user, active_role=active_role)
        if case.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
            raise ValueError("Este caso não está aguardando confirmação de recebimento.")
        _assert_receipt_lease(case=case, user=user, token=lock_token)

        if case.post_schedule_issue_status == POST_SCHEDULE_ISSUE_STATUS_RESPONDED:
            case = acknowledge_scheduled_post_acceptance_issue(case=case, user=user)
        else:
            case.cleanup_triggered(user=user)
            case.save()
            case.cleanup_completed(user=user)
            case.save()

        _clear_receipt_lease(case)

    return Case.objects.get(pk=case.case_id)


def _enqueue_pipeline_or_schedule_recovery(case_id: uuid.UUID) -> None:
    """R4/C5: um único enqueue LLM pós-commit; em falha agenda retry automático.

    O retry usa ``Schedule`` ONCE apontando para ``execute_pdf_extraction``:
    em ``LLM_STRUCT`` ela re-enfileira o pipeline sem reextrair o PDF
    (recovery idempotente existente). Nenhum enqueue de extração de PDF é
    feito aqui. Se a programação do retry também falhar, o caso permanece em
    ``LLM_STRUCT`` para recovery manual/documentado.
    """
    from apps.pipeline.tasks import enqueue_pipeline

    try:
        enqueue_pipeline(case_id)
    except Exception as exc:
        logger.exception("enqueue_pipeline falhou para %s — agendando retry", case_id)
        recovery_scheduled = False
        try:
            _schedule_pipeline_recovery(case_id)
            recovery_scheduled = True
        except Exception:
            logger.exception("Falha ao agendar retry automático para %s", case_id)
        raise EnqueueAfterCommitError(recovery_scheduled=recovery_scheduled, original=exc) from exc


def _schedule_pipeline_recovery(case_id: uuid.UUID) -> None:
    """Programa retry automático via django-q2 Schedule ONCE (C5/RR1/RR3).

    Direciona explicitamente ao cluster ``pdf`` — o único cluster implantado
    que executa ``execute_pdf_extraction`` (dev/prod rodam apenas
    ``Q_CLUSTER_NAME=llm`` e ``Q_CLUSTER_NAME=pdf``; schedules com cluster
    NULL só são consumidos pelo cluster default ``ats``, não implantado).

    Em ``LLM_STRUCT``, ``execute_pdf_extraction`` não reextrai PDF: reavalia
    o regulation gate e chama ``enqueue_pipeline``. ONCE usa o default
    ``repeats=-1``: o scheduler do django-q2 DELETA o Schedule após o
    dispatch, sem deixar nome residual determinístico por ``case_id`` que
    bloquearia um novo recovery do mesmo caso (IntegrityError).
    """
    from datetime import timedelta

    from django_q.models import Schedule
    from django_q.tasks import schedule as q_schedule

    q_schedule(
        "apps.intake.tasks.execute_pdf_extraction",
        str(case_id),
        schedule_type=Schedule.ONCE,
        next_run=timezone.now() + timedelta(seconds=RECOVERY_SCHEDULE_DELAY_SECONDS),
        name=f"slice006-recovery:{case_id}",
        cluster="pdf",
    )


# ── Validation ──────────────────────────────────────────────────────────


class FileValidationError(ValueError):
    """A single file failed validation (does not imply batch rejection)."""


class BatchValidationError(ValueError):
    """The entire batch is invalid (e.g. empty or exceeds batch limit)."""


class AttachmentValidationError(ValueError):
    """An attachment file failed validation (rejects the whole batch)."""


def validate_single_file(file: UploadedFile) -> None:
    """Validate a single uploaded PDF file.

    Raises ``FileValidationError`` if the file fails any check.

    Checks (in order):
    1. Extension must be ``.pdf``.
    2. File size must not exceed ``INTAKE_MAX_UPLOAD_BYTES_PER_FILE``.
    """
    file_name = file.name or ""
    file_size = file.size or 0

    # Extension check (belt-and-suspenders with form validator)
    if not file_name.lower().endswith(".pdf"):
        raise FileValidationError(f'"{file_name}" não é um arquivo PDF.')

    max_file_size = settings.INTAKE_MAX_UPLOAD_BYTES_PER_FILE
    if file_size > max_file_size:
        raise FileValidationError(
            f'"{file_name}" excede o limite de {max_file_size // (1024 * 1024)} MB '
            f"({file_size / (1024 * 1024):.1f} MB)."
        )


def validate_batch(files: list[UploadedFile]) -> None:
    """Validate the entire batch before per-file processing.

    Raises ``BatchValidationError`` if the batch is rejected outright.
    """
    if not files:
        raise BatchValidationError("Nenhum arquivo enviado.")

    max_files = settings.INTAKE_MAX_FILES_PER_BATCH
    if len(files) > max_files:
        raise BatchValidationError(f"Máximo de {max_files} arquivos por lote. Recebidos: {len(files)}.")

    total_bytes = sum(f.size or 0 for f in files)
    max_batch = settings.INTAKE_MAX_UPLOAD_BYTES_PER_BATCH
    if total_bytes > max_batch:
        raise BatchValidationError(
            f"Tamanho total do lote ({total_bytes / (1024 * 1024):.1f} MB) "
            f"excede o limite de {max_batch // (1024 * 1024)} MB."
        )


# ── Attachment validation ────────────────────────────────────────────────


def validate_attachment_file(file: UploadedFile) -> None:
    """Validate a single attachment file.

    Raises ``AttachmentValidationError`` if the file fails any check.

    Checks:
    1. Extension must be .pdf, .jpg, .jpeg, or .png.
    2. Content-type must be one of the accepted types.
    3. File size must not exceed ``INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE``.
    """
    file_name = file.name or ""
    file_size = file.size or 0
    content_type = (file.content_type or "").lower()

    # Extension check
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in ACCEPTED_ATTACHMENT_EXTENSIONS:
        raise AttachmentValidationError(f'"{file_name}" formato não aceito. Use PDF, JPEG ou PNG.')

    # Content-type check (belt-and-suspenders)
    if content_type and content_type not in ACCEPTED_ATTACHMENT_CONTENT_TYPES:
        raise AttachmentValidationError(f'"{file_name}" tipo de conteúdo não aceito: {content_type}.')

    # Size check
    max_size = settings.INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE
    if file_size > max_size:
        raise AttachmentValidationError(
            f'"{file_name}" excede o limite de {max_size // (1024 * 1024)} MB ({file_size / (1024 * 1024):.1f} MB).'
        )


def validate_attachments(
    attachments: list[UploadedFile],
    pdf_count: int,
) -> None:
    """Validate the full set of attachments before processing.

    Raises ``AttachmentValidationError`` on first violation.

    Checks:
    1. Attachments are only allowed when there is exactly 1 PDF.
    2. Maximum 10 attachments.
    3. Total size of attachments does not exceed per-case limit.
    4. Per-file validation via ``validate_attachment_file``.
    """
    if not attachments:
        return

    # Only allowed with exactly 1 PDF
    if pdf_count != 1:
        raise AttachmentValidationError(
            "Anexos só são permitidos quando há exatamente 1 relatório principal. "
            "Remova os anexos ou envie apenas 1 PDF."
        )

    # Max count
    max_attachments = settings.INTAKE_MAX_ATTACHMENTS_PER_CASE
    if len(attachments) > max_attachments:
        raise AttachmentValidationError(f"Máximo de {max_attachments} anexos por caso. Recebidos: {len(attachments)}.")

    # Per-file validation
    for att in attachments:
        validate_attachment_file(att)

    # Total size
    total_bytes = sum(f.size or 0 for f in attachments)
    max_total = settings.INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE
    if total_bytes > max_total:
        raise AttachmentValidationError(
            f"Tamanho total dos anexos ({total_bytes / (1024 * 1024):.1f} MB) "
            f"excede o limite de {max_total // (1024 * 1024)} MB."
        )


# ── Attachment creation ─────────────────────────────────────────────────


def create_case_attachment(
    *,
    case: Case,
    uploaded_file: UploadedFile,
    user: AccountsUser,
    upload_phase: str = "initial",
) -> CaseAttachment:
    """Create a CaseAttachment from an uploaded file.

    Computes SHA256 hash, saves metadata, and creates the record.
    The file is already saved via the FileField on save().
    """
    file_content = uploaded_file.read()
    sha256 = hashlib.sha256(file_content).hexdigest()
    file_name = uploaded_file.name or ""
    content_type = uploaded_file.content_type or "application/octet-stream"
    file_size = uploaded_file.size or len(file_content)
    ext = os.path.splitext(file_name)[1].lower()

    # Rewind the file for Django's storage backend
    uploaded_file.seek(0)

    attachment = CaseAttachment(
        case=case,
        file=uploaded_file,
        original_filename=file_name,
        stored_filename=f"{case.case_id}{ext}",
        content_type=content_type,
        size_bytes=file_size,
        sha256=sha256,
        uploaded_by=user,
        upload_phase=upload_phase,
        uploaded_when_case_status=case.status,
    )
    attachment.save()
    return attachment


def record_attachment_event(attachment: CaseAttachment) -> None:
    """Record CASE_ATTACHMENT_ADDED audit event."""
    from apps.cases.models import CaseEvent

    CaseEvent.objects.create(
        case=attachment.case,
        event_type="CASE_ATTACHMENT_ADDED",
        actor=attachment.uploaded_by,
        actor_type="human",
        payload={
            "attachment_id": str(attachment.attachment_id),
            "original_filename": attachment.original_filename,
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
            "sha256": attachment.sha256,
        },
    )


# ── Processing ──────────────────────────────────────────────────────────


def process_uploaded_files(
    files: list[UploadedFile],
    user: AccountsUser,
    attachments: list[UploadedFile] | None = None,
    *,
    exam_type: str | None = None,
) -> tuple[list[Case], list[str]]:
    """Validate and process a batch of uploaded PDFs with optional attachments.

    For each valid file a new ``Case`` is created, the PDF saved, the
    FSM advanced to ``R1_ACK_PROCESSING``, and PDF extraction enqueued.

    ``exam_type`` é obrigatório (R2): um único tipo válido se aplica a TODOS
    os PDFs do lote. A validação ocorre ANTES de qualquer criação de caso;
    tipo ausente/inválido/bloqueado pela flag rejeita o request inteiro.

    Args:
        files: List of uploaded files from ``request.FILES.getlist(...)``.
        user: The authenticated NIR user creating the cases.
        attachments: Optional list of attachment files.
        exam_type: Tipo de exame declarado para o lote inteiro.

    Returns:
        A tuple ``(cases, errors)`` where ``cases`` is the list of
        successfully created ``Case`` instances and ``errors`` is a list
        of human-readable error messages for the files that were rejected.
    """
    cases: list[Case] = []
    errors: list[str] = []

    # Exam type gate FIRST — sem tipo válido, nenhum caso é criado (R2/R3)
    try:
        validated_exam_type = ensure_exam_type_allowed(exam_type)
    except ValueError as exc:
        return [], [str(exc)]

    # Batch-level validation (empty, too many, too large total)
    try:
        validate_batch(files)
    except BatchValidationError as exc:
        return [], [str(exc)]

    # Validate and process attachments
    att_list = attachments or []
    attachment_error: str | None = None
    if att_list:
        try:
            validate_attachments(att_list, pdf_count=len(files))
        except AttachmentValidationError as exc:
            attachment_error = str(exc)
            # If multi-PDF, we still create cases but reject attachments
            # If single PDF with invalid attachments, we don't create cases
            if len(files) == 1:
                errors.append(str(exc))
                return [], errors

    # Per-file validation & processing
    for file in files:
        try:
            validate_single_file(file)
        except FileValidationError as exc:
            errors.append(str(exc))
            continue

        case = _create_case_from_file(file, user, exam_type=validated_exam_type)
        cases.append(case)

    # If there was a multi-PDF attachment error, report it after creating cases
    if attachment_error:
        errors.append(attachment_error)

    # If we have exactly 1 case and valid attachments, save them
    if cases and att_list and len(cases) == 1 and not attachment_error:
        case = cases[0]
        for att_file in att_list:
            try:
                attachment = create_case_attachment(
                    case=case,
                    uploaded_file=att_file,
                    user=user,
                    upload_phase="initial",
                )
                record_attachment_event(attachment)
            except Exception as exc:
                logger.exception("Failed to save attachment for case %s", case.case_id)
                errors.append(f"Erro ao salvar anexo: {exc}")

    return cases, errors


def _create_case_from_file(
    file: UploadedFile,
    user: AccountsUser,
    *,
    exam_type: str,
) -> Case:
    """Create a single Case from an uploaded PDF file.

    Steps:
    1. Create ``Case(created_by=user)`` (conjunto declarado via rows).
    2. Save ``pdf_file``.
    3. FSM transition ``NEW → R1_ACK_PROCESSING``.
    4. Enqueue async PDF extraction.

    The caller is responsible for calling ``case.save()`` on each
    transition step.
    """
    # 1. Create case
    with transaction.atomic():
        case = Case.objects.create(created_by=user)

        # 2. Save PDF
        case.pdf_file = file
        case.save()

        # Slice 001 (R5): projeção declarada no MESMO caso — um PDF combinado
        # vira UM Case com DUAS rows; falha aqui reverte o caso.
        set_declared_procedures(
            case=case,
            procedure_types=procedure_types_for_selection(exam_type),
            actor=user,
        )

        # 3. FSM: NEW → R1_ACK_PROCESSING
        case.start_processing(user=user)
        case.save()

    # 4. Enqueue async PDF extraction (runs in background cluster "pdf")
    from apps.intake.tasks import enqueue_pdf_extraction

    enqueue_pdf_extraction(case.case_id)

    return case


# ── Corrected resubmission ──────────────────────────────────────────────


def create_corrected_resubmission(
    *,
    original_case: Case,
    pdf_file: UploadedFile,
    user: AccountsUser,
    correction_reason: str,
    attachments: list[UploadedFile] | None = None,
    exam_type: str | None = None,
) -> Case:
    """Create a new Case that explicitly corrects a previous Case.

    ``exam_type`` é OBRIGATÓRIO (Slice 007): o novo caso exige escolha
    explícita do NIR — o tipo do original NÃO é herdado. O tipo informado
    passa sempre pela validação central (choice + flag de intake), pois o
    reenvio cria um NOVO Case — é novo intake (R3/F1): flag desligada
    impede novo colonoscopia mesmo quando o original é colonoscopia.

    Steps:
    1. Validate correction_reason (required, not blank).
    2. Validate pdf_file (must be a single valid PDF).
    3. Validate attachments per existing rules.
    4. Create new ``Case`` with correction metadata.
    5. Save PDF and advance FSM to ``R1_ACK_PROCESSING``.
    6. Enqueue PDF extraction.
    7. Save attachments on the new case (if provided).
    8. Record ``CASE_CORRECTION_CREATED`` on the new case.
    9. Record ``CASE_MARKED_SUPERSEDED`` on the original case.
    10. Return the new case.

    The original case is NOT modified in status, decision fields,
    attachments, or any other data.
    """
    from django.utils import timezone as tz

    # 0. Exam type OBRIGATÓRIO — validação central (choice + flag) ANTES
    #    de qualquer criação/evento/save/enqueue. Ausente/inválido levanta
    #    ValueError e nada é criado (R3).
    validated_exam_type = ensure_exam_type_allowed(exam_type)

    # 1. Validate correction_reason
    reason = (correction_reason or "").strip()
    if not reason:
        raise ValueError("Motivo do reenvio corrigido é obrigatório.")

    # 2. Validate PDF
    validate_single_file(pdf_file)

    # 3. Validate attachments
    att_list = attachments or []
    if att_list:
        validate_attachments(att_list, pdf_count=1)

    # 4/5/6. Create new Case (atomic): PDF, projeção declarada e FSM inicial.
    # Slice 001: reenvio é NOVO intake — a seleção declarada projeta rows
    # (combinação → duas rows); falha reverte o caso inteiro.
    with transaction.atomic():
        new_case = Case.objects.create(
            created_by=user,
            corrects_case=original_case,
            correction_reason=reason,
            correction_created_by=user,
            correction_created_at=tz.now(),
        )

        new_case.pdf_file = pdf_file
        new_case.save()

        set_declared_procedures(
            case=new_case,
            procedure_types=procedure_types_for_selection(validated_exam_type),
            actor=user,
        )

        new_case.start_processing(user=user)
        new_case.save()

    # 6. Enqueue PDF extraction
    from apps.intake.tasks import enqueue_pdf_extraction

    enqueue_pdf_extraction(new_case.case_id)

    # 7. Save attachments on the new case (if provided)
    if att_list:
        for att_file in att_list:
            attachment = create_case_attachment(
                case=new_case,
                uploaded_file=att_file,
                user=user,
                upload_phase="initial",
            )
            record_attachment_event(attachment)

    # 8. Record CASE_CORRECTION_CREATED on new case
    new_case._record_event(
        "CASE_CORRECTION_CREATED",
        user=user,
        payload={
            "original_case_id": str(original_case.case_id),
            "original_agency_record_number": original_case.agency_record_number or "",
            "correction_reason": reason,
            "created_by_id": str(user.pk),
            # R4: tipo do novo caso — divergência fica auditável sem mudar
            # semântica dos eventos existentes (sem PDF/texto clínico).
            "exam_type": validated_exam_type,
        },
    )
    new_case.save()

    # 9. Record CASE_MARKED_SUPERSEDED on original case
    original_case._record_event(
        "CASE_MARKED_SUPERSEDED",
        user=user,
        payload={
            "corrected_case_id": str(new_case.case_id),
            "corrected_agency_record_number": new_case.agency_record_number or "",
            "correction_reason": reason,
            "created_by_id": str(user.pk),
        },
    )
    original_case.save()

    return new_case
