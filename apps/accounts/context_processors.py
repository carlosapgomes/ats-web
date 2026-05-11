"""Context processors for the accounts app."""

from apps.cases.models import Case, CaseStatus

ROLE_DISPLAY_NAMES = {
    "nir": "NIR",
    "doctor": "Médico",
    "scheduler": "Agendador",
    "manager": "Supervisor",
    "admin": "Administrador",
}


def role_context(request):  # type: ignore[no-untyped-def]
    """Adiciona active_role_display ao contexto de todos os templates."""
    active_role = request.session.get("active_role", "")
    return {
        "active_role_display": ROLE_DISPLAY_NAMES.get(active_role, active_role),
    }


def queue_counts(request):  # type: ignore[no-untyped-def]
    """Adiciona queue_count ao contexto baseado no papel ativo.

    Doctor: conta casos em WAIT_DOCTOR.
    Scheduler: conta casos em WAIT_APPT.
    Outros papéis: retorna dict vazio.
    """
    if not request.user.is_authenticated:
        return {}
    active_role = request.session.get("active_role", "")
    if active_role == "doctor":
        count = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count()
        return {"queue_count": count}
    if active_role == "scheduler":
        count = Case.objects.filter(status=CaseStatus.WAIT_APPT).count()
        return {"queue_count": count}
    return {}
