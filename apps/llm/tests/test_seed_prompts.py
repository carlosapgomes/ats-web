"""Tests for the seed_prompts management command."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.llm.models import PromptTemplate
from apps.pipeline.llm1_service import LLM1_DEFAULT_USER_PROMPT


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

    def test_llm1_user_seed_contains_strict_schema_contract(self) -> None:
        """Seeded LLM1 user prompt must constrain the model to the Pydantic schema."""
        call_command("seed_prompts")
        pt = PromptTemplate.get_active("llm1_user")
        assert pt is not None
        assert "CONTRATO JSON OBRIGATORIO" in pt.content
        assert "language: exatamente" in pt.content
        assert "patient.sex" in pt.content
        assert "EvidenceFlag devem ser strings" in pt.content
        assert "NUNCA use estes nomes/aliases" in pt.content
        assert "age_years" in pt.content
        assert "triage_summary" in pt.content

    def test_llm1_user_seed_uses_updated_default_prompt_for_tracked_exam_hardening(self) -> None:
        """LLM1_USER seed usa LLM1_DEFAULT_USER_PROMPT atualizado com regras de hardening."""
        # Prova que DEFAULT_CONTENTS["llm1_user"] é LLM1_DEFAULT_USER_PROMPT
        from apps.llm.management.commands.seed_prompts import DEFAULT_CONTENTS

        assert DEFAULT_CONTENTS.get("llm1_user") is LLM1_DEFAULT_USER_PROMPT
        # Prove que o conteúdo semeado tem as regras de hardening
        call_command("seed_prompts")
        pt = PromptTemplate.get_active("llm1_user")
        assert pt is not None
        assert "sem exame" in pt.content.lower() or "Sem Exame" in pt.content
        assert "exam_datetime_iso" in pt.content
        assert "data do exame" in pt.content.lower() or "data dos exames" in pt.content.lower()
        assert "resumo" in pt.content.lower() or "summary" in pt.content.lower()
        assert "quando disponivel" in pt.content.lower()
