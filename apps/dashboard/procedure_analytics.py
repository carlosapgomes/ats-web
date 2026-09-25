"""Analytics por dimensão de procedimento (Slice 006 / design D14).

Separa métricas de casos (case-level, R1) de volume de componentes (R3),
classifica cada caso em categoria exclusiva por dimensão (R2/D12), expõe a
matriz de conversão declarado→detectado→autorizado (R4) e conta
agendamentos casados uma única vez (R4).

Todos os predicates/helpers de projeção estão centralizados aqui e
reutilizam os helpers de domínio (``get_*_procedure_types``), evitando
fórmulas duplicadas de accepted/denied/admin-closed (R6). Universo de
categorias e de opções de filtro derivam do catálogo (Slice 009, R6) —
nenhuma lista local de tipos.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Exists, OuterRef, Q

from apps.cases.models import EDA_COLONOSCOPY, CaseEvent, CaseProcedure
from apps.cases.procedures import (
    PROCEDURE_CATALOG,
    SELECTION_KEYS,
    SUPPORTED_PROCEDURE_TYPES,
    format_procedure_selection,
    get_approved_procedure_types,
    get_declared_procedure_types,
    get_detected_procedure_types,
    is_paired_appointment_set,
    procedure_types_for_selection,
    selection_key,
)

# Dimensões válidas do parâmetro SSR ``procedure_dimension``.
# Default documentado: ``declared`` (dimensão da declaração NIR).
DIMENSIONS: tuple[str, ...] = ("declared", "detected", "approved")

DIMENSION_LABELS: dict[str, str] = {
    "declared": "Solicitado (NIR)",
    "detected": "Detectado (análise)",
    "approved": "Autorizado (médico)",
}

# Seleções válidas do parâmetro ``procedure_selection`` da tabela gerencial
# (Slice 009, R2/R6): ``all`` (sem filtro), cada chave de seleção do catálogo
# (dez identidades atômicas + ``eda_colonoscopy``) e ``none`` (conjunto vazio
# da dimensão consultada). Derivado do catálogo — o bucket ``invalid`` NÃO é
# uma seleção: conjunto persistido fora da matriz nunca é reduzido a categoria
# válida, aparece somente em ``all`` e tem o desvio visível no resumo (R5).
SELECTIONS: tuple[str, ...] = ("all", *SELECTION_KEYS, "none")

# Rótulo da opção "sem filtro" (não é categoria do catálogo).
_ALL_SELECTION_LABEL: str = "Todos"

# Categorias exclusivas de um caso numa dimensão (D12): cada identidade do
# catálogo, o combinado derivado, ``none`` quando a projeção da dimensão é
# vazia (ex.: negativa integral na dimensão autorizado) e ``invalid`` para o
# sentinela de ``selection_key`` — conjunto persistido fora da matriz nunca é
# somado a uma categoria válida nem omitido em silêncio. Derivar de
# ``SELECTION_KEYS`` mantém card e select no MESMO universo (R6).
CATEGORY_ORDER: tuple[str, ...] = (*SELECTION_KEYS, "none", "invalid")

CATEGORY_LABELS: dict[str, str] = {
    **{definition.code: definition.label for definition in PROCEDURE_CATALOG},
    # Chave derivada do combinado: label composta pelas labels do catálogo.
    EDA_COLONOSCOPY: format_procedure_selection(procedure_types_for_selection(EDA_COLONOSCOPY)),
    "none": "Nenhum",
    "invalid": "Conjunto inválido",
}

# Predicado de cada dimensão sobre rows CaseProcedure (fonte única, D14).
DIMENSION_PREDICATES: dict[str, dict[str, Any]] = {
    "declared": {"declared_by_nir": True},
    "detected": {"detection_status": "detected"},
    "approved": {"doctor_disposition": "approved"},
}

# Helper de domínio que projeta o conjunto ordenado de cada dimensão. Slice 010
# (R3): os getters retornam apenas rows normalizadas — sem fallback da ponte
# ``Case.exam_type`` nem de ``doctor_decision=accept``.
DIMENSION_GETTERS: dict[str, Any] = {
    "declared": get_declared_procedure_types,
    "detected": get_detected_procedure_types,
    "approved": get_approved_procedure_types,
}


def resolve_dimension(raw: str) -> str:
    """Valida ``procedure_dimension``; valor inválido/ausente cai em ``declared``."""
    return raw if raw in DIMENSIONS else "declared"


def resolve_selection(raw: str) -> str:
    """Valida ``procedure_selection``; valor inválido/ausente cai em ``all``."""
    return raw if raw in SELECTIONS else "all"


def procedure_selection_options() -> list[dict[str, str]]:
    """Opções do select de procedimento da tabela gerencial (R2/R6).

    ``all`` + cada chave do catálogo + ``none``, na ordem canônica, com labels
    de ``CATEGORY_LABELS`` (derivadas do catálogo). O template itera esta lista
    em vez de repetir opções fechadas — card e select compartilham o universo.
    """
    return [{"key": key, "label": _ALL_SELECTION_LABEL if key == "all" else CATEGORY_LABELS[key]} for key in SELECTIONS]


def category_key(procedure_types: tuple[str, ...]) -> str:
    """Categoria exclusiva de um conjunto ordenado (design D12/D13).

    Chave do catálogo, ``eda_colonoscopy`` para o par exato, ``none`` para o
    conjunto vazio e o sentinela ``invalid`` para conjunto persistido fora da
    matriz — nunca reduzido a singleton e nunca omitido em silêncio.
    """
    return selection_key(procedure_types) or "none"


def admin_closed_case_ids(cases: Any) -> set[Any]:
    """Ids de casos com evento de encerramento administrativo (auditoria).

    Fonte única da exclusão de admin-closed: consumida por
    ``compute_procedure_analytics`` (paired_confirmed) e por
    ``_compute_summary`` (accepted/denied). Nenhuma fórmula de desfecho é
    duplicada aqui (R6).
    """
    return set(
        CaseEvent.objects.filter(
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
            case__in=cases,
        )
        .values_list("case_id", flat=True)
        .distinct()
    )


def compute_procedure_analytics(period_cases: Any) -> dict[str, Any]:
    """Computa breakdown, volume, matriz de conversão e casados numa passada.

    ``period_cases`` deve ser um QuerySet de ``Case`` já filtrado pelo período
    ativo (mesma janela das métricas consolidadas — desfechos usam período,
    esperas permanecem snapshot). A passada usa ``prefetch_related`` + os
    helpers de domínio: total de queries constante (~3), sem N+1 (R6).

    Retorna::

        {
            "breakdown": {dimensão: {categoria: int}},
            "volume": {dimensão: {componente: int}},
            "matrix": {(declarado_key, detectado_key): {autorizado_key: int}},
            "paired_confirmed": int,
        }

    ``volume`` distingue cada identidade atômica do catálogo (dez códigos) e
    ``combined`` (contador derivado do set exato EDA + Colonoscopia), sem nunca
    somar identidades por família/profile — um pacote conta como UM componente
    no seu próprio código.
    """
    prefetched = period_cases.prefetch_related("procedures")
    admin_closed_ids = admin_closed_case_ids(period_cases)

    breakdown: dict[str, dict[str, int]] = {dim: {cat: 0 for cat in CATEGORY_ORDER} for dim in DIMENSIONS}
    volume: dict[str, dict[str, int]] = {
        dim: {**{procedure_type: 0 for procedure_type in SUPPORTED_PROCEDURE_TYPES}, "combined": 0}
        for dim in DIMENSIONS
    }
    matrix: dict[tuple[str, str], dict[str, int]] = {}
    paired_confirmed = 0

    for case in prefetched:
        declared = get_declared_procedure_types(case)
        detected = get_detected_procedure_types(case)
        approved = get_approved_procedure_types(case)
        per_dimension = {"declared": declared, "detected": detected, "approved": approved}

        for dim in DIMENSIONS:
            proc_set = per_dimension[dim]
            breakdown[dim][category_key(proc_set)] += 1
            for procedure_type in SUPPORTED_PROCEDURE_TYPES:
                if procedure_type in proc_set:
                    volume[dim][procedure_type] += 1
            if is_paired_appointment_set(proc_set):
                volume[dim]["combined"] += 1

        path = (category_key(declared), category_key(detected))
        cell = matrix.setdefault(path, {})
        approved_key = category_key(approved)
        cell[approved_key] = cell.get(approved_key, 0) + 1

        if (
            is_paired_appointment_set(approved)
            and case.appointment_status == "confirmed"
            and case.case_id not in admin_closed_ids
        ):
            paired_confirmed += 1

    return {
        "breakdown": breakdown,
        "volume": volume,
        "matrix": matrix,
        "paired_confirmed": paired_confirmed,
    }


def apply_procedure_selection_filter(cases_qs: Any, dimension: str, selection: str) -> Any:
    """Filtra ``cases_qs`` pela categoria ``selection`` na ``dimension``.

    ``all`` não filtra. ``none`` significa ausência de rows na dimensão
    consultada (conjunto vazio), consistente com o breakdown Python e os
    helpers de domínio. Qualquer chave do catálogo exige igualdade EXATA do
    conjunto da dimensão (Slice 009, R2): presença do(s) código(s) exigidos e
    ausência de TODOS os demais do catálogo — então EDA simples nunca casa
    ``eda_gastrostomy`` e nenhuma identidade é agregada por família/profile.
    Igualdade exata também mantém o filtro alinhado ao breakdown: conjunto
    persistido fora da matriz não casa seleção válida nenhuma (só ``all``).

    Predicados via ``Exists`` correlacionado sobre rows ``CaseProcedure``
    (aproveita os índices dimensionais do Slice 001) — sem fallback da ponte
    ``Case.exam_type`` nem de ``doctor_decision`` (Slice 010, R2) e sem query
    por identidade (R6).

    Slice 009 (D12): os predicados são gerados a partir do catálogo; a versão
    anterior enumerava os quatro tipos clássicos e devolvia rows erradas para
    as novas identidades.
    """
    if selection == "all":
        return cases_qs

    predicate = DIMENSION_PREDICATES[dimension]
    proc = CaseProcedure.objects.filter(case=OuterRef("pk"))

    if selection == "none":
        return cases_qs.filter(~Exists(proc.filter(**predicate)))

    required = procedure_types_for_selection(selection)
    present_required = Q(*(Exists(proc.filter(procedure_type=code, **predicate)) for code in required))
    absent_others = ~Exists(proc.filter(**predicate).exclude(procedure_type__in=required))
    return cases_qs.filter(present_required, absent_others)
