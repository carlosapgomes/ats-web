"""Precheck não destrutivo do caminho de downgrade 4.0 (Slice 010, R2).

Prova, sem escrever nada, se o retorno à imagem ANTERIOR (writer strict 3.0,
quatro identidades ``eda|colonoscopy|echoendoscopy|cpre``) ainda é admissível.
A fronteira de rollback deste change é o **primeiro write 4.0** ou a **primeira
row de identidade nova** (design D14 ``Migration Plan``/``Risks``; spec
``procedure-neutral-analysis``: "Primeiro write 4.0 concluído → rollback para
writer 3.0 não é suportado"; ADR-0010 §6). Não existe deleção de dados nem
reverse migration destrutiva para viabilizar downgrade.

``status`` e exit code refletem SOMENTE essa fronteira. Exit 0 (``allowed``)
somente enquanto nenhuma classe de fronteira existir; exit 1 (``blocked``)
diante de QUALQUER uma das três classes:

1. ``pipeline_job_in_flight`` — caso em estado de pipeline: há um writer ativo
   em voo que precisa ser drenado antes do cutover (spec: "Writers 3.0 SHALL
   encerrar antes do primeiro write 4.0");
2. ``new_identity_case_procedure`` — row ``CaseProcedure`` com identidade nova
   deste change (as seis que a imagem anterior não conhece: pacotes EDA e
   família Retossigmoidoscopia);
3. ``v4_artifact_write`` — marcador ``schema_version="4.0"`` persistido em
   ``Case.structured_data``, ``Case.suggested_action`` ou payload de
   ``CaseEvent``.

Dado produzido pela própria imagem anterior (writer 3.0) é baseline e NUNCA
bloqueia o retorno a ela:

4. ``specialized_case_procedure`` — row ``CaseProcedure`` de Ecoendoscopia/CPRE;
5. ``v3_artifact_write`` — marcador ``schema_version="3.0"`` persistido;
6. ``specialized_case_event`` — ``CaseEvent`` cujo payload referencia um
   procedimento especializado;
7. ``legacy_echo_artifact`` — artefato derivado do sinal legado ``echoendoscopy``
   (projeção ``priority_signals``) da era 2.0.

Essas quatro classes aparecem no relatório como contagens informativas e em
``notes``; ``old_image_return_available`` é ``true`` exatamente quando
``status == "allowed"`` (retorno à imagem 3.0 disponível).

O relatório é machine-readable: um único documento JSON no stdout, apenas com
contagens e UUIDs de caso (amostras limitadas) — nunca texto clínico, PDF,
``extracted_text`` ou conteúdo de mensagem. O caminho bloqueado emite o
relatório e levanta ``CommandError`` (exit code 1) orientando fix-forward:
depois do primeiro write 4.0 / row nova, NUNCA reativar o writer 3.0, NUNCA
apagar rows/artefatos e NUNCA reclassificar — pausar a ingestão e corrigir
para frente.

Usage:
    uv run python manage.py check_specialized_procedure_downgrade --settings=config.settings.prod
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.cases.models import Case, CaseEvent, CaseProcedure, CaseStatus, ProcedureType
from apps.cases.procedures import SUPPORTED_PROCEDURE_TYPES

COMMAND_NAME = "check_specialized_procedure_downgrade"

# Fronteira de rollback deste change (design D14 / spec procedure-neutral-analysis).
BOUNDARY = "first_4_0_write"

# Códigos estáveis das classes de FRONTEIRA (bloqueiam o downgrade).
CODE_PIPELINE_JOB = "pipeline_job_in_flight"
CODE_NEW_IDENTITY_ROW = "new_identity_case_procedure"
CODE_V4_WRITE = "v4_artifact_write"

# Códigos estáveis das classes de BASELINE da imagem anterior (informativas).
CODE_SPECIALIZED_ROW = "specialized_case_procedure"
CODE_V3_WRITE = "v3_artifact_write"
CODE_SPECIALIZED_EVENT = "specialized_case_event"
CODE_LEGACY_ECHO = "legacy_echo_artifact"

BOUNDARY_CODES: tuple[str, ...] = (CODE_PIPELINE_JOB, CODE_NEW_IDENTITY_ROW, CODE_V4_WRITE)
BASELINE_CODES: tuple[str, ...] = (CODE_SPECIALIZED_ROW, CODE_V3_WRITE, CODE_SPECIALIZED_EVENT, CODE_LEGACY_ECHO)

BASELINE_NOTE = (
    "baseline_checks={codes}: dado produzido pela imagem anterior (writer 3.0) — artefatos 3.0, "
    "rows de Ecoendoscopia/CPRE e dado legado v2 — não bloqueia o retorno à imagem 3.0."
)

# Sinal prioritário legado derivado do subtipo EDA ``echoendoscopy``
# (``apps/cases/priority_signals.py``).
LEGACY_ECHO_SIGNAL_CODE = "echoendoscopy"

# Marcadores de schema gravável: 3.0 (imagem anterior) e 4.0 (este change).
V3_SCHEMA_VERSION = "3.0"
V4_SCHEMA_VERSION = "4.0"

# Identidades que a imagem anterior conhece.
PREVIOUS_IMAGE_PROCEDURE_TYPES = frozenset(
    {ProcedureType.EDA, ProcedureType.COLONOSCOPY, ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE}
)

# Identidades novas deste change: todo código do catálogo 4.0 fora do writer 3.0.
NEW_IDENTITY_PROCEDURE_TYPES = frozenset(SUPPORTED_PROCEDURE_TYPES) - PREVIOUS_IMAGE_PROCEDURE_TYPES

SPECIALIZED_PROCEDURE_TYPES = frozenset({ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE})

# Estados de pipeline: writer em voo (deve ser drenado antes do cutover).
PIPELINE_STATUSES: tuple[str, ...] = (
    CaseStatus.NEW,
    CaseStatus.R1_ACK_PROCESSING,
    CaseStatus.EXTRACTING,
    CaseStatus.LLM_STRUCT,
    CaseStatus.LLM_SUGGEST,
)

# Limite de amostras por check no relatório (o ``count`` é sempre completo).
SAMPLE_LIMIT = 5

_SPECIALIZED_LABELS = "Ecoendoscopia/CPRE"


# ── Predicados de payload (JSON já persistido) ───────────────────────────────


def _references_specialized_procedure(payload: Any) -> bool:
    """True quando algum valor do payload é um procedimento especializado."""
    if isinstance(payload, str):
        return payload in SPECIALIZED_PROCEDURE_TYPES
    if isinstance(payload, dict):
        return any(_references_specialized_procedure(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_references_specialized_procedure(item) for item in payload)
    return False


def _has_schema_marker(payload: Any, version: str) -> bool:
    """True quando o payload persistido carrega o marcador ``schema_version`` dado."""
    if isinstance(payload, dict):
        if payload.get("schema_version") == version:
            return True
        return any(_has_schema_marker(value, version) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_has_schema_marker(item, version) for item in payload)
    return False


# ── Coleta por classe ────────────────────────────────────────────────────────


def _scan_events() -> dict[str, list[Any]]:
    """Uma passada somente-leitura pelos eventos, por classe relevante."""
    found: dict[str, list[Any]] = {"specialized": [], "v3": [], "v4": []}
    for case_id, payload in CaseEvent.objects.values_list("case_id", "payload").iterator(chunk_size=500):
        if _references_specialized_procedure(payload):
            found["specialized"].append(case_id)
        if _has_schema_marker(payload, V3_SCHEMA_VERSION):
            found["v3"].append(case_id)
        if _has_schema_marker(payload, V4_SCHEMA_VERSION):
            found["v4"].append(case_id)
    return found


def _pipeline_job_ids() -> list[Any]:
    return list(Case.objects.filter(status__in=PIPELINE_STATUSES).values_list("case_id", flat=True))


def _new_identity_row_ids() -> list[Any]:
    return list(
        CaseProcedure.objects.filter(procedure_type__in=NEW_IDENTITY_PROCEDURE_TYPES).values_list("case_id", flat=True)
    )


def _specialized_row_ids() -> list[Any]:
    return list(
        CaseProcedure.objects.filter(procedure_type__in=SPECIALIZED_PROCEDURE_TYPES).values_list("case_id", flat=True)
    )


def _legacy_echo_ids() -> list[Any]:
    # Containment jsonb sobre a projeção canônica de sinais.
    return list(
        Case.objects.filter(priority_signals__contains=[{"code": LEGACY_ECHO_SIGNAL_CODE}]).values_list(
            "case_id", flat=True
        )
    )


def _case_artifact_ids_by_version() -> dict[str, list[Any]]:
    """Writes de artefato por versão de schema (um scan de ``structured_data``/``suggested_action``)."""
    found: dict[str, list[Any]] = {V3_SCHEMA_VERSION: [], V4_SCHEMA_VERSION: []}
    queryset = (
        Case.objects.filter(Q(structured_data__isnull=False) | Q(suggested_action__isnull=False))
        .values_list("case_id", "structured_data", "suggested_action")
        .iterator(chunk_size=500)
    )
    for case_id, structured_data, suggested_action in queryset:
        for version in found:
            if _has_schema_marker(structured_data, version) or _has_schema_marker(suggested_action, version):
                found[version].append(case_id)
    return found


def _check(code: str, label: str, case_ids: Iterable[Any]) -> dict[str, Any]:
    unique = sorted({str(case_id) for case_id in case_ids})
    return {
        "code": code,
        "label": label,
        "count": len(unique),
        "samples": unique[:SAMPLE_LIMIT],
    }


def build_report() -> dict[str, Any]:
    """Relatório machine-readable do precheck (leitura pura)."""
    events = _scan_events()
    artifacts = _case_artifact_ids_by_version()
    checks = [
        _check(
            CODE_PIPELINE_JOB,
            "Caso em estado de pipeline (writer em voo — drenar antes do cutover)",
            _pipeline_job_ids(),
        ),
        _check(
            CODE_NEW_IDENTITY_ROW,
            "Row CaseProcedure de identidade nova do catálogo 4.0",
            _new_identity_row_ids(),
        ),
        _check(
            CODE_V4_WRITE,
            "Write 4.0 persistido (structured_data/suggested_action/evento)",
            [*artifacts[V4_SCHEMA_VERSION], *events["v4"]],
        ),
        _check(
            CODE_SPECIALIZED_ROW,
            f"Row CaseProcedure de {_SPECIALIZED_LABELS} (baseline da imagem anterior)",
            _specialized_row_ids(),
        ),
        _check(
            CODE_V3_WRITE,
            "Write 3.0 persistido (baseline da imagem anterior)",
            [*artifacts[V3_SCHEMA_VERSION], *events["v3"]],
        ),
        _check(
            CODE_SPECIALIZED_EVENT,
            f"CaseEvent com procedimento especializado ({_SPECIALIZED_LABELS}) — baseline",
            events["specialized"],
        ),
        _check(
            CODE_LEGACY_ECHO,
            "Artefato derivado do sinal legado de Ecoendoscopia (baseline v2)",
            _legacy_echo_ids(),
        ),
    ]
    counts = {check["code"]: check["count"] for check in checks}
    blocking_checks = [code for code in BOUNDARY_CODES if counts[code]]
    baseline_hits = [code for code in BASELINE_CODES if counts[code]]
    allowed = not blocking_checks
    notes = [BASELINE_NOTE.format(codes=", ".join(baseline_hits))] if baseline_hits else []
    return {
        "command": COMMAND_NAME,
        "boundary": BOUNDARY,
        "status": "allowed" if allowed else "blocked",
        "blocking_checks": blocking_checks,
        "old_image_return_available": allowed,
        "notes": notes,
        "checks": checks,
    }


class Command(BaseCommand):
    help = "Precheck não destrutivo do caminho de downgrade 4.0 (Slice 010)"

    def handle(self, *args: object, **options: object) -> None:
        report = build_report()
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["status"] == "blocked":
            raise CommandError(
                "Downgrade bloqueado: a fronteira do primeiro write 4.0 (design D14) já foi cruzada "
                f"({', '.join(report['blocking_checks'])}). Proteja os dados: pausar a ingestão, manter "
                "imagem/schema 4.0 e corrigir para frente (fix-forward) — NUNCA reativar o writer 3.0, NUNCA "
                "apagar rows/artefatos "
                "(CaseProcedure, structured_data, suggested_action, CaseEvent, priority_signals) e NUNCA "
                "reclassificar identidades novas como EDA/Colonoscopia. Sem deleção de dados e sem reverse "
                "migration. Dado 3.0/Eco-CPRE/legado v2 é baseline da imagem anterior e aparece apenas em "
                "`old_image_return_available`/`notes`; quando presente, não bloqueia o retorno à imagem 3.0."
            )
