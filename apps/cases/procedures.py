"""Projeção de procedimentos por caso — serviço central (design D1/D4).

``CaseProcedure`` é a fonte alvo de EDA/Colonoscopia como componentes de um
único caso; ``Case.exam_type`` permanece apenas como ponte transitória
(dual-write centralizado, removida no Slice 007).

Writes críticos (declaração) passam por este módulo: nenhuma view escreve rows
diretamente. A declaração é atômica — falha em uma row não deixa caso/projeção
parcial. Detecção (``set_detected_procedures``) e decisão médica
(``record_doctor_procedure_decisions``) são slices posteriores e NÃO existem
aqui (YAGNI — não antecipar pipeline/CHD/dashboard).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseProcedure,
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


# ── Leitura para consumo (templates NIR recebem label projetado na view) ──


def get_declared_procedure_types(case: Case) -> tuple[str, ...]:
    """Conjunto declarado ordenado a partir da projeção.

    Fallback explícito da ponte transitória: casos criados antes da projeção
    (fixtures/legado) ou combinados históricos sem rows refletem
    ``Case.exam_type`` — mantém cada slice verde até o cutover. A UI NUNCA
    consulta a ponte diretamente: a view projeta este resultado no contexto.
    """
    declared = sorted(
        (p.procedure_type for p in case.procedures.all() if p.declared_by_nir),
        key=lambda t: _PROCEDURE_ORDER[t],
    )
    if declared:
        return tuple(declared)
    if case.exam_type == EDA_COLONOSCOPY:
        return (ProcedureType.EDA, ProcedureType.COLONOSCOPY)
    if case.exam_type in _DECLARED_SINGLE_TYPES:
        return (case.exam_type,)
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
