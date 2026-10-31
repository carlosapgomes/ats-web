"""Encerra casos WAIT_DOCTOR sem lock válido (rotina 06h, Slice 002).

Execução: fecha via `close_unevaluated_wait_doctor_cases` com ator sistema e
motivo `not_evaluated_by_doctor`. `--dry-run` classifica e reporta sem travar
linhas nem escrever.

O relatório é operacional (contagens + ids + responsável pelo lock, nunca
texto clínico). Exit 0 sempre: pulados não são erro.

Verificação da execução diária (R5 do slice 003):
- admin do django-q2 → Schedules → `auto-close-unevaluated-06h` (última task,
  próximo `next_run` em 06:00 America/Bahia);
- log do worker `llm` (`... created a task from schedule [auto-...]`);
- este command com `--dry-run` a qualquer hora (só leitura).
Semântica de falta: clusters com `catch_up: False` — worker fora do ar às
06:00 = execução pulada sem back-fill (tolerado pelo desenho idempotente).

Usage:
    uv run python manage.py auto_close_unevaluated_cases --settings=config.settings.dev
    uv run python manage.py auto_close_unevaluated_cases --dry-run --settings=config.settings.dev
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.cases.services import close_unevaluated_wait_doctor_cases


class Command(BaseCommand):
    help = "Encerra casos parados em WAIT_DOCTOR sem lock válido (rotina 06h)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Classifica e reporta sem travar linhas nem escrever.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = bool(options["dry_run"])
        result = close_unevaluated_wait_doctor_cases(dry_run=dry_run)
        mode = "DRY-RUN (sem escrita)" if dry_run else "EXECUÇÃO"
        self.stdout.write(
            f"{mode}: closed={result.closed} "
            f"skipped_locked={result.skipped_locked} "
            f"skipped_changed={result.skipped_changed}"
        )
        for entry in result.skipped_locked_entries:
            self.stdout.write(f"  lock válido mantido: {entry}")
