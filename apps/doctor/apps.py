"""Django app configuration for the Doctor module."""

from django.apps import AppConfig


class DoctorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.doctor"
    verbose_name = "Médico"
