"""Seed initial LLM prompt templates — idempotent management command.

Creates version 1 of each prompt template with starter content.
Safe to run multiple times — skips if prompts already exist.

Usage:
    uv run python manage.py seed_prompts --settings=config.settings.dev
"""

from django.core.management.base import BaseCommand

from apps.llm.models import PromptTemplate

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
    "llm1_system": (
        "Voce e um assistente clinico para triagem de Endoscopia Digestiva Alta "
        "(EDA). Retorne APENAS JSON valido que siga estritamente o schema_version "
        "1.1. Escreva todos os campos narrativos em portugues brasileiro (pt-BR). "
        "Nao use palavras em ingles nos campos narrativos. Nao inclua markdown, "
        "blocos de codigo ou chaves extras. Nao invente fatos; use null/unknown "
        "quando faltar informacao. Classifique o procedimento EDA suportado com "
        "subtype em standard, gastrostomy, esophageal_dilation ou foreign_body. "
        "Estime ASA pratico apenas nos buckets I-II, III ou mais, ou "
        "insufficient_data, sempre de forma conservadora e baseada no texto. "
        "Nao inferir Mallampati ou risco OSA. "
        "Extraia origin_context (cidade/hospital/unidade/UF) quando disponivel. "
        "Identifique tracked_exams com recencia por data/hora ou posicao textual. "
        "Registre had_transfusion como binario (yes/no); ausencia de evidencia "
        "de transfusao deve ser tratada como 'no'."
    ),
    "llm1_user": (
        "Tarefa: extrair dados estruturados e gerar resumo conciso de triagem "
        "a partir de um relatorio clinico para triagem EDA. Exigir evidencia "
        "textual explicita para cada campo objetivo. Quando nao houver evidencia "
        "textual, retornar unknown (ou null para numericos). Preencher "
        "preop_screening.rulebook_signals para o novo rulebook, incluindo exames "
        "minimos, exames condicionais, subtipo EDA suportado e contexto de "
        "paciente pediatrico. Incluir preop_screening.evidence_spans com "
        "field_path e excerpt sempre que houver evidencia. "
        "Extrair origin_context (cidade/hospital/unidade/UF) quando disponivel "
        "no texto. Identificar exames rastreados (tracked_exams) com recencia "
        "determinada por data/hora ou posicao textual, com desempate pela ultima "
        "ocorrencia. Registrar had_transfusion como binario (yes/no); ausencia de "
        "evidencia de transfusao deve ser tratada como 'no'."
    ),
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
