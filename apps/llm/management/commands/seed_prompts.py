"""Seed initial LLM prompt templates — idempotent management command.

Creates version 1 of each prompt template with starter content.
Safe to run multiple times — skips if prompts already exist.

Usage:
    uv run python manage.py seed_prompts --settings=config.settings.dev
"""

from django.core.management.base import BaseCommand

from apps.llm.models import PromptTemplate
from apps.pipeline.llm1_service import LLM1_DEFAULT_SYSTEM_PROMPT, LLM1_DEFAULT_USER_PROMPT

# Canonical prompt names matching the legacy system and admin UI.
PROMPT_NAMES = [
    "llm1_system",
    "llm1_user",
    "llm2_system",
    "llm2_user",
]

# Default contents ported from the legacy augmented-triage-system.
# llm1: most recent versions (v6 from 0018_prompt_templates_llm1_ptbr_v6).
# llm2: most recent versions (v3 from 0005_prompt_templates_ptbr_v3).
DEFAULT_CONTENTS = {
    "llm1_system": LLM1_DEFAULT_SYSTEM_PROMPT,
    "llm1_user": LLM1_DEFAULT_USER_PROMPT,
    "llm2_system": (
        "Voce e um assistente de apoio a decisao clinica para triagem de "
        "Endoscopia Digestiva Alta (EDA). Retorne APENAS JSON valido que siga "
        "estritamente o schema_version 1.1. Escreva todos os campos narrativos em "
        "portugues brasileiro (pt-BR). Nao use palavras em ingles nos campos "
        "narrativos. Use apenas valores de enum permitidos para suggestion e "
        "support_recommendation. Nao inclua markdown, blocos de codigo ou chaves "
        "extras."
    ),
    "llm2_user": (
        "Tarefa: sugerir accept/deny e recomendacao de suporte para triagem EDA "
        "usando dados estruturados do LLM1 e contexto de caso anterior. "
        "Nao use palavras em ingles nos campos narrativos."
    ),
}


class Command(BaseCommand):
    help = "Seed initial LLM prompt templates (idempotent)"

    def handle(self, *args: object, **options: object) -> None:
        created_count = 0
        skipped_count = 0

        for name in PROMPT_NAMES:
            exists = PromptTemplate.objects.filter(name=name).exists()
            if exists:
                skipped_count += 1
                self.stdout.write(f"  Skipped (already exists): {name}")
                continue

            content = DEFAULT_CONTENTS.get(name, "{case_id}")
            PromptTemplate.objects.create(
                name=name,
                version=1,
                content=content,
                is_active=True,
            )
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"  Created: {name} v1"))

        self.stdout.write(self.style.SUCCESS(f"\nDone. {created_count} created, {skipped_count} skipped."))
