"""User and Role models for the ATS Web system."""

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class ProfessionalCouncil(models.TextChoices):
    """Conselhos profissionais disponíveis."""

    COREN = "COREN", "COREN"
    CRM = "CRM", "CRM"


class Role(models.Model):
    """Papel do usuário no sistema. Um usuário pode ter múltiplos papéis."""

    name = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name = "Papel"
        verbose_name_plural = "Papéis"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """Usuário customizado com multi-role e status de conta."""

    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    account_status = models.CharField(
        max_length=10,
        choices=[
            ("active", "Active"),
            ("blocked", "Blocked"),
            ("removed", "Removed"),
        ],
        default="active",
    )

    professional_council = models.CharField(
        "Conselho profissional",
        max_length=10,
        choices=ProfessionalCouncil.choices,
        blank=True,
    )
    professional_council_number = models.CharField(
        "Número do conselho profissional",
        max_length=30,
        blank=True,
    )

    def clean(self) -> None:
        super().clean()
        has_council = bool(self.professional_council)
        has_number = bool(self.professional_council_number)
        if has_council != has_number:
            raise ValidationError("Os campos de conselho profissional devem ser preenchidos juntos ou ambos vazios.")

    @property
    def display_name(self) -> str:
        """Nome preferencial: full name ou fallback para username."""
        return self.get_full_name() or self.username

    @property
    def professional_registration_display(self) -> str:
        """Registro profissional formatado: ex: 'CRM 12345' ou '' se vazio."""
        if self.professional_council and self.professional_council_number:
            return f"{self.professional_council} {self.professional_council_number}"
        return ""

    @property
    def is_account_active(self) -> bool:
        return self.account_status == "active" and self.is_active


class UserNotification(models.Model):
    """Notificação in-app para um usuário destinatário.

    Criada quando uma menção (@role ou @username) é detectada
    em uma mensagem de comunicação operacional (CaseCommunicationMessage).
    """

    notification_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    case = models.ForeignKey(
        "cases.Case",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    communication_message = models.ForeignKey(
        "cases.CaseCommunicationMessage",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_triggered",
    )
    notification_type = models.CharField(max_length=60, default="case_communication_mention")
    title = models.CharField(max_length=160)
    body_preview = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "created_at"]),
            models.Index(fields=["case", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "communication_message"],
                name="unique_notification_per_recipient_message",
            )
        ]

    def __str__(self) -> str:
        return f"UserNotification {self.notification_id} -> {self.recipient}"
