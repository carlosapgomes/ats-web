"""Projeção de procedimentos por caso — serviço central (design D1/D4).

``CaseProcedure`` é a fonte alvo de EDA/Colonoscopia como componentes de um
único caso; ``Case.exam_type`` permanece apenas como ponte transitória
(dual-write centralizado, removida no Slice 007).

Writes críticos (declaração) passam por este módulo: nenhuma view escreve rows
diretamente. A declaração é atômica — falha em uma row não deixa caso/projeção
parcial. Detecção (``set_detected_procedures``, Slice 002) e decisão médica
(``record_doctor_procedure_decisions``, Slice 003) também são atômicas e
centralizadas aqui (D4).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseEvent,
    CaseProcedure,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)

# Ordem canônica de exibição: EDA antes de Colonoscopia (label "EDA + Colonoscopia").
_PROCEDURE_ORDER: dict[str, int] = {
    ProcedureType.EDA: 0,
    ProcedureType.COLONOSCOPY: 1,
}

# Seleção declarada aceita no intake: EDA, Colonoscopia ou a combinação.
_DECLARED_SINGLE_TYPES: tuple[str, ...] = (ProcedureType.EDA, ProcedureType.COLONOSCOPY)


def normalize_procedure_selection(procedure_types: Any) -> tuple[str, ...]:
    """Valida e ordena uma seleção declarada de procedimentos.

    Regras: não-vazia, sem duplicatas e somente EDA/Colonoscopia (sem CPRE ou
    procedure genérica). Retorna tupla ordenada (eda, colonoscopy) para
    exibição/auditoria determinísticas. Levanta ``ValueError`` caso contrário.
    """
    seen: list[str] = []
    for raw in procedure_types or ():
        value = str(raw)
        if value not in _DECLARED_SINGLE_TYPES:
            raise ValueError(f"Procedimento inválido: {value!r}. Aceitos: {', '.join(_DECLARED_SINGLE_TYPES)}.")
        if value not in seen:
            seen.append(value)
    if not seen:
        raise ValueError("Selecione ao menos um procedimento (EDA e/ou Colonoscopia).")
    seen.sort(key=lambda t: _PROCEDURE_ORDER[t])
    return tuple(seen)


def bridge_exam_type_for_types(procedure_types: tuple[str, ...]) -> str:
    """Valor transitório de ``Case.exam_type`` para um conjunto declarado.

    Um tipo → o próprio tipo; dois tipos → ``EDA_COLONOSCOPY`` (ponte).
    Nunca chamado com conjunto vazio/inválido (passa por normalize).
    """
    if len(procedure_types) == 2:
        return EDA_COLONOSCOPY
    return procedure_types[0]


def _sync_declared_rows(case: Case, procedure_types: tuple[str, ...]) -> None:
    """Marca as rows declaradas e desmarca as demais do caso.

    Rows não declaradas permanecem (projeção de transformação, D1); apenas a
    flag ``declared_by_nir`` muda. Sem lock: os callers garantem o contexto
    (transaction + row lock do Case).
    """
    for procedure_type in procedure_types:
        row, _ = CaseProcedure.objects.get_or_create(case=case, procedure_type=procedure_type)
        if not row.declared_by_nir:
            row.declared_by_nir = True
            row.save(update_fields=["declared_by_nir"])
    CaseProcedure.objects.filter(case=case).exclude(procedure_type__in=procedure_types).update(declared_by_nir=False)


def sync_declared_projection(case: Case, procedure_types: Any) -> None:
    """Escreve projeção + ponte numa transação/lock já existentes (correção).

    Usado por fluxos que já possuem ``transaction.atomic`` + ``select_for_update``
    (ex.: ``correct_case_exam_type``). NÃO salva o ``Case`` nem registra evento:
    o caller decide o save e o evento de auditoria do fluxo.
    """
    types = normalize_procedure_selection(procedure_types)
    _sync_declared_rows(case, types)
    case.exam_type = bridge_exam_type_for_types(types)


def set_declared_procedures(
    *,
    case: Case,
    procedure_types: Any,
    actor: Any = None,
) -> Case:
    """Define o conjunto declarado de um caso atomicamente (D4).

    Cria/atualiza rows declaradas, atualiza a ponte ``Case.exam_type`` e
    registra o evento enxuto ``CASE_PROCEDURES_DECLARED`` com o conjunto
    ordenado (sem texto clínico). Toda falha reverte a operação inteira —
    nunca deixa caso/projeção parcial.

    Args:
        case: instância do caso (a linha é relockada dentro da transação).
        procedure_types: iterável com eda/colonoscopy (combinação = os dois).
        actor: usuário autor da declaração (NIR), para auditoria.

    Returns:
        Instância atualizada do caso.
    """
    types = normalize_procedure_selection(procedure_types)
    with transaction.atomic():
        locked = Case.objects.select_for_update().get(pk=case.pk)
        _sync_declared_rows(locked, types)
        locked.exam_type = bridge_exam_type_for_types(types)
        locked._record_event(
            "CASE_PROCEDURES_DECLARED",
            user=actor,
            payload={"procedures": list(types)},
        )
        locked.save()
    return locked


def normalize_detected_set(detected_types: Any) -> tuple[str, ...]:
    """Valida e ordena um conjunto detectado (apenas EDA/Colonoscopia, sem duplicatas).

    Conjunto vazio é aceito (nenhum procedimento detectado) — usado pela
    projeção quando a análise não sustenta nenhum procedimento.
    """
    seen: list[str] = []
    for raw in detected_types or ():
        value = str(raw)
        if value not in _DECLARED_SINGLE_TYPES:
            raise ValueError(f"Procedimento detectado inválido: {value!r}. Aceitos: EDA/Colonoscopia.")
        if value not in seen:
            seen.append(value)
    seen.sort(key=lambda t: _PROCEDURE_ORDER[t])
    return tuple(seen)


def set_detected_procedures(
    *,
    case: Case,
    detected_types: Any,
    actor: Any = None,
) -> Case:
    """Projeta a detecção da análise atomicamente (D4/R4, Slice 002).

    Marca ``detection_status=DETECTED`` para cada procedimento detectado,
    criando row não declarada quando o segundo procedimento é detectado, e
    marca ``NOT_DETECTED`` nas rows existentes fora do conjunto. NUNCA altera
    ``declared_by_nir`` (LLM não escreve a declaração). Falha reverte a
    operação inteira — nenhum conjunto parcial.

    Args:
        case: instância do caso (relockada dentro da transação).
        detected_types: iterável com eda/colonoscopy detectados (pode ser vazio).
        actor: usuário/autor do pipeline para auditoria (opcional).

    Returns:
        Instância atualizada do caso.
    """
    types = normalize_detected_set(detected_types)
    with transaction.atomic():
        locked = Case.objects.select_for_update().get(pk=case.pk)
        for procedure_type in types:
            row, _ = CaseProcedure.objects.get_or_create(case=locked, procedure_type=procedure_type)
            if row.detection_status != DetectionStatus.DETECTED:
                row.detection_status = DetectionStatus.DETECTED
                row.save(update_fields=["detection_status"])
        CaseProcedure.objects.filter(case=locked).exclude(procedure_type__in=types).update(
            detection_status=DetectionStatus.NOT_DETECTED
        )
        locked.save()
    return locked


def reset_detection_and_doctor_statuses(case: Case) -> None:
    """Zera detecção e disposições médicas para reprocessamento (D12/R2).

    Usado pela correção NIR: como o conjunto declarado muda, a detecção e as
    decisões médicas (sempre pendentes nesse estágio — correção é bloqueada
    após qualquer decisão) voltam a ``pending`` e a razão médica é apagada.
    NÃO altera ``declared_by_nir`` (a projeção da declaração é escrita por
    ``sync_declared_projection``/``set_declared_procedures``) nem deleta rows
    — a transformação permanece auditável (D1).
    """
    CaseProcedure.objects.filter(case=case).update(
        detection_status=DetectionStatus.PENDING,
        doctor_disposition=DoctorDisposition.PENDING,
        doctor_reason="",
    )


def record_doctor_procedure_decisions(
    *,
    case: Case,
    decisions: list[dict[str, Any]],
    actor: Any = None,
) -> Case:
    """Persiste as decisões médicas por componente atomicamente (D9/R3).

    Cada decisão: ``{procedure_type, disposition (approved|denied), reason,
    added_by_doctor}``. Escreve ``doctor_disposition``/``doctor_reason`` na
    row ``CaseProcedure`` correspondente (get_or_create — inclusão cria a row
    sem alterar ``declared_by_nir``/``detection_status``) e registra o evento
    enxuto ``DOCTOR_PROCEDURE_DECISIONS_RECORDED`` com a lista ordenada
    (EDA antes de Colonoscopia). NUNCA reexecuta LLM e NUNCA escreve a
    detecção/declaração. Toda falha reverte a operação inteira — nenhuma
    disposição ou evento parcial.

    Args:
        case: instância do caso (relockada dentro da transação).
        decisions: lista ordenável de decisões por componente (R2).
        actor: usuário médico autor da decisão, para auditoria.

    Returns:
        Instância atualizada do caso.
    """
    with transaction.atomic():
        locked = Case.objects.select_for_update().get(pk=case.pk)
        entries: list[dict[str, Any]] = []
        for decision in decisions:
            procedure_type = str(decision["procedure_type"])
            disposition = str(decision["disposition"])
            if disposition not in (DoctorDisposition.APPROVED, DoctorDisposition.DENIED):
                raise ValueError(f"Disposição inválida para {procedure_type}: {disposition!r}.")
            reason = str(decision.get("reason") or "").strip()
            row, _ = CaseProcedure.objects.get_or_create(case=locked, procedure_type=procedure_type)
            row.doctor_disposition = disposition
            row.doctor_reason = reason
            row.save(update_fields=["doctor_disposition", "doctor_reason"])
            entries.append(
                {
                    "procedure_type": procedure_type,
                    "disposition": disposition,
                    "reason_present": bool(reason),
                    "added_by_doctor": bool(decision.get("added_by_doctor")),
                }
            )
        entries.sort(key=lambda entry: _PROCEDURE_ORDER[entry["procedure_type"]])
        CaseEvent.objects.create(
            case=locked,
            event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED",
            actor=actor,
            actor_type="human",
            payload={"decisions": entries},
        )
    return locked


# ── Leitura para consumo (templates NIR recebem label projetado na view) ──


def get_declared_procedure_types(case: Case, *, fallback_to_bridge: bool = True) -> tuple[str, ...]:
    """Conjunto declarado ordenado a partir da projeção.

    Fallback explícito da ponte transitória: casos criados antes da projeção
    (fixtures/legado) ou combinados históricos sem rows refletem
    ``Case.exam_type`` — mantém cada slice verde até o cutover. A UI NUNCA
    consulta a ponte diretamente: a view projeta este resultado no contexto.

    ``fallback_to_bridge=False`` (modo estrito, Slice 008) desabilita o
    fallback: um caso sem rows declaradas devolve ``()``. Consumidores já
    migrados (fluxo NIR) devem passá-lo explicitamente; os demais preservam
    o default até os Slices 009–010.
    """
    declared = sorted(
        (p.procedure_type for p in case.procedures.all() if p.declared_by_nir),
        key=lambda t: _PROCEDURE_ORDER[t],
    )
    if declared:
        return tuple(declared)
    if not fallback_to_bridge:
        return ()
    if case.exam_type == EDA_COLONOSCOPY:
        return (ProcedureType.EDA, ProcedureType.COLONOSCOPY)
    if case.exam_type in _DECLARED_SINGLE_TYPES:
        return (case.exam_type,)
    return ()


def get_detected_procedure_types(case: Case, *, fallback_to_bridge: bool = True) -> tuple[str, ...]:
    """Conjunto detectado ordenado (dimensão da fila médica Pendentes).

    Fallback explícito da ponte transitória: casos sem rows (legado/fixtures)
    refletem ``Case.exam_type`` — mantém a fila médica verde até o cutover.
    ``fallback_to_bridge=False`` (modo estrito, Slice 008) devolve ``()`` para
    caso sem rows detectadas.
    """
    detected = sorted(
        (p.procedure_type for p in case.procedures.all() if p.detection_status == DetectionStatus.DETECTED),
        key=lambda t: _PROCEDURE_ORDER[t],
    )
    if detected:
        return tuple(detected)
    if not fallback_to_bridge:
        return ()
    if case.exam_type == EDA_COLONOSCOPY:
        return (ProcedureType.EDA, ProcedureType.COLONOSCOPY)
    if case.exam_type in _DECLARED_SINGLE_TYPES:
        return (case.exam_type,)
    return ()


def get_approved_procedure_types(case: Case, *, fallback_to_bridge: bool = True) -> tuple[str, ...]:
    """Conjunto autorizado pelo médico, ordenado (dimensão do CHD/Decididos Hoje).

    Fonte autoritativa é a row ``CaseProcedure.doctor_disposition=approved``;
    fallback da ponte para casos legados aceitos sem rows
    (``doctor_decision=accept``) preserva a fila até o cutover. Em modo estrito
    (``fallback_to_bridge=False``, Slice 008) NÃO chega à ponte — nem direto,
    nem via ``get_declared_procedure_types``.
    """
    approved = sorted(
        (p.procedure_type for p in case.procedures.all() if p.doctor_disposition == DoctorDisposition.APPROVED),
        key=lambda t: _PROCEDURE_ORDER[t],
    )
    if approved:
        return tuple(approved)
    if not fallback_to_bridge:
        return ()
    if case.doctor_decision == "accept":
        return get_declared_procedure_types(case)
    return ()


def selection_key(procedure_types: tuple[str, ...]) -> str:
    """Chave textual do badge/CSS: eda | colonoscopy | eda_colonoscopy.

    Derivada do conjunto (nunca do campo legado), para labels acessíveis.
    """
    if len(procedure_types) == 2:
        return EDA_COLONOSCOPY
    return procedure_types[0] if procedure_types else ""


def format_procedure_selection(procedure_types: Any) -> str:
    """Label textual ordenado: 'EDA', 'Colonoscopia' ou 'EDA + Colonoscopia'."""
    ordered = normalize_procedure_selection(procedure_types)
    return " + ".join(ProcedureType(t).label for t in ordered)
