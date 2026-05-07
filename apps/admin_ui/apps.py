"""App config for admin_ui."""

from django.apps import AppConfig


class AdminUiConfig(AppConfig):
    """Configuração do app admin_ui — gestão de usuários e prompts."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin_ui"
    verbose_name = "Administração"
