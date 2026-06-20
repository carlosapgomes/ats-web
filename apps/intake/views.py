"""Views do app intake."""

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseAttachment, CaseStatus
from apps.cases.services import (
    acknowledge_post_schedule_issue,
    assert_case_lock,
    claim_case_lock,
    compute_lock_display,
    expire_stale_locks_for_statuses,
    get_post_schedule_issue_reason_label,
)
from apps.cases.services import (
    release_case_lock as release_lock_service,
)
from apps.cases.services import (
    renew_case_lock as renew_lock_service,
)

from .forms import CaseUploadForm
from .services import process_uploaded_files

STATUS_LABELS: dict[str, str] = {
    "NEW": "Novo",
    "R1_ACK_PROCESSING": "Processando",
    "EXTRACTING": "Extraindo dados",
    "LLM_STRUCT": "Análise IA (estrutura)",
    "LLM_SUGGEST": "Análise IA (sugestão)",
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
    "CASE_START_PROCESSING": "Processamento iniciado",
    "CASE_START_EXTRACTION": "Extração de dados iniciada",
    "CASE_EXTRACTION_OK": "Extração de dados concluída",
    "CASE_EXTRACTION_FAILED": "Falha na extração de dados",
    "LLM1_OK": "Análise IA (estrutura) concluída",
    "LLM1_FAILED": "Falha na análise IA (estrutura)",
    "LLM2_OK": "Análise IA (sugestão) concluída",
    "LLM2_FAILED": "Falha na análise IA (sugestão)",
    "CASE_READY_FOR_DOCTOR": "Caso enviado para avaliação médica",
    "DOCTOR_ACCEPT": "Aceito pelo médico",
    "DOCTOR_DENY": "Recusado pelo médico",
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
    # ── Scope gate ───────────────────────────────────────────
    "SCOPE_GATE_BYPASS": "Fora do escopo — revisão manual necessária",
    # ── Pipeline / sistema ────────────────────────────────────
    "EDA_SCOPE_GATED_MANUAL_REVIEW": "Encaminhado para revisão manual",
    "EDA_PREOP_POLICY_DECISION": "Política pré-operatória avaliada",
    "PIPELINE_FAILED": "Falha no processamento",
    "PRIOR_CASE_LOOKUP": "Casos anteriores consultados",
    "REGULATION_REPORT_GATE_FAILED": "Laudo de regulação inválido",
    # ── Work locks ────────────────────────────────────────────
    "WORK_LOCK_CLAIMED": "Caso reservado",
    "WORK_LOCK_RELEASED": "Reserva liberada",
    "WORK_LOCK_EXPIRED": "Reserva expirada",
    # ── Vinda imediata ────────────────────────────────────────
    "IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE": "Aviso de vinda imediata",
    "SCHEDULER_IMMEDIATE_ACK": "Ciência de vinda imediata",
    # ── Anexos ────────────────────────────────────────────────
    "CASE_ATTACHMENT_ADDED": "Anexo adicionado",
    # ── Encerramento administrativo ────────────────────────────
    "CASE_ADMINISTRATIVELY_CLOSED": "Encerrado administrativamente",
}

# Cores do dot da timeline por event_type
SUPPORT_FLAG_MAP: dict[str, str] = {
    "none": "Nenhum",
    "anesthesist": "Anestesista",
    "anesthesist_icu": "Anestesista + UTI",
}

ADMISSION_FLOW_MAP: dict[str, str] = {
    "scheduled": "Agendamento",
    "immediate": "Vinda Imediata",
}

EVENT_DOT_CSS: dict[str, str] = {
    "CASE_CREATED": "reception",
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
    # ── Scope gate ───────────────────────────────────────────
    "SCOPE_GATE_BYPASS": "system",
    # ── Pipeline / sistema ────────────────────────────────────
    "EDA_SCOPE_GATED_MANUAL_REVIEW": "system",
    "EDA_PREOP_POLICY_DECISION": "system",
    "PIPELINE_FAILED": "system",
    "PRIOR_CASE_LOOKUP": "system",
    "REGULATION_REPORT_GATE_FAILED": "system",
    # ── Work locks ────────────────────────────────────────────
    "WORK_LOCK_CLAIMED": "system",
    "WORK_LOCK_RELEASED": "system",
    "WORK_LOCK_EXPIRED": "system",
    # ── Vinda imediata ────────────────────────────────────────
    "IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE": "system",
    "SCHEDULER_IMMEDIATE_ACK": "scheduler",
    # ── Anexos ────────────────────────────────────────────────
    "CASE_ATTACHMENT_ADDED": "system",
    # ── Encerramento administrativo ────────────────────────────
    "CASE_ADMINISTRATIVELY_CLOSED": "system",
}

# Etapas do stepper
STEPS: list[dict[str, str]] = [
    {"icon": "📄", "label": "Upload"},
    {"icon": "🤖", "label": "Extração IA"},
    {"icon": "🩺", "label": "Avaliação Médica"},
    {"icon": "📅", "label": "Agendamento"},
    {"icon": "✅", "label": "Resultado Final"},
]


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
        cases, errors = process_uploaded_files(files, user, attachments=attachments or None)

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
    recent_cases = Case.objects.filter(created_by=user).exclude(status="CLEANED").order_by("-created_at")[:10]

    recent_cases_data = [
        {
            "case": c,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
        }
        for c in recent_cases
    ]

    return render(
        request,
        "intake/intake_home.html",
        {
            "form": form,
            "recent_cases": recent_cases_data,
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
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    search = request.GET.get("q", "")
    if search:
        qs = qs.filter(agency_record_number__icontains=search)

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
    ) and (case.doctor_decision == "deny" or case.doctor_admission_flow == "immediate")
    is_doctor_denied_final = terminal_without_scheduling and case.doctor_decision == "deny"
    is_immediate_final = terminal_without_scheduling and case.doctor_admission_flow == "immediate"
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

    # Active attachments (non-suppressed, ordered by created_at)
    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

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
    elif is_immediate_final:
        result_info = {
            "type": "accepted_immediate",
            "support": SUPPORT_FLAG_MAP.get(case.doctor_support_flag, case.doctor_support_flag),
            "flow": ADMISSION_FLOW_MAP.get(case.doctor_admission_flow, case.doctor_admission_flow),
            "doctor_display": case.doctor_display,
        }
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
            "can_confirm_receipt": can_confirm,
            "lock_token": lock_token or "",
            "lock_error": lock_error,
            "lock_locked_by_display": lock_locked_by_display or "",
            "lock_held": lock_held,
            "result_info": result_info,
            "patient_name": patient_name,
            "prior_case_lookup": prior_case_lookup,
            # Parametrização para template compartilhado
            "show_intake_nav": True,
            "back_url": reverse("intake:my_cases"),
            "back_label": "← Voltar para lista",
            "pdf_url": reverse("intake:serve_pdf", args=[case.case_id]),
            "attachments": active_attachments,
        },
    )


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

    return FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
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

    return FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )


@login_required
@role_required("nir")
def confirm_receipt(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Confirma recebimento do resultado final e conclui o caso.

    Qualquer NIR autorizado pode confirmar recebimento de um resultado
    pendente (WAIT_R1_CLEANUP_THUMBS), desde que possua a reserva (lock)
    válida com token e contexto 'nir_receipt'.

    Após confirmação, o caso vai para CLEANED e não fica mais acessível
    pela rota operacional NIR — redireciona para a lista.
    """
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)

    if case.status != CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        messages.warning(request, "Este caso não está aguardando confirmação de recebimento.")
        return redirect("intake:case_detail", case_id=case.case_id)

    # Validate lock token
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

    # Check lock validity before proceeding
    try:
        assert_case_lock(
            case=case,
            user=request.user,
            token=token,
            context="nir_receipt",
        )
    except PermissionError as exc:
        messages.warning(request, str(exc))
        return redirect("intake:case_detail", case_id=case.case_id)

    # Execute FSM transitions
    if case.post_schedule_issue_status == "responded":
        acknowledge_post_schedule_issue(case=case, user=request.user)
    else:
        case.cleanup_triggered(user=request.user)
        case.save()
        case.cleanup_completed(user=request.user)
        case.save()

    # Clear lock after completion
    case.locked_by = None
    case.locked_at = None
    case.locked_until = None
    case.lock_token = None
    case.lock_context = ""
    case.lock_role = ""
    case.save(
        update_fields=[
            "locked_by",
            "locked_at",
            "locked_until",
            "lock_token",
            "lock_context",
            "lock_role",
        ]
    )

    messages.success(request, "Recebimento confirmado. Caso concluído.")
    return redirect("intake:my_cases")


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
        get_post_schedule_issue_ineligibility_reason,
        is_post_schedule_issue_eligible,
    )

    query = request.GET.get("q", "").strip()
    results: list[dict[str, object]] = []

    if query:
        # Busca: casos CLEANED + casos com intercorrência ativa (qualquer status)
        qs = (
            Case.objects.filter(
                models.Q(status=CaseStatus.CLEANED) | models.Q(post_schedule_issue_status__in=["opened", "responded"])
            )
            .filter(
                models.Q(agency_record_number__icontains=query)
                | models.Q(structured_data__patient__name__icontains=query)
            )
            .order_by("-created_at")[:50]
        )

        for c in qs:
            eligible = is_post_schedule_issue_eligible(c)
            results.append(
                {
                    "case": c,
                    "eligible": eligible,
                    "ineligibility_reason": ("" if eligible else get_post_schedule_issue_ineligibility_reason(c)),
                    "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
                    "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
                    "patient_name": c.patient_name,
                    "has_active_issue": bool(c.post_schedule_issue_status),
                    "issue_status": c.post_schedule_issue_status or "",
                }
            )

    return render(
        request,
        "intake/closed_cases_search.html",
        {
            "query": query,
            "results": results,
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
        get_post_schedule_issue_ineligibility_reason,
        is_post_schedule_issue_eligible,
        open_post_schedule_issue,
    )

    from .forms import PostScheduleIssueForm

    case = get_object_or_404(Case, case_id=case_id)

    # Verificar elegibilidade
    if not is_post_schedule_issue_eligible(case):
        reason = get_post_schedule_issue_ineligibility_reason(case)
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
                open_post_schedule_issue(
                    case=case,
                    user=request.user,
                    reason=reason,
                    message=message,
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
