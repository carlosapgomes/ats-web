"""Seed initial LLM prompt templates — idempotent management command.

Cutover 3.0 (design D5/D6 / ADR-0006): o seed é canônico para os QUATRO prompts
neutros ``exam_llm{1,2}_{system,user}``. Ao rodar, garante exatamente UMA versão
ativa por nome neutro com o conteúdo 3.0:

- se não há versão ativa, cria a próxima versão (v1 em banco novo);
- se a versão ativa tem conteúdo anterior (2.0), cria uma nova versão 3.0 e
  desativa as demais, sem apagar linhas/versões históricas;
- se a versão ativa já é 3.0, é no-op (idempotente).

Também desativa toda versão ATIVA dos oito nomes legados (``llm{1,2}_*`` e
``colonoscopy_llm{1,2}_*``), preservando o histórico para auditoria/rollback.

Usage:
    uv run python manage.py seed_prompts --settings=config.settings.dev
"""

from django.core.management.base import BaseCommand

from apps.llm.models import PromptTemplate
from apps.pipeline.llm1_service_v3 import (
    LLM1_V3_DEFAULT_SYSTEM_PROMPT,
    LLM1_V3_DEFAULT_USER_PROMPT,
)
from apps.pipeline.llm2_service_v3 import (
    LLM2_V3_DEFAULT_SYSTEM_PROMPT,
    LLM2_V3_DEFAULT_USER_PROMPT,
)

# Quatro prompts NEUTROS canônicos para novos jobs (dispatch 3.0).
PROMPT_NAMES = [
    "exam_llm1_system",
    "exam_llm1_user",
    "exam_llm2_system",
    "exam_llm2_user",
]

# Oito nomes legados (1.1) que deixam de participar do dispatch após o cutover.
# O seed desativa versões ativas existentes, mas NUNCA apaga linhas/versões.
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

# Default contents do contrato neutro 3.0.
DEFAULT_CONTENTS = {
    "exam_llm1_system": LLM1_V3_DEFAULT_SYSTEM_PROMPT,
    "exam_llm1_user": LLM1_V3_DEFAULT_USER_PROMPT,
    "exam_llm2_system": LLM2_V3_DEFAULT_SYSTEM_PROMPT,
    "exam_llm2_user": LLM2_V3_DEFAULT_USER_PROMPT,
}


class Command(BaseCommand):
    help = "Seed initial LLM prompt templates (idempotent)"

    def handle(self, *args: object, **options: object) -> None:
        created_count = 0
        skipped_count = 0

        # 1. Quatro nomes neutros: garante exatamente UMA versão ativa por nome
        # com o conteúdo 3.0. Se o ativo já é 3.0 → no-op; senão cria nova
        # versão ativa (max+1) e desativa as demais, sem reativar row antiga.
        for name in PROMPT_NAMES:
            content = DEFAULT_CONTENTS.get(name, "{case_id}")
            active = PromptTemplate.get_active(name)
            if active is not None and active.content == content:
                skipped_count += 1
                self.stdout.write(f"  Skipped (3.0 active exists): {name}")
                continue

            latest = PromptTemplate.objects.filter(name=name).order_by("-version").first()
            new_version = (latest.version + 1) if latest is not None else 1
            PromptTemplate.objects.filter(name=name, is_active=True).update(is_active=False)
            PromptTemplate.objects.create(
                name=name,
                version=new_version,
                content=content,
                is_active=True,
            )
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"  Created: {name} v{new_version} (3.0)"))

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
