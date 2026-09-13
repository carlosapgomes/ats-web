"""Adapters estritos entre schemas 1.1/2.0/3.0 (design D5/D8 / ADR-0006).

Nenhum JSON histórico é reescrito: a leitura detecta ``schema_version`` e
projeta apenas em memória. ``project_v2_to_llm1_shape`` alimenta as políticas
determinísticas e sinais prioritários existentes (sem copiar policy para
combinado — R5); ``project_v3_to_llm1_shape`` faz o mesmo para o contrato 3.0,
que acrescenta os quatro tipos e a coleção tipada de imagem abdominal.
"""

from __future__ import annotations

from typing import Any

from apps.cases.models import ProcedureType

SUPPORTED_V2_PROCEDURE_TYPES: tuple[str, ...] = (ProcedureType.EDA, ProcedureType.COLONOSCOPY)
SUPPORTED_V3_PROCEDURE_TYPES: tuple[str, ...] = (
    ProcedureType.EDA,
    ProcedureType.COLONOSCOPY,
    ProcedureType.ECHOENDOSCOPY,
    ProcedureType.CPRE,
)

_V3_PROCEDURE_ORDER: dict[str, int] = {type_: position for position, type_ in enumerate(SUPPORTED_V3_PROCEDURE_TYPES)}


def detect_schema_version(structured_data: Any) -> str:
    """Retorna a versão de schema de um payload estruturado (``3.0``/``2.0``/``1.1``)."""
    if isinstance(structured_data, dict):
        version = structured_data.get("schema_version")
        if version == "3.0":
            return "3.0"
        if version == "2.0":
            return "2.0"
    return "1.1"


def requested_procedure_types_v2(structured_data: Any) -> tuple[str, ...]:
    """Conjunto ordenado de procedimentos declarados pela extração v2."""
    if not isinstance(structured_data, dict):
        return ()
    raw = structured_data.get("requested_procedures")
    if not isinstance(raw, list):
        return ()
    seen: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        procedure_type = item.get("procedure_type")
        if procedure_type in SUPPORTED_V2_PROCEDURE_TYPES and procedure_type not in seen:
            seen.append(procedure_type)
    seen.sort(key=lambda t: 0 if t == ProcedureType.EDA else 1)
    return tuple(seen)


def requested_procedure_for_type(structured_data: Any, procedure_type: str) -> dict[str, Any]:
    """Item tipado de ``requested_procedures`` para um procedimento, ou {}."""
    if not isinstance(structured_data, dict):
        return {}
    raw = structured_data.get("requested_procedures")
    if not isinstance(raw, list):
        return {}
    for item in raw:
        if isinstance(item, dict) and item.get("procedure_type") == procedure_type:
            return item
    return {}


def requested_procedure_types_v3(structured_data: Any) -> tuple[str, ...]:
    """Conjunto ordenado de procedimentos declarados pela extração v3.

        Preserva valores desconhecidos? Não: um valor fora do catálogo v3 é
    descartado aqui e a reconciliação falha fechada ao receber conjuntos vazios
    ou incoerentes (R3). A leitura histórica 2.0 continua em
    ``requested_procedure_types_v2``.
    """
    if not isinstance(structured_data, dict):
        return ()
    raw = structured_data.get("requested_procedures")
    if not isinstance(raw, list):
        return ()
    seen: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        procedure_type = item.get("procedure_type")
        if procedure_type in SUPPORTED_V3_PROCEDURE_TYPES and procedure_type not in seen:
            seen.append(procedure_type)
    seen.sort(key=lambda t: _V3_PROCEDURE_ORDER[t])
    return tuple(seen)


def project_v3_to_llm1_shape(
    *,
    v3_data: dict[str, object],
    procedure_type: str,
) -> dict[str, object]:
    """Projeta dados v3 para a forma 1.1 consumida por policy/sinais.

    Espelha ``project_v2_to_llm1_shape`` acrescentando a coleção tipada de
    imagem abdominal (D6) em ``preop_screening``; a forma legada de ``eda``
    continua servindo as policies determinísticas existentes.
    """
    procedure = requested_procedure_for_type(v3_data, procedure_type)
    common = _get_dict(v3_data, "common_preop")
    labs = _get_dict(common, "labs")
    ecg = _get_dict(common, "ecg")

    preop: dict[str, Any] = {
        "exam_type": procedure_type,
        "has_cardiovascular_disease": ecg.get("report_present"),
        "has_active_respiratory_symptoms": "unknown",
        "has_prior_respiratory_disease": "unknown",
        "has_ecg_report": ecg.get("report_present"),
        "has_chest_xray_report": "unknown",
        "has_echocardiogram_report": "unknown",
        "hb_g_dl": labs.get("hb_g_dl"),
        "platelets_per_mm3": labs.get("platelets_per_mm3"),
        "inr": labs.get("inr"),
        "evidence_spans": [
            *(_get_list(common, "evidence_spans")),
            *(_get_list(procedure, "evidence_spans")),
        ],
        "rulebook_signals": common.get("rulebook_signals") or {},
        "comorbidities_described": _get_list(common, "comorbidities_described"),
        "medications_described": _get_list(common, "medications_described"),
        "abdominal_imaging": _get_list(common, "abdominal_imaging"),
    }

    eda: dict[str, Any] = {
        "indication_category": procedure.get("indication_category") or "unknown",
        "requested_procedure": {
            "name": procedure.get("name"),
            "subtype": procedure.get("subtype") or "standard",
        },
        "labs": labs,
        "ecg": ecg,
        "asa": common.get("asa"),
        "cardiovascular_risk": common.get("cardiovascular_risk"),
        "is_pediatric": False,
        "foreign_body_suspected": False,
    }

    return {
        "schema_version": "1.1",  # forma legada consumida pelas policies (não é artefato persistido)
        "patient": v3_data.get("patient") or {},
        "eda": eda,
        "preop_screening": preop,
        "policy_precheck": v3_data.get("policy_precheck") or {},
        "summary": v3_data.get("summary") or {},
        "extraction_quality": v3_data.get("extraction_quality") or {},
        "origin_context": v3_data.get("origin_context") or {},
        "transfusion": v3_data.get("transfusion") or {},
        "tracked_exams": _get_list(v3_data, "tracked_exams"),
    }


def _get_dict(payload: Any, key: str) -> dict[str, Any]:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _get_list(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def project_v2_to_llm1_shape(
    *,
    v2_data: dict[str, object],
    procedure_type: str,
) -> dict[str, object]:
    """Projeta dados v2 para a forma 1.1 consumida por policy/sinais.

    Executa para CADA procedimento detectado (R5): os dados comuns alimentam
    a política compartilhada; o item tipado do procedimento fornece subtipo/
    indicação/evidence spans próprios — exceções (corpo estranho) nunca vazam
    para o outro componente.
    """
    procedure = requested_procedure_for_type(v2_data, procedure_type)
    common = _get_dict(v2_data, "common_preop")
    labs = _get_dict(common, "labs")
    ecg = _get_dict(common, "ecg")

    preop: dict[str, Any] = {
        "exam_type": procedure_type,
        "has_cardiovascular_disease": ecg.get("report_present"),
        "has_active_respiratory_symptoms": "unknown",
        "has_prior_respiratory_disease": "unknown",
        "has_ecg_report": ecg.get("report_present"),
        "has_chest_xray_report": "unknown",
        "has_echocardiogram_report": "unknown",
        "hb_g_dl": labs.get("hb_g_dl"),
        "platelets_per_mm3": labs.get("platelets_per_mm3"),
        "inr": labs.get("inr"),
        "evidence_spans": [
            *(_get_list(common, "evidence_spans")),
            *(_get_list(procedure, "evidence_spans")),
        ],
        "rulebook_signals": common.get("rulebook_signals") or {},
        "comorbidities_described": _get_list(common, "comorbidities_described"),
        "medications_described": _get_list(common, "medications_described"),
    }

    eda: dict[str, Any] = {
        "indication_category": procedure.get("indication_category") or "unknown",
        "requested_procedure": {
            "name": procedure.get("name"),
            "subtype": procedure.get("subtype") or "standard",
        },
        "labs": labs,
        "ecg": ecg,
        "asa": common.get("asa"),
        "cardiovascular_risk": common.get("cardiovascular_risk"),
        "is_pediatric": False,
        "foreign_body_suspected": False,
    }

    return {
        "schema_version": "1.1",  # forma legada consumida pelas policies (não é artefato persistido)
        "patient": v2_data.get("patient") or {},
        "eda": eda,
        "preop_screening": preop,
        "policy_precheck": v2_data.get("policy_precheck") or {},
        "summary": v2_data.get("summary") or {},
        "extraction_quality": v2_data.get("extraction_quality") or {},
        "origin_context": v2_data.get("origin_context") or {},
        "transfusion": v2_data.get("transfusion") or {},
        "tracked_exams": _get_list(v2_data, "tracked_exams"),
    }
