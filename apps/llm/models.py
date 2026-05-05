"""LLM models — PromptTemplate versionado."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PromptTemplate(models.Model):
    """Template de prompt versionado para LLM.

    Apenas 1 versão pode estar ativa por nome.
    A constraint é garantida em nível de aplicação (clean/save)
    e via unique constraint parcial no banco.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    version = models.PositiveIntegerField()
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = [("name", "version")]
        ordering = ["-name", "-version"]
        indexes = [
            models.Index(fields=["name", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} v{self.version} {'[active]' if self.is_active else ''}"

    def clean(self) -> None:
        super().clean()
        if self.is_active:
            # Garantir apenas 1 ativo por nome
            active = PromptTemplate.objects.filter(name=self.name, is_active=True).exclude(pk=self.pk)
            if active.exists():
                raise ValidationError(
                    f"Já existe uma versão ativa para '{self.name}'. Desative a versão atual antes de ativar esta."
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls, name: str) -> PromptTemplate | None:
        """Retorna a versão ativa do prompt pelo nome."""
        return cls.objects.filter(name=name, is_active=True).first()

    def activate(self, user: object = None) -> None:
        """Ativa esta versão e desativa as demais do mesmo nome."""
        PromptTemplate.objects.filter(name=self.name, is_active=True).exclude(pk=self.pk).update(is_active=False)
        self.is_active = True
        self.updated_by = user  # type: ignore[assignment]
        self.save()

    def deactivate(self, user: object = None) -> None:
        """Desativa esta versão."""
        self.is_active = False
        self.updated_by = user  # type: ignore[assignment]
        self.save()
