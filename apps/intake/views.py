"""Views do app intake."""

import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.admission import (
    ADMISSION_FLOW_MAP,
    COMPACT_ADMISSION_FLOW_LABELS,
    SUPPORT_FLAG_MAP,
    get_admission_flow_notice_copy,
    is_operational_notice_flow,
    is_scheduled_admission_flow,
)
from apps.cases.models import (
    EDA_COLONOSCOPY,
    Case,
    CaseAttachment,
    CaseProcedure,
    CaseStatus,
    DetectionStatus,
    DoctorDisposition,
    ProcedureType,
)
from apps.cases.navigation import resolve_safe_next_url
from apps.cases.priority_signals import build_priority_signal_badges
from apps.cases.procedures import (
    format_procedure_selection,
    get_approved_procedure_types,
    get_declared_procedure_types,
    get_detected_procedure_types,
    selection_key,
)
from apps.cases.services import (
    CASE_COMMUNICATION_MAX_LENGTH,
    ELIGIBLE_SUPPLEMENTAL_STATUSES,
    CaseCommunicationError,
    add_supplemental_case_attachment,
    claim_case_lock,
    compute_lock_display,
    expire_stale_locks_for_statuses,
    get_post_schedule_issue_reason_label,
    post_case_communication_message,
    suppress_case_attachment,
)
from apps.cases.services import (
    release_case_lock as release_lock_service,
)
from apps.cases.services import (
    renew_case_lock as renew_lock_service,
)

from .forms import CaseUploadForm
from .services import (
    EXAM_TYPE_CORRECTION_REASONS,
    EnqueueAfterCommitError,
    confirm_case_receipt,
    correct_case_exam_type,
    ensure_exam_type_allowed,
    is_colonoscopy_intake_enabled,
    is_exam_type_correction_eligible,
    process_uploaded_files,
    validate_attachment_file,
)

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})


def _declared_badge(case: Case) -> dict[str, str]:
    """Label/chave do badge declarado, projetados da projeção na view.

    Templates NUNCA consultam rows ou o campo legado: recebem o label
    textual (R6) e a chave de CSS derivados do conjunto declarado.
    """
    types = get_declared_procedure_types(case)
    if types:
        return {
            "declared_label": format_procedure_selection(types),
            "declared_type_key": selection_key(types),
        }
    # Apresentação fail-closed (Slice 008 review fix F3): caso sem rows
    # declaradas recebe label neutro/chave vazia — nunca default EDA/
    # Colonoscopia/combinado da ponte.
    return {"declared_label": "—", "declared_type_key": ""}


# Dimensões aceitas nos filtros NIR (R5/D13): Todos + EDA/Colonoscopia/Combinado,
# SEMPRE pelo conjunto DECLARADO (nunca detected/approved). ``eda_colonoscopy``
# é a seleção combinada; o valor inválido cai para all.
_NIR_DECLARED_DIMENSIONS: frozenset[str] = frozenset(
    {"all", ProcedureType.EDA, ProcedureType.COLONOSCOPY, EDA_COLONOSCOPY}
)


def _filter_by_declared_dimension(qs: models.QuerySet[Case], dimension: str) -> models.QuerySet[Case]:
    """Filtra um queryset pela dimensão DECLARADA (R5/D13, Slice 008).

    Usa subqueries ``Exists`` explícitas para evitar a semântica ambígua de
    ``exclude`` sobre relação múltipla (que divide condições em dois EXISTS
    separados). Buckets EXCLUSIVOS: ``eda``/``colonoscopy`` exigem a row
    declarada do tipo e a AUSÊNCIA da row declarada do outro; combinado exige
    as duas rows declaradas. NUNCA consulta detected/approved (D13) e, desde o
    Slice 008, NUNCA consulta a ponte ``Case.exam_type``: um caso sem rows
    declaradas (legado/inválido) é fail-closed — não aparece em bucket
    específico e não recebe default EDA. Apenas "Todos" (sem filtro) o lista.
    """
    declared_eda = models.Exists(
        CaseProcedure.objects.filter(
            case_id=models.OuterRef("pk"),
            procedure_type=ProcedureType.EDA,
            declared_by_nir=True,
        )
    )
    declared_colon = models.Exists(
        CaseProcedure.objects.filter(
            case_id=models.OuterRef("pk"),
            procedure_type=ProcedureType.COLONOSCOPY,
            declared_by_nir=True,
        )
    )
    qs = qs.annotate(
        _decl_eda=declared_eda,
        _decl_colon=declared_colon,
    )
    if dimension == EDA_COLONOSCOPY:
        return qs.filter(_decl_eda=True, _decl_colon=True)
    if dimension == ProcedureType.EDA:
        return qs.filter(_decl_eda=True, _decl_colon=False)
    return qs.filter(_decl_colon=True, _decl_eda=False)


def _procedure_origin_text(*, is_declared: bool, is_detected: bool, is_approved: bool) -> str:
    """Origem textual de um componente para a resposta comparativa (R6)."""
    if is_declared and is_detected:
        return "Declarado e detectado"
    if is_declared:
        return "Declarado, não detectado na análise"
    if is_detected:
        return "Detectado na análise"
    if is_approved:
        return "Incluído pelo médico"
    return "Não declarado nem detectado"


def _procedure_comparison(case: Case) -> dict[str, object]:
    """Snapshot declarado→detectado→autorizado com razões por componente (R6/D12).

    Projetado na view: o template recebe labels prontos e nunca consulta rows.
    A declaração original NUNCA é escondida após upgrade automático; a
    comparação fica visível assim que a detecção existe, inclusive enquanto o
    caso segue para ``WAIT_DOCTOR``. ``added_by_doctor`` = aprovado sem ter
    sido detectado (inclusão médica, razão própria exigida — D9).
    """
    declared = get_declared_procedure_types(case)
    detected = get_detected_procedure_types(case)
    approved = get_approved_procedure_types(case)

    rows_by_type = {p.procedure_type: p for p in case.procedures.all()}
    per_procedure: list[dict[str, object]] = []
    for procedure_type in (ProcedureType.EDA, ProcedureType.COLONOSCOPY):
        row = rows_by_type.get(procedure_type)
        is_declared = procedure_type in declared
        is_detected = procedure_type in detected
        is_approved = procedure_type in approved
        is_denied = bool(row and row.doctor_disposition == DoctorDisposition.DENIED)
        if not is_declared and not is_detected and not is_approved and not is_denied:
            continue
        per_procedure.append(
            {
                "label": ProcedureType(procedure_type).label,
                "origin": _procedure_origin_text(
                    is_declared=is_declared,
                    is_detected=is_detected,
                    is_approved=is_approved,
                ),
                "status": "Aprovado" if is_approved else ("Negado" if is_denied else "Pendente"),
                "status_css": "text-success fw-semibold"
                if is_approved
                else ("text-danger fw-semibold" if is_denied else "text-muted"),
                "reason": (row.doctor_reason if row else "") or "",
            }
        )

    has_detection = bool(detected) or any(p.detection_status != DetectionStatus.PENDING for p in case.procedures.all())
    has_decision = bool(approved) or any(
        p.doctor_disposition != DoctorDisposition.PENDING for p in case.procedures.all()
    )
    return {
        "declared_label": format_procedure_selection(declared) if declared else "—",
        "declared_key": selection_key(declared),
        "detected_label": format_procedure_selection(detected) if detected else "—",
        "detected_key": selection_key(detected),
        "authorized_label": format_procedure_selection(approved) if approved else "",
        "authorized_key": selection_key(approved),
        "has_detection": has_detection,
        "has_decision": has_decision,
        "per_procedure": per_procedure,
        "is_paired": len(approved) == 2,
        "paired_label": "EDA + Colonoscopia · Agendamento casado",
    }


STATUS_LABELS: dict[str, str] = {
    "NEW": "Novo",
    "R1_ACK_PROCESSING": "Processando",
    "EXTRACTING": "Extraindo dados",
    "LLM_STRUCT": "Análise Automática (estrutura)",
    "LLM_SUGGEST": "Análise Automática (sugestão)",
    "R2_POST_WIDGET": "Preparando avaliação",
    "WAIT_DOCTOR": "Aguardando médico",
    "DOCTOR_ACCEPTED": "Aceito pelo médico",
    "DOCTOR_DENIED": "Recusado pelo médico",
    "R3_POST_REQUEST": "Preparando agendamento",
    "WAIT_APPT": "Aguardando agendamento",
    "APPT_CONFIRMED": "Agendamento confirmado",
    "APPT_DENIED": "Agendamento negado",
    "FAILED": "Falha no processamento",
    "R1_FINAL_REPLY_POSTED": "Resultado enviado",
    "WAIT_R1_CLEANUP_THUMBS": "Aguardando confirmação",
    "CLEANUP_RUNNING": "Em limpeza",
    "CLEANED": "Concluído",
}

STATUS_CSS_CLASS: dict[str, str] = {
    "NEW": "status-pending",
    "R1_ACK_PROCESSING": "status-progress",
    "EXTRACTING": "status-progress",
    "LLM_STRUCT": "status-progress",
    "LLM_SUGGEST": "status-progress",
    "R2_POST_WIDGET": "status-progress",
    "WAIT_DOCTOR": "status-progress",
    "DOCTOR_ACCEPTED": "status-accepted",
    "DOCTOR_DENIED": "status-denied",
    "R3_POST_REQUEST": "status-progress",
    "WAIT_APPT": "status-progress",
    "APPT_CONFIRMED": "status-done",
    "APPT_DENIED": "status-denied",
    "FAILED": "status-denied",
    "R1_FINAL_REPLY_POSTED": "status-done",
    "WAIT_R1_CLEANUP_THUMBS": "status-pending",
    "CLEANUP_RUNNING": "status-pending",
    "CLEANED": "status-done",
}

# Mapeamento de status → índice do stepper (0-4)
STEP_STATUS_INDEX: dict[str, int] = {
    CaseStatus.NEW: 0,
    CaseStatus.R1_ACK_PROCESSING: 0,
    CaseStatus.EXTRACTING: 1,
    CaseStatus.LLM_STRUCT: 1,
    CaseStatus.LLM_SUGGEST: 1,
    CaseStatus.R2_POST_WIDGET: 2,
    CaseStatus.WAIT_DOCTOR: 2,
    CaseStatus.DOCTOR_ACCEPTED: 2,
    CaseStatus.DOCTOR_DENIED: 2,
    CaseStatus.R3_POST_REQUEST: 3,
    CaseStatus.WAIT_APPT: 3,
    CaseStatus.APPT_CONFIRMED: 3,
    CaseStatus.APPT_DENIED: 3,
    CaseStatus.FAILED: 3,
    CaseStatus.R1_FINAL_REPLY_POSTED: 4,
    CaseStatus.WAIT_R1_CLEANUP_THUMBS: 4,
    CaseStatus.CLEANUP_RUNNING: 4,
    CaseStatus.CLEANED: 4,
}

# Labels em português para eventos de auditoria
EVENT_LABELS: dict[str, str] = {
    "CASE_CREATED": "Caso criado",
    "CASE_PROCEDURES_DECLARED": "Procedimentos declarados pelo NIR",
    "CASE_START_PROCESSING": "Processamento iniciado",
    "CASE_START_EXTRACTION": "Extração de dados iniciada",
    "CASE_EXTRACTION_OK": "Extração de dados concluída",
    "CASE_EXTRACTION_FAILED": "Falha na extração de dados",
    "LLM1_OK": "Análise Automática (estrutura) concluída",
    "LLM1_FAILED": "Falha na análise automática (estrutura)",
    "LLM2_OK": "Análise Automática (sugestão) concluída",
    "LLM2_FAILED": "Falha na análise automática (sugestão)",
    "CASE_READY_FOR_DOCTOR": "Caso enviado para avaliação médica",
    "DOCTOR_ACCEPT": "Aceito pelo médico",
    "DOCTOR_DENY": "Recusado pelo médico",
    "DOCTOR_PROCEDURE_DECISIONS_RECORDED": "Decisões médicas por procedimento registradas",
    "CASE_READY_FOR_SCHEDULER": "Caso enviado para agendamento",
    "SCHEDULER_REQUEST_POSTED": "Solicitação de agendamento enviada",
    "APPT_CONFIRMED": "Agendamento confirmado",
    "APPT_DENIED": "Agendamento negado",
    "FINAL_REPLY_POSTED": "Resultado final enviado",
    "CLEANUP_TRIGGERED": "Limpeza iniciada",
    "CLEANUP_COMPLETED": "Caso concluído",
    "POST_SCHEDULE_ISSUE_OPENED": "Intercorrência aberta",
    "POST_SCHEDULE_ISSUE_RESPONDED": "Intercorrência respondida pelo agendador",
    "POST_SCHEDULE_ISSUE_ACKNOWLEDGED": "Ciência de intercorrência confirmada",
    "POST_ACCEPTANCE_ISSUE_OPENED": "Intercorrência pós-aceitação aberta",
    "POST_ACCEPTANCE_ISSUE_RESPONDED": "Intercorrência pós-aceitação respondida",
    "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED": "Ciência de intercorrência pós-aceitação confirmada",
    # ── Scope gate ───────────────────────────────────────────
    "SCOPE_GATE_BYPASS": "Fora do escopo — revisão manual necessária",
    # ── Pipeline / sistema ────────────────────────────────────
    "EDA_SCOPE_GATED_MANUAL_REVIEW": "Encaminhado para revisão manual",
    "EDA_PREOP_POLICY_DECISION": "Política pré-operatória avaliada",
    "PIPELINE_FAILED": "Falha no processamento",
    "PRIOR_CASE_LOOKUP": "Casos anteriores consultados",
    "CASE_PROCEDURES_DETECTED": "Procedimentos detectados na análise",
    "PROCEDURE_SELECTION_AUTO_UPGRADED": "Upgrade automático para EDA + Colonoscopia",
    "REGULATION_REPORT_GATE_FAILED": "Laudo de regulação inválido",
    # ── Work locks ────────────────────────────────────────────
    "WORK_LOCK_CLAIMED": "Caso reservado",
    "WORK_LOCK_RELEASED": "Reserva liberada",
    "WORK_LOCK_EXPIRED": "Reserva expirada",
    # ── Ciência operacional CHD ───────────────────────────────
    "ADMISSION_FLOW_OPERATIONAL_NOTICE": "Aviso de fluxo sem agendamento",
    "SCHEDULER_OPERATIONAL_NOTICE_ACK": "Ciência de fluxo sem agendamento",
    # ── Vinda imediata (eventos legados) ───────────────────────
    "IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE": "Aviso de vinda imediata",
    "SCHEDULER_IMMEDIATE_ACK": "Ciência de vinda imediata",
    # ── Anexos ────────────────────────────────────────────────
    "CASE_ATTACHMENT_ADDED": "Anexo adicionado",
    "CASE_ATTACHMENT_SUPPRESSED": "Anexo suprimido pelo NIR",
    "CASE_ATTACHMENT_SUPPLEMENT_ADDED": "Anexo complementar adicionado",
    # ── Encerramento administrativo ────────────────────────────
    "CASE_ADMINISTRATIVELY_CLOSED": "Encerrado administrativamente",
    # ── Reenvio corrigido ─────────────────────────────────────
    "CASE_CORRECTION_CREATED": "Reenvio corrigido criado",
    "CASE_MARKED_SUPERSEDED": "Caso corrigido por novo envio",
    # ── Correção de tipo e reprocessamento (Slice 006) ────────
    "EXAM_TYPE_CORRECTED": "Tipo de exame corrigido pelo NIR",
    "CASE_PROCEDURE_DECLARATION_CORRECTED": "Conjunto de procedimentos declarado corrigido pelo NIR",
    "CASE_REPROCESSING_REQUESTED": "Reprocessamento solicitado",
    # ── Comunicação operacional ───────────────────────────────
    "CASE_COMMUNICATION_MESSAGE_POSTED": "Mensagem operacional registrada",
    # ── Follow-up de desfecho do supervisor ────────────────────
    "FOLLOWUP_RECORDED": "Follow-up registrado",
    "FOLLOWUP_UPDATED": "Follow-up atualizado",
}

# Cores do dot da timeline por event_type
EVENT_DOT_CSS: dict[str, str] = {
    "CASE_CREATED": "reception",
    "CASE_PROCEDURES_DECLARED": "nir",
    "CASE_START_PROCESSING": "system",
    "CASE_START_EXTRACTION": "system",
    "CASE_EXTRACTION_OK": "system",
    "CASE_EXTRACTION_FAILED": "system",
    "LLM1_OK": "system",
    "LLM1_FAILED": "system",
    "LLM2_OK": "system",
    "LLM2_FAILED": "system",
    "CASE_READY_FOR_DOCTOR": "system",
    "DOCTOR_ACCEPT": "doctor",
    "DOCTOR_DENY": "doctor",
    "DOCTOR_PROCEDURE_DECISIONS_RECORDED": "doctor",
    "CASE_READY_FOR_SCHEDULER": "system",
    "SCHEDULER_REQUEST_POSTED": "system",
    "APPT_CONFIRMED": "scheduler",
    "APPT_DENIED": "scheduler",
    "FINAL_REPLY_POSTED": "system",
    "CLEANUP_TRIGGERED": "system",
    "CLEANUP_COMPLETED": "system",
    "POST_SCHEDULE_ISSUE_OPENED": "nir",
    "POST_SCHEDULE_ISSUE_RESPONDED": "scheduler",
    "POST_SCHEDULE_ISSUE_ACKNOWLEDGED": "nir",
    "POST_ACCEPTANCE_ISSUE_OPENED": "nir",
    "POST_ACCEPTANCE_ISSUE_RESPONDED": "scheduler",
    "POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED": "nir",
    # ── Scope gate ───────────────────────────────────────────
    "SCOPE_GATE_BYPASS": "system",
    # ── Pipeline / sistema ────────────────────────────────────
    "EDA_SCOPE_GATED_MANUAL_REVIEW": "system",
    "EDA_PREOP_POLICY_DECISION": "system",
    "PIPELINE_FAILED": "system",
    "PRIOR_CASE_LOOKUP": "system",
    "CASE_PROCEDURES_DETECTED": "system",
    "PROCEDURE_SELECTION_AUTO_UPGRADED": "system",
    "REGULATION_REPORT_GATE_FAILED": "system",
    # ── Work locks ────────────────────────────────────────────
    "WORK_LOCK_CLAIMED": "system",
    "WORK_LOCK_RELEASED": "system",
    "WORK_LOCK_EXPIRED": "system",
    # ── Ciência operacional CHD ───────────────────────────────
    "ADMISSION_FLOW_OPERATIONAL_NOTICE": "system",
    "SCHEDULER_OPERATIONAL_NOTICE_ACK": "scheduler",
    # ── Vinda imediata (eventos legados) ───────────────────────
    "IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE": "system",
    "SCHEDULER_IMMEDIATE_ACK": "scheduler",
    # ── Anexos ────────────────────────────────────────────────
    "CASE_ATTACHMENT_ADDED": "system",
    "CASE_ATTACHMENT_SUPPRESSED": "nir",
    "CASE_ATTACHMENT_SUPPLEMENT_ADDED": "nir",
    # ── Encerramento administrativo ────────────────────────────
    "CASE_ADMINISTRATIVELY_CLOSED": "system",
    # ── Reenvio corrigido ─────────────────────────────────────
    "CASE_CORRECTION_CREATED": "nir",
    "CASE_MARKED_SUPERSEDED": "system",
    # ── Correção de tipo e reprocessamento (Slice 006) ────────
    "EXAM_TYPE_CORRECTED": "nir",
    "CASE_PROCEDURE_DECLARATION_CORRECTED": "nir",
    "CASE_REPROCESSING_REQUESTED": "system",
    # ── Comunicação operacional ───────────────────────────────
    "CASE_COMMUNICATION_MESSAGE_POSTED": "system",
}

# Etapas do stepper
STEPS: list[dict[str, str]] = [
    {"icon": "📄", "label": "Upload"},
    {"icon": "⚙️", "label": "Extração Automática"},
    {"icon": "🩺", "label": "Avaliação Médica"},
    {"icon": "📅", "label": "Agendamento"},
    {"icon": "✅", "label": "Resultado Final"},
]

# Labels legíveis para o tipo detectado no card de correção (Slice 006).
CORRECTION_DETECTED_TYPE_LABELS: dict[str, str] = {
    "eda": "EDA",
    "colonoscopy": "Colonoscopia",
    "mixed": "Solicitação mista (EDA + Colonoscopia)",
    "unknown": "Não identificado",
    "non_eda": "Fora do escopo suportado",
}


@login_required
@role_required("nir")
def intake_home(request: HttpRequest) -> HttpResponse:
    """Dashboard do NIR — formulário de upload + lista de casos recentes."""
    user = request.user
    assert user.is_authenticated

    if request.method == "POST":
        form = CaseUploadForm(request.POST, request.FILES)
        files = request.FILES.getlist("pdf_files")
        attachments = request.FILES.getlist("attachment_files")
        exam_type = request.POST.get("exam_type", "")
        cases, errors = process_uploaded_files(
            files,
            user,
            attachments=attachments or None,
            exam_type=exam_type,
        )

        for error in errors:
            messages.warning(request, error)

        if cases:
            count = len(cases)
            msg = f"{count} encaminhamento{'s' if count > 1 else ''} recebido{'s' if count > 1 else ''} com sucesso. O processamento continuará em background."
            messages.success(request, msg)
            return redirect("intake:my_cases")
        elif not errors:
            messages.warning(request, "Nenhum arquivo enviado.")
    else:
        form = CaseUploadForm()

    # Casos recentes do NIR logado
    recent_cases = (
        Case.objects.filter(created_by=user)
        .exclude(status="CLEANED")
        .prefetch_related("procedures")
        .order_by("-created_at")[:10]
    )

    recent_cases_data = [
        {
            "case": c,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
            **_declared_badge(c),
        }
        for c in recent_cases
    ]

    return render(
        request,
        "intake/intake_home.html",
        {
            "form": form,
            "recent_cases": recent_cases_data,
            # R3: UI explica indisponibilidade de colonoscopia quando a flag
            # de intake está desligada (a opção ativa só aparece com flag on).
            "colonoscopy_intake_enabled": is_colonoscopy_intake_enabled(),
        },
    )


DOCTOR_DECISION_MAP: dict[str, str] = {
    "accept": "ACEITAR",
    "deny": "NEGAR",
}


def _get_doctor_decision_display(case: Case) -> str:
    if case.doctor_decision:
        return DOCTOR_DECISION_MAP.get(case.doctor_decision, case.doctor_decision.upper())
    return ""


def _my_cases_context(request: HttpRequest) -> dict[str, object]:
    """Build context for full and HTMX NIR case-list renders.

    All active NIR users see all operational cases (status != CLEANED)
    for shift continuity, regardless of who created the case.
    """
    user = request.user
    assert user.is_authenticated

    # Lazily expire stale locks for WAIT_R1_CLEANUP_THUMBS before query
    expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_R1_CLEANUP_THUMBS])

    qs = (
        Case.objects.exclude(status=CaseStatus.CLEANED)
        .select_related("doctor", "created_by", "locked_by")
        .prefetch_related("procedures")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    search = request.GET.get("q", "")
    if search:
        qs = qs.filter(agency_record_number__icontains=search)

    # R5 (Slice 005): filtro server-side por conjunto DECLARADO — default
    # Todos; compõe com status e busca; valor inválido cai para all. NUNCA usa
    # detected/approved (D13).
    raw_exam_type = request.GET.get("exam_type", "all")
    exam_type = raw_exam_type if raw_exam_type in _NIR_DECLARED_DIMENSIONS else "all"
    if exam_type != "all":
        qs = _filter_by_declared_dimension(qs, exam_type)

    case_data = [
        {
            "case": c,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
            "origin_unit": c.get_origin_unit_display(compact=True),
            "patient_name": c.patient_name,
            "patient_age": c.patient_age,
            "patient_gender": c.patient_gender,
            "diagnosis": c.diagnosis,
            "doctor_decision_display": _get_doctor_decision_display(c),
            "doctor_display": c.doctor_display,
            "has_doctor_observation": c.has_doctor_observation,
            "created_by_other_nir": c.created_by_id != user.pk,
            "created_by_display": c.created_by.get_full_name() or c.created_by.username,
            # Badges projetados exclusivamente do valor persistido (Slice 005) —
            # a view nunca redetecta sinais a partir de texto bruto.
            "priority_signal_badges": build_priority_signal_badges(c.priority_signals),
            # Slice 001 (R6): label declarado projetado da projeção (rows);
            # template não faz query por row nem infere do campo legado.
            **_declared_badge(c),
            # Lock info for WAIT_R1_CLEANUP_THUMBS cases (other statuses: all clear)
            **(
                compute_lock_display(c, user=user)
                if c.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
                else {
                    "is_locked": False,
                    "is_locked_by_current_user": False,
                    "locked_by_display": "",
                    "locked_until": "",
                    "lock_context": "",
                }
            ),
        }
        for c in qs
    ]

    query_string = request.META.get("QUERY_STRING", "")
    partial_url = "/cases/my-cases/partial/"
    if query_string:
        partial_url = f"{partial_url}?{query_string}"

    return {
        "case_data": case_data,
        "status_filter": status_filter,
        "search": search,
        "exam_type": exam_type,
        "status_labels": STATUS_LABELS,
        "status_css": STATUS_CSS_CLASS,
        "my_cases_partial_url": partial_url,
    }


@login_required
@role_required("nir")
def my_cases(request: HttpRequest) -> HttpResponse:
    """Lista de 'Meus Casos' do NIR — cards com filtros."""
    return render(request, "intake/my_cases.html", _my_cases_context(request))


@login_required
@role_required("nir")
def my_cases_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial for polling the NIR case list without full refresh."""
    return render(request, "intake/_my_cases_content.html", _my_cases_context(request))


@login_required
@role_required("nir")
def case_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhes de um caso para o NIR — timeline, stepper e PDF inline.

    Any active NIR can open any operational case (status != CLEANED)
    for shift continuity, regardless of who created the case.

    For WAIT_R1_CLEANUP_THUMBS cases, a lock with context 'nir_receipt'
    is acquired to prevent concurrent receipt confirmation.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )
    # Block access to CLEANED cases via the operational route
    if case.status == CaseStatus.CLEANED:
        raise Http404("Caso concluído não está disponível na fila operacional.")
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

    # Enriquecer eventos com labels e cores
    enriched_events = []
    for e in events:
        enriched_events.append(
            {
                "event": e,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
            }
        )

    # ── Lock acquisition for WAIT_R1_CLEANUP_THUMBS ──────────────
    user = request.user
    lock_token = None
    lock_error = None
    lock_locked_by_display = None
    can_confirm = case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS
    lock_held = False

    if case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
            context="nir_receipt",
            role="nir",
        )
        if result.acquired:
            lock_token = str(result.token)
            # Re-fetch case with fresh lock data
            case = Case.objects.get(pk=case.case_id)
            lock_held = True
        elif result.locked_by_display:
            lock_locked_by_display = result.locked_by_display
            can_confirm = False
        else:
            can_confirm = False

    # Slice 001 (R6): label declarado projetado da projeção — computado na view
    # após o re-fetch do lock, nunca consultado no template.
    declared_badge = _declared_badge(case)

    # Active attachments (non-suppressed, ordered by created_at)
    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    # Para WAIT_DOCTOR, popular info de lock médico exclusivamente para a UI do
    # anexo complementar (Spec R5: NIR vê mensagem de reserva em vez do form).
    # Variáveis dedicadas para não poluir o bloco "Ações" do WAIT_R1_CLEANUP_THUMBS.
    supplemental_lock_blocked_by = ""
    if case.status == CaseStatus.WAIT_DOCTOR:
        lock_display = compute_lock_display(case, user=user)
        if lock_display["is_locked"]:
            supplemental_lock_blocked_by = lock_display["locked_by_display"]

    # Prior case lookup — extrair informações do evento PRIOR_CASE_LOOKUP
    prior_case_lookup = None
    for e in events:
        if e.event_type == "PRIOR_CASE_LOOKUP":
            payload = e.payload or {}
            prior_case_lookup = {
                "prior_case_id": payload.get("prior_case_id", ""),
                "decision": payload.get("decision", ""),
                "reason": payload.get("reason", ""),
                "decided_at": payload.get("decided_at", ""),
                "decided_by": payload.get("decided_by", ""),
                "decided_by_role": payload.get("decided_by_role", ""),
                "prior_denial_count_7d": payload.get("prior_denial_count_7d", 0),
            }
            break

    # Resultado final
    result_info = None
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
    if is_scope_gated:
        reason_code = case.suggested_action.get("reason_code", "") if isinstance(case.suggested_action, dict) else ""
        reason_text = case.suggested_action.get("reason_text", "") if isinstance(case.suggested_action, dict) else ""
        result_info = {
            "type": "manual_review_required",
            "reason_code": reason_code,
            "reason_text": reason_text,
        }
    elif is_doctor_denied_final or case.status == CaseStatus.DOCTOR_DENIED:
        result_info = {
            "type": "doctor_denied",
            "reason": case.doctor_reason,
            "doctor_display": case.doctor_display,
        }
    elif is_operational_notice_final:
        copy = get_admission_flow_notice_copy(case.doctor_admission_flow)
        result_info = {
            "type": "accepted_immediate",
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "doctor_display": case.doctor_display,
            "badge": copy["nir_badge"],
            "body": copy["nir_body"],
        }
        # Slice 002: badge compacto apenas para fluxo ward_icu_backup (label longo que transborda)
        if case.doctor_admission_flow == "ward_icu_backup":
            compact_label = COMPACT_ADMISSION_FLOW_LABELS["ward_icu_backup"]
            result_info["compact_badge"] = f"✓ {compact_label}"
    elif case.status == CaseStatus.APPT_DENIED or (terminal_with_result and case.appointment_status == "denied"):
        result_info = {
            "type": "appt_denied",
            "reason": case.appointment_reason,
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result:
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
        }
    elif case.status == CaseStatus.FAILED:
        result_info = {"type": "failed"}

    # ── Post-schedule intercurrence result info ────────────────────
    if case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS and case.post_schedule_issue_status == "responded":
        issue_action_labels = {
            "cancel": "Cancelado",
            "reschedule": "Reagendado",
            "maintain": "Mantido",
            "deny": "Solicitação Negada",
        }
        result_info = {
            "type": "post_schedule_issue_responded",
            "nir_reason_code": case.post_schedule_issue_reason,
            "nir_reason_label": get_post_schedule_issue_reason_label(case.post_schedule_issue_reason),
            "nir_message": case.post_schedule_issue_message,
            "response_action": case.post_schedule_issue_response_action,
            "response_action_label": issue_action_labels.get(
                case.post_schedule_issue_response_action, case.post_schedule_issue_response_action
            ),
            "response_message": case.post_schedule_issue_response_message,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
            "appointment_status": case.appointment_status,
        }

    # Elegibilidade para anexo complementar
    can_add_supplemental = (
        case.status not in (CaseStatus.CLEANED,)
        and not case.doctor_decision
        and case.status in ELIGIBLE_SUPPLEMENTAL_STATUSES
    )

    # ── Correção de conjunto (Slice 005): card NIR apenas em manual review ──
    can_correct_exam_type = False
    correction_form_context = None
    if lock_held and is_exam_type_correction_eligible(case):
        can_correct_exam_type = True
        suggested = case.suggested_action or {}
        detected = suggested.get("detected_exam_type") or suggested.get("exam_type") or ""
        correction_form_context = {
            # Label declarado projetado da projeção (combinado → "EDA + Colonoscopia").
            "declared_label": declared_badge["declared_label"],
            # Slice 011-C (decisão 2): chave de seleção derivada da projeção
            # para os radios marcarem "(atual)" — nunca a coluna removida.
            "declared_type_key": declared_badge["declared_type_key"],
            "detected_exam_type_label": CORRECTION_DETECTED_TYPE_LABELS.get(detected, detected or "—"),
            "reason_text": suggested.get("reason_text", ""),
            "correction_reason_choices": list(EXAM_TYPE_CORRECTION_REASONS.items()),
        }

    # ── Correction context (R1: corrects_case card) ──────────────
    correction_context = None
    if case.corrects_case_id:
        try:
            original = Case.objects.get(pk=case.corrects_case_id)
            correction_context = {
                "type": "corrects_case",
                "original_case_id": str(original.case_id),
                "original_agency_record_number": original.agency_record_number or str(original.case_id)[:8],
                "original_short_id": str(original.case_id)[:8],
                "original_patient_name": original.patient_name,
                "original_created_at": original.created_at,
                "original_status": original.status,
                "original_status_label": STATUS_LABELS.get(original.status, original.get_status_display()),
                "correction_reason": case.correction_reason,
                "correction_created_by": case.correction_created_by.get_full_name()
                if case.correction_created_by
                else "",
                "correction_created_at": case.correction_created_at,
            }
        except Case.DoesNotExist:
            pass

    # ── Correction context (R2: corrected_by_cases card) ───────────
    corrected_by_cases_list: list[dict[str, object]] = []
    if hasattr(case, "corrected_by_cases"):
        corrected_qs = case.corrected_by_cases.all().order_by("-correction_created_at", "-created_at")
        corrected_by_cases_list = [
            {
                "case_id": str(c.case_id),
                "short_id": str(c.case_id)[:8],
                "agency_record_number": c.agency_record_number or "",
                "correction_created_at": c.correction_created_at or c.created_at,
            }
            for c in corrected_qs
        ]

    # Nome do paciente
    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

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
            "declared_label": declared_badge["declared_label"],
            "declared_type_key": declared_badge["declared_type_key"],
            "can_confirm_receipt": can_confirm,
            "lock_token": lock_token or "",
            "lock_error": lock_error,
            "lock_locked_by_display": lock_locked_by_display or "",
            "lock_held": lock_held,
            "result_info": result_info,
            "patient_name": patient_name,
            "prior_case_lookup": prior_case_lookup,
            # Badges persistidos no topo do detalhe (Slice 005) — projeção
            # compartilhada; nunca reexecuta detecção/LLM.
            "priority_signal_badges": build_priority_signal_badges(case.priority_signals),
            # Parametrização para template compartilhado
            "show_intake_nav": True,
            "back_url": reverse("intake:my_cases"),
            "back_label": "← Voltar para lista",
            "pdf_url": reverse("intake:serve_pdf", args=[case.case_id]),
            "mobile_pdf_viewer_url": reverse("intake:pdf_viewer", args=[case.case_id])
            + f"?next={reverse('intake:case_detail', args=[case.case_id])}",
            "attachments": active_attachments,
            "can_add_supplemental": can_add_supplemental,
            "supplemental_lock_blocked_by": supplemental_lock_blocked_by,
            "can_correct_exam_type": can_correct_exam_type,
            "correction_form_context": correction_form_context,
            "procedures": _procedure_comparison(case),
            "correction_context": correction_context,
            "corrected_by_cases": corrected_by_cases_list,
            # ── Comunicação operacional ───────────────────────────────
            "communication_messages": case.communication_messages.select_related("author").all(),
            "can_post_communication": case.status != CaseStatus.CLEANED,
            "communication_post_url": reverse("intake:post_case_communication", args=[case.case_id]),
            "communication_next_url": request.get_full_path() + "#case-communication",
            "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
        },
    )


def _get_nir_attachment_or_404(case_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[Case, CaseAttachment]:
    """Busca e autoriza anexo para o NIR operacional.

    Retorna (case, attachment) se autorizado.
    Levanta Http404 se o caso é CLEANED ou o anexo está suprimido.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("Anexo de caso concluído não está disponível na fila operacional.")

    attachment = get_object_or_404(
        CaseAttachment,
        attachment_id=attachment_id,
        case=case,
        is_suppressed=False,
    )

    return case, attachment


@login_required
@role_required("nir")
@xframe_options_sameorigin
def serve_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """Serve um anexo protegido para visualização NIR.

    Acesso permitido para NIR com papel ativo 'nir'.
    O caso não pode estar CLEANED.
    Anexos suprimidos retornam 404.
    """
    case, attachment = _get_nir_attachment_or_404(case_id, attachment_id)

    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@role_required("nir")
def suppress_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """POST: Suprime um anexo ativo de forma auditável.

    Acesso permitido para NIR com papel ativo 'nir'.
    O caso não pode estar CLEANED.
    Motivo obrigatório no POST.
    Após sucesso, redireciona para detalhe do caso com mensagem.
    """
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("Anexo de caso concluído não está disponível na fila operacional.")

    attachment = get_object_or_404(
        CaseAttachment,
        attachment_id=attachment_id,
        case=case,
        is_suppressed=False,
    )

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.warning(request, "Informe o motivo da supressão do anexo.")
        return redirect("intake:case_detail", case_id=case.case_id)

    try:
        suppress_case_attachment(
            attachment=attachment,
            user=request.user,
            reason=reason,
        )
        messages.success(request, "Anexo suprimido com sucesso.")
    except ValueError as exc:
        messages.warning(request, str(exc))

    return redirect("intake:case_detail", case_id=case.case_id)


@login_required
@role_required("nir")
def add_supplemental_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
) -> HttpResponse:
    """POST: Adiciona anexo(s) complementar(es) a um caso antes da decisão médica.

    Valida elegibilidade, lock médico (se WAIT_DOCTOR), justificativa obrigatória.
    Aceita múltiplos arquivos.
    Redireciona para detalhe do caso com mensagem.
    """
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )

    note = request.POST.get("note", "").strip()
    if not note:
        messages.warning(request, "Justificativa obrigatória para anexo complementar.")
        return redirect("intake:case_detail", case_id=case.case_id)

    files = request.FILES.getlist("attachment_files")
    if not files:
        messages.warning(request, "Selecione ao menos um arquivo para anexar.")
        return redirect("intake:case_detail", case_id=case.case_id)

    # Validate attachments using existing helpers
    for f in files:
        try:
            validate_attachment_file(f)
        except ValueError as exc:
            messages.warning(request, str(exc))
            return redirect("intake:case_detail", case_id=case.case_id)

    # Check max total attachments per case
    existing_count = case.attachments.filter(is_suppressed=False).count()
    max_attachments = settings.INTAKE_MAX_ATTACHMENTS_PER_CASE
    if existing_count + len(files) > max_attachments:
        messages.warning(
            request,
            f"Máximo de {max_attachments} anexos por caso. Já existem {existing_count} anexo(s).",
        )
        return redirect("intake:case_detail", case_id=case.case_id)

    success_count = 0
    for f in files:
        try:
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=f,
                user=request.user,
                note=note,
            )
            success_count += 1
        except ValueError as exc:
            messages.warning(request, str(exc))
            return redirect("intake:case_detail", case_id=case.case_id)

    if success_count > 0:
        msg = f"{success_count} anexo(s) complementar(es) adicionado(s) com sucesso."
        messages.success(request, msg)

    return redirect("intake:case_detail", case_id=case.case_id)


@login_required
def post_case_communication(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Cria uma mensagem de comunicação operacional no caso.

    Valida active_role da sessão, chama o serviço de domínio e
    redireciona para next seguro ou fallback.
    """
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)
    active_role = request.session.get("active_role", "")
    body = request.POST.get("body", "")

    try:
        post_case_communication_message(
            case=case,
            author=request.user,
            author_role=active_role,
            body=body,
        )
        messages.success(request, "Mensagem enviada com sucesso.")
    except CaseCommunicationError as exc:
        messages.warning(request, str(exc))
    except Exception:
        logger.exception("Erro inesperado ao postar mensagem de comunicação.")
        messages.warning(request, "Erro inesperado ao enviar mensagem. Tente novamente.")

    # Redirect seguro
    next_url = request.POST.get("next", "")
    if next_url and not _is_safe_redirect(next_url):
        next_url = ""
    if not next_url:
        next_url = reverse("intake:case_detail", args=[case.case_id])
    return redirect(next_url)


def _is_safe_redirect(url: str) -> bool:
    """Verifica se a URL de redirect é segura (mesmo host)."""
    from django.utils.http import url_has_allowed_host_and_scheme

    return url_has_allowed_host_and_scheme(url, allowed_hosts=None)


@login_required
@role_required("nir")
def corrected_resubmission(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Formulário NIR de reenvio corrigido explícito.

    GET: Exibe formulário contextualizado pelo caso anterior.
    POST: Cria novo Case vinculado ao anterior com novo PDF e motivo.
    """
    from apps.intake.services import create_corrected_resubmission

    original_case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )

    if request.method == "POST":
        correction_reason = request.POST.get("correction_reason", "")
        pdf_file = request.FILES.get("pdf_file")
        attachment_files = request.FILES.getlist("attachment_files")
        exam_type = request.POST.get("exam_type", "")

        errors: list[str] = []

        # Validate reason
        if not correction_reason.strip():
            errors.append("Informe o motivo do reenvio corrigido.")

        # Validate PDF presence
        if not pdf_file:
            errors.append("Selecione um novo PDF principal para o reenvio.")

        # Validate explicit confirmation checkbox (backend is source of truth)
        if not request.POST.get("confirmation"):
            errors.append("Confirme que os documentos do caso anterior não serão herdados.")

        # R3 (Slice 007): tipo explícito obrigatório — backend é a fonte de
        # verdade (choice + flag de intake); o tipo do original não é herdado.
        try:
            ensure_exam_type_allowed(exam_type)
        except ValueError as exc:
            errors.append(str(exc))

        if errors:
            for err in errors:
                messages.warning(request, err)
            return render(
                request,
                "intake/corrected_resubmission.html",
                {
                    "original_case": original_case,
                    "patient_name": original_case.patient_name,
                    "colonoscopy_intake_enabled": is_colonoscopy_intake_enabled(),
                },
            )

        # pdf_file já validado acima como não-None
        assert pdf_file is not None  # nosec
        assert request.user.is_authenticated  # nosec

        try:
            new_case = create_corrected_resubmission(
                original_case=original_case,
                pdf_file=pdf_file,
                user=request.user,
                correction_reason=correction_reason,
                attachments=attachment_files or None,
                # Slice 007 (R3/R4): escolha explícita do NIR; pode divergir
                # do original; nunca herda silenciosamente.
                exam_type=exam_type,
            )
            messages.success(
                request,
                f"Reenvio corrigido criado com sucesso. Novo caso: {new_case.case_id}",
            )
            return redirect("intake:case_detail", case_id=new_case.case_id)
        except ValueError as exc:
            messages.warning(request, str(exc))
        except Exception:
            logger.exception("Erro ao criar reenvio corrigido")
            messages.warning(request, "Erro inesperado ao criar reenvio corrigido. Tente novamente.")

        return render(
            request,
            "intake/corrected_resubmission.html",
            {
                "original_case": original_case,
                "patient_name": original_case.patient_name,
                "colonoscopy_intake_enabled": is_colonoscopy_intake_enabled(),
            },
        )

    # GET
    return render(
        request,
        "intake/corrected_resubmission.html",
        {
            "original_case": original_case,
            "patient_name": original_case.patient_name,
            "status_label": STATUS_LABELS.get(original_case.status, original_case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(original_case.status, "status-pending"),
            "colonoscopy_intake_enabled": is_colonoscopy_intake_enabled(),
        },
    )


@login_required
@role_required("nir")
@xframe_options_sameorigin
def serve_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve o PDF original do caso para visualização inline no <embed>.

    Any active NIR can view PDFs of operational cases (status != CLEANED)
    for shift continuity.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("PDF de caso concluído não está disponível na fila operacional.")
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    response = FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@role_required("nir")
def confirm_receipt(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Confirma recebimento do resultado final e conclui o caso.

    View fina: parseia o token, delega ao serviço transacional
    ``confirm_case_receipt`` — que serializa com a correção de tipo pelo
    MESMO row lock (``select_for_update``) e revalida estado + reserva na
    instância bloqueada e atualizada — traduz erros esperados e redireciona.
    Nenhuma regra de negócio duplicada na view e nenhum save sobre instância
    obsoleta.
    """
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)

    # Pré-checagem apenas para mensagem amigável; a validação autoritativa
    # ocorre no serviço, sob o row lock.
    if case.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        messages.warning(request, "Este caso não está aguardando confirmação de recebimento.")
        return redirect("intake:case_detail", case_id=case.case_id)

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        messages.warning(
            request,
            "Token de reserva não encontrado. Volte para a lista e tente novamente.",
        )
        return redirect("intake:case_detail", case_id=case.case_id)

    user = request.user
    assert user.is_authenticated  # garantido por @login_required

    try:
        confirm_case_receipt(
            case_id=case.case_id,
            user=user,
            active_role=request.session.get("active_role", ""),
            lock_token=token,
        )
    except PermissionError as exc:
        messages.warning(request, str(exc))
        return redirect("intake:case_detail", case_id=case.case_id)
    except ValueError as exc:
        messages.warning(request, str(exc))
        return redirect("intake:case_detail", case_id=case.case_id)

    messages.success(request, "Recebimento confirmado. Caso concluído.")
    return redirect("intake:my_cases")


@login_required
@role_required("nir")
def exam_type_correction(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: corrige o tipo de exame de um caso em revisão manual (Slice 006).

    View fina: parseia token e papel ativo da sessão, delega ao serviço
    transacional ``correct_case_exam_type`` (que serializa com a confirmação
    pelo MESMO row lock e valida ator + reserva sob o lock) e traduz erros.
    Em caso inelegível o controle não existe na UI e o POST retorna 404
    seguro, sem qualquer mutação.
    """
    if request.method != "POST":
        raise Http404

    case = get_object_or_404(Case, case_id=case_id)

    if not is_exam_type_correction_eligible(case):
        raise Http404("Caso não está em revisão manual elegível para correção de tipo.")

    user = request.user
    assert user.is_authenticated  # garantido por @login_required

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        messages.warning(
            request,
            "Token de reserva não encontrado. Volte para a lista e tente novamente.",
        )
        return redirect("intake:case_detail", case_id=case.case_id)

    new_exam_type = request.POST.get("exam_type", "")
    reason_code = request.POST.get("reason_code", "")
    try:
        case = correct_case_exam_type(
            case_id=case.case_id,
            new_exam_type=new_exam_type,
            user=user,
            active_role=request.session.get("active_role", ""),
            lock_token=token,
            reason_code=reason_code,
        )
    except PermissionError as exc:
        messages.warning(request, str(exc))
        return redirect("intake:case_detail", case_id=case.case_id)
    except ValueError as exc:
        messages.warning(request, str(exc))
        return redirect("intake:case_detail", case_id=case.case_id)
    except EnqueueAfterCommitError as exc:
        # Falha PÓS-commit: a correção foi aplicada (LLM_STRUCT). Mensagem
        # verdadeira: retry automático programado ou erro operacional explícito
        # — sem prometer retomada automática inexistente.
        if exc.recovery_scheduled:
            messages.error(
                request,
                "Tipo de exame corrigido, mas o reprocessamento automático não pôde ser "
                "agendado imediatamente. Uma nova tentativa automática foi programada; "
                "o caso permanece em análise automática (LLM_STRUCT).",
            )
        else:
            messages.error(
                request,
                "Tipo de exame corrigido, mas o reprocessamento automático não pôde ser "
                "agendado. O caso permanece em análise automática (LLM_STRUCT); acione o "
                "suporte para reenfileirar o pipeline manualmente.",
            )
        return redirect("intake:case_detail", case_id=case.case_id)

    messages.success(
        request,
        f"Tipo de exame corrigido para {format_procedure_selection(get_declared_procedure_types(case))}. "
        "Caso em reprocessamento.",
    )
    return redirect("intake:case_detail", case_id=case.case_id)


@login_required
@role_required("nir")
def nir_lock_renew(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Renova a reserva NIR de um caso (heartbeat).

    Requer lock_token no body do POST.
    Retorna JsonResponse com 'success' e 'locked_until' ou erro.
    """
    if request.method != "POST":
        raise Http404

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        return JsonResponse({"success": False, "error": "Token de reserva não fornecido."}, status=200)

    result = renew_lock_service(
        case_id=case_id,
        user=request.user,
        token=token,
        context="nir_receipt",
    )

    if result.acquired:
        return JsonResponse(
            {
                "success": True,
                "locked_until": result.locked_until.isoformat() if result.locked_until else None,
            }
        )
    return JsonResponse({"success": False, "error": result.reason}, status=200)


@login_required
@role_required("nir")
def nir_lock_release(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Libera a reserva NIR de um caso explicitamente.

    Requer lock_token no body do POST.
    Retorna JsonResponse com 'success'.
    """
    if request.method != "POST":
        raise Http404

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        return JsonResponse({"success": False, "error": "Token de reserva não fornecido."}, status=200)

    released = release_lock_service(
        case_id=case_id,
        user=request.user,
        token=token,
        context="nir_receipt",
    )

    return JsonResponse({"success": released})


# ── Post-schedule intercurrence views ───────────────────────────────────


@login_required
@role_required("nir")
def closed_cases_search(request: HttpRequest) -> HttpResponse:
    """Busca NIR de casos encerrados (CLEANED) para abrir intercorrência.

    Pesquisa por número da ocorrência ou nome do paciente.
    Mostra elegibilidade e botão de abertura apenas para elegíveis.
    """
    from apps.cases.services import (
        get_post_acceptance_issue_ineligibility_reason,
        is_post_acceptance_issue_eligible,
    )

    query = request.GET.get("q", "").strip()
    # R5 (Slice 005): filtro server-side por conjunto DECLARADO — default
    # Todos; valor inválido cai para all; dimensão específica sem termo lista
    # os últimos 50 daquela dimensão (design D13).
    raw_exam_type = request.GET.get("exam_type", "all")
    exam_type = raw_exam_type if raw_exam_type in _NIR_DECLARED_DIMENSIONS else "all"
    results: list[dict[str, object]] = []

    if query or exam_type != "all":
        # Busca: casos CLEANED + casos com intercorrência ativa (qualquer status)
        qs = Case.objects.filter(
            models.Q(status=CaseStatus.CLEANED) | models.Q(post_schedule_issue_status__in=["opened", "responded"])
        )
        if exam_type != "all":
            qs = _filter_by_declared_dimension(qs, exam_type)
        qs = qs.filter(
            models.Q(agency_record_number__icontains=query) | models.Q(structured_data__patient__name__icontains=query)
        ).order_by("-created_at")[:50]

        for c in qs:
            eligible_scheduled = is_post_acceptance_issue_eligible(c, context="scheduled")
            eligible_operational = is_post_acceptance_issue_eligible(c, context="operational_notice")
            eligible = eligible_scheduled or eligible_operational
            # Build ineligibility reason based on the most relevant context
            if eligible:
                ineligibility_reason = ""
            elif c.doctor_admission_flow in ("immediate", "pre_icu", "ward_icu_backup", "pediatric_em"):
                ineligibility_reason = get_post_acceptance_issue_ineligibility_reason(c, context="operational_notice")
            else:
                ineligibility_reason = get_post_acceptance_issue_ineligibility_reason(c, context="scheduled")
            # Check if this case has corrected_by_cases (R3)
            corrected_by_count = 0
            if hasattr(c, "corrected_by_cases"):
                corrected_by_count = c.corrected_by_cases.count()
            results.append(
                {
                    "case": c,
                    "eligible": eligible,
                    "ineligibility_reason": ineligibility_reason,
                    "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
                    "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
                    "patient_name": c.patient_name,
                    "has_active_issue": bool(c.post_schedule_issue_status),
                    "issue_status": c.post_schedule_issue_status or "",
                    "corrected_by_count": corrected_by_count,
                    # R5: badge por conjunto DECLARADO projetado (combinado
                    # renderiza "EDA + Colonoscopia", nunca a ponte crua).
                    **_declared_badge(c),
                }
            )

    return render(
        request,
        "intake/closed_cases_search.html",
        {
            "query": query,
            "exam_type": exam_type,
            "results": results,
        },
    )


HISTORICAL_ALLOWED_STATUSES = frozenset(
    {
        CaseStatus.CLEANED,
    }
)
"""Status permitidos na rota histórica NIR."""


def _is_historical_scope_nir(case: Case) -> bool:
    """Verifica se o caso está no escopo histórico NIR.

    Permite:
    - Casos CLEANED
    - Casos com intercorrência ativa/respondida (qualquer status)
    """
    if case.status == CaseStatus.CLEANED:
        return True
    return bool(case.post_schedule_issue_status in ("opened", "responded"))


def _closed_detail_communication_context(case: Case, request: HttpRequest) -> dict[str, object]:
    """Monta contexto de comunicação para o detalhe histórico."""
    return {
        "communication_messages": case.communication_messages.select_related("author").all(),
        "can_post_communication": False,  # Read-only em CLEANED neste slice
        "communication_post_url": "",
        "communication_next_url": request.get_full_path() + "#case-communication",
        "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
    }


@login_required
@role_required("nir")
def closed_case_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhe histórico NIR de caso encerrado (read-only + intercorrência).

    GET: Exibe contexto do caso, timeline, comunicação e, se elegível,
         formulário de intercorrência.
    POST: Abre intercorrência via serviço existente.

    Não adquire lock. Não altera FSM em GET.
    """
    from apps.cases.services import (
        get_post_acceptance_issue_ineligibility_reason,
        is_post_acceptance_issue_eligible,
        open_post_acceptance_issue,
    )

    from .forms import PostScheduleIssueForm

    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )

    # Validar escopo histórico NIR
    if not _is_historical_scope_nir(case):
        raise Http404("Caso não está no escopo histórico NIR.")

    # Armazena formulário bound (com erros) para re-renderizar em POST inválido
    detail_form: PostScheduleIssueForm | None = None

    # Determinar o contexto de elegibilidade para este caso
    # Scheduled tem prioridade porque ja esta implementado e e mais restritivo
    eligible_scheduled = is_post_acceptance_issue_eligible(case, context="scheduled")
    eligible_operational = is_post_acceptance_issue_eligible(case, context="operational_notice")

    # Processar POST de abertura de intercorrencia
    if request.method == "POST":
        # Detecta qual contexto usar baseado no caso
        if eligible_scheduled:
            issue_context = "scheduled"
        elif eligible_operational:
            issue_context = "operational_notice"
        else:
            messages.warning(
                request,
                get_post_acceptance_issue_ineligibility_reason(case, context="scheduled"),
            )
            return redirect("intake:closed_case_detail", case_id=case.case_id)

        form = PostScheduleIssueForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["reason"]
            message = form.cleaned_data.get("message", "")
            try:
                open_post_acceptance_issue(
                    case=case,
                    user=request.user,
                    reason=reason,
                    message=message,
                    context=issue_context,
                )
                if issue_context == "operational_notice":
                    messages.success(
                        request,
                        "Intercorrência registrada com sucesso. O agendador receberá um aviso para confirmar ciência.",
                    )
                else:
                    messages.success(
                        request,
                        "Intercorrência registrada com sucesso. O caso foi enviado para o agendador.",
                    )
                return redirect("intake:closed_case_detail", case_id=case.case_id)
            except ValueError as exc:
                messages.warning(request, str(exc))
        # Form invalido — manter bound com erros para re-renderizar
        detail_form = form

    # ── GET: montar contexto ──────────────────────────────────

    # Re-fetch após possível POST (garantir dados frescos)
    if request.method == "POST":
        case = Case.objects.select_related("created_by", "doctor").get(pk=case.case_id)

    events = case.events.all()

    # Stepper
    current_step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    steps = STEPS
    terminal_without_scheduling = case.status in (
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        CaseStatus.CLEANED,
    ) and (case.doctor_decision == "deny" or is_operational_notice_flow(case.doctor_admission_flow))
    if terminal_without_scheduling:
        steps = [step for step in STEPS if step["label"] != "Agendamento"]
        current_step_idx = len(steps) - 1

    # Enriquecer eventos
    enriched_events = []
    for e in events:
        enriched_events.append(
            {
                "event": e,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
            }
        )

    # Elegibilidade para intercorrencia — ambos os contextos
    eligible = eligible_scheduled or eligible_operational
    if not eligible:
        # Mostra o motivo mais relevante
        ineligibility_reason = get_post_acceptance_issue_ineligibility_reason(
            case,
            context=("scheduled" if is_scheduled_admission_flow(case.doctor_admission_flow) else "operational_notice"),
        )
    else:
        ineligibility_reason = ""

    # Formulario (se elegivel e GET, criar form vazio; POST invalido mantem detail_form do POST)
    if not request.method == "POST" and eligible:
        detail_form = PostScheduleIssueForm()

    # Result info simplificado para histórico
    result_info = _build_historical_result_info(case)

    # Patient name
    patient_name = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            patient_name = patient.get("name", "")

    # Origin unit
    origin_unit = case.get_origin_unit_display(compact=True)

    # Attachments (não suprimidos)
    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    context: dict[str, object] = {
        "case": case,
        "events": enriched_events,
        "steps": steps,
        "current_step_idx": current_step_idx,
        "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
        "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
        "result_info": result_info,
        "patient_name": patient_name,
        "origin_unit": origin_unit,
        # R6: comparativo declarado→detectado→autorizado (fonte: projeção).
        "procedures": _procedure_comparison(case),
        # Badges persistidos no histórico (Slice 005) — projeção compartilhada;
        # casos CLEANED antigos sem backfill não exibem container.
        "priority_signal_badges": build_priority_signal_badges(case.priority_signals),
        # Comunicação operacional (read-only)
        **_closed_detail_communication_context(case, request),
        # Intercorrência
        "eligible": eligible,
        "ineligibility_reason": ineligibility_reason,
        "form": detail_form,
        # PDF / Attachments
        "pdf_url": reverse("intake:closed_case_pdf", args=[case.case_id]) if case.pdf_file else "",
        "mobile_pdf_viewer_url": reverse("intake:closed_case_pdf_viewer", args=[case.case_id])
        + f"?next={reverse('intake:closed_case_detail', args=[case.case_id])}"
        if case.pdf_file
        else "",
        "attachments": active_attachments,
        # Navegação
        "back_url": reverse("intake:closed_cases_search"),
        "back_label": "← Voltar para busca de casos encerrados",
    }

    response = render(request, "intake/closed_case_detail.html", context)
    return response


def _build_historical_result_info(case: Case) -> dict[str, object] | None:
    """Monta result_info para o detalhe histórico NIR."""
    from typing import Any as _Any

    from apps.cases.services import get_post_schedule_issue_reason_label

    suggested_action: _Any = case.suggested_action or {}

    terminal_with_result = case.status in (
        CaseStatus.WAIT_R1_CLEANUP_THUMBS,
        CaseStatus.CLEANED,
    )
    is_doctor_denied_final = terminal_with_result and case.doctor_decision == "deny"
    is_operational_notice_final = terminal_with_result and is_operational_notice_flow(case.doctor_admission_flow)

    # Scope-gated manual review
    is_scope_gated = isinstance(suggested_action, dict) and suggested_action.get("decision") == "manual_review_required"

    result_info = None

    if is_scope_gated:
        result_info = {
            "type": "manual_review_required",
            "reason_code": suggested_action.get("reason_code", ""),
            "reason_text": suggested_action.get("reason_text", ""),
        }
    elif is_doctor_denied_final:
        result_info = {
            "type": "doctor_denied",
            "reason": case.doctor_reason,
            "doctor_display": case.doctor_display,
        }
    elif is_operational_notice_final:
        copy = get_admission_flow_notice_copy(case.doctor_admission_flow)
        result_info = {
            "type": "accepted_immediate",
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "doctor_display": case.doctor_display,
            "badge": copy["nir_badge"],
            "body": copy["nir_body"],
        }
        # Slice 002: badge compacto apenas para fluxo ward_icu_backup (label longo que transborda)
        if case.doctor_admission_flow == "ward_icu_backup":
            compact_label = COMPACT_ADMISSION_FLOW_LABELS["ward_icu_backup"]
            result_info["compact_badge"] = f"✓ {compact_label}"
    elif case.status == CaseStatus.APPT_DENIED or (terminal_with_result and case.appointment_status == "denied"):
        result_info = {
            "type": "appt_denied",
            "reason": case.appointment_reason,
            "doctor_display": case.doctor_display,
            "scheduler_display": case.scheduler_display,
        }
    elif case.status == CaseStatus.APPT_CONFIRMED or terminal_with_result:
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
        }
    elif case.status == CaseStatus.FAILED:
        result_info = {"type": "failed"}

    # Post-schedule intercurrence responded override
    if case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS and case.post_schedule_issue_status == "responded":
        issue_action_labels = {
            "cancel": "Cancelado",
            "reschedule": "Reagendado",
            "maintain": "Mantido",
            "deny": "Solicitação Negada",
        }
        result_info = {
            "type": "post_schedule_issue_responded",
            "nir_reason_code": case.post_schedule_issue_reason,
            "nir_reason_label": get_post_schedule_issue_reason_label(case.post_schedule_issue_reason),
            "nir_message": case.post_schedule_issue_message,
            "response_action": case.post_schedule_issue_response_action,
            "response_action_label": issue_action_labels.get(
                case.post_schedule_issue_response_action, case.post_schedule_issue_response_action
            ),
            "response_message": case.post_schedule_issue_response_message,
            "appointment_at": case.appointment_at,
            "appointment_location": case.appointment_location,
            "appointment_instructions": case.appointment_instructions,
            "appointment_status": case.appointment_status,
        }

    if case.status == CaseStatus.CLEANED and not result_info:
        # Fallback para CLEANED sem resultado específico
        result_info = {
            "type": "accepted_scheduled",
            "appointment_at": case.appointment_at,
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "instructions": case.appointment_instructions or "",
            "doctor_display": case.doctor_display,
        }

    return result_info


@login_required
@role_required("nir")
@xframe_options_sameorigin
def closed_case_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve o PDF de um caso encerrado para NIR.

    Acesso permitido apenas para escopo histórico NIR.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )

    if not _is_historical_scope_nir(case):
        raise Http404("PDF não disponível para este caso.")

    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    response = FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Cache-Control"] = "no-store"
    return response


def _get_closed_case_attachment_or_404(case_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[Case, CaseAttachment]:
    """Busca e autoriza anexo para o escopo histórico NIR.

    Retorna (case, attachment) se autorizado.
    Levanta Http404 se o caso está fora do escopo histórico,
    o anexo está suprimido ou não pertence ao caso.
    """
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )

    if not _is_historical_scope_nir(case):
        raise Http404("Caso não está no escopo histórico NIR.")

    attachment = get_object_or_404(
        CaseAttachment,
        attachment_id=attachment_id,
        case=case,
        is_suppressed=False,
    )

    return case, attachment


@login_required
@role_required("nir")
@xframe_options_sameorigin
def closed_case_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """Serve um anexo protegido para NIR histórico.

    Acesso permitido apenas para NIR com papel ativo 'nir'
    e casos dentro do escopo histórico NIR.
    Anexos suprimidos retornam 404.
    Resposta inclui Cache-Control: no-store.
    """
    case, attachment = _get_closed_case_attachment_or_404(case_id, attachment_id)

    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@role_required("nir")
def closed_case_attachment_pdf_viewer(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponse:
    """Renderiza o viewer PDF mobile interno para anexo PDF do NIR histórico.

    Exige login e papel ativo 'nir'.
    Usa intake:closed_case_attachment como fonte protegida.
    Aplica a mesma autorização da rota binária.
    Retorna 404 se o anexo não for PDF.
    """
    case, attachment = _get_closed_case_attachment_or_404(case_id, attachment_id)

    if attachment.content_type != "application/pdf":
        raise Http404("Anexo não é um PDF.")

    back_url = resolve_safe_next_url(
        request,
        reverse("intake:closed_case_detail", args=[case.case_id]),
    )
    pdf_url = reverse("intake:closed_case_attachment", args=[case.case_id, attachment.attachment_id])

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
        },
    )


@login_required
@role_required("nir")
def attachment_pdf_viewer(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponse:
    """Renderiza o viewer PDF mobile interno para anexo PDF do NIR operacional.

    Exige login e papel ativo 'nir'.
    Usa intake:serve_attachment como fonte protegida.
    Bloqueia casos CLEANED.
    Retorna 404 se o anexo não for PDF ou estiver suprimido/inacessível.
    """
    case, attachment = _get_nir_attachment_or_404(case_id, attachment_id)

    if attachment.content_type != "application/pdf":
        raise Http404("Anexo não é um PDF.")

    back_url = resolve_safe_next_url(request, reverse("intake:case_detail", args=[case.case_id]))
    pdf_url = reverse("intake:serve_attachment", args=[case.case_id, attachment.attachment_id])

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
        },
    )


def _is_supported_image_attachment(attachment: CaseAttachment) -> bool:
    """Check if attachment is a supported image type (JPEG/PNG)."""
    return attachment.content_type in SUPPORTED_IMAGE_TYPES


@login_required
@role_required("nir")
def attachment_image_viewer(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponse:
    """Renderiza o viewer mobile interno para anexo imagem (JPEG/PNG) do NIR operacional.

    Exige login e papel ativo 'nir'.
    Usa intake:serve_attachment como fonte protegida.
    Bloqueia casos CLEANED.
    Retorna 404 se o anexo não for JPEG/PNG ou estiver suprimido/inacessível.
    """
    case, attachment = _get_nir_attachment_or_404(case_id, attachment_id)

    if not _is_supported_image_attachment(attachment):
        raise Http404("Anexo não é uma imagem suportada (JPEG/PNG).")

    back_url = resolve_safe_next_url(request, reverse("intake:case_detail", args=[case.case_id]))
    image_url = reverse("intake:serve_attachment", args=[case.case_id, attachment.attachment_id])

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
        },
    )


@login_required
@role_required("nir")
def closed_case_attachment_image_viewer(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponse:
    """Renderiza o viewer mobile interno para anexo imagem (JPEG/PNG) do NIR histórico.

    Exige login e papel ativo 'nir'.
    Usa intake:closed_case_attachment como fonte protegida.
    Aplica a mesma autorização da rota binária histórica.
    Retorna 404 se o anexo não for JPEG/PNG.
    """
    case, attachment = _get_closed_case_attachment_or_404(case_id, attachment_id)

    if not _is_supported_image_attachment(attachment):
        raise Http404("Anexo não é uma imagem suportada (JPEG/PNG).")

    back_url = resolve_safe_next_url(
        request,
        reverse("intake:closed_case_detail", args=[case.case_id]),
    )
    image_url = reverse("intake:closed_case_attachment", args=[case.case_id, attachment.attachment_id])

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
        },
    )


@login_required
@role_required("nir")
def pdf_viewer(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Renderiza o viewer PDF mobile interno para NIR operacional.

    Exige login e papel ativo 'nir'.
    Usa intake:serve_pdf como fonte protegida.
    Bloqueia casos CLEANED (devem usar closed_case_pdf_viewer).
    """
    case = get_object_or_404(Case, pk=case_id)
    if case.status == CaseStatus.CLEANED:
        raise Http404("PDF de caso concluído não está disponível na fila operacional.")
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    back_url = resolve_safe_next_url(request, reverse("intake:case_detail", args=[case.case_id]))

    pdf_url = reverse("intake:serve_pdf", args=[case.case_id])

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
        },
    )


@login_required
@role_required("nir")
def closed_case_pdf_viewer(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Renderiza o viewer PDF mobile interno para detalhe histórico NIR.

    Exige login e papel ativo 'nir'.
    Usa intake:closed_case_pdf como fonte protegida.
    """
    case = get_object_or_404(Case, pk=case_id)
    if not _is_historical_scope_nir(case):
        raise Http404("PDF não disponível para este caso.")
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    back_url = resolve_safe_next_url(request, reverse("intake:closed_case_detail", args=[case.case_id]))

    pdf_url = reverse("intake:closed_case_pdf", args=[case.case_id])

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
        },
    )


@login_required
@role_required("nir")
def post_schedule_issue_open(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Formulário NIR para abrir intercorrência pós-agendamento.

    GET: Exibe formulário com motivo e mensagem.
    POST: Valida e abre intercorrência via serviço de domínio.
    """
    from apps.cases.services import (
        get_post_acceptance_issue_ineligibility_reason,
        is_post_acceptance_issue_eligible,
        open_post_acceptance_issue,
    )

    from .forms import PostScheduleIssueForm

    case = get_object_or_404(Case, case_id=case_id)

    # Verificar elegibilidade (contexto scheduled)
    if not is_post_acceptance_issue_eligible(case, context="scheduled"):
        reason = get_post_acceptance_issue_ineligibility_reason(case, context="scheduled")
        return render(
            request,
            "intake/post_schedule_issue_form.html",
            {
                "case": case,
                "eligible": False,
                "ineligibility_reason": reason,
                "form": None,
                "patient_name": case.patient_name,
            },
        )

    if request.method == "POST":
        form = PostScheduleIssueForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["reason"]
            message = form.cleaned_data.get("message", "")
            try:
                open_post_acceptance_issue(
                    case=case,
                    user=request.user,
                    reason=reason,
                    message=message,
                    context="scheduled",
                )
                messages.success(
                    request,
                    "Intercorrência registrada com sucesso. O caso foi enviado para o agendador.",
                )
                return redirect("intake:closed_cases_search")
            except ValueError as exc:
                messages.warning(request, str(exc))
        # Se form inválido, renderiza com erros
        return render(
            request,
            "intake/post_schedule_issue_form.html",
            {
                "case": case,
                "eligible": True,
                "form": form,
                "patient_name": case.patient_name,
            },
        )

    # GET: exibir formulário vazio
    form = PostScheduleIssueForm()
    return render(
        request,
        "intake/post_schedule_issue_form.html",
        {
            "case": case,
            "eligible": True,
            "form": form,
            "patient_name": case.patient_name,
        },
    )
