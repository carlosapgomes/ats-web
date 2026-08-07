"""Tests for the seed_prompts management command.

Slice 007 (D6/ADR-0004): o seed tornou-se canônico para os QUATRO prompts
neutros ``exam_llm{1,2}_{system,user}``. Ele garante exatamente uma versão
ativa por nome neutro (cria v1 ativa quando ausente) e desativa toda versão
ATIVA dos oito nomes legados, preservando linhas/versões históricas. Reexecutar
não cria versões extras nem reativa nome antigo.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.llm.models import PromptTemplate
from apps.pipeline.llm1_service import LLM1_DEFAULT_USER_PROMPT

NEUTRAL_NAMES = ["exam_llm1_system", "exam_llm1_user", "exam_llm2_system", "exam_llm2_user"]
LEGACY_NAMES = [
    "llm1_system",
    "llm1_user",
    "llm2_system",
    "llm2_user",
    "colonoscopy_llm1_system",
    "colonoscopy_llm1_user",
    "colonoscopy_llm2_system",
    "colonoscopy_llm2_user",
]
DEPRECATED_NAMES = [
    "llm1_system_prompt",
    "llm1_user_prompt",
    "llm2_system_prompt",
    "llm2_user_prompt",
]


@pytest.mark.django_db
class TestSeedPromptsNeutralCanonical:
    """seed_prompts usa somente os quatro nomes neutros (R3)."""

    def test_creates_all_neutral_names(self) -> None:
        """seed_prompts creates all 4 neutral prompt names."""
        assert not PromptTemplate.objects.exists()
        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            assert PromptTemplate.objects.filter(name=name).exists(), f"Missing: {name}"

    def test_does_not_create_deprecated_names(self) -> None:
        """seed_prompts does NOT create names with _prompt suffix."""
        call_command("seed_prompts")
        for name in DEPRECATED_NAMES:
            assert not PromptTemplate.objects.filter(name=name).exists(), f"Deprecated name should not exist: {name}"

    def test_does_not_create_legacy_names(self) -> None:
        """seed_prompts does NOT create the eight legacy (1.1) names."""
        call_command("seed_prompts")
        for name in LEGACY_NAMES:
            assert not PromptTemplate.objects.filter(name=name).exists(), f"Legacy name should not be created: {name}"

    def test_each_neutral_prompt_is_active(self) -> None:
        """All four seeded neutral prompts are active."""
        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            pt = PromptTemplate.get_active(name)
            assert pt is not None, f"Missing active template: {name}"
            assert pt.is_active is True

    def test_exactly_one_active_version_per_neutral_name(self) -> None:
        """R3: exactly one active version per neutral name after seed."""
        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            active_count = PromptTemplate.objects.filter(name=name, is_active=True).count()
            assert active_count == 1, f"{name} has {active_count} active versions"

    def test_idempotent(self) -> None:
        """Running seed_prompts twice is safe (4 neutral on fresh DB)."""
        call_command("seed_prompts")
        count1 = PromptTemplate.objects.count()
        call_command("seed_prompts")
        count2 = PromptTemplate.objects.count()
        assert count1 == count2
        # 4 neutros criados; nomes antigos não criados.
        assert count1 == 4

    def test_no_endoscopy_fallback(self) -> None:
        """Seed content must NOT reference 'relatório de endoscopia'."""
        call_command("seed_prompts")
        for pt in PromptTemplate.objects.all():
            assert "relatório de endoscopia" not in pt.content.lower(), (
                f"Prompt {pt.name} contains 'relatório de endoscopia'"
            )
            assert "achados endoscópicos" not in pt.content.lower(), f"Prompt {pt.name} contains 'achados endoscópicos'"


@pytest.mark.django_db
class TestSeedPromptsDeactivatesLegacy:
    """R4: oito nomes antigos ficam inativos, não apagados (histórico preservado)."""

    def test_seed_deactivates_active_legacy_versions_preserving_rows(self) -> None:
        """Active legacy versions are deactivated; rows/history remain."""
        for name in LEGACY_NAMES:
            PromptTemplate.objects.create(name=name, version=1, content=f"legacy {name}", is_active=True)

        call_command("seed_prompts")

        # 4 neutros ativos + 8 antigos inativos.
        for name in NEUTRAL_NAMES:
            assert PromptTemplate.get_active(name) is not None
        for name in LEGACY_NAMES:
            assert PromptTemplate.get_active(name) is None, f"{name} should be inactive"
            # Linha/versão histórica permanece consultável (não apagada).
            assert PromptTemplate.objects.filter(name=name).exists(), f"{name} history deleted"

    def test_seed_idempotent_does_not_reactivate_legacy(self) -> None:
        """Re-running seed never reactivates a legacy name."""
        for name in LEGACY_NAMES:
            PromptTemplate.objects.create(name=name, version=1, content="legacy", is_active=True)

        call_command("seed_prompts")
        call_command("seed_prompts")

        for name in LEGACY_NAMES:
            assert PromptTemplate.get_active(name) is None, f"{name} reactivated"
            assert PromptTemplate.objects.filter(name=name, version=1).count() == 1, f"{name} extra version"

    def test_seed_idempotent_does_not_create_extra_neutral_versions(self) -> None:
        """Re-running seed creates no extra neutral versions."""
        call_command("seed_prompts")
        call_command("seed_prompts")
        for name in NEUTRAL_NAMES:
            assert PromptTemplate.objects.filter(name=name).count() == 1, f"{name} extra version"

    def test_legacy_prompt_with_no_active_version_is_untouched(self) -> None:
        """A legacy name that is already inactive is neither deleted nor reactivated."""
        PromptTemplate.objects.create(name="llm1_system", version=1, content="legacy", is_active=False)
        call_command("seed_prompts")
        assert PromptTemplate.get_active("llm1_system") is None
        assert PromptTemplate.objects.filter(name="llm1_system").count() == 1


class TestLegacyLlm1UserDefaultContent:
    """Slice 007: conteúdo hardening do prompt LLM1 (1.1) permanece na constante
    legada (fallback de rollback) — não é mais gerenciado pelo seed, mas sua
    regressão é preservada desacoplada do seed.
    """

    def test_legacy_default_contains_strict_schema_contract(self) -> None:
        """LLM1 (1.1) default constrains the model to the Pydantic schema."""
        content = LLM1_DEFAULT_USER_PROMPT
        assert "CONTRATO JSON OBRIGATORIO" in content
        assert "language: exatamente" in content
        assert "patient.sex" in content
        assert "age_years" in content
        assert "triage_summary" in content

    def test_legacy_default_has_tracked_exam_hardening(self) -> None:
        """LLM1 (1.1) default carries tracked-exam/date hardening."""
        content = LLM1_DEFAULT_USER_PROMPT
        assert "sem exame" in content.lower() or "Sem Exame" in content
        assert "exam_datetime_iso" in content
        assert "data do exame" in content.lower() or "data dos exames" in content.lower()
        assert "resumo" in content.lower() or "summary" in content.lower()
        assert "quando disponivel" in content.lower()

    def test_legacy_default_mentions_caustic_ingestion(self) -> None:
        """LLM1 (1.1) default must mention caustic/corrosive ingestion."""
        content = LLM1_DEFAULT_USER_PROMPT
        has_caustica = "cáustica" in content.lower() or "caustica" in content.lower()
        has_corrosiva = "corrosiva" in content.lower() or "corrosivo" in content.lower()
        assert has_caustica or has_corrosiva, "LLM1 (1.1) default deve mencionar ingestão cáustica/corrosiva"
