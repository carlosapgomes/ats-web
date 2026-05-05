"""User and Role models for the ATS Web system."""

from django.contrib.auth.models import AbstractUser
from django.db import models


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

    @property
    def is_account_active(self) -> bool:
        return self.account_status == "active" and self.is_active

    def get_active_role(self) -> str | None:
        """Retorna o papel ativo da sessão. Usado em views/middleware."""
        # O papel ativo real fica na sessão, não no model.
        return None
