from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.decorators import role_required


@login_required
@role_required("nir")
def intake_home(request: HttpRequest) -> HttpResponse:
    """Dashboard do NIR — lista de casos e upload."""
    # Placeholder — será implementado nos próximos slices
    return render(request, "intake/intake_home.html", {})
