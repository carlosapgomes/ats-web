"""Context processors for the accounts app."""

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
