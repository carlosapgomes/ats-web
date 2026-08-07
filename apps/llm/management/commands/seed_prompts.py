"""Seed initial LLM prompt templates — idempotent management command.

Slice 007 (D6/ADR-0004): o seed tornou-se canônico para os QUATRO prompts
neutros ``exam_llm{1,2}_{system,user}``. Ao rodar, ele garante exatamente uma
versão ativa por nome neutro (cria v1 ativa quando ausente) e desativa toda
versão ATIVA dos oito nomes legados (``llm{1,2}_*`` e ``colonoscopy_llm{1,2}_*``)
preservando linhas/versões históricas para auditoria/rollback. Reexecutar não
cria versões extras nem reativa nome antigo.

Usage:
    uv run python manage.py seed_prompts --settings=config.settings.dev
"""

from django.core.management.base import BaseCommand

from apps.llm.models import PromptTemplate
from apps.pipeline.llm1_service_v2 import (
    LLM1_V2_DEFAULT_SYSTEM_PROMPT,
    LLM1_V2_DEFAULT_USER_PROMPT,
)
from apps.pipeline.llm2_service_v2 import (
    LLM2_V2_DEFAULT_SYSTEM_PROMPT,
    LLM2_V2_DEFAULT_USER_PROMPT,
)

# Quatro prompts NEUTROS canônicos para novos jobs (dispatch v2 exclusivo,
# Slice 007). Seed/admin/fallback usam somente estes nomes.
PROMPT_NAMES = [
    "exam_llm1_system",
    "exam_llm1_user",
    "exam_llm2_system",
    "exam_llm2_user",
]

# Oito nomes legados (1.1) que deixam de participar do dispatch após o cutover.
# O seed desativa versões ativas existentes, mas NUNCA apaga linhas/versões —
# o histórico permanece consultável para auditoria/rollback.
LEGACY_PROMPT_NAMES = [
    "llm1_system",
    "llm1_user",
    "llm2_system",
    "llm2_user",
    "colonoscopy_llm1_system",
    "colonoscopy_llm1_user",
    "colonoscopy_llm2_system",
    "colonoscopy_llm2_user",
]

# Default contents portados do contrato neutro 2.0.
DEFAULT_CONTENTS = {
    "exam_llm1_system": LLM1_V2_DEFAULT_SYSTEM_PROMPT,
    "exam_llm1_user": LLM1_V2_DEFAULT_USER_PROMPT,
    "exam_llm2_system": LLM2_V2_DEFAULT_SYSTEM_PROMPT,
    "exam_llm2_user": LLM2_V2_DEFAULT_USER_PROMPT,
}


class Command(BaseCommand):
    help = "Seed initial LLM prompt templates (idempotent)"

    def handle(self, *args: object, **options: object) -> None:
        created_count = 0
        skipped_count = 0

        # 1. Quatro nomes neutros: garante exatamente UMA versão ativa por nome
        # (idempotente). Se já há ativo → no-op. Se só há versões inativas →
        # cria nova versão ativa (max+1), sem reativar row antiga via update.
        # Se nenhuma row existe → cria v1 ativa.
        for name in PROMPT_NAMES:
            if PromptTemplate.get_active(name) is not None:
                skipped_count += 1
                self.stdout.write(f"  Skipped (active exists): {name}")
                continue

            latest = PromptTemplate.objects.filter(name=name).order_by("-version").first()
            new_version = (latest.version + 1) if latest is not None else 1
            content = DEFAULT_CONTENTS.get(name, "{case_id}")
            PromptTemplate.objects.create(
                name=name,
                version=new_version,
                content=content,
                is_active=True,
            )
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"  Created: {name} v{new_version}"))

        # 2. Desativa toda versão ATIVA dos oito nomes legados (preserva
        # histórico). Idempotente: reexecutar é no-op (não reativa nada).
        deactivated_count = PromptTemplate.objects.filter(name__in=LEGACY_PROMPT_NAMES, is_active=True).update(
            is_active=False
        )
        if deactivated_count:
            self.stdout.write(self.style.WARNING(f"  Deactivated {deactivated_count} active legacy prompt version(s)."))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_count} created, {skipped_count} skipped, {deactivated_count} deactivated."
            )
        )
