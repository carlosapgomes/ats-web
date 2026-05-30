"""User and Role models for the ATS Web system."""

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
    def is_account_active(self) -> bool:
        return self.account_status == "active" and self.is_active
