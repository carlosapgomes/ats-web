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
    PROCEDURE_CATALOG,
    SUPPORTED_PROCEDURE_TYPES,
    get_approved_procedure_types,
    get_declared_procedure_types,
    get_detected_procedure_types,
    is_paired_appointment_set,
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

# Seleções válidas do parâmetro ``procedure_selection`` da tabela gerencial.
# ``none`` permanece porque a dimensão consultada admite negativa integral.
# O bucket ``invalid`` (sentinel de ``selection_key``) é renderizado pelo
# ``CATEGORY_ORDER``/``CATEGORY_LABELS``; ele NÃO entra nesta tupla enquanto o
# predicado de filtro continuar fechado nos quatro tipos clássicos, senão o
# parâmetro cairia no ramo ``none`` e devolveria rows erradas (Slice 009
# generaliza o filtro para o catálogo ampliado).
SELECTIONS: tuple[str, ...] = ("all", "eda", "colonoscopy", "eda_colonoscopy", "echoendoscopy", "cpre", "none")

# Categorias exclusivas de um caso numa dimensão (D13). ``none`` pertence ao
# universo quando a projeção da dimensão é vazia (ex.: negativa integral na
# dimensão autorizado, ou detecção ainda não sustentada). ``invalid`` é o
# bucket próprio do sentinela de ``selection_key``: conjunto persistido fora
# da matriz nunca é somado a uma categoria válida nem omitido em silêncio
# (design D12).
CATEGORY_ORDER: tuple[str, ...] = (
    "eda",
    "eda_gastrostomy",
    "eda_capsule",
    "eda_dilation",
    "colonoscopy",
    "rectosigmoidoscopy",
    "rectosigmoidoscopy_dilation",
    "rectosigmoidoscopy_argon",
    "echoendoscopy",
    "cpre",
    "eda_colonoscopy",
    "none",
    "invalid",
)

CATEGORY_LABELS: dict[str, str] = {
    **{definition.code: definition.label for definition in PROCEDURE_CATALOG},
    "eda_colonoscopy": "EDA + Colonoscopia",
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

    ``volume`` distingue os quatro componentes (``eda``, ``colonoscopy``,
    ``echoendoscopy``, ``cpre``) e ``combined`` (set exato EDA + Colonoscopia),
    sem jamais somar Eco/CPRE em EDA.
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

    ``all`` não filtra. Predicados via ``Exists`` sobre rows ``CaseProcedure``
    (aproveita os índices dimensionais do Slice 001) — sem fallback da ponte
    ``Case.exam_type`` nem de ``doctor_decision`` (Slice 010, R2). ``none``
    significa ausência de rows na dimensão consultada (conjunto vazio),
    consistente com o breakdown Python e os helpers de domínio.

    Slice 008 (D13): predicado de singleton exige presença do tipo e ausência
    dos demais; ``eda_colonoscopy`` exige exatamente EDA + Colonoscopia. Assim
    Eco/CPRE nunca casam as categorias clássicas e vice-versa.
    """
    if selection == "all":
        return cases_qs

    predicate = DIMENSION_PREDICATES[dimension]
    proc = CaseProcedure.objects.filter(case=OuterRef("pk"))

    def present(procedure_type: str) -> Exists:
        return Exists(proc.filter(procedure_type=procedure_type, **predicate))

    annotations = {
        "_proc_eda": present(ProcedureType.EDA),
        "_proc_colonoscopy": present(ProcedureType.COLONOSCOPY),
        "_proc_echoendoscopy": present(ProcedureType.ECHOENDOSCOPY),
        "_proc_cpre": present(ProcedureType.CPRE),
    }

    if selection == "eda":
        category_q = Q(_proc_eda=True) & Q(_proc_colonoscopy=False, _proc_echoendoscopy=False, _proc_cpre=False)
    elif selection == "colonoscopy":
        category_q = Q(_proc_colonoscopy=True) & Q(_proc_eda=False, _proc_echoendoscopy=False, _proc_cpre=False)
    elif selection == "echoendoscopy":
        category_q = Q(_proc_echoendoscopy=True) & Q(_proc_eda=False, _proc_colonoscopy=False, _proc_cpre=False)
    elif selection == "cpre":
        category_q = Q(_proc_cpre=True) & Q(_proc_eda=False, _proc_colonoscopy=False, _proc_echoendoscopy=False)
    elif selection == "eda_colonoscopy":
        category_q = Q(_proc_eda=True, _proc_colonoscopy=True) & Q(_proc_echoendoscopy=False, _proc_cpre=False)
    else:  # none — ausência de rows da dimensão consultada
        category_q = Q(_proc_eda=False, _proc_colonoscopy=False, _proc_echoendoscopy=False, _proc_cpre=False)

    return cases_qs.annotate(**annotations).filter(category_q)
