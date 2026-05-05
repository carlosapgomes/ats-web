"""Views do app intake."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseStatus

from .forms import CaseUploadForm
from .pdf_utils import extract_pdf_text

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
        if form.is_valid():
            case = Case.objects.create(
                created_by=user,
                agency_record_number=form.cleaned_data["agency_record_number"],
            )
            # Salvar PDF
            case.pdf_file = form.cleaned_data["pdf_file"]
            case.save()

            # FSM: NEW → R1_ACK_PROCESSING → EXTRACTING
            case.start_processing(user=user)
            case.save()
            case.start_extraction(user=user)
            case.save()

            # Extrair texto do PDF
            extracted = extract_pdf_text(case.pdf_file.path)
            case.extracted_text = extracted
            case.agency_record_extracted_at = timezone.now()
            case.save()

            # Marcar extração como concluída com sucesso → LLM_STRUCT
            case.extraction_complete(success=True, user=user)
            case.save()

            messages.success(request, "Encaminhamento enviado com sucesso.")
            return redirect("intake:case_detail", case_id=case.case_id)
    else:
        form = CaseUploadForm()

    # Casos recentes do NIR logado
    recent_cases = Case.objects.filter(created_by=user).exclude(status="CLEANED").order_by("-created_at")[:10]

    return render(
        request,
        "intake/intake_home.html",
        {
            "form": form,
            "recent_cases": recent_cases,
        },
    )


@login_required
@role_required("nir")
def my_cases(request: HttpRequest) -> HttpResponse:
    """Lista de 'Meus Casos' do NIR — cards com filtros."""
    user = request.user
    assert user.is_authenticated

    qs = (
        Case.objects.filter(
            created_by=user,
        )
        .exclude(status="CLEANED")
        .order_by("-created_at")
    )

    # Filtro por status
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Busca por número de registro
    search = request.GET.get("q", "")
    if search:
        qs = qs.filter(agency_record_number__icontains=search)

    # Prepara dados enriquecidos: label + css class por caso
    case_data = [
        {
            "case": c,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
        }
        for c in qs
    ]

    return render(
        request,
        "intake/my_cases.html",
        {
            "case_data": case_data,
            "status_filter": status_filter,
            "search": search,
            "status_labels": STATUS_LABELS,
            "status_css": STATUS_CSS_CLASS,
        },
    )


@login_required
@role_required("nir")
def case_detail(request: HttpRequest, case_id: str) -> HttpResponse:
    """Detalhes de um caso para o NIR — timeline, stepper e PDF inline."""
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
        created_by=request.user,
    )
    events = case.events.all()

    current_step_idx = STEP_STATUS_INDEX.get(case.status, 0)

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

    return render(
        request,
        "intake/case_detail.html",
        {
            "case": case,
            "events": enriched_events,
            "steps": STEPS,
            "current_step_idx": current_step_idx,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "can_confirm_receipt": can_confirm,
        },
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
