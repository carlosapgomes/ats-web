"""Precheck não destrutivo do caminho de downgrade especializado (Slice 009, R4).

Prova, sem escrever nada, se o retorno à imagem anterior ainda é admissível
quando a fronteira é o PRIMEIRO write 3.0 (ADR-0006 §9; design ``Migration
Plan``): depois do primeiro write 3.0 — mesmo de EDA/Colonoscopia — ou da
primeira row especializada, uma imagem antiga que só conhece o writer 2.0 e os
dois tipos convencionais é insegura. Não existe deleção de dados nem reverse
migration destrutiva para viabilizar downgrade.

Exit 0 (``allowed``) somente pré-cutover, com zero write 3.0 e zero artefato
especializado. Exit 1 (``blocked``) diante de QUALQUER uma das cinco classes:

1. ``pipeline_job_in_flight`` — caso em estado de pipeline; o writer ativo é
   exclusivamente o 3.0 (Slice 001/R1), então todo job em voo é um job 3.0;
2. ``specialized_case_procedure`` — row ``CaseProcedure`` de Ecoendoscopia/CPRE;
3. ``specialized_case_event`` — ``CaseEvent`` cujo payload referencia um
   procedimento especializado;
4. ``legacy_echo_artifact`` — artefato derivado do sinal legado
   ``echoendoscopy`` (projeção ``priority_signals``), que o writer 3.0 exclui
   (design D14); a checagem é conservadora e fail-closed;
5. ``v3_artifact_write`` — marcador ``schema_version="3.0"`` persistido em
   ``Case.structured_data``, ``Case.suggested_action`` ou payload de
   ``CaseEvent``.

O relatório é machine-readable: um único documento JSON no stdout, apenas com
contagens e UUIDs de caso (amostras limitadas) — nunca texto clínico, PDF,
``extracted_text`` ou conteúdo de mensagem. O caminho bloqueado emite o
relatório e levanta ``CommandError`` (exit code 1).

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

COMMAND_NAME = "check_specialized_procedure_downgrade"

# Fronteira de rollback (ADR-0006 §9 / design Migration Plan).
BOUNDARY = "first_3_0_write"

# Sinal prioritário legado derivado do subtipo EDA ``echoendoscopy``
# (``apps/cases/priority_signals.py``).
LEGACY_ECHO_SIGNAL_CODE = "echoendoscopy"

# Contrato gravável após o cutover (design D5). O writer mantém a constante
# privada em ``apps.pipeline.orchestrator``; este precheck só precisa
# reconhecer o marcador persistido.
V3_SCHEMA_VERSION = "3.0"

SPECIALIZED_PROCEDURE_TYPES = frozenset({ProcedureType.ECHOENDOSCOPY, ProcedureType.CPRE})

# Estados de pipeline: job 3.0 em voo (o writer ativo é o 3.0).
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


def _has_v3_marker(payload: Any) -> bool:
    """True quando o payload persistido carrega o marcador de contrato 3.0."""
    if isinstance(payload, dict):
        if payload.get("schema_version") == V3_SCHEMA_VERSION:
            return True
        return any(_has_v3_marker(value) for value in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(_has_v3_marker(item) for item in payload)
    return False


# ── Coleta por classe ────────────────────────────────────────────────────────


def _scan_events() -> tuple[list[Any], list[Any]]:
    """Uma passada somente-leitura pelos eventos: (especializados, writes 3.0)."""
    specialized: list[Any] = []
    v3: list[Any] = []
    for case_id, payload in CaseEvent.objects.values_list("case_id", "payload").iterator(chunk_size=500):
        if _references_specialized_procedure(payload):
            specialized.append(case_id)
        if _has_v3_marker(payload):
            v3.append(case_id)
    return specialized, v3


def _pipeline_job_ids() -> list[Any]:
    return list(Case.objects.filter(status__in=PIPELINE_STATUSES).values_list("case_id", flat=True))


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


def _v3_case_artifact_ids() -> list[Any]:
    return [
        case_id
        for case_id, structured_data, suggested_action in Case.objects.filter(
            Q(structured_data__isnull=False) | Q(suggested_action__isnull=False)
        )
        .values_list("case_id", "structured_data", "suggested_action")
        .iterator(chunk_size=500)
        if _has_v3_marker(structured_data) or _has_v3_marker(suggested_action)
    ]


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
    specialized_events, v3_events = _scan_events()
    checks = [
        _check(
            "pipeline_job_in_flight",
            "Caso em estado de pipeline (job 3.0 em voo)",
            _pipeline_job_ids(),
        ),
        _check(
            "specialized_case_procedure",
            f"Row CaseProcedure de {_SPECIALIZED_LABELS}",
            _specialized_row_ids(),
        ),
        _check(
            "specialized_case_event",
            f"CaseEvent com procedimento especializado ({_SPECIALIZED_LABELS})",
            specialized_events,
        ),
        _check(
            "legacy_echo_artifact",
            "Artefato derivado do sinal legado de Ecoendoscopia",
            _legacy_echo_ids(),
        ),
        _check(
            "v3_artifact_write",
            "Write 3.0 persistido (structured_data/suggested_action/evento)",
            [*_v3_case_artifact_ids(), *v3_events],
        ),
    ]
    blocking_checks = [check["code"] for check in checks if check["count"]]
    return {
        "command": COMMAND_NAME,
        "boundary": BOUNDARY,
        "status": "blocked" if blocking_checks else "allowed",
        "blocking_checks": blocking_checks,
        "checks": checks,
    }


class Command(BaseCommand):
    help = "Precheck não destrutivo do caminho de downgrade especializado (Slice 009)"

    def handle(self, *args: object, **options: object) -> None:
        report = build_report()
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["status"] == "blocked":
            raise CommandError(
                "Downgrade bloqueado: a fronteira do primeiro write 3.0 já foi cruzada "
                f"({', '.join(report['blocking_checks'])}). Caminho suportado: desligar "
                "ECHOENDOSCOPY_INTAKE_ENABLED e CPRE_INTAKE_ENABLED, manter imagem/schema 3.0, "
                "drenar jobs e corrigir para frente — sem deleção de dados e sem reverse migration."
            )
