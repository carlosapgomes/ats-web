"""Projeção de procedimentos por caso — serviço central (design D1/D4).

``CaseProcedure`` é a fonte autoritativa dos procedimentos de um caso; o
conjunto declarado é derivado exclusivamente das rows (Slice 011-C removeu a
coluna ponte ``Case.exam_type``).

Catálogo, ordem canônica e matriz válida ficam centralizados aqui (design D1)
e são a fonte única dos consumidores. ``PROCEDURE_CATALOG`` registra as dez
identidades atômicas na ordem canônica, com label, família e ``profile_key``
clínico; ``SUPPORTED_PROCEDURE_TYPES``, ``PROCEDURE_ORDER``, labels e
``ALLOWED_PROCEDURE_SETS`` são derivados dele. A matriz é fechada: qualquer
singleton canônico mais exatamente ``{EDA, Colonoscopia}``; o agendamento
casado é exatamente ``{EDA, Colonoscopia}`` (nunca ``len == 2``).

Writes críticos (declaração) passam por este módulo: nenhuma view escreve rows
diretamente. A declaração é atômica — falha em uma row não deixa caso/projeção
parcial. Detecção (``set_detected_procedures``) e decisão médica
(``record_doctor_procedure_decisions``) também são atômicas e centralizadas
(D4).
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ProcedureDefinition:
    """Metadados canônicos de uma identidade atômica do catálogo (design D1).

    ``family`` é a dimensão de apresentação (agrupamento de badge/CSS e
    afinidade operacional) e ``profile_key`` resolve as regras clínicas em
    ``apps.cases.exam_profiles``. Aliases/detalhes de detecção entram nos
    slices que os consomem (002-005) — o catálogo começa somente com os
    metadados exigidos pelo cutover.
    """

    code: str
    label: str
    family: str  # "eda" | "colonoscopy" | "specialized"
    profile_key: str


# Ordem canônica única (design D1/D2): EDA e seus pacotes, depois Colonoscopia
# e a família Retossigmoidoscopia, depois os especializados.
PROCEDURE_CATALOG: tuple[ProcedureDefinition, ...] = (
    ProcedureDefinition(
        code=ProcedureType.EDA,
        label=ProcedureType.EDA.label,
        family="eda",
        profile_key="eda",
    ),
    ProcedureDefinition(
        code=ProcedureType.EDA_GASTROSTOMY,
        label=ProcedureType.EDA_GASTROSTOMY.label,
        family="eda",
        profile_key="eda",
    ),
    ProcedureDefinition(
        code=ProcedureType.EDA_CAPSULE,
        label=ProcedureType.EDA_CAPSULE.label,
        family="eda",
        profile_key="eda",
    ),
    ProcedureDefinition(
        code=ProcedureType.EDA_DILATION,
        label=ProcedureType.EDA_DILATION.label,
        family="eda",
        profile_key="eda",
    ),
    ProcedureDefinition(
        code=ProcedureType.COLONOSCOPY,
        label=ProcedureType.COLONOSCOPY.label,
        family="colonoscopy",
        profile_key="colonoscopy",
    ),
    ProcedureDefinition(
        code=ProcedureType.RECTOSIGMOIDOSCOPY,
        label=ProcedureType.RECTOSIGMOIDOSCOPY.label,
        family="colonoscopy",
        profile_key="colonoscopy",
    ),
    ProcedureDefinition(
        code=ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
        label=ProcedureType.RECTOSIGMOIDOSCOPY_DILATION.label,
        family="colonoscopy",
        profile_key="colonoscopy",
    ),
    ProcedureDefinition(
        code=ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
        label=ProcedureType.RECTOSIGMOIDOSCOPY_ARGON.label,
        family="colonoscopy",
        profile_key="colonoscopy",
    ),
    ProcedureDefinition(
        code=ProcedureType.ECHOENDOSCOPY,
        label=ProcedureType.ECHOENDOSCOPY.label,
        family="specialized",
        profile_key="echoendoscopy",
    ),
    ProcedureDefinition(
        code=ProcedureType.CPRE,
        label=ProcedureType.CPRE.label,
        family="specialized",
        profile_key="cpre",
    ),
)

# Catálogo canônico e ordem de exibição (design D1), derivados do registro.
SUPPORTED_PROCEDURE_TYPES: tuple[str, ...] = tuple(definition.code for definition in PROCEDURE_CATALOG)

PROCEDURE_LABELS: dict[str, str] = {definition.code: definition.label for definition in PROCEDURE_CATALOG}

# Contratos procedure-neutral legíveis pelo domínio: 2.0 (histórico), 3.0
# (writer anterior) e 4.0 (writer atual). 1.1 continua suportado apenas pelos
# adapters/presenters como leitura histórica.
PROCEDURE_NEUTRAL_SCHEMA_VERSIONS: frozenset[str] = frozenset({"2.0", "3.0", "4.0"})


def is_procedure_neutral_structured_data(structured_data: Any) -> bool:
    """True quando o artefato estruturado usa o contrato procedure-neutral.

    Aceita 2.0/3.0 (históricos) e 4.0 (writer atual) — a decisão por componente
    exige um deles; artefatos 1.1 continuam no caminho legado. Substitui os
    gates literais ``== "2.0"`` espalhados pela UI médica (R6 do cutover 3.0).
    """
    return (
        isinstance(structured_data, dict) and structured_data.get("schema_version") in PROCEDURE_NEUTRAL_SCHEMA_VERSIONS
    )


PROCEDURE_ORDER: dict[str, int] = {type_: position for position, type_ in enumerate(SUPPORTED_PROCEDURE_TYPES)}

# Agendamento casado: igualdade exata com {EDA, Colonoscopia} (design D1/D2).
PAIRED_APPOINTMENT_SET: frozenset[str] = frozenset({ProcedureType.EDA, ProcedureType.COLONOSCOPY})

# Matriz fechada (design D2): qualquer singleton canônico mais o par exato.
ALLOWED_PROCEDURE_SETS: frozenset[frozenset[str]] = frozenset(
    {frozenset({code}) for code in SUPPORTED_PROCEDURE_TYPES} | {PAIRED_APPOINTMENT_SET}
)

# Chaves de seleção válidas (design D10): cada código atômico mais a chave
# derivada do combinado. Aliases e labels nunca são valores válidos.
SELECTION_KEYS: tuple[str, ...] = (*SUPPORTED_PROCEDURE_TYPES, EDA_COLONOSCOPY)

# Sentinela reservado de ``selection_key`` para conjunto não-vazio fora da
# matriz (design D2/D12): nunca o primeiro elemento, nunca categoria válida.
INVALID_SELECTION_KEY: str = "invalid"

_SUPPORTED_LABEL = ", ".join(PROCEDURE_LABELS[code] for code in SUPPORTED_PROCEDURE_TYPES)
_SELECTION_LABEL = ", ".join(PROCEDURE_LABELS[code] for code in SUPPORTED_PROCEDURE_TYPES)


def _ordered_supported(procedure_types: Any) -> tuple[str, ...]:
    """Valida tipos contra o catálogo e devolve tupla ordenada sem duplicatas.

    Qualquer valor fora do catálogo falha explicitamente — nunca é descartado
    em silêncio (R3).
    """
    seen: list[str] = []
    for raw in procedure_types or ():
        value = str(raw)
        if value not in PROCEDURE_ORDER:
            raise ValueError(f"Procedimento inválido: {value!r}. Aceitos: {_SUPPORTED_LABEL}.")
        if value not in seen:
            seen.append(value)
    seen.sort(key=lambda t: PROCEDURE_ORDER[t])
    return tuple(seen)


def is_paired_appointment_set(procedure_types: Any) -> bool:
    """True somente quando o conjunto é exatamente ``{EDA, Colonoscopia}``.

    Substitui qualquer regra ``len == 2`` em consumidores de agendamento.
    """
    return frozenset(str(raw) for raw in (procedure_types or ())) == PAIRED_APPOINTMENT_SET


def normalize_procedure_selection(procedure_types: Any) -> tuple[str, ...]:
    """Valida e ordena uma seleção declarada de procedimentos (D2).

    Regras: não-vazia, sem duplicatas, todos os tipos no catálogo e o conjunto
    resultante presente em ``ALLOWED_PROCEDURE_SETS``. Retorna tupla ordenada
    para exibição/auditoria determinísticas. Levanta ``ValueError`` caso
    contrário.
    """
    ordered = _ordered_supported(procedure_types)
    if not ordered:
        raise ValueError("Selecione ao menos um procedimento.")
    if frozenset(ordered) not in ALLOWED_PROCEDURE_SETS:
        raise ValueError(f"Conjunto de procedimentos não suportado: {list(ordered)}.")
    return ordered


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
    """Escreve a projeção declarada numa transação/lock já existentes (correção).

    Usado por fluxos que já possuem ``transaction.atomic`` + ``select_for_update``
    (ex.: ``correct_case_exam_type``). NÃO salva o ``Case`` nem registra evento:
    o caller decide o save e o evento de auditoria do fluxo.
    """
    types = normalize_procedure_selection(procedure_types)
    _sync_declared_rows(case, types)


def set_declared_procedures(
    *,
    case: Case,
    procedure_types: Any,
    actor: Any = None,
) -> Case:
    """Define o conjunto declarado de um caso atomicamente (D4).

    Cria/atualiza rows declaradas e registra o evento enxuto
    ``CASE_PROCEDURES_DECLARED`` com o conjunto ordenado (sem texto clínico).
    Toda falha reverte a operação inteira — nunca deixa caso/projeção parcial.

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
        locked._record_event(
            "CASE_PROCEDURES_DECLARED",
            user=actor,
            payload={"procedures": list(types)},
        )
        locked.save()
    return locked


def normalize_detected_set(detected_types: Any) -> tuple[str, ...]:
    """Valida e ordena um conjunto detectado (catálogo, sem duplicatas, D2).

    Conjunto vazio é aceito (nenhum procedimento detectado) — usado pela
    projeção quando a análise não sustenta nenhum procedimento. Conjunto não
    vazio precisa pertencer à matriz fechada.
    """
    ordered = _ordered_supported(detected_types)
    if ordered and frozenset(ordered) not in ALLOWED_PROCEDURE_SETS:
        raise ValueError(f"Conjunto detectado não suportado: {list(ordered)}.")
    return ordered


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
    row ``CaseProcedure`` correspondente (get_or_create — inclusão/troca cria
    a row sem alterar ``declared_by_nir``/``detection_status``) e registra o
    evento enxuto ``DOCTOR_PROCEDURE_DECISIONS_RECORDED`` com a lista ordenada
    (ordem canônica do catálogo). Quando o conjunto autorizado difere do
    detectado, registra adicionalmente ``DOCTOR_PROCEDURE_SET_CHANGED`` (D11)
    na MESMA transação. NUNCA reexecuta LLM e NUNCA escreve a
    detecção/declaração. Toda falha reverte a operação inteira — nenhuma
    disposição ou evento parcial.

    O conjunto autorizado final é validado contra a matriz fechada
    (``ALLOWED_PROCEDURE_SETS``) DENTRO da transação (D2): combinação
    incompatível (ex.: manter Colonoscopia e incluir Ecoendoscopia) falha com
    ``ValueError`` antes de qualquer write. Procedimento fora do catálogo
    também falha explicitamente — nunca é descartado em silêncio.

    Args:
        case: instância do caso (relockada dentro da transação).
        decisions: lista ordenável de decisões por componente (R2).
        actor: usuário médico autor da decisão, para auditoria.

    Returns:
        Instância atualizada do caso.

    Raises:
        ValueError: disposição inválida, procedimento fora do catálogo ou
            conjunto autorizado fora da matriz fechada.
    """
    with transaction.atomic():
        locked = Case.objects.select_for_update().get(pk=case.pk)
        approved: set[str] = {
            row.procedure_type
            for row in CaseProcedure.objects.filter(case=locked, doctor_disposition=DoctorDisposition.APPROVED)
        }
        entries: list[dict[str, Any]] = []
        reason_present = False
        for decision in decisions:
            procedure_type = str(decision["procedure_type"])
            if procedure_type not in PROCEDURE_ORDER:
                raise ValueError(f"Procedimento inválido: {procedure_type!r}. Aceitos: {_SUPPORTED_LABEL}.")
            disposition = str(decision["disposition"])
            if disposition not in (DoctorDisposition.APPROVED, DoctorDisposition.DENIED):
                raise ValueError(f"Disposição inválida para {procedure_type}: {disposition!r}.")
            reason = str(decision.get("reason") or "").strip()
            reason_present = reason_present or bool(reason)
            row, _ = CaseProcedure.objects.get_or_create(case=locked, procedure_type=procedure_type)
            row.doctor_disposition = disposition
            row.doctor_reason = reason
            row.save(update_fields=["doctor_disposition", "doctor_reason"])
            if disposition == DoctorDisposition.APPROVED:
                approved.add(procedure_type)
            else:
                approved.discard(procedure_type)
            entries.append(
                {
                    "procedure_type": procedure_type,
                    "disposition": disposition,
                    "reason_present": bool(reason),
                    "added_by_doctor": bool(decision.get("added_by_doctor")),
                }
            )
        if approved and frozenset(approved) not in ALLOWED_PROCEDURE_SETS:
            labels = " + ".join(ProcedureType(t).label for t in sorted(approved, key=lambda t: PROCEDURE_ORDER[t]))
            raise ValueError(f"Conjunto de procedimentos autorizado não suportado: {labels}.")
        entries.sort(key=lambda entry: PROCEDURE_ORDER[entry["procedure_type"]])
        CaseEvent.objects.create(
            case=locked,
            event_type="DOCTOR_PROCEDURE_DECISIONS_RECORDED",
            actor=actor,
            actor_type="human",
            payload={"decisions": entries},
        )

        approved_types = tuple(sorted(approved, key=lambda t: PROCEDURE_ORDER[t]))
        detected_types = tuple(
            sorted(
                (
                    row.procedure_type
                    for row in CaseProcedure.objects.filter(case=locked, detection_status=DetectionStatus.DETECTED)
                ),
                key=lambda t: PROCEDURE_ORDER[t],
            )
        )
        if approved_types != detected_types:
            CaseEvent.objects.create(
                case=locked,
                event_type="DOCTOR_PROCEDURE_SET_CHANGED",
                actor=actor,
                actor_type="human",
                payload={
                    "detected": list(detected_types),
                    "approved": list(approved_types),
                    "reason_present": reason_present,
                },
            )
    return locked


# ── Leitura para consumo (templates NIR recebem label projetado na view) ──


def _declared_types_from_rows(case: Case) -> tuple[str, ...]:
    return tuple(
        sorted(
            (p.procedure_type for p in case.procedures.all() if p.declared_by_nir),
            key=lambda t: PROCEDURE_ORDER[t],
        )
    )


def get_declared_procedure_types(case: Case) -> tuple[str, ...]:
    """Conjunto declarado ordenado a partir da projeção (Slice 010, R3).

    Retorna apenas rows normalizadas: um caso sem rows declaradas devolve
    ``()``. A coluna ponte ``Case.exam_type`` foi removida no Slice 011-C.
    """
    return _declared_types_from_rows(case)


def get_detected_procedure_types(case: Case) -> tuple[str, ...]:
    """Conjunto detectado ordenado (dimensão da fila médica Pendentes, Slice 010 R3).

    Retorna apenas rows com ``detection_status=DETECTED``: caso sem rows
    detectadas devolve ``()`` (não herda a declaração).
    """
    return tuple(
        sorted(
            (p.procedure_type for p in case.procedures.all() if p.detection_status == DetectionStatus.DETECTED),
            key=lambda t: PROCEDURE_ORDER[t],
        )
    )


def get_approved_procedure_types(case: Case) -> tuple[str, ...]:
    """Conjunto autorizado pelo médico, ordenado (dimensão do CHD/Decididos, Slice 010 R3).

    Fonte autoritativa: rows ``CaseProcedure.doctor_disposition=approved``. O
    fallback global ``doctor_decision=accept`` foi removido — um caso aceito
    sem rows aprovadas devolve ``()``.
    """
    return tuple(
        sorted(
            (p.procedure_type for p in case.procedures.all() if p.doctor_disposition == DoctorDisposition.APPROVED),
            key=lambda t: PROCEDURE_ORDER[t],
        )
    )


def selection_key(procedure_types: tuple[str, ...]) -> str:
    """Chave textual do badge/CSS derivada do conjunto (design D2/D12).

    Função total — nunca levanta, pois leitores tolerantes a consomem:

    - par exato ``{eda, colonoscopy}`` → ``eda_colonoscopy``;
    - singleton canônico → o próprio código (mesmo quando a label contém ``+``);
    - conjunto vazio → ``""``;
    - conjunto não-vazio fora da matriz (ou valor fora do catálogo) →
      :data:`INVALID_SELECTION_KEY` — nunca o primeiro elemento e nunca uma
      categoria válida.
    """
    types = tuple(str(raw) for raw in (procedure_types or ()))
    if frozenset(types) == PAIRED_APPOINTMENT_SET:
        return EDA_COLONOSCOPY
    if len(types) == 1 and types[0] in PROCEDURE_ORDER:
        return types[0]
    if not types:
        return ""
    return INVALID_SELECTION_KEY


def procedure_types_for_selection(key: str) -> tuple[str, ...]:
    """Converte uma chave de seleção declarada em procedimentos (design D10).

    ``eda_colonoscopy`` (chave derivada) → ``(eda, colonoscopy)``; qualquer
    código atômico canônico → singleton. Chave desconhecida (alias, label ou
    valor livre) falha explicitamente com ``ValueError`` — nunca é interpretada
    por proximidade textual e nunca cria procedimento fora do catálogo.
    """
    value = str(key or "").strip()
    if value == EDA_COLONOSCOPY:
        return (ProcedureType.EDA, ProcedureType.COLONOSCOPY)
    if value not in PROCEDURE_ORDER:
        raise ValueError(f"Seleção de procedimento inválida: {value!r}. Aceitas: {_SELECTION_LABEL}.")
    return (value,)


def format_procedure_selection(procedure_types: Any) -> str:
    """Label textual ordenado: 'EDA', 'Colonoscopia' ou 'EDA + Colonoscopia'."""
    ordered = normalize_procedure_selection(procedure_types)
    return " + ".join(PROCEDURE_LABELS[t] for t in ordered)
