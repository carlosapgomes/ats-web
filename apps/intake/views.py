"""Views do app intake."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.cases.models import Case

from .forms import CaseUploadForm
from .pdf_utils import extract_pdf_text


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
def case_detail(request: HttpRequest, case_id: str) -> HttpResponse:
    """Detalhes de um caso para o NIR."""
    case = get_object_or_404(Case.objects.select_related("created_by"), case_id=case_id)
    events = case.events.all()

    return render(
        request,
        "intake/upload_success.html",
        {
            "case": case,
            "events": events,
        },
    )
