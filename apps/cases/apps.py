from django.apps import AppConfig


class CasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cases"

    def ready(self) -> None:
        import apps.cases.signals  # noqa: F401
