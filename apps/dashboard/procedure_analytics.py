"""Analytics por dimensão de procedimento (Slice 006 / design D14).

Separa métricas de casos (case-level, R1) de volume de componentes (R3),
classifica cada caso em categoria exclusiva por dimensão (R2), expõe a
matriz de conversão declarado→detectado→autorizado (R4) e conta
agendamentos casados uma única vez (R4).

Todos os predicates/helpers de projeção estão centralizados aqui e
reutilizam os helpers de domínio (``get_*_procedure_types``), evitando
fórmulas duplicadas de accepted/denied/admin-closed (R6).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Exists, OuterRef, Q

from apps.cases.models import CaseEvent, CaseProcedure, ProcedureType
from apps.cases.procedures import (
    get_approved_procedure_types,
    get_declared_procedure_types,
    get_detected_procedure_types,
    selection_key,
)

# Dimensões válidas do parâmetro SSR ``procedure_dimension``.
# Default documentado: ``declared`` (dimensão da declaração NIR).
DIMENSIONS: tuple[str, ...] = ("declared", "detected", "approved")

DIMENSION_LABELS: dict[str, str] = {
    "declared": "Declarado",
    "detected": "Detectado",
    "approved": "Autorizado",
}

# Seleções válidas do parâmetro ``procedure_selection`` da tabela gerencial.
SELECTIONS: tuple[str, ...] = ("all", "eda", "colonoscopy", "eda_colonoscopy", "none")

# Categorias exclusivas de um caso numa dimensão (D14). ``none`` pertence ao
# universo quando a projeção da dimensão é vazia (ex.: negativa integral na
# dimensão autorizado, ou detecção ainda não sustentada).
CATEGORY_ORDER: tuple[str, ...] = ("eda", "colonoscopy", "eda_colonoscopy", "none")

CATEGORY_LABELS: dict[str, str] = {
    "eda": "EDA",
    "colonoscopy": "Colonoscopia",
    "eda_colonoscopy": "EDA + Colonoscopia",
    "none": "Nenhum",
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


def category_key(procedure_types: tuple[str, ...]) -> str:
    """Categoria exclusiva de um conjunto ordenado: eda|colonoscopy|eda_colonoscopy|none."""
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
            "volume": {dimensão: {"eda": int, "colonoscopy": int, "combined": int}},
            "matrix": {(declarado_key, detectado_key): {autorizado_key: int}},
            "paired_confirmed": int,
        }
    """
    prefetched = period_cases.prefetch_related("procedures")
    admin_closed_ids = admin_closed_case_ids(period_cases)

    breakdown: dict[str, dict[str, int]] = {dim: {cat: 0 for cat in CATEGORY_ORDER} for dim in DIMENSIONS}
    volume: dict[str, dict[str, int]] = {dim: {"eda": 0, "colonoscopy": 0, "combined": 0} for dim in DIMENSIONS}
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
            if ProcedureType.EDA in proc_set:
                volume[dim]["eda"] += 1
            if ProcedureType.COLONOSCOPY in proc_set:
                volume[dim]["colonoscopy"] += 1
            if len(proc_set) == 2:
                volume[dim]["combined"] += 1

        path = (category_key(declared), category_key(detected))
        cell = matrix.setdefault(path, {})
        approved_key = category_key(approved)
        cell[approved_key] = cell.get(approved_key, 0) + 1

        if len(approved) == 2 and case.appointment_status == "confirmed" and case.case_id not in admin_closed_ids:
            paired_confirmed += 1

    return {
        "breakdown": breakdown,
        "volume": volume,
        "matrix": matrix,
        "paired_confirmed": paired_confirmed,
    }


def apply_procedure_selection_filter(cases_qs: Any, dimension: str, selection: str) -> Any:
    """Filtra ``cases_qs`` pela categoria ``selection`` na ``dimension``.

    ``all`` não filtra. Predicados via ``Exists`` sobre rows ``CaseProcedure``
    (aproveita os índices dimensionais do Slice 001) — sem fallback da ponte
    ``Case.exam_type`` nem de ``doctor_decision`` (Slice 010, R2). ``none``
    significa ausência de rows na dimensão consultada (conjunto vazio),
    consistente com o breakdown Python e os helpers de domínio.
    """
    if selection == "all":
        return cases_qs

    predicate = DIMENSION_PREDICATES[dimension]
    proc = CaseProcedure.objects.filter(case=OuterRef("pk"))
    eda_match = Exists(proc.filter(procedure_type=ProcedureType.EDA, **predicate))
    col_match = Exists(proc.filter(procedure_type=ProcedureType.COLONOSCOPY, **predicate))

    if selection == "eda":
        category_q = Q(_proc_eda=True) & Q(_proc_col=False)
    elif selection == "colonoscopy":
        category_q = Q(_proc_eda=False) & Q(_proc_col=True)
    elif selection == "eda_colonoscopy":
        category_q = Q(_proc_eda=True) & Q(_proc_col=True)
    else:  # none — ausência de rows da dimensão consultada
        category_q = Q(_proc_eda=False) & Q(_proc_col=False)

    return cases_qs.annotate(_proc_eda=eda_match, _proc_col=col_match).filter(category_q)
