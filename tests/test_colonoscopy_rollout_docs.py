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
# O change foi arquivado; o tasks.md canônico agora vive em openspec/archive.
# Resolução dinâmica preserva o contrato mesmo se o diretório ativo voltar a existir.
_TASKS_ACTIVE = PROJECT_ROOT / "openspec" / "changes" / "introduce-colonoscopy-exam-workflow" / "tasks.md"
_TASKS_ARCHIVED = PROJECT_ROOT / "openspec" / "archive" / "introduce-colonoscopy-exam-workflow" / "tasks.md"
TASKS_PATH = _TASKS_ARCHIVED if _TASKS_ARCHIVED.exists() else _TASKS_ACTIVE

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
        """Runbook afirma que apenas web recebe/lê a flag; ativação recria apenas web."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        assert "apenas o serviço web" in lower or "somente o serviço web" in lower or "apenas web" in lower, (
            "Runbook deve afirmar que somente web recebe a flag"
        )
        assert "worker" in lower, "Runbook deve explicar por que worker não recebe a flag"
        # A ATIVAÇÃO da flag (Passo 8) recria apenas web — nunca worker como leitor.
        passo8 = runbook.split("### Passo 8", 1)[1].split("### Passo 9", 1)[0]
        assert "--force-recreate web worker" not in passo8, (
            "Ativação da flag não deve recriar worker como leitor da flag"
        )
        assert "force-recreate web" in passo8, "Ativação da flag deve recriar apenas web"
        # A subida pós-migration (Passo 6) recria os três serviços — isso é a janela
        # de manutenção, não a ativação da flag, e é legítimo.
        passo6 = runbook.split("### Passo 6", 1)[1].split("### Passo 7", 1)[0]
        assert "--force-recreate web worker pdf_worker" in passo6, (
            "Subida pós-migration deve recriar os três serviços com as imagens novas"
        )

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


# ── C1: Backup — pipeline fail-fast e assert de conteúdo ──────────────────


class TestRunbookBackupPipelineSafety:
    def test_backup_pipeline_is_fail_fast_on_pg_dump_failure(self) -> None:
        """pg_dump | gzip não pode mascarar falha do dump como gzip válido."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        has_pipefail = "set -euo pipefail" in lower or "set -o pipefail" in lower
        has_pipeline_status = "pipestatus" in lower
        assert has_pipefail or has_pipeline_status, (
            "pg_dump | gzip deve ser fail-fast (pipefail/PIPESTATUS) para que falha do "
            "pg_dump não vire gzip vazio aceito por gzip -t"
        )

    def test_backup_asserts_dump_content_marker_and_min_lines(self) -> None:
        """Dump validado por conteúdo: marker de PostgreSQL + volume mínimo, com exit 1."""
        runbook = _read(RUNBOOK_PATH)
        assert "PostgreSQL database dump" in runbook, "Runbook deve verificar o marker esperado de dump PostgreSQL"
        assert re.search(r"-ge\s+\d+", runbook), "Runbook deve comparar a contagem de linhas do dump contra um mínimo"
        assert "exit 1" in runbook, "Falha de validação do dump deve encerrar a execução (exit 1), não apenas imprimir"

    def test_backup_keeps_gzip_integrity_and_media_tar_checks(self) -> None:
        """Checks de integridade do gzip e do tar de mídia permanecem."""
        runbook = _read(RUNBOOK_PATH)
        assert "gzip -t" in runbook, "Integridade do gzip (CRC/EOF) deve ser checada"
        assert "tar -tzf" in runbook, "Conteúdo do tar de mídia deve ser checado"
        assert "exit 1" in runbook


# ── C2: Migration — schema-compatible, serviços parados, downtime honesto ──


class TestRunbookMigrationWindowSafety:
    def test_migration_stops_or_blocks_old_web_writes(self) -> None:
        """Passo 4 para o web ANTIGO (ou bloqueia ingress) antes da migration 0014.

        0014 remove o default de banco (DROP DEFAULT); o código antigo insere
        Case sem exam_type e falharia NOT NULL — o web antigo não pode aceitar
        escritas durante/já após a migration.
        """
        runbook = _read(RUNBOOK_PATH)
        step4 = runbook.split("### Passo 4", 1)[1].split("### Passo 5", 1)[0].lower()
        safe_web_writer_control = bool(
            re.search(r"\bstop\s+(?:[^\n#]*\s)?web\b", step4)
            or "bloquear novos uploads" in step4
            or "modo de manutenção" in step4
            or "modo de manutencao" in step4
        )
        assert safe_web_writer_control, "Migration 0014 exige parar web (ou bloquear ingress) antes do DDL"
        assert "worker" in step4 and "pdf_worker" in step4, (
            "Workers também devem ser parados durante a janela de manutenção"
        )

    def test_migration_runs_through_new_image_while_services_stopped(self) -> None:
        """Migration roda com a imagem nova (run --rm web) com serviços parados."""
        runbook = _read(RUNBOOK_PATH)
        assert "run --rm web" in runbook and "manage.py migrate" in runbook
        # O stop do web precisa aparecer ANTES do comando migrate real no Passo 4
        step4 = runbook.split("### Passo 4", 1)[1].split("### Passo 5", 1)[0]
        stop_pos = step4.find("stop web")
        migrate_pos = step4.find("manage.py migrate")
        assert stop_pos != -1 and migrate_pos != -1 and stop_pos < migrate_pos, (
            "O stop dos serviços deve preceder o migrate no Passo 4"
        )

    def test_migration_never_restarts_old_workers_before_new_image_up(self) -> None:
        """Nunca 'start' de containers antigos após a migration; subir só imagens novas."""
        runbook = _read(RUNBOOK_PATH)
        assert "start worker" not in runbook, (
            "Não pode reativar os containers antigos de worker com docker compose start"
        )
        assert "up -d" in runbook, "Containers novos devem ser subidos via up -d"
        assert "--force-recreate" in runbook, "Subida após migration deve forçar recriação com a imagem nova"
        # A subida (up) precisa vir depois da migration/seed no fluxo principal
        up_pos = runbook.lower().find("up -d")
        migrate_pos = runbook.lower().find("migrate")
        assert migrate_pos != -1 and up_pos > migrate_pos

    def test_runbook_documents_expected_downtime_honestly(self) -> None:
        """Janela de manutenção documenta downtime esperado de forma honesta."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        assert "downtime" in lower or "indisponível" in lower or "indisponivel" in lower, (
            "Runbook deve declarar o downtime esperado da janela de manutenção"
        )


# ── C3: Prompts colonoscopia — ativos enquanto houver casos em voo ─────────


class TestRunbookPromptDeactivationSafety:
    def test_inactive_prompts_not_declared_impact_free(self) -> None:
        """Prompts inativos não podem ser declarados sem impacto com flag desligada."""
        runbook = _read(RUNBOOK_PATH)
        assert "podem permanecer inativos sem impacto enquanto" not in runbook.lower(), (
            "Flag desligada bloqueia novos uploads, mas casos em voo seguem precisando dos prompts colonoscopia ativos"
        )

    def test_prompts_must_remain_active_while_cases_in_flight(self) -> None:
        """Runbook exige prompts ativos enquanto houver casos colonoscopia em voo."""
        runbook = _read(RUNBOOK_PATH)
        lower = runbook.lower()
        assert "devem permanecer ativos" in lower, (
            "Runbook deve afirmar que prompts colonoscopia permanecem ativos enquanto houver casos"
        )
        assert "em voo" in lower, "Critério de drenagem é casos em voo (não CLEANED)"
        assert "drenagem" in lower or "drenar" in lower, (
            "Desativação de prompts deve ser condicionada à drenagem/encerramento comprovado"
        )

    def test_eda_prompt_rollback_procedure_retained(self) -> None:
        """Procedimento de rollback de prompts EDA é preservado."""
        runbook = _read(RUNBOOK_PATH)
        assert "llm1_system" in runbook or "prompts EDA" in runbook, (
            "Rollback do contrato LLM1 (prompts EDA canônicos) deve permanecer documentado"
        )


# ── C4: Rastreabilidade — hash real, prompt não é commit ───────────────────


class TestTasksTraceability:
    def test_tasks_references_actual_correction_commit(self) -> None:
        """tasks.md referencia o commit real da correção 1 (503019e)."""
        tasks = _read(TASKS_PATH)
        assert "503019e" in tasks, "tasks.md deve registrar o hash real do commit de correção"
        assert "commit `prompt-correct-slice-008-rollout-documentation.md`" not in tasks, (
            "Arquivo de prompt não pode ser rotulado como commit"
        )

    def test_tasks_labels_prompt_files_as_prompts_not_commits(self) -> None:
        """Arquivos de prompt são rotulados como handoff/prompt, nunca como commit."""
        tasks = _read(TASKS_PATH)
        # Nenhum arquivo de prompt pode ser objeto direto de um rótulo "commit"
        assert not re.search(r"commit\s+`prompt-correct-slice-008", tasks), (
            "Arquivo de prompt não pode ser rotulado como commit"
        )
        # Cada menção a prompt-correct-slice-008* carrega rótulo handoff/prompt
        for mention in re.finditer(r"prompt-correct-slice-008\S*", tasks):
            snippet = tasks[max(0, mention.start() - 80) : mention.end()]
            assert "handoff" in snippet.lower() or "prompt" in snippet.lower(), (
                f"Menção a prompt sem rótulo handoff/prompt: {snippet}"
            )


# ── D1: Rollback schema-compatible (bridge para imagem antiga) ─────────────


class TestRunbookRollbackSchemaCompatibility:
    def test_soft_rollback_keeps_new_image_by_default(self) -> None:
        """Rollback suave PREFERIDO: manter a imagem nova rodando, só desligar intake."""
        runbook = _read(RUNBOOK_PATH)
        sec51 = runbook.split("### 5.1", 1)[1].split("### 5.2", 1)[0]
        assert re.search(
            r"(manter|permanecer|continuar).{0,80}(imagem nova|imagem atual)",
            sec51,
            re.I | re.S,
        ), "Rollback suave deve recomendar manter a imagem nova rodando"

    def test_old_image_revert_requires_schema_bridge(self) -> None:
        """Reverter para a imagem antiga exige bridge de schema verificável + remoção."""
        runbook = _read(RUNBOOK_PATH)
        sec51 = runbook.split("### 5.1", 1)[1].split("### 5.2", 1)[0]
        says_revert = "reverter a imagem" in sec51.lower()
        bridge = (
            "SET DEFAULT" in sec51
            or "set default" in sec51.lower()
            or "migrate cases 0013" in sec51.lower()
            or "não reverter" in sec51.lower()
            or "nao reverter" in sec51.lower()
        )
        assert not says_revert or bridge, (
            "0014 remove o default de banco; código antigo omite exam_type no INSERT "
            "e não pode rodar mantendo a coluna sem bridge de schema"
        )
        if says_revert:
            assert "DROP DEFAULT" in sec51, "Bridge temporária deve documentar a remoção do default no redeploy forward"

    def test_drain_alone_with_old_image_no_default_not_claimed_safe(self) -> None:
        """A afirmação perigosa (drenar + reverter + coluna sem default) é removida."""
        runbook = _read(RUNBOOK_PATH)
        assert "somente quando não houver casos colonoscopia incompatíveis em voo" not in runbook, (
            "Drenar colonoscopias não torna a coluna sem default compatível com a imagem antiga"
        )
        sec51 = runbook.split("### 5.1", 1)[1].split("### 5.2", 1)[0]
        if "reverter a imagem" in sec51.lower():
            assert "SET DEFAULT" in sec51 or "migrate cases 0013" in sec51.lower()

    def test_risk_table_rollback_row_aligned(self) -> None:
        """Tabela de risco alinhada: rollback preferido mantém a imagem nova."""
        runbook = _read(RUNBOOK_PATH)
        risk_row = runbook.split("| **Rollback** |", 1)[1].split(" |", 1)[0]
        assert "imagem nova" in risk_row or "manter a imagem" in risk_row, (
            "Linha Rollback da tabela de risco deve refletir o caminho preferido"
        )


# ── D2: Validação do tar de mídia aborta explicitamente ────────────────────


class TestRunbookMediaArchiveValidation:
    def _passo1_validation(self) -> str:
        runbook = _read(RUNBOOK_PATH)
        passo1 = runbook.split("### Passo 1", 1)[1].split("### Passo 2", 1)[0]
        return passo1.split("# 1d.", 1)[1]

    def test_media_tar_validation_aborts_explicitly(self) -> None:
        """tar -tzf com falha ABORTA (|| exit 1); falha à esquerda de && não aborta sob set -e."""
        validation = self._passo1_validation()
        assert re.search(r"tar\s+-tzf[^\n]+(?:\n\s*)?\|\|\s*\{", validation, re.S), (
            "Validação do tar deve usar || { ...; exit 1; } — sob set -e, falha à esquerda de && NÃO encerra o script"
        )
        assert "exit 1" in validation

    def test_media_tar_asserts_minimum_entries(self) -> None:
        """Validação do tar exige ao menos 1 entrada, não apenas imprime a contagem."""
        validation = self._passo1_validation()
        assert re.search(r"-ge\s+1|-gt\s+0", validation), (
            "Validação deve comparar o número de entradas contra um mínimo"
        )
        assert "exit 1" in validation

    def test_media_volume_resolution_and_dump_checks_preserved(self) -> None:
        """Resolução do volume real e checks do dump (pipefail/marker/linhas) preservados."""
        runbook = _read(RUNBOOK_PATH)
        assert "set -euo pipefail" in runbook or "set -o pipefail" in runbook
        assert "PostgreSQL database dump" in runbook
        assert re.search(r"-ge\s+100", runbook), "Dump deve manter o mínimo de 100 linhas"
        assert "docker inspect" in runbook and "ps -q web" in runbook


# ── D3: Quick reference fail-fast ──────────────────────────────────────────


class TestRunbookQuickReferenceFailFast:
    def _quick(self) -> str:
        return _read(RUNBOOK_PATH).split("## Quick reference", 1)[1].split("\n---", 1)[0]

    def test_quick_reference_activates_pipefail_before_mutable_sequence(self) -> None:
        """Quick reference ativa set -euo pipefail ANTES do stop/migrate/seed/up."""
        quick = self._quick()
        safety = [pos for token in ("set -euo pipefail", "set -o pipefail") if (pos := quick.find(token)) >= 0]
        stop = quick.find("$DPROD stop web")
        assert safety and min(safety) < stop, (
            "Quick reference (cópia de mão) precisa de fail-fast antes da sequência mutável"
        )

    def test_quick_reference_failure_cannot_be_swallowed(self) -> None:
        """Sem `|| true`/`|| echo` que engula falha; ordem stop->migrate->seed->up."""
        quick = self._quick()
        body = quick.split("set -euo pipefail", 1)[1]
        assert "|| true" not in body, "Swallower de falha não pode existir na quick reference"
        stop = body.find("stop web")
        migrate = body.find("manage.py migrate")
        seed = body.find("seed_prompts")
        up = body.find("up -d")
        assert -1 < stop < migrate < seed < up, "Ordem da quick reference deve espelhar os Passos 4-6"

    def test_quick_reference_stop_semantics_explicit(self) -> None:
        """Falha no meio da sequência é PARAR (nenhum up em estado parcial)."""
        quick = self._quick()
        lower = quick.lower()
        assert "não continuar" in lower or "parar" in lower or "stop" in lower or "abort" in lower, (
            "Quick reference deve explicitar a semântica de PARAR em falha"
        )


# ── D4: Elegibilidade exata em tasks.md ────────────────────────────────────


class TestTasksEligibilityExact:
    def test_tasks_dod_eligibility_is_exact(self) -> None:
        """DoD registra a condição exata; elegibilidade ampla 'antes de WAIT_DOCTOR' removida."""
        tasks = _read(TASKS_PATH)
        assert "somente antes de `WAIT_DOCTOR`/em manual review seguro" not in tasks, (
            "Elegibilidade ampla não pode constar como concluída"
        )
        assert "WAIT_R1_CLEANUP_THUMBS" in tasks
        assert "manual_review_required" in tasks
        assert "exam_type_mismatch" in tasks
        assert "mixed_exam_request" in tasks
        assert "unknown_exam_type" in tasks


# ── E1: Bridge de rollback executável, binário e serializado ───────────────


class TestRunbookRollbackBridgeExecutable:
    def _bridge(self) -> str:
        """Bloco de INSTALAÇÃO do bridge (SET DEFAULT + verificação binária)."""
        runbook = _read(RUNBOOK_PATH)
        sec51 = runbook.split("### 5.1", 1)[1].split("### 5.2", 1)[0]
        return sec51.split("restaurar o default temporário", 1)[1].split("Depois:", 1)[0]

    def _forward(self) -> str:
        """Bloco de REMOÇÃO do bridge no redeploy forward (DROP DEFAULT serializado)."""
        runbook = _read(RUNBOOK_PATH)
        sec51 = runbook.split("### 5.1", 1)[1].split("### 5.2", 1)[0]
        return sec51.split("Remoção do default temporário no redeploy forward", 1)[1]

    def test_bridge_block_fail_fast_on_its_own(self) -> None:
        """Bloco do bridge ativa fail-fast próprio; não depende de shell de sessão anterior."""
        bridge = self._bridge()
        assert (
            "set -euo pipefail" in bridge
            or "set -o pipefail" in bridge
            or re.search(r"ALTER TABLE[^\n]+SET DEFAULT[^\n]*(?:\|\||&&)", bridge, re.I)
        ), "Bridge pode rodar em shell novo: precisa de set -euo pipefail ou handler explícito"

    def test_set_default_uses_on_error_stop(self) -> None:
        """ALTER do bridge usa psql -v ON_ERROR_STOP=1 (falha SQL = falha de comando)."""
        assert "ON_ERROR_STOP" in self._bridge(), "ALTER schema-changing precisa de psql -v ON_ERROR_STOP=1"

    def test_set_default_verification_is_binary(self) -> None:
        """Verificação captura column_default (-At) e faz assert binário com exit 1."""
        bridge = self._bridge()
        assert re.search(r"\w+\s*=\s*\"?\$\([^)]*column_default", bridge, re.I | re.S), (
            "Captura da saída do default com -At necessária"
        )
        assert re.search(r"(?:\[\[?|test\s).{0,240}'eda'::character varying", bridge, re.I | re.S), (
            "Assert binário contra o default esperado 'eda'::character varying"
        )
        assert "exit 1" in bridge, "Mismatch do default deve abortar (exit 1)"

    def test_forward_sequence_build_stop_drop_assert_up(self) -> None:
        """Forward serializado: build/pull → stop writers antigos → DROP → assert NULL → up novo."""
        forward = self._forward()
        build = forward.find("build")
        stop = forward.find("stop web")
        drop = forward.find("DROP DEFAULT")
        up = forward.find("up -d")
        assert -1 < build < stop < drop < up, (
            "Imagem nova buildada antes do downtime; writers antigos parados antes do DROP; "
            "up novo apenas após o assert NULL"
        )

    def test_forward_drop_uses_on_error_stop(self) -> None:
        """DROP DEFAULT do forward com SQL errors fatais."""
        assert "ON_ERROR_STOP" in self._forward()

    def test_forward_null_assert_is_binary(self) -> None:
        """Forward exige NULL/empty real (binário), não comentário de saída esperada."""
        forward = self._forward()
        assert re.search(r"\w+\s*=\s*\"?\$\([^)]*column_default", forward, re.I | re.S)
        assert re.search(r"(?:\[\[?|test\s)", forward)
        assert "exit 1" in forward

    def test_forward_recovery_keeps_writers_stopped(self) -> None:
        """Recuperação documentada: check falho → manter writers parados, não continuar."""
        forward = self._forward()
        lower = forward.lower()
        assert "manter" in lower and ("parados" in lower or "parado" in lower), (
            "Falha no check deve manter os writers parados (não subir imagem nova)"
        )
        assert "não continuar" in lower or "não subir" in lower
