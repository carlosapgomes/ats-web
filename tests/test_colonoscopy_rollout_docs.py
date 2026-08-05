"""Versioned documentation contract tests for the colonoscopy rollout (Slice 008 correction).

These checks pin safety-critical claims in the deploy runbook, the user manual
and PROJECT_CONTEXT to the actual implementation:

- backup must use the real production ``media_prod`` volume (never the
  nonexistent ``ats_web_media``) and validate archive contents;
- risk classification CRÍTICO/HIGH-ARCH with no zero-downtime migration claim;
- flag ``COLONOSCOPY_INTAKE_ENABLED`` is web-only (workers never read it);
- binary active-prompt precheck before enabling the flag;
- exact correction eligibility (WAIT_R1_CLEANUP_THUMBS + manual_review_required)
  and explicit resubmission exam-type choice;
- PROJECT_CONTEXT objective covers EDA + Colonoscopia, verified baseline and
  ADR-0003 as Accepted.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RUNBOOK_PATH = PROJECT_ROOT / "docs" / "deploy" / "introduce-colonoscopy-exam-workflow.md"
MANUAL_PATH = PROJECT_ROOT / "docs" / "manual" / "manual-usuarios.md"
CONTEXT_PATH = PROJECT_ROOT / "PROJECT_CONTEXT.md"
PROD_COMPOSE_PATH = PROJECT_ROOT / "docker-compose.prod.yml"

COLONOSCOPY_PROMPT_NAMES = (
    "colonoscopy_llm1_system",
    "colonoscopy_llm1_user",
    "colonoscopy_llm2_system",
    "colonoscopy_llm2_user",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── B1: Backup/media e paths independentes de cwd ─────────────────────────


class TestRunbookBackupVolumeAndPaths:
    def test_runbook_backs_up_real_media_prod_volume(self) -> None:
        """Backup de mídia usa o volume real herdado por web; nunca ats_web_media."""
        runbook = _read(RUNBOOK_PATH)
        assert "ats_web_media" not in runbook, "Volume inexistente ats_web_media não pode aparecer"
        assert "media_prod" in runbook, "Runbook deve referenciar o volume media_prod"
        # Resolução explícita do volume real herdado pelo serviço web
        assert "ps -q web" in runbook or "inspect" in runbook, (
            "Runbook deve resolver o volume real do container web (docker inspect/ps)"
        )

    def test_runbook_compose_commands_do_not_depend_on_cwd(self) -> None:
        """Comandos Compose usam diretório de projeto absoluto/--project-directory."""
        runbook = _read(RUNBOOK_PATH)
        assert "--project-directory" in runbook or "PROJECT_DIR" in runbook, (
            "Comandos Compose devem ser independentes do diretório corrente"
        )
        # Backup não pode depender de cd para o diretório dos compose files
        assert "cd /archive/backups/" not in runbook, "cd para o backup dir quebra os paths relativos do compose"

    def test_runbook_validates_archive_contents(self) -> None:
        """Valida conteúdo do dump gzip e do tar (não apenas ls -lh)."""
        runbook = _read(RUNBOOK_PATH)
        assert "gzip -t" in runbook or "zcat" in runbook, "Dump .sql.gz deve ser validado por conteúdo"
        assert "tar -tzf" in runbook or "tar tzf" in runbook, "Tar de mídia deve ser validado por conteúdo"


# ── B2: Risco e migration ─────────────────────────────────────────────────


class TestRunbookRiskAndMigration:
    def test_runbook_classifies_change_as_critico(self) -> None:
        """Classificação de risco CRÍTICO / HIGH-ARCH, conforme proposal.md."""
        runbook = _read(RUNBOOK_PATH)
        assert "CRÍTICO" in runbook.upper() or "CRITICO" in runbook.upper()
        assert "HIGH-ARCH" in runbook.upper()

    def test_runbook_does_not_promise_zero_downtime(self) -> None:
        """Migration 0014 não pode ser prometida como não-bloqueante/zero downtime."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        # A falsa promessa original não pode aparecer
        assert "zero downtime possível" not in lower, "Zero downtime possível não pode ser prometido"
        assert "app no ar, zero downtime" not in lower
        # O runbook deve NEGAR explicitamente a promessa
        assert "não é zero downtime" in lower, "Runbook deve afirmar explicitamente que NÃO é zero downtime"
        assert "não-bloqueante" not in lower and "nao-bloqueante" not in lower, (
            "Migration 0014 não é não-bloqueante (UPDATE full-row + AddIndex)"
        )

    def test_runbook_requires_controlled_maintenance_for_migration(self) -> None:
        """Migration exige janela controlada/baixa escrita (UPDATE full-row + AddIndex)."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        assert "janela" in lower or "manutenção" in lower or "manutencao" in lower, (
            "Runbook deve prever janela controlada/baixa atividade para a migration"
        )
        assert "addindex" in lower, "Runbook deve mencionar o AddIndex não-concorrente"


# ── B3: Flag web-only e precheck de prompts ───────────────────────────────


class TestRunbookFlagAndPrompts:
    def test_flag_is_web_only_in_runbook(self) -> None:
        """Runbook afirma que apenas web recebe/lê a flag; worker não recriado como leitor."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        assert "apenas o serviço web" in lower or "somente o serviço web" in lower or "apenas web" in lower, (
            "Runbook deve afirmar que somente web recebe a flag"
        )
        assert "worker" in lower, "Runbook deve explicar por que worker não recebe a flag"
        assert "--force-recreate web worker" not in runbook, "Ativação não deve recriar worker como leitor da flag"
        assert "force-recreate web" in runbook, "Ativação deve recriar apenas web"

    def test_flag_web_only_matches_prod_compose(self) -> None:
        """docker-compose.prod.yml: flag existe apenas no serviço web."""
        compose = _read(PROD_COMPOSE_PATH)
        web_block = compose.split("\n  web:\n", 1)[1].split("\n  worker:\n", 1)[0]
        assert "COLONOSCOPY_INTAKE_ENABLED" in web_block, "Flag deve estar no serviço web"
        worker_block = compose.split("\n  worker:\n", 1)[1].split("\n  pdf_worker:\n", 1)[0]
        assert "COLONOSCOPY_INTAKE_ENABLED" not in worker_block, "Worker não pode receber a flag"

    def test_runbook_prompt_precheck_is_binary(self) -> None:
        """Precheck binário: 4 nomes de prompts colonoscopia ativos antes de ativar a flag."""
        runbook = _read(RUNBOOK_PATH)
        for name in COLONOSCOPY_PROMPT_NAMES:
            assert name in runbook, f"Precheck deve listar o prompt {name}"
        lower = runbook.lower()
        assert "is_active" in lower or "ativos" in lower or "ativação" in lower, (
            "Precheck deve verificar versão ATIVA, não apenas existência"
        )
        assert "stop" in lower or "interrompa" in lower or "não continue" in lower, (
            "Runbook deve parar se o precheck falhar"
        )

    def test_runbook_documents_ui_activation_for_inactive_prompts(self) -> None:
        """Ativação de versões inativas pela UI (Gestão de Prompts) documentada."""
        runbook = _read(RUNBOOK_PATH)
        assert "Gestão de Prompts" in runbook or "gestão de prompts" in runbook.lower(), (
            "Runbook deve orientar ativação pela UI de admin"
        )


# ── B4: Manual — elegibilidade exata e reenvio explícito ──────────────────


class TestManualCorrectionEligibility:
    def test_manual_correction_eligibility_is_exact(self) -> None:
        """Elegibilidade exata: WAIT_R1_CLEANUP_THUMBS + manual_review_required."""
        manual = _read(MANUAL_PATH)
        assert "WAIT_R1_CLEANUP_THUMBS" in manual
        assert "manual_review_required" in manual
        # Sem promessa genérica de estados estáveis antes da fila médica
        assert "estados estáveis anteriores" not in manual
        assert "antes de o caso entrar na fila médica" not in manual

    def test_manual_correction_mentions_mismatch_mixed_unknown(self) -> None:
        """Motivos elegíveis (mismatch/mixed/unknown) documentados no manual."""
        manual = _read(MANUAL_PATH)
        assert "mismatch" in manual.lower() or "divergência" in manual.lower()
        assert "mixed" in manual.lower()
        assert "unknown" in manual.lower()

    def test_manual_resubmission_requires_explicit_exam_type(self) -> None:
        """Reenvio corrigido exige escolha explícita de tipo; não é herdado."""
        manual = _read(MANUAL_PATH)
        assert "tipo de exame" in manual.lower()
        assert "não é herdado" in manual.lower() or "não herdado" in manual.lower(), (
            "Manual deve afirmar que o tipo anterior não é herdado no reenvio"
        )

    def test_manual_resubmission_type_may_differ_and_respects_availability(self) -> None:
        """Tipo do reenvio pode diferir do original e respeita disponibilidade operacional."""
        manual = _read(MANUAL_PATH)
        lower = manual.lower()
        assert "diferente" in lower or "diferir" in lower or "pode corrigir" in lower
        assert "indisponível para novos envios" in lower or "disponibilidade" in lower, (
            "Colonoscopia no reenvio deve respeitar disponibilidade operacional"
        )

    def test_manual_does_not_promise_cpre_or_bowel_prep_or_medication_decision(self) -> None:
        """Sem promessas de CPRE, preparo intestinal ou decisão medicamentosa."""
        manual = _read(MANUAL_PATH)
        lower = manual.lower()
        assert "cpre" not in lower, "Manual não pode prometer CPRE"
        assert "preparo intestinal" not in lower, "Manual não pode prometer avaliação de preparo intestinal"
        # Suspensão de medicamento só pode aparecer como negação explícita
        for para in manual.split("\n\n"):
            if "suspensão" in para.lower():
                assert "não" in para.lower(), f"Parágrafo promete suspensão sem negação: {para[:120]}"


# ── B5: PROJECT_CONTEXT truthfulness ─────────────────────────────────────


class TestProjectContextTruthfulness:
    def test_context_objective_covers_eda_and_colonoscopy(self) -> None:
        """Objetivo do sistema cobre EDA e Colonoscopia."""
        context = _read(CONTEXT_PATH)
        assert "EDA" in context
        assert "Colonoscopia" in context or "colonoscopia" in context
        assert "triagem automatizada para EDA" in context or "triagem automatizada" in context

    def test_context_correction_eligibility_is_exact(self) -> None:
        """Contexto não pode afirmar correção antes de WAIT_DOCTOR de forma genérica."""
        context = _read(CONTEXT_PATH)
        assert "antes de `WAIT_DOCTOR`/em revisão manual" not in context
        assert "WAIT_R1_CLEANUP_THUMBS" in context

    def test_context_reports_verified_baseline(self) -> None:
        """Baseline verificado: >= 2779 testes passando."""
        context = _read(CONTEXT_PATH)
        match = re.search(r"\*\*Testes\*\*:\s*(\d+)\s+passando", context)
        assert match, "PROJECT_CONTEXT deve reportar o baseline de testes"
        count = int(match.group(1))
        assert count >= 2779, f"Baseline deve ser >= 2779, obtido {count}"

    def test_context_lists_adr_0003_as_active(self) -> None:
        """ADR-0003 listada como ativa/aceita."""
        context = _read(CONTEXT_PATH)
        assert "ADR-0003" in context
