"""Tests for the seed_prompts management command."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.llm.models import PromptTemplate


@pytest.mark.django_db
class TestSeedPromptsCanonicalNames:
    """seed_prompts must use canonical names (no _prompt suffix)."""

    CANONICAL_NAMES = ["llm1_system", "llm1_user", "llm2_system", "llm2_user"]
    DEPRECATED_NAMES = [
        "llm1_system_prompt",
        "llm1_user_prompt",
        "llm2_system_prompt",
        "llm2_user_prompt",
    ]

    def test_creates_all_canonical_names(self) -> None:
        """seed_prompts creates all 4 canonical prompt names."""
        assert not PromptTemplate.objects.exists()
        call_command("seed_prompts")
        for name in self.CANONICAL_NAMES:
            assert PromptTemplate.objects.filter(name=name).exists(), f"Missing: {name}"

    def test_does_not_create_deprecated_names(self) -> None:
        """seed_prompts does NOT create names with _prompt suffix."""
        call_command("seed_prompts")
        for name in self.DEPRECATED_NAMES:
            assert not PromptTemplate.objects.filter(name=name).exists(), f"Deprecated name should not exist: {name}"

    def test_each_prompt_is_active(self) -> None:
        """All seeded prompts are active."""
        call_command("seed_prompts")
        for name in self.CANONICAL_NAMES:
            pt = PromptTemplate.get_active(name)
            assert pt is not None, f"Missing active template: {name}"
            assert pt.is_active is True

    def test_idempotent(self) -> None:
        """Running seed_prompts twice is safe."""
        call_command("seed_prompts")
        count1 = PromptTemplate.objects.count()
        call_command("seed_prompts")
        count2 = PromptTemplate.objects.count()
        assert count1 == count2
        assert count1 == 4  # exactly 4 prompts

    def test_no_endoscopy_fallback(self) -> None:
        """Seed content must NOT reference 'relatório de endoscopia'."""
        call_command("seed_prompts")
        for pt in PromptTemplate.objects.all():
            assert "relatório de endoscopia" not in pt.content.lower(), (
                f"Prompt {pt.name} contains 'relatório de endoscopia'"
            )
            assert "achados endoscópicos" not in pt.content.lower(), f"Prompt {pt.name} contains 'achados endoscópicos'"
