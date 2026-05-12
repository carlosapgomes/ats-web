"""Seed initial LLM prompt templates — idempotent management command.

Creates version 1 of each prompt template with starter content.
Safe to run multiple times — skips if prompts already exist.

Usage:
    uv run python manage.py seed_prompts --settings=config.settings.dev
"""

from django.core.management.base import BaseCommand

from apps.llm.models import PromptTemplate

# Prompt names used by the pipeline orchestrator
PROMPT_NAMES = [
    "llm1_system_prompt",
    "llm1_user_prompt",
    "llm2_system_prompt",
    "llm2_user_prompt",
]

DEFAULT_CONTENTS = {
    "llm1_system_prompt": (
        "Você é um assistente médico especializado em triagem de endoscopia digestiva alta (EDA). "
        "Analise o relatório do paciente e extraia dados estruturados em JSON.\n\n"
        "Campos obrigatórios:\n"
        "- patient: name, age, sex\n"
        "- exam_findings: lista de achados endoscópicos\n"
        "- clinical_indication: indicação clínica do exame\n"
        "- urgency: elective | urgent | emergency\n\n"
        "Responda APENAS com JSON válido."
    ),
    "llm1_user_prompt": (
        "Analise o seguinte relatório de endoscopia e extraia os dados estruturados.\n\n"
        "ID do caso: {case_id}\n\n"
        "Relatório:\n{extracted_text}"
    ),
    "llm2_system_prompt": (
        "Você é um assistente médico especializado em triagem de EDA. "
        "Com base nos dados estruturados e na política de triagem, gere uma recomendação.\n\n"
        "Campos obrigatórios na resposta:\n"
        "- summary_text: resumo em linguagem clara para o médico\n"
        "- suggested_action.support_recommendation: none | partial | full\n"
        "- suggested_action.suggestion: scheduled | immediate\n"
        "- confidence: 0.0 a 1.0\n"
        "- reasoning: justificativa da recomendação\n\n"
        "Responda APENAS com JSON válido."
    ),
    "llm2_user_prompt": (
        "Dados estruturados do caso:\n{llm1_structured_data}\n\n"
        "Caso anterior (se houver):\n{prior_case}\n\n"
        "ID do caso: {case_id}\n\n"
        "Gere a recomendação de triagem."
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

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_count} created, {skipped_count} skipped."
            )
        )
