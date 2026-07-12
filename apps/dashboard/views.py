"""Views do dashboard de monitoramento para manager e admin."""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, DateTimeField, DurationField, ExpressionWrapper, F, OuterRef, Q, QuerySet, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, Lower
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.cases.admission import (
    ADMISSION_FLOW_MAP,
    SUPPORT_FLAG_MAP,
    get_admission_flow_notice_copy,
    is_operational_notice_flow,
)
from apps.cases.models import Case, CaseAttachment, CaseEvent, CaseStatus, SupervisorSummary
from apps.cases.navigation import resolve_safe_next_url
from apps.cases.services import (
    ADMINISTRATIVE_CLOSURE_REASON_CHOICES,
    administratively_close_case,
    local_day_bounds,
)

# Reaproveita mapeamentos definidos no intake para consistência visual
from apps.intake.views import (
    EVENT_DOT_CSS,
    EVENT_LABELS,
    STATUS_CSS_CLASS,
    STATUS_LABELS,
    STEP_STATUS_INDEX,
    STEPS,
)

# ── Badge compacto para fluxos operacionais (Slice 001) ──────────────

COMPACT_ADMISSION_FLOW_LABELS: dict[str, str] = {
    "immediate": "Vinda imediata",
    "pre_icu": "Pré-UTI",
    "ward_icu_backup": "Enfermaria + retaguarda UTI",
    "pediatric_em": "EM pediátrica",
}


def _parse_iso_date(raw: str) -> date | None:
    """Tenta fazer parse de uma string ISO date (YYYY-MM-DD).

    Retorna None se a string for vazia, inválida ou mal formatada.
    """
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _period_bounds(period: str) -> tuple[datetime | None, datetime | None]:
    """Retorna (start, end) para o período de métricas.

    Valores aceitos:
        'today' → início de hoje até início de amanhã
        '7d'    → início de hoje - 6 dias até início de amanhã
        '30d'   → início de hoje - 29 dias até início de amanhã
        'all'   → (None, None) — sem filtro temporal

    Períodos personalizados:
        'custom_date:YYYY-MM-DD' → dia local específico inteiro
        'custom_range:start:end' → intervalo inclusivo local

    Valor inválido ou ausente cai para 'today'.
    """
    if period == "all":
        return None, None

    today_start, tomorrow_start = local_day_bounds()

    # Período personalizado: data específica
    if period.startswith("custom_date:"):
        parsed = _parse_iso_date(period.split(":", 1)[1])
        if parsed is not None:
            return local_day_bounds(parsed)
        # Fallback seguro para today
        return today_start, tomorrow_start

    # Período personalizado: intervalo inclusivo
    if period.startswith("custom_range:"):
        parts = period.split(":", 2)
        if len(parts) == 3:
            start_date = _parse_iso_date(parts[1])
            end_date = _parse_iso_date(parts[2])
            if start_date is not None and end_date is not None and start_date <= end_date:
                start = local_day_bounds(start_date)[0]
                # end é exclusivo: início do dia seguinte a end_date
                next_day = end_date + timedelta(days=1)
                end = local_day_bounds(next_day)[0]
                return start, end
        # Fallback seguro para today
        return today_start, tomorrow_start

    if period == "7d":
        return today_start - timedelta(days=6), tomorrow_start
    elif period == "30d":
        return today_start - timedelta(days=29), tomorrow_start
    else:
        # 'today' ou qualquer valor inválido
        return today_start, tomorrow_start


def _compute_summary(day: date | None = None, period: str | None = None) -> dict[str, int]:
    """Computa métricas resumidas do dashboard.

    Usa campos de decisão imutáveis (doctor_decision, appointment_status)
    em vez do status FSM transitório, garantindo que:
    - Casos negados e já limpos (CLEANED) ainda são contados como negados.
    - Casos aceitos pelo médico mas negados pelo scheduler são contados
      como negados, não como aceitos.
    - Aceitos e Negados são mutuamente exclusivos.

    Usa local_day_bounds() ou _period_bounds() para filtrar casos.

    Se period for fornecido ("today", "7d", "30d", "all"), as métricas
    refletem o período correspondente. day é mantido para compatibilidade
    reversa com testes existentes.
    """
    if period is not None:
        start, end = _period_bounds(period)
        if start is None:
            # all: sem filtro temporal
            period_cases = Case.objects.all()
        else:
            period_cases = Case.objects.filter(created_at__gte=start, created_at__lt=end)
    else:
        start, end = local_day_bounds(day)
        period_cases = Case.objects.filter(created_at__gte=start, created_at__lt=end)

    total_today = period_cases.count()

    # Casos administrativamente encerrados (via CASE_ADMINISTRATIVELY_CLOSED)
    admin_closed_ids = set(
        CaseEvent.objects.filter(
            event_type="CASE_ADMINISTRATIVELY_CLOSED",
            case__in=period_cases,
        )
        .values_list("case_id", flat=True)
        .distinct()
    )
    admin_closed_count = len(admin_closed_ids)

    # Excluir admin-closed de accepted e denied
    accepted = (
        period_cases.filter(doctor_decision="accept")
        .exclude(appointment_status="denied")
        .exclude(pk__in=admin_closed_ids)
        .count()
    )
    denied = (
        period_cases.filter(Q(doctor_decision="deny") | Q(appointment_status="denied"))
        .exclude(pk__in=admin_closed_ids)
        .count()
    )

    in_progress = total_today - accepted - denied - admin_closed_count

    return {
        "total_today": total_today,
        "accepted": accepted,
        "denied": denied,
        "administratively_closed": admin_closed_count,
        "in_progress": in_progress,
    }


def _compute_stage_waiting() -> dict[str, int]:
    """Contagem de casos aguardando por etapa."""
    return {
        "waiting_doctor": Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count(),
        "waiting_appt": Case.objects.filter(status=CaseStatus.WAIT_APPT).count(),
        "waiting_confirm": Case.objects.filter(status=CaseStatus.WAIT_R1_CLEANUP_THUMBS).count(),
    }


def _compute_admission_flow(day: date | None = None, period: str | None = None) -> dict[str, int]:
    """Fluxo de admissão (agendado vs imediato) para casos aceitos no período.

    Usa local_day_bounds() ou _period_bounds() para filtrar.

    Se period for fornecido, o fluxo reflete o período correspondente.
    day é mantido para compatibilidade reversa.
    """
    if period is not None:
        start, end = _period_bounds(period)
        if start is None:
            base = Case.objects.filter(doctor_decision="accept")
        else:
            base = Case.objects.filter(
                created_at__gte=start,
                created_at__lt=end,
                doctor_decision="accept",
            )
    else:
        start, end = local_day_bounds(day)
        base = Case.objects.filter(
            created_at__gte=start,
            created_at__lt=end,
            doctor_decision="accept",
        )
    return {
        "scheduled": base.filter(doctor_admission_flow="scheduled").count(),
        "immediate": base.filter(doctor_admission_flow="immediate").count(),
        "pre_icu": base.filter(doctor_admission_flow="pre_icu").count(),
        "ward_icu_backup": base.filter(doctor_admission_flow="ward_icu_backup").count(),
        "pediatric_em": base.filter(doctor_admission_flow="pediatric_em").count(),
    }


def _fmt_duration(td: timedelta | None) -> str:
    """Formata timedelta para minutos ou horas/minutos.

    Retorna:
        valor ausente    → "—"
        < 60 min         → "N min"
        60 min           → "1 h"
        65 min           → "1 h 05 min"
        1100 min         → "18 h 20 min"
        timedelta(0)     → "0 min"
    """
    if td is None:
        return "—"
    total_minutes = int(td.total_seconds() // 60)
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if minutes == 0:
        return f"{hours} h"
    return f"{hours} h {minutes:02d} min"


def _compute_average_times(day: date | None = None, period: str | None = None) -> dict[str, str]:
    """Tempos médios do fluxo.

    Calcula médias apenas quando há dados suficientes.
    Se period for fornecido ("today", "7d", "30d", "all"), filtra por
    timestamp de conclusão da etapa no período:
    - Upload → Decisão Médica: doctor_decided_at no período
    - Decisão → Agendamento: appointment_decided_at no período
    - Ciclo Total: completed_at_for_metrics no período

    day é mantido para compatibilidade reversa (filtra por created_at).
    """
    cases_qs = Case.objects.all()

    if period is not None:
        start, end = _period_bounds(period)

        # Upload → Decisão Médica: filtra por doctor_decided_at no período
        if start is None:
            decided_qs = cases_qs.exclude(doctor_decided_at=None)
        else:
            decided_qs = cases_qs.filter(doctor_decided_at__gte=start, doctor_decided_at__lt=end)
        decided_qs = decided_qs.annotate(
            decision_time=ExpressionWrapper(
                F("doctor_decided_at") - F("created_at"),
                output_field=DurationField(),
            ),
        )
        avg_decision = decided_qs.aggregate(avg=Avg("decision_time"))["avg"]

        # Decisão → Agendamento: filtra por appointment_decided_at no período
        if start is None:
            scheduled_qs = cases_qs.filter(
                appointment_decided_at__isnull=False,
                doctor_decided_at__isnull=False,
            )
        else:
            scheduled_qs = cases_qs.filter(
                appointment_decided_at__gte=start,
                appointment_decided_at__lt=end,
                doctor_decided_at__isnull=False,
            )
        scheduled_qs = scheduled_qs.annotate(
            sched_time=ExpressionWrapper(
                F("appointment_decided_at") - F("doctor_decided_at"),
                output_field=DurationField(),
            ),
        )
        avg_sched = scheduled_qs.aggregate(avg=Avg("sched_time"))["avg"]

        # Ciclo Total: filtra por completed_at_for_metrics no período
        cleanup_completed_event_ts = CaseEvent.objects.filter(
            case=OuterRef("pk"),
            event_type="CLEANUP_COMPLETED",
        ).values("timestamp")[:1]
        completed_qs = cases_qs.annotate(
            completed_at_for_metrics=Coalesce(
                "cleanup_completed_at",
                Subquery(cleanup_completed_event_ts),
                output_field=DateTimeField(),
            )
        ).exclude(completed_at_for_metrics=None)
        if start is not None:
            completed_qs = completed_qs.filter(
                completed_at_for_metrics__gte=start,
                completed_at_for_metrics__lt=end,
            )
        avg_cycle = completed_qs.annotate(
            cycle_time=ExpressionWrapper(
                F("completed_at_for_metrics") - F("created_at"),
                output_field=DurationField(),
            ),
        ).aggregate(avg=Avg("cycle_time"))["avg"]
    else:
        if day is not None:
            start, end = local_day_bounds(day)
            cases_qs = cases_qs.filter(created_at__gte=start, created_at__lt=end)

        # Upload → Decisão Médica
        decided_qs = cases_qs.exclude(doctor_decided_at=None).annotate(
            decision_time=ExpressionWrapper(
                F("doctor_decided_at") - F("created_at"),
                output_field=DurationField(),
            ),
        )
        avg_decision = decided_qs.aggregate(avg=Avg("decision_time"))["avg"]

        # Decisão → Agendamento
        scheduled_qs = cases_qs.filter(
            appointment_decided_at__isnull=False,
            doctor_decided_at__isnull=False,
        ).annotate(
            sched_time=ExpressionWrapper(
                F("appointment_decided_at") - F("doctor_decided_at"),
                output_field=DurationField(),
            ),
        )
        avg_sched = scheduled_qs.aggregate(avg=Avg("sched_time"))["avg"]

        # Ciclo Total
        cleanup_completed_event_ts = CaseEvent.objects.filter(
            case=OuterRef("pk"),
            event_type="CLEANUP_COMPLETED",
        ).values("timestamp")[:1]
        completed_qs = cases_qs.annotate(
            completed_at_for_metrics=Coalesce(
                "cleanup_completed_at",
                Subquery(cleanup_completed_event_ts),
                output_field=DateTimeField(),
            )
        ).exclude(completed_at_for_metrics=None)
        avg_cycle = completed_qs.annotate(
            cycle_time=ExpressionWrapper(
                F("completed_at_for_metrics") - F("created_at"),
                output_field=DurationField(),
            ),
        ).aggregate(avg=Avg("cycle_time"))["avg"]

    return {
        "upload_to_decision": _fmt_duration(avg_decision),
        "decision_to_schedule": _fmt_duration(avg_sched),
        "total_cycle": _fmt_duration(avg_cycle),
    }


def _has_admin_close_event(case: Case) -> bool:
    """Verifica se o caso tem evento de encerramento administrativo."""
    return case.events.filter(event_type="CASE_ADMINISTRATIVELY_CLOSED").exists()


def _compute_result(case: Case) -> tuple[str, str]:
    """Computa label e classe CSS (Bootstrap badge) do resultado final.

    Prioridade:
    1. Encerramento administrativo (tem precedência sobre todos)
    2. Scope-gated manual review
    3. Doctor denied
    4. Appointment denied
    5. Accepted scheduled confirmed
    6. Immediate admission
    7. Failed
    8. Awaiting scheduler
    9. In progress step
    """
    # Administrative closure has top priority
    if _has_admin_close_event(case):
        return ("🔒 Encerrado administrativamente", "bg-secondary")

    # Scope-gated manual review
    if (
        case.suggested_action
        and isinstance(case.suggested_action, dict)
        and case.suggested_action.get("decision") == "manual_review_required"
    ):
        return ("⚠ Revisão Manual", "bg-warning text-dark")

    # Doctor denied
    if case.doctor_decision == "deny":
        return ("✗ Negado pelo Médico", "bg-danger")

    # Appointment cancelled after post-schedule intercurrence
    if case.appointment_status == "cancelled":
        return ("↯ Agendamento cancelado após intercorrência", "bg-warning text-dark")

    # Appointment denied
    if case.appointment_status == "denied":
        return ("✗ Agendamento Negado", "bg-danger")

    # Accepted — scheduled confirmed
    if case.doctor_decision == "accept" and case.appointment_status == "confirmed":
        return ("✓ Agendamento Confirmado", "bg-success")

    # Accepted — operational notice flow without scheduling
    if case.doctor_decision == "accept" and is_operational_notice_flow(case.doctor_admission_flow):
        # Usa label compacto para badges da lista (evita overflow em mobile)
        flow = case.doctor_admission_flow
        compact_label = COMPACT_ADMISSION_FLOW_LABELS.get(flow, ADMISSION_FLOW_MAP.get(flow, flow))
        return (f"✓ {compact_label}", "bg-success")

    # Failed
    if case.status == CaseStatus.FAILED:
        return ("✗ Falha no Processamento", "bg-danger")

    # Accepted by doctor — awaiting scheduler
    if case.doctor_decision == "accept":
        return ("⏳ Aguardando Agendamento", "bg-secondary")

    # In progress — show current pipeline step
    step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    step_label = STEPS[step_idx]["label"] if step_idx < len(STEPS) else "..."
    return (f"⏳ {step_label}", "bg-secondary")


# ── Attention filter constants ─────────────────────────────────────────

ATTENTION_PROCESSING_STUCK_AFTER = timedelta(minutes=30)
ATTENTION_WAITING_STUCK_AFTER = timedelta(hours=48)

ATTENTION_PROCESSING_STATUSES: tuple[str, ...] = (
    CaseStatus.NEW,
    CaseStatus.R1_ACK_PROCESSING,
    CaseStatus.EXTRACTING,
    CaseStatus.LLM_STRUCT,
    CaseStatus.LLM_SUGGEST,
    CaseStatus.R2_POST_WIDGET,
    CaseStatus.DOCTOR_ACCEPTED,
    CaseStatus.DOCTOR_DENIED,
    CaseStatus.R3_POST_REQUEST,
    CaseStatus.APPT_CONFIRMED,
    CaseStatus.APPT_DENIED,
    CaseStatus.R1_FINAL_REPLY_POSTED,
    CaseStatus.CLEANUP_RUNNING,
)

ATTENTION_WAITING_STATUSES: tuple[str, ...] = (
    CaseStatus.WAIT_DOCTOR,
    CaseStatus.WAIT_APPT,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS,
)


def _attention_q(now: datetime) -> Q:
    """Retorna Q object com os critérios de atenção para filtrar casos suspeitos."""
    processing_cutoff = now - ATTENTION_PROCESSING_STUCK_AFTER
    waiting_cutoff = now - ATTENTION_WAITING_STUCK_AFTER
    return (
        Q(status=CaseStatus.FAILED)
        | Q(locked_by__isnull=False, locked_until__isnull=False, locked_until__lte=now)
        | Q(status__in=ATTENTION_PROCESSING_STATUSES, updated_at__lte=processing_cutoff)
        | Q(status__in=ATTENTION_WAITING_STATUSES, updated_at__lte=waiting_cutoff)
    )


def _get_attention_reason(case: Case, *, now: datetime | None = None) -> str:
    """Retorna motivo compacto de atenção para exibição no card do dashboard.

    Retorna string vazia se o caso não necessita atenção.
    """
    if now is None:
        now = timezone.now()

    # Falha sempre é motivo de atenção
    if case.status == CaseStatus.FAILED:
        return "Falha no processamento"

    # Lock expirado
    if case.locked_by_id is not None and case.locked_until is not None and case.locked_until <= now:
        return "Lock expirado"

    # Processamento parado há mais de 30 min
    if case.status in ATTENTION_PROCESSING_STATUSES:
        cutoff = now - ATTENTION_PROCESSING_STUCK_AFTER
        if case.updated_at <= cutoff:
            return "Processamento parado há mais de 30 min"

    # Espera humana há mais de 48h
    if case.status in ATTENTION_WAITING_STATUSES:
        cutoff = now - ATTENTION_WAITING_STUCK_AFTER
        if case.updated_at <= cutoff:
            return "Aguardando ação humana há mais de 48 h"

    return ""


def _compute_next_step(case: Case) -> tuple[str, str] | None:
    """Computa label e CSS do próximo passo operacional pendente.

    Retorna (label, css) ou None se não há pendência relevante.
    Baseado deterministicamente no status do caso, sem novo campo persistido.
    """
    # WAIT_DOCTOR → Pendente: médico
    if case.status == CaseStatus.WAIT_DOCTOR:
        return ("Pendente: médico", "bg-info text-dark")

    # DOCTOR_ACCEPTED / R3_POST_REQUEST → Pendente: agendador
    if case.status in (CaseStatus.DOCTOR_ACCEPTED, CaseStatus.R3_POST_REQUEST):
        return ("Pendente: agendador", "bg-info text-dark")

    # WAIT_APPT — se fluxo agendado, Pendente: agendador
    if case.status == CaseStatus.WAIT_APPT:
        if case.doctor_admission_flow == "scheduled":
            return ("Pendente: agendador", "bg-info text-dark")
        # Fluxo operacional sem agendamento → NIR
        return ("Pendente: NIR", "bg-info text-dark")

    # Estados que aguardam ação do NIR
    if case.status in (
        CaseStatus.APPT_CONFIRMED,
        CaseStatus.APPT_DENIED,
        CaseStatus.R1_FINAL_REPLY_POSTED,
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    ):
        return ("Pendente: NIR", "bg-info text-dark")

    # Fluxo operacional (sem agendamento) aceito e antes de cleanup → NIR
    if case.doctor_decision == "accept" and is_operational_notice_flow(case.doctor_admission_flow):
        if case.status not in (CaseStatus.CLEANUP_RUNNING, CaseStatus.CLEANED):
            return ("Pendente: NIR", "bg-info text-dark")

    # FAILED → Pendente: suporte
    if case.status == CaseStatus.FAILED:
        return ("Pendente: suporte", "bg-warning text-dark")

    # CLEANUP_RUNNING → Encerrando
    if case.status == CaseStatus.CLEANUP_RUNNING:
        return ("Encerrando", "bg-secondary")

    # CLEANED → sem sub-badge (ou Encerrado, conforme preferência)
    return None


def _enrich_case(case: Case, *, now: datetime | None = None, attention_filter: bool = False) -> dict[str, Any]:
    """Enriquece um Case com dados de apresentação para cards do dashboard."""
    if now is None:
        now = timezone.now()

    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    result_label, result_css = _compute_result(case)

    attention_reason = _get_attention_reason(case, now=now) if attention_filter else ""

    next_step = _compute_next_step(case)
    next_step_label = next_step[0] if next_step else ""
    next_step_css = next_step[1] if next_step else ""

    return {
        "case": case,
        "patient_name": patient_name,
        "patient_age": case.patient_age,
        "patient_gender": case.patient_gender,
        "result_label": result_label,
        "result_css": result_css,
        "origin_unit": case.get_origin_unit_display(compact=True),
        "attention_reason": attention_reason,
        "next_step_label": next_step_label,
        "next_step_css": next_step_css,
    }


def _apply_case_search(cases_qs: QuerySet[Case], search_term: str) -> QuerySet[Case]:
    """Aplica busca server-side alinhada aos índices GIN trigram.

    Filtra por nome do paciente (structured_data -> patient -> name) e por
    agency_record_number. As expressões ``lower(...)`` casam com os índices
    da migration ``cases.0011`` (``cases_case_arn_trgm_idx`` e
    ``cases_case_patient_name_trgm_idx``), permitindo Bitmap Index Scan em
    vez de seq scan em tabelas grandes.

    Observação: ``__icontains`` seria compilado como ``UPPER(col) LIKE
    UPPER(p)``, expressão incompatível com o índice ``lower(col)`` e que
    portanto não seria acelerada por ele.
    """
    search_lower = search_term.lower()
    patient_name = KeyTextTransform("name", "structured_data__patient")
    return cases_qs.annotate(
        search_arn=Lower("agency_record_number"),
        search_patient_name=Lower(patient_name),
    ).filter(Q(search_arn__contains=search_lower) | Q(search_patient_name__contains=search_lower))


def _dashboard_case_list_context(request: HttpRequest) -> dict[str, Any]:
    """Monta o contexto para a lista de casos do dashboard.

    Extraído para ser compartilhado entre a renderização completa e a
    renderização parcial (X-ATS-Partial: case-list).
    """
    now = timezone.now()

    # Filtro de atenção
    attention_filter: bool = request.GET.get("attention") == "1"

    # Busca server-side
    search_raw = request.GET.get("search", "")
    search_term = search_raw.strip()[:100]
    search_min_chars_help = False

    # Tabela de casos — todos, sem filtro de usuario
    cases_qs = Case.objects.select_related("created_by").order_by("-created_at")

    # Filtro de atenção (exclui CLEANED, aplica critérios de atenção)
    if attention_filter:
        cases_qs = cases_qs.exclude(status=CaseStatus.CLEANED).filter(_attention_q(now))

    # Busca: só filtra com 3+ caracteres. A expressão usada no helper
    # _apply_case_search é alinhada aos índices trigram para evitar seq scan.
    if len(search_term) >= 3:
        cases_qs = _apply_case_search(cases_qs, search_term)
    elif len(search_term) in (1, 2):
        search_min_chars_help = True

    # Filtros
    status_filter = request.GET.get("status", "")
    if status_filter:
        cases_qs = cases_qs.filter(status=status_filter)

    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if date_from:
        cases_qs = cases_qs.filter(created_at__date__gte=date_from)
    if date_to:
        cases_qs = cases_qs.filter(created_at__date__lte=date_to)

    # Contador de atenção (total de casos suspeitos, sem paginação)
    attention_count: int | None = None
    if attention_filter:
        attention_count = cases_qs.count()
    else:
        attention_count = Case.objects.exclude(status=CaseStatus.CLEANED).filter(_attention_q(now)).count()

    # Paginação
    paginator = Paginator(cases_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    enriched_cases = [_enrich_case(c, now=now, attention_filter=attention_filter) for c in page_obj]

    # Período das métricas — preservado nos links de filtro/paginação
    # Aceita presets e períodos personalizados
    raw_metrics_period = request.GET.get("metrics_period", "")
    valid_periods = {"today", "7d", "30d", "all", "custom_date", "custom_range"}
    if raw_metrics_period not in valid_periods:
        metrics_period = ""
    else:
        metrics_period = raw_metrics_period

    # Campos personalizados preservados
    metrics_date = request.GET.get("metrics_date", "")
    metrics_start = request.GET.get("metrics_start", "")
    metrics_end = request.GET.get("metrics_end", "")

    return {
        "cases": enriched_cases,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "date_from": date_from,
        "date_to": date_to,
        "search": search_raw,
        "search_term": search_term,
        "search_min_chars_help": search_min_chars_help,
        "attention_filter": attention_filter,
        "attention_count": attention_count,
        "metrics_period": metrics_period,
        "metrics_date": metrics_date,
        "metrics_start": metrics_start,
        "metrics_end": metrics_end,
    }


@login_required
@role_required("manager", "admin")
def dashboard_index(request: HttpRequest) -> HttpResponse:
    """Dashboard com métricas e tabela de todos os casos.

    Se o header ``X-ATS-Partial: case-list`` estiver presente, retorna
    apenas o partial ``dashboard/_case_list.html`` para busca dinâmica via
    Vanilla JS, **sem computar as métricas** (resposta leve). Caso
    contrário, renderiza a página completa.
    """
    # Busca dinâmica: retorna somente a lista de casos. O partial depende
    # apenas do contexto da lista, então computar summary/fluxo/tempos
    # médios seria trabalho descartado a cada keystroke (debounce).
    if request.headers.get("X-ATS-Partial") == "case-list":
        return render(
            request,
            "dashboard/_case_list.html",
            _dashboard_case_list_context(request),
        )

    # Período das métricas — usa query string metrics_period, padrão hoje
    raw_metrics_period = request.GET.get("metrics_period", "")

    # Parâmetros personalizados
    raw_metrics_date = request.GET.get("metrics_date", "")
    raw_metrics_start = request.GET.get("metrics_start", "")
    raw_metrics_end = request.GET.get("metrics_end", "")

    # Valida e resolve o período
    metrics_period_error = ""

    if raw_metrics_period == "custom_date":
        parsed_date = _parse_iso_date(raw_metrics_date)
        if parsed_date is None:
            metrics_period = "today"
            metrics_period_error = "Período personalizado inválido. Exibindo métricas de hoje."
        else:
            metrics_period = f"custom_date:{raw_metrics_date}"
    elif raw_metrics_period == "custom_range":
        parsed_start = _parse_iso_date(raw_metrics_start)
        parsed_end = _parse_iso_date(raw_metrics_end)
        if parsed_start is None or parsed_end is None or parsed_start > parsed_end:
            metrics_period = "today"
            metrics_period_error = "Período personalizado inválido. Exibindo métricas de hoje."
        else:
            metrics_period = f"custom_range:{raw_metrics_start}:{raw_metrics_end}"
    elif raw_metrics_period in {"today", "7d", "30d", "all"}:
        metrics_period = raw_metrics_period
    else:
        metrics_period = "today"

    summary = _compute_summary(period=metrics_period)
    stage_waiting = _compute_stage_waiting()
    admission_flow = _compute_admission_flow(period=metrics_period)
    avg_times = _compute_average_times(period=metrics_period)

    # Labels
    period_labels = {
        "today": "Total Hoje",
        "7d": "Total 7 dias",
        "30d": "Total 30 dias",
        "all": "Total geral",
    }
    period_labels_display = {
        "today": "Métricas de hoje",
        "7d": "Métricas dos últimos 7 dias",
        "30d": "Métricas dos últimos 30 dias",
        "all": "Métricas de todo o histórico",
    }

    # Label para exibição do período ativo
    # Usa metrics_period (já resolvido) como base para o display,
    # para que fallbacks com erro mostrem o label correto (e.g. "Métricas de hoje")
    resolved_for_display = metrics_period
    if metrics_period.startswith("custom_date:"):
        resolved_for_display = "custom_date"
    elif metrics_period.startswith("custom_range:"):
        resolved_for_display = "custom_range"
    elif metrics_period not in period_labels:
        resolved_for_display = "today"
    metrics_period_label = period_labels_display.get(resolved_for_display, "Métricas de hoje")
    total_label = period_labels.get(resolved_for_display, "Total Hoje")

    # Labels personalizados (apenas se não houve erro)
    if not metrics_period_error:
        if metrics_period.startswith("custom_date:"):
            parsed_date = _parse_iso_date(metrics_period.split(":", 1)[1])
            if parsed_date is not None:
                date_formatted = parsed_date.strftime("%d/%m/%Y")
                metrics_period_label = f"Métricas de {date_formatted}"
                total_label = f"Total {date_formatted}"
        elif metrics_period.startswith("custom_range:"):
            parts = metrics_period.split(":", 2)
            if len(parts) == 3:
                parsed_start = _parse_iso_date(parts[1])
                parsed_end = _parse_iso_date(parts[2])
                if parsed_start is not None and parsed_end is not None:
                    start_formatted = parsed_start.strftime("%d/%m/%Y")
                    end_formatted = parsed_end.strftime("%d/%m/%Y")
                    metrics_period_label = f"Métricas de {start_formatted} a {end_formatted}"
                    total_label = "Total período"

    # Último resumo para o card no dashboard
    latest_summary = SupervisorSummary.objects.order_by("-window_end").first()

    # Contexto da lista de casos
    case_list_context = _dashboard_case_list_context(request)

    return render(
        request,
        "dashboard/index.html",
        {
            "summary": summary,
            "stage_waiting": stage_waiting,
            "admission_flow": admission_flow,
            "avg_times": avg_times,
            "latest_summary": latest_summary,
            "total_label": total_label,
            "metrics_period_label": metrics_period_label,
            "metrics_period_error": metrics_period_error,
            "status_choices": CaseStatus.choices,
            "STATUS_LABELS": STATUS_LABELS,
            **case_list_context,
        },
    )


@login_required
@role_required("manager", "admin")
@require_POST
def dashboard_administrative_close(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Encerra um caso administrativamente.

    Apenas manager/admin podem encerrar. Exige reason_code e reason_text.
    """
    case = get_object_or_404(Case, case_id=case_id)

    reason_code = request.POST.get("reason_code", "")
    reason_text = request.POST.get("reason_text", "")
    active_role = request.session.get("active_role", "")

    try:
        administratively_close_case(
            case=case,
            user=request.user,
            reason_code=reason_code,
            reason_text=reason_text,
            active_role=active_role,
        )
        messages.success(
            request,
            "Caso encerrado administrativamente. O caso foi removido das filas operacionais e permanece na auditoria.",
        )
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dashboard:case_detail", case_id=case.case_id)


@login_required
@role_required("manager", "admin")
@xframe_options_sameorigin
def dashboard_case_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve o PDF do caso para manager/admin (dashboard gerencial).

    Diferente da rota NIR (intake:serve_pdf), esta rota:
    - Aceita casos em qualquer status, incluindo CLEANED.
    - É restrita a manager/admin.
    - Retorna 404 quando não há pdf_file.
    """
    case = get_object_or_404(Case, case_id=case_id)
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")
    response = FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Cache-Control"] = "no-store"
    return response


def _get_dashboard_attachment_or_404(case_id: uuid.UUID, attachment_id: uuid.UUID) -> CaseAttachment:
    """Retorna anexo ativo acessível pelo dashboard gerencial."""
    return get_object_or_404(
        CaseAttachment,
        case__case_id=case_id,
        attachment_id=attachment_id,
        is_suppressed=False,
    )


@login_required
@role_required("manager", "admin")
@xframe_options_sameorigin
def dashboard_case_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """Serve anexo clínico para manager/admin pelo dashboard."""
    attachment = _get_dashboard_attachment_or_404(case_id, attachment_id)
    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@role_required("manager", "admin")
def dashboard_attachment_pdf_viewer(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponse:
    """Renderiza viewer mobile interno para anexo PDF no dashboard."""
    attachment = _get_dashboard_attachment_or_404(case_id, attachment_id)
    if attachment.content_type != "application/pdf":
        raise Http404("Anexo não é um PDF.")

    case = attachment.case
    back_url = resolve_safe_next_url(request, reverse("dashboard:case_detail", args=[case.case_id]))
    pdf_url = reverse("dashboard:case_attachment", args=[case.case_id, attachment.attachment_id])

    return render(
        request,
        "pdf_viewer/mobile_pdf_viewer.html",
        {
            "viewer_title": "Anexo PDF",
            "case": case,
            "pdf_url": pdf_url,
            "back_url": back_url,
            "back_label": "← Voltar ao caso",
            "fallback_pdf_url": pdf_url,
            "show_dashboard_nav": True,
        },
    )


@login_required
@role_required("manager", "admin")
def dashboard_attachment_image_viewer(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponse:
    """Renderiza viewer mobile interno para anexo de imagem no dashboard."""
    attachment = _get_dashboard_attachment_or_404(case_id, attachment_id)
    if not attachment.content_type.startswith("image/"):
        raise Http404("Anexo não é uma imagem.")

    case = attachment.case
    back_url = resolve_safe_next_url(request, reverse("dashboard:case_detail", args=[case.case_id]))
    image_url = reverse("dashboard:case_attachment", args=[case.case_id, attachment.attachment_id])

    return render(
        request,
        "image_viewer/mobile_image_viewer.html",
        {
            "viewer_title": "Anexo de imagem",
            "case": case,
            "attachment": attachment,
            "image_url": image_url,
            "fallback_image_url": image_url,
            "back_url": back_url,
            "back_label": "← Voltar ao caso",
            "show_dashboard_nav": True,
        },
    )


@login_required
@role_required("manager", "admin")
def dashboard_case_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhe de qualquer caso (admin) — sem botão 'Confirmar Recebimento'."""
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    events = case.events.all()

    current_step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    steps = STEPS
    terminal_without_scheduling = case.status in (
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        CaseStatus.CLEANED,
    ) and (case.doctor_decision == "deny" or is_operational_notice_flow(case.doctor_admission_flow))
    is_doctor_denied_final = terminal_without_scheduling and case.doctor_decision == "deny"
    is_operational_notice_final = terminal_without_scheduling and is_operational_notice_flow(case.doctor_admission_flow)
    if terminal_without_scheduling:
        steps = [step for step in STEPS if step["label"] != "Agendamento"]
        current_step_idx = len(steps) - 1

    enriched_events = []
    for e in events:
        enriched_events.append(
            {
                "event": e,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
            }
        )

    result_info: dict[str, object] | None = None

    # Administrative closure has top priority (before any other result)
    if _has_admin_close_event(case):
        # Busca o evento administrativo para extrair payload
        admin_event = case.events.filter(event_type="CASE_ADMINISTRATIVELY_CLOSED").first()
        reason_text = ""
        reason_code = ""
        previous_status = ""
        if admin_event and admin_event.payload:
            reason_text = admin_event.payload.get("reason_text", "")
            reason_code = admin_event.payload.get("reason_code", "")
            previous_status = admin_event.payload.get("previous_status", "")
        result_info = {
            "type": "administratively_closed",
            "reason_text": reason_text,
            "reason_code": reason_code,
            "previous_status": previous_status,
        }

    terminal_with_result = case.status in (
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        CaseStatus.CLEANED,
    )
    # Scope-gated manual review takes priority for WAIT_R1_CLEANUP_THUMBS
    is_scope_gated = (
        case.suggested_action
        and isinstance(case.suggested_action, dict)
        and case.suggested_action.get("decision") == "manual_review_required"
    )
    if result_info is None and is_scope_gated:
        reason_code = case.suggested_action.get("reason_code", "") if isinstance(case.suggested_action, dict) else ""
        reason_text = case.suggested_action.get("reason_text", "") if isinstance(case.suggested_action, dict) else ""
        result_info = {
            "type": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": reason_text,
        }
    elif result_info is None and (is_doctor_denied_final or case.status == CaseStatus.DOCTOR_DENIED):
        result_info = {
            "type": "doctor_denied",
            "reason": case.doctor_reason,
            "doctor_display": case.doctor_display,
        }
    elif result_info is None and is_operational_notice_final:
        copy = get_admission_flow_notice_copy(case.doctor_admission_flow)
        result_info = {
            "type": "accepted_immediate",
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "doctor_display": case.doctor_display,
            "badge": copy["nir_badge"],
            "body": copy["nir_body"],
        }
    elif result_info is None and case.appointment_status == "cancelled":
        result_info = {
            "type": "appt_cancelled",
            "appointment_at": case.appointment_at,
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif result_info is None and (
        case.status == CaseStatus.APPT_DENIED or (terminal_with_result and case.appointment_status == "denied")
    ):
        result_info = {
            "type": "appt_denied",
            "reason": case.appointment_reason,
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif result_info is None and (case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result):
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
        }
    elif result_info is None and case.status == CaseStatus.FAILED:
        result_info = {"type": "failed"}

    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    origin_unit = case.get_origin_unit_display(compact=False)

    return render(
        request,
        "intake/case_detail.html",
        {
            "case": case,
            "events": enriched_events,
            "steps": steps,
            "current_step_idx": current_step_idx,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "can_confirm_receipt": False,
            "result_info": result_info,
            "patient_name": patient_name,
            "origin_unit": origin_unit,
            "can_administratively_close": case.status != CaseStatus.CLEANED,
            "administrative_close_url": reverse("dashboard:administrative_close", args=[case.case_id]),
            "administrative_close_reason_choices": ADMINISTRATIVE_CLOSURE_REASON_CHOICES,
            # Parametrização para template compartilhado
            "show_dashboard_nav": True,
            "show_intake_nav": False,
            "back_url": reverse("dashboard:index"),
            "back_label": "← Voltar ao dashboard",
            "pdf_url": reverse("dashboard:case_pdf", args=[case.case_id]),
            "attachments": active_attachments,
            "mobile_pdf_viewer_url": reverse("dashboard:pdf_viewer", args=[case.case_id])
            + f"?next={reverse('dashboard:case_detail', args=[case.case_id])}",
        },
    )


@login_required
@role_required("manager", "admin")
def dashboard_pdf_viewer(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Renderiza o viewer PDF mobile interno para dashboard gerencial.

    Exige login e papel ativo 'manager' ou 'admin'.
    Usa dashboard:case_pdf como fonte protegida.
    """
    case = get_object_or_404(Case, pk=case_id)
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    back_url = resolve_safe_next_url(request, reverse("dashboard:case_detail", args=[case.case_id]))

    pdf_url = reverse("dashboard:case_pdf", args=[case.case_id])

    return render(
        request,
        "pdf_viewer/mobile_pdf_viewer.html",
        {
            "viewer_title": "PDF Original",
            "case": case,
            "pdf_url": pdf_url,
            "back_url": back_url,
            "back_label": "← Voltar ao caso",
            "fallback_pdf_url": pdf_url,
            "show_dashboard_nav": True,
        },
    )


@login_required
@role_required("manager", "admin")
def dashboard_summaries(request: HttpRequest) -> HttpResponse:
    """Página com histórico paginado de resumos de supervisão."""
    summaries_qs = SupervisorSummary.objects.order_by("-window_end")
    paginator = Paginator(summaries_qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "dashboard/summaries.html",
        {
            "page_obj": page_obj,
            "summaries": page_obj,
        },
    )
