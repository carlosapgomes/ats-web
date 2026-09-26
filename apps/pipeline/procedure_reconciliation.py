"""Reconciliação de detecção procedure-neutral (design D2/D3 / ADR-0006).

Aplica a matriz declarado × detectado com gate de evidência forte para
upgrade automático. Histórico/negação nunca combinam (detecção por ocorrência
em ``scope_detection``); o payload de revisão NIR é enxuto (conjuntos + reason
code), sem texto clínico integral.

R3: a validação ocorre ANTES de ordenar/filtrar — tipos desconhecidos,
duplicatas ou conjuntos fora da matriz fechada falham fechado com motivo
explícito e nunca são descartados para fazer o restante parecer válido.

D3: a precedência de um único procedimento especializado sobre procedimentos
convencionais depende de PROVENIÊNCIA POR OCORRÊNCIA (``occurrences``):
somente exatamente uma Ecoendoscopia OU exatamente uma CPRE detectada com
ocorrência textual do MESMO tipo qualificada como ``current_request`` suprime
EDA e/ou Colonoscopia, mesmo em trechos independentes (ADR-0008). Item
estruturado isolado, histórico, negação ou menção nunca suprimem; dois
especializados, tipo desconhecido ou duplicata continuam fail-closed.

Slice 003/004/005 (D3): a MESMA proveniência sustenta a supressão da base por
exatamente uma variação atômica atual (``eda_gastrostomy``/``eda_capsule``/
``eda_dilation`` sobre ``eda``; ``rectosigmoidoscopy_dilation``/
``rectosigmoidoscopy_argon`` sobre ``rectosigmoidoscopy``); o item estruturado
sem ocorrência atual não suprime e o conjunto permanece misto (fail-closed na
matriz, sem descartar valores).

Slice 003 (D3): a MESMA proveniência sustenta ainda a precedência de FAMÍLIA —
exatamente uma identidade atual de Retossigmoidoscopia absorve a ``colonoscopy``
cujo conjunto só se sustenta pelo alias guarda-chuva do Motivo ``endoscopia
digestiva baixa`` (``section == motivo_da_solicitacao``). Evidência atual
explícita de colonoscopia, guarda-chuva atual citado no corpo ou ausência de
ocorrência atual da família mantêm o conflito fail-closed na matriz.

Item 1.0 (change ``followup-body-clue-detection-hardening``): o motivo da revisão
NIR ganha o sufixo de ORIGEM (seções das ocorrências atuais do conjunto
detectado) e a listagem de pistas deixa de ser renderizada na UI — a projeção
``project_body_clues``/payload ``detected_body_clues`` seguem intactos para
auditoria.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.cases.models import EDA_COLONOSCOPY, ProcedureType
from apps.cases.procedures import (
    ALLOWED_PROCEDURE_SETS,
    PAIRED_APPOINTMENT_SET,
    PROCEDURE_ORDER,
    is_paired_appointment_set,
)


@dataclass(frozen=True)
class ProcedurePartition:
    """Separação explícita entre valores conhecidos do catálogo e desconhecidos."""

    ordered: tuple[str, ...]
    unknown: tuple[str, ...]
    had_duplicates: bool


def _partition_procedures(procedure_types: Any) -> ProcedurePartition:
    """Particiona valores preservando ordem canônica sem descartar desconhecidos.

    Nunca filtra em silêncio (R3): valores fora do catálogo são devolvidos em
    ``unknown`` e duplicatas são sinalizadas em ``had_duplicates``.
    """
    seen: list[str] = []
    unknown: list[str] = []
    had_duplicates = False
    for raw in procedure_types or ():
        value = str(raw)
        if value not in PROCEDURE_ORDER:
            if value not in unknown:
                unknown.append(value)
            continue
        if value in seen:
            had_duplicates = True
            continue
        seen.append(value)
    seen.sort(key=lambda t: PROCEDURE_ORDER[t])
    return ProcedurePartition(ordered=tuple(seen), unknown=tuple(unknown), had_duplicates=had_duplicates)


def _ordered(procedure_types: Any) -> tuple[str, ...]:
    """Compatibilidade: ordem canônica dos valores conhecidos (sem validar)."""
    return _partition_procedures(procedure_types).ordered


# Especializados que podem predominar sobre procedimentos convencionais (D1).
_SPECIALIZED_PROCEDURE_TYPES: frozenset[str] = frozenset({ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE})
# Convencionais suprimidos quando a precedência se aplica (R1).
_CONVENTIONAL_PROCEDURE_TYPES: frozenset[str] = frozenset({ProcedureType.EDA, ProcedureType.COLONOSCOPY})
# Qualificação textual que comprova solicitação ATUAL (contrato de
# ``scope_detection``); não é reimplementada nem alterada neste slice.
_QUALIFICATION_CURRENT_REQUEST = "current_request"
# Identificador da regra registrado em evento/sugestão (D3).
PROCEDURE_PRECEDENCE_RULE = "specialized_over_conventional"

# Variações atômicas e a base que elas clinicamente contêm (D3, Slices
# 003/004/005): exatamente UMA variação com ocorrência textual atual suprime a
# base detectada em qualquer trecho (mesma expressão ou trecho independente), no
# mesmo regime de proveniência da precedência especializada (ADR-0008).
_VARIATION_BASE_TYPES: dict[str, str] = {
    ProcedureType.EDA_GASTROSTOMY: ProcedureType.EDA,
    ProcedureType.EDA_CAPSULE: ProcedureType.EDA,
    ProcedureType.EDA_DILATION: ProcedureType.EDA,
    ProcedureType.RECTOSIGMOIDOSCOPY_DILATION: ProcedureType.RECTOSIGMOIDOSCOPY,
    ProcedureType.RECTOSIGMOIDOSCOPY_ARGON: ProcedureType.RECTOSIGMOIDOSCOPY,
}
# Termos ambíguos exigem vínculo local com a base na MESMA expressão; GTT e
# cápsula são marcadores autoevidentes da família e não exigem vínculo (D3).
_VARIATIONS_REQUIRING_LOCAL_LINK: frozenset[str] = frozenset(
    {
        ProcedureType.EDA_DILATION,
        ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
        ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
    }
)
# Identificador da regra de pacote registrado em evento/sugestão (D3).
VARIATION_PRECEDENCE_RULE = "variation_over_base"
# Identidades da família Retossigmoidoscopia (D3/Slice 003).
_FAMILY_PROCEDURE_TYPES: frozenset[str] = frozenset(
    {
        ProcedureType.RECTOSIGMOIDOSCOPY,
        ProcedureType.RECTOSIGMOIDOSCOPY_DILATION,
        ProcedureType.RECTOSIGMOIDOSCOPY_ARGON,
    }
)
# Alias guarda-chuva do Motivo: ``Endoscopia Digestiva Baixa`` é casado como
# Colonoscopia (``_COLONOSCOPY_TERM_PATTERN``) sem ser solicitação de
# colonoscopia por si (D3).
_UMBRELLA_COLONOSCOPY_EXCERPT = "endoscopia digestiva baixa"
# Seção de proveniência que autoriza a supressão (D1): o guarda-chuva citado no
# CORPO (Justificativa/Resumo) NÃO autoriza.
_MOTIVO_DA_SOLICITACAO_SECTION = "motivo_da_solicitacao"
# Item 1.0 — seções de origem reconhecidas e rótulos estáveis exibidos no motivo
# da revisão NIR (o card não renderiza mais a listagem de pistas).
_JUSTIFICATIVA_DA_TRANSFERENCIA_SECTION = "justificativa_da_transferencia"
_DETECTION_ORIGIN_LABELS: dict[str, str] = {
    _JUSTIFICATIVA_DA_TRANSFERENCIA_SECTION: "Justificativa da Transferência",
    _MOTIVO_DA_SOLICITACAO_SECTION: "Motivo da Solicitação",
}
# Ordem canônica de exibição (Justificativa antes do Motivo), independente da
# ordem textual das ocorrências no relatório.
_DETECTION_ORIGIN_ORDER: tuple[str, ...] = (
    _JUSTIFICATIVA_DA_TRANSFERENCIA_SECTION,
    _MOTIVO_DA_SOLICITACAO_SECTION,
)
_DETECTION_ORIGIN_PREFIX = " Origem da detecção: "
# Identificador da regra de família registrado em evento/sugestão (D3/Slice 003).
FAMILY_UMBRELLA_PRECEDENCE_RULE = "family_umbrella_over_colonoscopy"


def _current_request_occurrence_types(occurrences: Any) -> set[str]:
    """Tipos com ocorrência textual qualificada como solicitação atual (D1)."""
    return {
        str(getattr(occurrence, "procedure_type", ""))
        for occurrence in occurrences or ()
        if str(getattr(occurrence, "qualification", "")) == _QUALIFICATION_CURRENT_REQUEST
    }


def _detection_origin_suffix(*, detected: tuple[str, ...], occurrences: Any) -> str:
    """Sufixo do motivo NIR com a origem textual da detecção (item 1.0).

    Considera apenas ocorrências de solicitação ATUAL cujo tipo está no conjunto
    detectado e cuja seção tem rótulo estável; seções vazias ou desconhecidas são
    ignoradas. Os rótulos são deduplicados e exibidos na ordem canônica. Sem
    origem elegível devolve ``""`` e o motivo permanece intacto.
    """
    detected_set = set(detected)
    sections = {
        str(getattr(occurrence, "section", ""))
        for occurrence in occurrences or ()
        if str(getattr(occurrence, "qualification", "")) == _QUALIFICATION_CURRENT_REQUEST
        and str(getattr(occurrence, "procedure_type", "")) in detected_set
    }
    labels = [_DETECTION_ORIGIN_LABELS[section] for section in _DETECTION_ORIGIN_ORDER if section in sections]
    if not labels:
        return ""
    return f"{_DETECTION_ORIGIN_PREFIX}{', '.join(labels)}."


def _current_request_variation_types(occurrences: Any) -> set[str]:
    """Variações com ocorrência atual que autoriza supressão da base (D3).

    Termo ambíguo só autoriza quando a própria ocorrência carrega o vínculo
    local com a base; marcadores autoevidentes dispensam vínculo. O item
    estruturado sem ocorrência atual não entra aqui e, portanto, não suprime.
    """
    result: set[str] = set()
    for occurrence in occurrences or ():
        procedure_type = str(getattr(occurrence, "procedure_type", ""))
        if procedure_type not in _VARIATION_BASE_TYPES:
            continue
        if str(getattr(occurrence, "qualification", "")) != _QUALIFICATION_CURRENT_REQUEST:
            continue
        if procedure_type in _VARIATIONS_REQUIRING_LOCAL_LINK and not bool(getattr(occurrence, "linked_base", False)):
            continue
        result.add(procedure_type)
    return result


def _apply_variation_precedence(*, any_set: set[str], occurrences: Any) -> tuple[set[str], str, tuple[str, ...]]:
    """Supressão da base por exatamente uma variação atual (D3/Slices 003-005).

    Retorna o conjunto reconciliado, a variação selecionada e a base suprimida
    — vazios quando não houve redução. Duas variações atuais (de qualquer
    família), variação sem ocorrência atual e conjunto sem a base permanecem
    inalterados (fail-closed na matriz, sem descartar valores).
    """
    variations = any_set & set(_VARIATION_BASE_TYPES)
    if len(variations) != 1:
        return any_set, "", ()
    selected = str(next(iter(variations)))
    if selected not in _current_request_variation_types(occurrences):
        return any_set, "", ()
    base = _VARIATION_BASE_TYPES[selected]
    if base not in any_set:
        return any_set, "", ()
    # Somente a base é absorvida pela variação: qualquer outro componente do
    # conjunto bruto permanece e segue à matriz (fail-closed sem descartar
    # valores — ex.: pacote + Colonoscopia).
    return any_set - {base}, selected, (base,)


def _family_identity_is_current(*, selected: str, occurrences: Any) -> bool:
    """A identidade da família tem ocorrência atual que autoriza a regra (D3).

    Variações ambíguas reutilizam o regime de ``_current_request_variation_types``
    (vínculo local ``linked_base``); a base exige apenas ocorrência atual.
    """
    if selected in _VARIATION_BASE_TYPES:
        return selected in _current_request_variation_types(occurrences)
    return selected in _current_request_occurrence_types(occurrences)


def _colonoscopy_is_only_the_motive_umbrella(*, occurrences: Any) -> bool:
    """Toda ocorrência ATUAL de colonoscopia é o guarda-chuva marcado no Motivo (D3).

    Exige ao menos uma ocorrência atual: a colonoscopia sustentada apenas pelo
    item estruturado do LLM1 (sem evidência textual) não é "só guarda-chuva" e
    não autoriza a supressão (fail-closed). Ocorrência atual do termo explícito
    ou guarda-chuva atual citado no CORPO (``section`` ≠ Motivo) reprovam.
    """
    current_occurrences = [
        occurrence
        for occurrence in occurrences or ()
        if str(getattr(occurrence, "procedure_type", "")) == ProcedureType.COLONOSCOPY
        and str(getattr(occurrence, "qualification", "")) == _QUALIFICATION_CURRENT_REQUEST
    ]
    if not current_occurrences:
        return False
    return all(
        str(getattr(occurrence, "excerpt", "")) == _UMBRELLA_COLONOSCOPY_EXCERPT
        and str(getattr(occurrence, "section", "")) == _MOTIVO_DA_SOLICITACAO_SECTION
        for occurrence in current_occurrences
    )


def _apply_family_umbrella_precedence(*, any_set: set[str], occurrences: Any) -> tuple[set[str], str, tuple[str, ...]]:
    """Supressão da colonoscopia que só existe pelo guarda-chuva do Motivo (D3).

    Condições (todas): exatamente uma identidade da família Retossigmoidoscopia
    no conjunto; essa identidade com ocorrência atual (mesmo regime de
    proveniência das variações); ``colonoscopy`` presente e TODA ocorrência sua
    de solicitação atual sendo o alias guarda-chuva ``endoscopia digestiva
    baixa`` marcado em ``motivo_da_solicitacao`` (D1). Qualquer evidência atual
    explícita, guarda-chuva fora do Motivo ou ausência de ocorrência atual da
    família mantém o conjunto bruto e falha fechado na matriz. Retorna o
    conjunto reconciliado, a identidade selecionada e o tipo suprimido —
    vazios quando não houve redução.
    """
    family = any_set & _FAMILY_PROCEDURE_TYPES
    if len(family) != 1:
        return any_set, "", ()
    selected = str(next(iter(family)))
    if not _family_identity_is_current(selected=selected, occurrences=occurrences):
        return any_set, "", ()
    if ProcedureType.COLONOSCOPY not in any_set:
        return any_set, "", ()
    if not _colonoscopy_is_only_the_motive_umbrella(occurrences=occurrences):
        return any_set, "", ()
    return any_set - {ProcedureType.COLONOSCOPY}, selected, (ProcedureType.COLONOSCOPY,)


def _apply_specialized_precedence(*, any_set: set[str], occurrences: Any) -> tuple[set[str], str, tuple[str, ...]]:
    """Precedência de especializado único sobre convencionais (D1/ADR-0008).

    Exige exatamente um tipo especializado no conjunto detectado E ocorrência
    textual do MESMO tipo qualificada como ``current_request``. Item
    estruturado isolado, histórico, negação ou menção não autorizam supressão;
    dois especializados (Eco + CPRE) mantêm o conjunto bruto e falham fechado
    na matriz (R2). Retorna o conjunto reconciliado, o tipo especializado
    selecionado e os convencionais suprimidos — vazios quando não houve
    redução. Nenhum vínculo local ``com/e`` é exigido (ADR-0008).
    """
    specialized = any_set & _SPECIALIZED_PROCEDURE_TYPES
    if len(specialized) != 1:
        return any_set, "", ()
    selected = str(next(iter(specialized)))
    if selected not in _current_request_occurrence_types(occurrences):
        return any_set, "", ()
    suppressed = tuple(
        sorted(
            (str(procedure_type) for procedure_type in any_set & _CONVENTIONAL_PROCEDURE_TYPES),
            key=PROCEDURE_ORDER.__getitem__,
        )
    )
    if not suppressed:
        return any_set, "", ()
    return {selected}, selected, suppressed


@dataclass(frozen=True)
class ProcedureReconciliationResult:
    """Desfecho da matriz D7 para um caso.

    ``precedence_applied``/``selected_specialized_type``/
    ``suppressed_conventional_types`` carregam a precedência especializada
    efetivamente aplicada (D3); ``variation_precedence_applied``/
    ``selected_variation_type``/``suppressed_base_types`` carregam a supressão
    da base EDA por um pacote atômico (Slices 003/004);
    ``family_umbrella_precedence_applied``/``selected_family_type``/
    ``suppressed_umbrella_types`` carregam a supressão da colonoscopia que só
    existe pelo guarda-chuva do Motivo (Slice 003). Todos são vazios quando não
    houve redução.
    """

    action: str  # "proceed" | "auto_upgrade" | "nir_review"
    detected_procedure_types: tuple[str, ...]
    reason_code: str
    reason_text: str
    upgraded: bool = False
    precedence_applied: bool = False
    selected_specialized_type: str = ""
    suppressed_conventional_types: tuple[str, ...] = ()
    variation_precedence_applied: bool = False
    selected_variation_type: str = ""
    suppressed_base_types: tuple[str, ...] = ()
    family_umbrella_precedence_applied: bool = False
    selected_family_type: str = ""
    suppressed_umbrella_types: tuple[str, ...] = ()


def _proceed(
    detected: tuple[str, ...],
    *,
    selected_specialized_type: str = "",
    suppressed_conventional_types: tuple[str, ...] = (),
    selected_variation_type: str = "",
    suppressed_base_types: tuple[str, ...] = (),
    selected_family_type: str = "",
    suppressed_umbrella_types: tuple[str, ...] = (),
) -> ProcedureReconciliationResult:
    return ProcedureReconciliationResult(
        action="proceed",
        detected_procedure_types=detected,
        reason_code="",
        reason_text="",
        precedence_applied=bool(selected_specialized_type and suppressed_conventional_types),
        selected_specialized_type=selected_specialized_type,
        suppressed_conventional_types=suppressed_conventional_types,
        variation_precedence_applied=bool(selected_variation_type and suppressed_base_types),
        selected_variation_type=selected_variation_type,
        suppressed_base_types=suppressed_base_types,
        family_umbrella_precedence_applied=bool(selected_family_type and suppressed_umbrella_types),
        selected_family_type=selected_family_type,
        suppressed_umbrella_types=suppressed_umbrella_types,
    )


def _auto_upgrade(detected: tuple[str, ...]) -> ProcedureReconciliationResult:
    return ProcedureReconciliationResult(
        action="auto_upgrade",
        detected_procedure_types=detected,
        reason_code="auto_upgrade_strong_evidence",
        reason_text=("Solicitações atuais de EDA e Colonoscopia com evidência forte; upgrade automático auditado."),
        upgraded=True,
    )


def _nir_review(
    *,
    reason_code: str,
    reason_text: str,
    detected: tuple[str, ...],
    occurrences: Any = (),
    selected_specialized_type: str = "",
    suppressed_conventional_types: tuple[str, ...] = (),
    selected_variation_type: str = "",
    suppressed_base_types: tuple[str, ...] = (),
    selected_family_type: str = "",
    suppressed_umbrella_types: tuple[str, ...] = (),
) -> ProcedureReconciliationResult:
    # Item 1.0: a origem da detecção (seções das ocorrências atuais do conjunto
    # detectado) entra no motivo; sem origem elegível o texto permanece intacto.
    return ProcedureReconciliationResult(
        action="nir_review",
        detected_procedure_types=detected,
        reason_code=reason_code,
        reason_text=f"{reason_text}{_detection_origin_suffix(detected=detected, occurrences=occurrences)}",
        precedence_applied=bool(selected_specialized_type and suppressed_conventional_types),
        selected_specialized_type=selected_specialized_type,
        suppressed_conventional_types=suppressed_conventional_types,
        variation_precedence_applied=bool(selected_variation_type and suppressed_base_types),
        selected_variation_type=selected_variation_type,
        suppressed_base_types=suppressed_base_types,
        family_umbrella_precedence_applied=bool(selected_family_type and suppressed_umbrella_types),
        selected_family_type=selected_family_type,
        suppressed_umbrella_types=suppressed_umbrella_types,
    )


def reconcile_detected_procedures(
    *,
    declared: Any,
    strong: Any,
    any_evidence: Any,
    occurrences: Any = (),
    conflicting: Any = (),
) -> ProcedureReconciliationResult:
    """Matriz D2/D3 completa (declarado × detectado) com gate de evidência forte.

    Args:
        declared: conjunto declarado pelo NIR (ordem canônica aplicada).
        strong: procedimentos com evidência forte de solicitação atual.
        any_evidence: procedimentos com qualquer evidência de solicitação atual.
        occurrences: ocorrências qualificadas (``scope_detection``) que provam a
            atualidade textual do especializado; sem ocorrência ``current_request``
            do próprio tipo não há supressão de convencionais (D1/ADR-0008). As
            seções dessas ocorrências também alimentam o sufixo de origem do
            motivo NIR (item 1.0).
        conflicting: tipos cujo item estruturado do LLM1 foi contraditado por
            ocorrência não-atual no texto (``scope_detection`` v4); qualquer tipo
            conhecido aqui força ``nir_review`` ANTES de precedência/proceed
            (Slice 004/D4). Default vazio preserva o comportamento anterior.

    Returns:
        ``proceed`` (conjunto reconciliado = declarado), ``auto_upgrade``
        (declarado único EDA/Colon + ambos detectados com evidência forte do
        segundo) ou ``nir_review`` (tipo desconhecido, combinação não
        suportada, combined→single, mismatch único, item estruturado
        contraditado ou evidência insuficiente).
    """
    declared_partition = _partition_procedures(declared)
    strong_partition = _partition_procedures(strong)
    any_partition = _partition_procedures(any_evidence)

    # R3 — validação antes de qualquer ordenação/matriz: nenhum valor
    # desconhecido ou duplicata pode ser descartado em silêncio.
    if declared_partition.unknown or strong_partition.unknown or any_partition.unknown:
        return _nir_review(
            reason_code="unknown_exam_type",
            reason_text="Procedimento fora do catálogo suportado na solicitação; revisão manual obrigatória.",
            detected=any_partition.ordered,
            occurrences=occurrences,
        )

    if declared_partition.had_duplicates or any_partition.had_duplicates or strong_partition.had_duplicates:
        return _nir_review(
            reason_code="unsupported_procedure_combination",
            reason_text="Solicitação com procedimento duplicado; revisão manual obrigatória.",
            detected=any_partition.ordered,
            occurrences=occurrences,
        )

    declared_set = set(declared_partition.ordered)
    strong_set = set(strong_partition.ordered)
    any_set = set(any_partition.ordered)

    # Slice 004 (R2/D4) — item estruturado contraditado por ocorrência não-atual:
    # qualquer tipo CONHECIDO em ``conflicting`` força revisão NIR ANTES de
    # precedência/proceed. Fecha a falha aberta em que o conjunto restante coincide
    # com o declarado (ex.: declarado == detectado-pelo-Motivo) e a contradição do
    # LLM1 era descartada em silêncio. Tipos fora do catálogo nesse parâmetro não
    # criam revisão própria (aqui o item contraditado é proveniência do catálogo).
    conflicting_set = set(_partition_procedures(conflicting).ordered)
    if conflicting_set:
        return _nir_review(
            reason_code="conflicting_procedure_evidence",
            reason_text=(
                "Item estruturado do LLM contradiz o corpo do relatório "
                "(ocorrência não-atual do termo); revisão manual obrigatória."
            ),
            detected=_ordered(any_set | conflicting_set),
            occurrences=occurrences,
        )

    if declared_set and frozenset(declared_set) not in ALLOWED_PROCEDURE_SETS:
        return _nir_review(
            reason_code="unsupported_procedure_combination",
            reason_text="Conjunto declarado fora da matriz suportada; revisão manual obrigatória.",
            detected=_ordered(any_set),
            occurrences=occurrences,
        )

    # D1/ADR-0008 — precedência do especializado único: um tipo especializado
    # com ocorrência textual ATUAL do MESMO tipo suprime EDA/Colonoscopia,
    # inclusive em trechos independentes. A redução acontece ANTES da validação
    # da matriz do lado detectado, mas DEPOIS da validação de
    # catálogo/duplicatas (R3); dois especializados ou ausência de ocorrência
    # atual mantêm o conjunto bruto e falham fechado na matriz.
    any_set, selected_specialized_type, suppressed_conventional_types = _apply_specialized_precedence(
        any_set=any_set,
        occurrences=occurrences,
    )
    # D3/Slices 003/004 — supressão da base por exatamente uma variação atual
    # (pacote atômico). Roda DEPOIS da precedência especializada: um
    # especializado atual já reduziu o conjunto e não há variação a suprimir.
    any_set, selected_variation_type, suppressed_base_types = _apply_variation_precedence(
        any_set=any_set,
        occurrences=occurrences,
    )
    # D3/Slice 003 — a família Retossigmoidoscopia atual absorve a colonoscopia
    # que só se sustenta pelo alias guarda-chuva do Motivo. Roda DEPOIS da
    # variação (a base já foi absorvida) e ANTES da matriz; qualquer evidência
    # atual explícita de colonoscopia mantém o conflito fail-closed.
    any_set, selected_family_type, suppressed_umbrella_types = _apply_family_umbrella_precedence(
        any_set=any_set,
        occurrences=occurrences,
    )
    precedence_kwargs: dict[str, Any] = {
        "selected_specialized_type": selected_specialized_type,
        "suppressed_conventional_types": suppressed_conventional_types,
        "selected_variation_type": selected_variation_type,
        "suppressed_base_types": suppressed_base_types,
        "selected_family_type": selected_family_type,
        "suppressed_umbrella_types": suppressed_umbrella_types,
    }

    if any_set and frozenset(any_set) not in ALLOWED_PROCEDURE_SETS:
        return _nir_review(
            reason_code="unsupported_procedure_combination",
            reason_text="Combinação de procedimentos não suportada; revisão manual obrigatória.",
            detected=_ordered(any_set),
            occurrences=occurrences,
            **precedence_kwargs,
        )

    if not any_set:
        return _nir_review(
            reason_code="unknown_exam_type",
            reason_text="Nenhum procedimento suportado detectado na solicitação atual; revisão manual obrigatória.",
            detected=(),
            occurrences=occurrences,
            **precedence_kwargs,
        )

    if any_set == declared_set:
        # EDA | Colon | Eco | CPRE | Ambos | Ambos → prossegue.
        return _proceed(_ordered(any_set), **precedence_kwargs)

    if declared_set == PAIRED_APPOINTMENT_SET and len(any_set) == 1:
        # Combinado declarado, somente um detectado → revisão NIR.
        return _nir_review(
            reason_code="exam_type_mismatch",
            reason_text=(
                "Declarado EDA + Colonoscopia, mas apenas um procedimento foi "
                "detectado na solicitação atual; revisão manual obrigatória."
            ),
            detected=_ordered(any_set),
            occurrences=occurrences,
            **precedence_kwargs,
        )

    if len(declared_set) == 1 and len(any_set) == 2:
        # Declarado único, ambos detectados → upgrade automático SOMENTE para o
        # par EDA+Colonoscopia com evidência forte do segundo procedimento.
        # Qualquer conjunto contendo especializado retorna ao NIR: a precedência
        # do especializado único (acima) já removeu os convencionais quando
        # havia ocorrência atual, e a declaração NIR nunca é sobrescrita (D2).
        if any_set == PAIRED_APPOINTMENT_SET and (any_set - declared_set).issubset(strong_set):
            return _auto_upgrade(_ordered(any_set))
        return _nir_review(
            reason_code="mixed_exam_request",
            reason_text=(
                "Solicitação atual contém dois procedimentos, mas o segundo não "
                "possui evidência forte; revisão manual obrigatória."
            ),
            detected=_ordered(any_set),
            occurrences=occurrences,
            **precedence_kwargs,
        )

    if len(declared_set) == 1 and len(any_set) == 1 and any_set != declared_set:
        # Contradição entre tipos únicos → revisão NIR (sem swap silencioso).
        return _nir_review(
            reason_code="exam_type_mismatch",
            reason_text=(
                "Tipo de procedimento declarado difere do detectado na solicitação atual; revisão manual obrigatória."
            ),
            detected=_ordered(any_set),
            occurrences=occurrences,
            **precedence_kwargs,
        )

    # Fallback conservador: qualquer outra divergência retorna ao NIR.
    return _nir_review(
        reason_code="exam_type_mismatch",
        reason_text="Conjunto detectado diverge do declarado; revisão manual obrigatória.",
        detected=_ordered(any_set),
        occurrences=occurrences,
        **precedence_kwargs,
    )


def _precedence_rule(*, rule: str, selected: str, suppressed: tuple[str, ...]) -> dict[str, object]:
    """Metadado enxuto de UMA redução: regra, selecionado e suprimidos (D3)."""
    return {"rule": rule, "selected": selected, "suppressed": list(suppressed)}


def serialize_procedure_precedence_rules(reconciliation: ProcedureReconciliationResult) -> list[dict[str, object]]:
    """TODAS as reduções aplicadas, da mais significativa para a menos (D3).

    A ordem é especializado → variação → família (a mesma do dict único de
    ``serialize_procedure_precedence``); lista vazia quando nenhuma regra foi
    aplicada. Existe separado porque o orchestrator atribui o retorno daquele
    serializer direto a ``procedure_precedence`` (formato dict consumido pelo
    presenter e por casos já persistidos).
    """
    rules: list[dict[str, object]] = []
    if reconciliation.precedence_applied:
        rules.append(
            _precedence_rule(
                rule=PROCEDURE_PRECEDENCE_RULE,
                selected=reconciliation.selected_specialized_type,
                suppressed=reconciliation.suppressed_conventional_types,
            )
        )
    if reconciliation.variation_precedence_applied:
        rules.append(
            _precedence_rule(
                rule=VARIATION_PRECEDENCE_RULE,
                selected=reconciliation.selected_variation_type,
                suppressed=reconciliation.suppressed_base_types,
            )
        )
    if reconciliation.family_umbrella_precedence_applied:
        rules.append(
            _precedence_rule(
                rule=FAMILY_UMBRELLA_PRECEDENCE_RULE,
                selected=reconciliation.selected_family_type,
                suppressed=reconciliation.suppressed_umbrella_types,
            )
        )
    return rules


def serialize_procedure_precedence(reconciliation: ProcedureReconciliationResult) -> dict[str, object] | None:
    """Metadados enxutos de precedência para evento e sugestão (D3).

    Retorna ``None`` quando nenhuma regra foi aplicada (singleton normal,
    conflito fail-closed, legado), evitando confundir correção determinística
    com operação normal. Quando mais de uma redução se aplica, devolve a MAIS
    SIGNIFICATIVA (a primeira de ``serialize_procedure_precedence_rules``) para
    preservar o formato dict dos consumidores existentes. Todas as reduções usam
    o MESMO formato de proveniência — regra, selecionado e suprimidos —, nunca
    excerpt ou texto clínico.
    """
    rules = serialize_procedure_precedence_rules(reconciliation)
    return rules[0] if rules else None


def _project_review_evidence_spans(evidence_spans: list[dict[str, str]]) -> list[dict[str, str]]:
    """Projeta spans com limites explícitos para o payload de revisão (F4/R8)."""
    projected: list[dict[str, str]] = []
    for span in evidence_spans[:5]:
        projected.append(
            {
                "field_path": span["field_path"][:120],
                "excerpt": span["excerpt"][:200],
            }
        )
    return projected


# D5 (Slice 005) — limites e traduções da projeção de pistas do corpo.
_BODY_CLUE_QUALIFICATION_LABELS: dict[str, str] = {
    "current_request": "Solicitação atual",
    "mention": "Menção",
    "historical": "Histórico",
    "negated": "Negado",
}
_BODY_CLUE_LIMIT = 8
_BODY_CLUE_EXCERPT_LIMIT = 200


def project_body_clues(occurrences: Any) -> list[dict[str, str]]:
    """Projeta ocorrências do CORPO do relatório como pistas da revisão NIR (D5).

    Exclui ocorrências marcadas na seção ``motivo_da_solicitacao`` (D1/Slice 001):
    a evidência do Motivo não é pista do corpo — declarado e detectado já estão no
    card de correção.
    Ordena ``current_request`` primeiro e o restante pela ordem canônica do tipo,
    limita a ``_BODY_CLUE_LIMIT`` entradas e trunca ``excerpt`` a
    ``_BODY_CLUE_EXCERPT_LIMIT`` chars. Função pura sobre ``ProcedureOccurrence``:
    sem ocorrências devolve lista vazia.
    """
    eligible = [occurrence for occurrence in occurrences or () if occurrence.section != _MOTIVO_DA_SOLICITACAO_SECTION]
    eligible.sort(
        key=lambda occurrence: (
            occurrence.qualification != "current_request",
            PROCEDURE_ORDER.get(occurrence.procedure_type, len(PROCEDURE_ORDER)),
        )
    )
    return [
        {
            "procedure_type": occurrence.procedure_type,
            "procedure_label": ProcedureType(occurrence.procedure_type).label,
            "qualification": occurrence.qualification,
            "qualification_label": _BODY_CLUE_QUALIFICATION_LABELS.get(
                occurrence.qualification, occurrence.qualification
            ),
            "section": occurrence.section,
            "excerpt": occurrence.excerpt[:_BODY_CLUE_EXCERPT_LIMIT],
        }
        for occurrence in eligible[:_BODY_CLUE_LIMIT]
    ]


def build_v2_review_payload(
    *,
    case_id: str,
    agency_record_number: str,
    reason_code: str,
    reason_text: str,
    declared: tuple[str, ...],
    detected: tuple[str, ...],
    evidence_spans: list[dict[str, str]],
    body_clues: Any = None,
) -> dict[str, object]:
    """Payload enxuto de revisão NIR para contrato 2.1 (conjuntos + reason + pistas).

    Mantém campos legados (``declared_exam_type``/``detected_exam_type``)
    apenas para compatibilidade de exibição; a informação canônica são os
    conjuntos ``declared_procedures``/``detected_procedures``. ``body_clues``
    recebe a lista já projetada por ``project_body_clues`` (D5); o campo
    ``detected_body_clues`` é aditivo e vazio quando ausente.
    """
    declared_types = _ordered(declared)
    detected_types = _ordered(detected)
    detected_label = "mixed" if len(detected_types) == 2 else (detected_types[0] if detected_types else "unknown")
    declared_label = (
        EDA_COLONOSCOPY if is_paired_appointment_set(declared_types) else (declared_types[0] if declared_types else "")
    )
    return {
        "schema_version": "2.1",
        "language": "pt-BR",
        "case_id": case_id,
        "agency_record_number": agency_record_number,
        "decision": "manual_review_required",
        "suggestion": "manual_review_required",
        "reason_code": reason_code,
        "reason_text": reason_text,
        "declared_procedures": list(declared_types),
        "detected_procedures": list(detected_types),
        "exam_type": detected_label,
        "declared_exam_type": declared_label,
        "detected_exam_type": detected_label,
        "evidence_spans": _project_review_evidence_spans(evidence_spans),
        "detected_body_clues": list(body_clues or []),
    }
