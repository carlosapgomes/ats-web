"""Context processors for the accounts app."""

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import UserNotification
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


def app_display_name(request):  # type: ignore[no-untyped-def]
    """Adiciona app_display_name ao contexto de todos os templates.

    Lê de settings.APP_DISPLAY_NAME (configurável via env var APP_DISPLAY_NAME).
    Default: "ATS".
    """
    return {
        "app_display_name": getattr(settings, "APP_DISPLAY_NAME", "ATS"),
    }


def notification_unread_count(request):  # type: ignore[no-untyped-def]
    """Adiciona notification_unread_count ao contexto.

    Contagem de notificações não lidas para o usuário autenticado.
    """
    if not request.user.is_authenticated:
        return {}
    count = UserNotification.objects.filter(recipient=request.user, read_at__isnull=True).count()
    return {"notification_unread_count": count}


def queue_counts(request):  # type: ignore[no-untyped-def]
    """Adiciona queue_count ao contexto baseado no papel ativo.

    Doctor: conta casos em WAIT_DOCTOR.
    Scheduler: conta casos em WAIT_APPT + vindas imediatas do dia para ciência.
    Outros papéis: retorna dict vazio.
    """
    if not request.user.is_authenticated:
        return {}
    active_role = request.session.get("active_role", "")
    if active_role == "doctor":
        count = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).count()
        return {"queue_count": count}
    if active_role == "scheduler":
        today = timezone.localdate()
        count = Case.objects.filter(status=CaseStatus.WAIT_APPT).count()
        count += (
            Case.objects.filter(
                doctor_admission_flow="immediate",
                events__event_type="IMMEDIATE_ADMISSION_OPERATIONAL_NOTICE",
                events__timestamp__date=today,
            )
            .exclude(status=CaseStatus.WAIT_APPT)
            .exclude(events__event_type="SCHEDULER_IMMEDIATE_ACK")
            .distinct()
            .count()
        )
        return {"queue_count": count}
    return {}
