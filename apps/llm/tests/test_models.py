"""Tests for the PromptTemplate model."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.llm.models import PromptTemplate


class TestPromptTemplate:
    """Unit tests for PromptTemplate model."""

    def test_create_prompt_template(self, user) -> None:
        """Criar template com nome, versão e conteúdo."""
        pt = PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="You are an assistant...",
            updated_by=user,
        )
        assert pt.name == "llm1_system"
        assert pt.version == 1
        assert pt.content == "You are an assistant..."
        assert pt.is_active is True
        assert pt.id is not None

    def test_unique_name_version(self, user) -> None:
        """Não pode criar 2 templates com mesmo nome+versão."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="First version",
            updated_by=user,
        )
        with pytest.raises(ValidationError):
            PromptTemplate.objects.create(
                name="llm1_system",
                version=1,
                content="Duplicate version",
                updated_by=user,
            )

    def test_get_active_returns_active_version(self, user) -> None:
        """get_active retorna a versão ativa."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="v1 content",
            is_active=True,
            updated_by=user,
        )
        PromptTemplate.objects.create(
            name="llm1_system",
            version=2,
            content="v2 content",
            is_active=False,
            updated_by=user,
        )
        active = PromptTemplate.get_active("llm1_system")
        assert active is not None
        assert active.version == 1
        assert active.is_active is True

    def test_get_active_returns_none_when_no_active(self, user) -> None:
        """get_active retorna None se não há versão ativa."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="v1 content",
            is_active=False,
            updated_by=user,
        )
        active = PromptTemplate.get_active("llm1_system")
        assert active is None

    def test_activate_deactivates_others(self, user) -> None:
        """Ativar v2 desativa v1 automaticamente."""
        v1 = PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="v1 content",
            is_active=True,
            updated_by=user,
        )
        v2 = PromptTemplate.objects.create(
            name="llm1_system",
            version=2,
            content="v2 content",
            is_active=False,
            updated_by=user,
        )

        v2.activate(user=user)

        v1.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True

    def test_activate_sets_is_active(self, user) -> None:
        """activate() marca como ativo e define updated_by."""
        pt = PromptTemplate.objects.create(
            name="llm1_user",
            version=1,
            content="User prompt content",
            is_active=False,
            updated_by=user,
        )
        pt.activate(user=user)
        assert pt.is_active is True
        assert pt.updated_by == user

    def test_deactivate(self, user) -> None:
        """deactivate() marca como inativo."""
        pt = PromptTemplate.objects.create(
            name="llm1_user",
            version=1,
            content="User prompt content",
            is_active=True,
            updated_by=user,
        )
        pt.deactivate(user=user)
        assert pt.is_active is False
        assert pt.updated_by == user

    def test_cannot_have_two_active_same_name(self, user) -> None:
        """clean() rejeita salvar 2 ativos com mesmo nome."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="v1 content",
            is_active=True,
            updated_by=user,
        )
        v2 = PromptTemplate(
            name="llm1_system",
            version=2,
            content="v2 content",
            is_active=True,
            updated_by=user,
        )
        with pytest.raises(ValidationError) as exc_info:
            v2.save()
        assert "Já existe uma versão ativa" in str(exc_info.value)

    def test_different_names_can_both_be_active(self, user) -> None:
        """Nomes diferentes podem ter ativos independentes."""
        pt1 = PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="system prompt",
            is_active=True,
            updated_by=user,
        )
        pt2 = PromptTemplate.objects.create(
            name="llm1_user",
            version=1,
            content="user prompt",
            is_active=True,
            updated_by=user,
        )
        assert pt1.is_active is True
        assert pt2.is_active is True

    def test_str_representation(self, user) -> None:
        """__str__ mostra nome, versão e status de ativo."""
        pt = PromptTemplate.objects.create(
            name="llm1_system",
            version=3,
            content="Test content",
            is_active=True,
            updated_by=user,
        )
        assert "llm1_system" in str(pt)
        assert "v3" in str(pt)
        assert "[active]" in str(pt)
