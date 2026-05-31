"""Views do app intake."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseStatus

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
    "LLM2_OK": "Análise IA (sugestão) concluída",
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
    "LLM2_OK": "system",
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
        cases, errors = process_uploaded_files(files, user)

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
    """Build context for full and HTMX NIR case-list renders."""
    user = request.user
    assert user.is_authenticated

    qs = (
        Case.objects.filter(
            created_by=user,
        )
        .exclude(status="CLEANED")
        .select_related("doctor")
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
def case_detail(request: HttpRequest, case_id: str) -> HttpResponse:
    """Detalhes de um caso para o NIR — timeline, stepper e PDF inline."""
    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
        created_by=request.user,
    )
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

    can_confirm = case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS

    # Prior case lookup — extrair informações do evento PRIOR_CASE_LOOKUP
    prior_case_lookup = None
    for e in events:
        if e.event_type == "PRIOR_CASE_LOOKUP":
            payload = e.payload or {}
            prior_case_lookup = {
                "prior_case_id": payload.get("prior_case_id", ""),
                "decision": payload.get("decision", ""),
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
            "result_info": result_info,
            "patient_name": patient_name,
            "prior_case_lookup": prior_case_lookup,
        },
    )


@login_required
@role_required("nir")
@xframe_options_sameorigin
def serve_pdf(request: HttpRequest, case_id: str) -> HttpResponseBase:
    """Serve o PDF original do caso para visualização inline no <embed>."""
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
        created_by=request.user,
    )
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    return FileResponse(
        case.pdf_file.open("rb"),
        content_type="application/pdf",
    )


@login_required
@role_required("nir")
def confirm_receipt(request: HttpRequest, case_id: str) -> HttpResponse:
    """Confirma recebimento do resultado final e conclui o caso."""
    case = get_object_or_404(
        Case,
        case_id=case_id,
        created_by=request.user,
    )

    if request.method == "POST" and case.status == CaseStatus.WAIT_R1_CLEANUP_THUMBS:
        case.cleanup_triggered(user=request.user)
        case.save()
        case.cleanup_completed(user=request.user)
        case.save()
        messages.success(request, "Recebimento confirmado. Caso concluído.")

    return redirect("intake:case_detail", case_id=case.case_id)
