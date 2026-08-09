"""Versioned documentation contract tests for the combined EDA+Colonoscopy rollout (Slice 012).

These checks pin the safety-critical claims of the rollout runbook, the user
manual and PROJECT_CONTEXT to the actual implementation:

- CRITICAL runbook with absolute compose paths and the real ``media_prod``
  volume, without zero-downtime / no-impact promises;
- fail-closed backups (DB dump + media tar) validated by content before any
  migration step;
- machine-readable data/state preflight (CaseProcedure 1–2 rows, no
  duplicates, valid combinations, pipeline states drained, prompt matrix with
  exactly one active version per neutral name and zero active legacy names);
- serialized deploy: all writers stopped before migration, schema/prompt
  verification before ``up``, flag web-only and activated only after smoke;
- complete smoke matrix (EDA, Colon, combined, auto-upgrade, combined→single,
  partial decision/inclusion, paired appointment, NIR response, dashboard);
- preferred rollback preserving new image/data/prompts;
- exceptional old-image bridge refusing combined/ambiguous rows with binary
  fail-fast asserts and exact legacy-prompt reactivation;
- safe forward re-establishing neutral mode before new writers;
- manual/context/ADR links aligned.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RUNBOOK_PATH = PROJECT_ROOT / "docs" / "deploy" / "support-combined-eda-colonoscopy-workflow.md"
DEPLOY_README_PATH = PROJECT_ROOT / "docs" / "deploy" / "README.md"
MANUAL_PATH = PROJECT_ROOT / "docs" / "manual" / "manual-usuarios.md"
CONTEXT_PATH = PROJECT_ROOT / "PROJECT_CONTEXT.md"
PROD_COMPOSE_PATH = PROJECT_ROOT / "docker-compose.prod.yml"
SEED_PROMPTS_PATH = PROJECT_ROOT / "apps" / "llm" / "management" / "commands" / "seed_prompts.py"
ADR3_PATH = PROJECT_ROOT / "docs" / "adr" / "ADR-0003-perfis-procedimento-tipo-exame-explicito.md"
ADR4_PATH = PROJECT_ROOT / "docs" / "adr" / "ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md"

NEUTRAL_PROMPT_NAMES = (
    "exam_llm1_system",
    "exam_llm1_user",
    "exam_llm2_system",
    "exam_llm2_user",
)
LEGACY_PROMPT_NAMES = (
    "llm1_system",
    "llm1_user",
    "llm2_system",
    "llm2_user",
    "colonoscopy_llm1_system",
    "colonoscopy_llm1_user",
    "colonoscopy_llm2_system",
    "colonoscopy_llm2_user",
)
ALL_PROMPT_NAMES = NEUTRAL_PROMPT_NAMES + LEGACY_PROMPT_NAMES


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(runbook: str, start: str, end: str) -> str:
    return runbook.split(start, 1)[1].split(end, 1)[0]


# ── R1: Runbook CRITICAL e paths reais ─────────────────────────────────────


class TestRunbookRiskAndPaths:
    def test_runbook_exists_and_classifies_critico(self) -> None:
        """Runbook do change existe e classifica CRÍTICO / HIGH-ARCH."""
        assert RUNBOOK_PATH.exists(), "Runbook docs/deploy/support-combined-eda-colonoscopy-workflow.md ausente"
        runbook = _read(RUNBOOK_PATH)
        assert "CRÍTICO" in runbook.upper() or "CRITICO" in runbook.upper()
        assert "HIGH-ARCH" in runbook.upper()

    def test_runbook_does_not_promise_zero_downtime_or_no_impact(self) -> None:
        """Sem promessas inseguras: zero downtime / sem impacto / não há risco."""
        runbook = _read(RUNBOOK_PATH).lower()
        for forbidden in ("zero downtime", "sem impacto", "não há risco"):
            assert forbidden not in runbook, f"Claim inseguro proibido no runbook: {forbidden!r}"
        # O downtime da janela de manutenção é documentado honestamente.
        assert "downtime" in runbook or "indisponível" in runbook or "indisponivel" in runbook, (
            "Runbook deve declarar o downtime esperado da janela de manutenção"
        )

    def test_runbook_uses_absolute_compose_paths(self) -> None:
        """Comandos Compose usam --project-directory/caminhos absolutos."""
        runbook = _read(RUNBOOK_PATH)
        assert "--project-directory" in runbook
        assert "PROJECT_DIR" in runbook
        assert "docker compose" in runbook

    def test_runbook_references_real_media_prod_volume(self) -> None:
        """Backup de mídia usa o volume real media_prod (nunca ats_web_media)."""
        runbook = _read(RUNBOOK_PATH)
        assert "ats_web_media" not in runbook, "Volume inexistente ats_web_media não pode aparecer"
        assert "media_prod" in runbook
        assert "docker inspect" in runbook and "ps -q web" in runbook, (
            "Volume real deve ser resolvido pelo container web"
        )


# ── R2: Backup fail-closed ─────────────────────────────────────────────────


class TestRunbookBackupFailClosed:
    def test_backup_pipeline_is_fail_fast(self) -> None:
        """pg_dump | gzip com set -euo pipefail; falha do dump aborta o pipeline."""
        runbook = _read(RUNBOOK_PATH)
        assert "set -euo pipefail" in runbook or "set -o pipefail" in runbook
        assert "pg_dump" in runbook
        assert "| gzip" in runbook

    def test_dump_validated_by_content(self) -> None:
        """Dump validado por conteúdo: marker PostgreSQL + mínimo de linhas + gzip -t."""
        runbook = _read(RUNBOOK_PATH)
        assert "PostgreSQL database dump" in runbook
        assert re.search(r"-ge\s+100", runbook), "Dump deve comparar contra mínimo de 100 linhas"
        assert "gzip -t" in runbook
        assert "exit 1" in runbook

    def test_media_tar_validated_by_content(self) -> None:
        """Tar de mídia validado: tar -tzf + mínimo de entradas + aborta com exit 1."""
        runbook = _read(RUNBOOK_PATH)
        assert "tar -tzf" in runbook
        assert re.search(r"-ge\s+1|-gt\s+0", runbook), "Tar deve comparar contra mínimo de entradas"
        assert "exit 1" in runbook

    def test_backup_precedes_migration(self) -> None:
        """Backup (Passo 1) ocorre antes de qualquer migrate no fluxo."""
        runbook = _read(RUNBOOK_PATH)
        backup_pos = runbook.find("pg_dump")
        migrate_pos = runbook.find("manage.py migrate")
        assert backup_pos != -1 and migrate_pos != -1 and backup_pos < migrate_pos, (
            "Backup deve ser executado antes da migration"
        )


# ── R3: Preflight de dados/estados ─────────────────────────────────────────


class TestRunbookPreflight:
    def _preflight(self) -> str:
        return _section(_read(RUNBOOK_PATH), "### Passo 2", "### Passo 3")

    def test_preflight_covers_caseprocedure_rows_and_duplicates(self) -> None:
        """Preflight exige 1–2 rows CaseProcedure por caso e zero duplicatas."""
        preflight = self._preflight()
        assert "CaseProcedure" in preflight
        assert "1–2" in preflight or "1-2" in preflight, "Preflight deve exigir 1–2 rows por caso"
        assert "duplic" in preflight.lower(), "Preflight deve verificar ausência de duplicatas"

    def test_preflight_covers_valid_combinations(self) -> None:
        """Combinações válidas: somente eda/colonoscopy; combinado eda_colonoscopy."""
        preflight = self._preflight()
        assert "eda" in preflight and "colonoscopy" in preflight
        assert "eda_colonoscopy" in preflight, "Seleção combinada deve ser nomeada no preflight"

    def test_preflight_requires_pipeline_states_drained(self) -> None:
        """Estados LLM_STRUCT/LLM_SUGGEST drenados ou listados para tratamento."""
        preflight = self._preflight()
        assert "LLM_STRUCT" in preflight and "LLM_SUGGEST" in preflight
        assert "drenad" in preflight.lower() or "listad" in preflight.lower(), (
            "Estados de pipeline devem ser drenados ou listados para tratamento"
        )

    def test_preflight_prompt_matrix_neutral(self) -> None:
        """Exatamente uma versão ativa por nome neutro (4 nomes)."""
        preflight = self._preflight()
        for name in NEUTRAL_PROMPT_NAMES:
            assert name in preflight, f"Preflight deve listar o nome neutro {name}"
        assert "exatamente uma" in preflight.lower() or "uma versão ativa" in preflight.lower(), (
            "Preflight deve exigir exatamente uma versão ativa por nome neutro"
        )

    def test_preflight_prompt_matrix_legacy_inactive(self) -> None:
        """Zero versões ativas dos oito nomes legados após o cutover."""
        preflight = self._preflight()
        for name in LEGACY_PROMPT_NAMES:
            assert name in preflight, f"Preflight deve listar o nome legado {name}"
        assert "inativ" in preflight.lower(), "Legados devem ser verificados como inativos"

    def test_preflight_asserts_flag_false_and_fails_on_mismatch(self) -> None:
        """Flag deve estar false no preflight; mismatch termina não zero."""
        preflight = self._preflight()
        assert "COLONOSCOPY_INTAKE_ENABLED" in preflight
        assert "false" in preflight.lower()
        assert "exit 1" in preflight, "Mismatch do preflight deve terminar não zero"
        assert "PARAR" in preflight.upper(), "Preflight deve mandar PARAR em falha"


# ── R4: Deploy serializado ─────────────────────────────────────────────────


class TestRunbookSerializedDeploy:
    def test_stop_all_writers_before_migration(self) -> None:
        """Passo 4 para web worker pdf_worker ANTES do migrate."""
        runbook = _read(RUNBOOK_PATH)
        passo4 = _section(runbook, "### Passo 4", "### Passo 5")
        stop_pos = passo4.find("stop web worker pdf_worker")
        migrate_pos = passo4.find("manage.py migrate")
        assert stop_pos != -1 and migrate_pos != -1 and stop_pos < migrate_pos, (
            "Writers devem ser parados antes da migration no Passo 4"
        )

    def test_migration_and_seed_run_with_new_image(self) -> None:
        """Migration/seed rodam com a imagem nova (run --rm web) com serviços parados."""
        runbook = _read(RUNBOOK_PATH)
        assert "run --rm web" in runbook and "manage.py migrate" in runbook
        assert "seed_prompts" in runbook

    def test_schema_verified_before_up(self) -> None:
        """Verificação pós-migration (coluna legada ausente/constraints/prompts) antes do up."""
        runbook = _read(RUNBOOK_PATH)
        verify = _section(runbook, "### Passo 6", "### Passo 7")
        assert "information_schema" in verify, "Verificação de schema deve ser machine-readable"
        assert "exit 1" in verify
        up_pos = runbook.find("up -d --force-recreate")
        verify_pos = runbook.find("### Passo 6")
        assert verify_pos != -1 and up_pos != -1 and verify_pos < up_pos, (
            "Verificação de schema/prompts deve preceder o up"
        )

    def test_up_uses_force_recreate_for_three_services(self) -> None:
        """Subida pós-migration recria os três serviços com a imagem nova."""
        runbook = _read(RUNBOOK_PATH)
        assert "up -d --force-recreate web worker pdf_worker" in runbook

    def test_steps_are_serialized_in_order(self) -> None:
        """Passos 1–11 aparecem em ordem crescente no arquivo."""
        runbook = _read(RUNBOOK_PATH)
        positions = [runbook.find(f"### Passo {n}") for n in range(1, 12)]
        assert all(p != -1 for p in positions), f"Passos ausentes: {positions}"
        assert positions == sorted(positions), "Passos de deploy devem estar serializados em ordem"

    def test_flag_web_only_in_prod_compose(self) -> None:
        """docker-compose.prod.yml: flag existe apenas no serviço web."""
        compose = _read(PROD_COMPOSE_PATH)
        web_block = compose.split("\n  web:\n", 1)[1].split("\n  worker:\n", 1)[0]
        assert "COLONOSCOPY_INTAKE_ENABLED" in web_block
        worker_block = compose.split("\n  worker:\n", 1)[1].split("\n  pdf_worker:\n", 1)[0]
        pdf_block = compose.split("\n  pdf_worker:\n", 1)[1]
        assert "COLONOSCOPY_INTAKE_ENABLED" not in worker_block + pdf_block, "Workers não podem receber a flag"

    def test_flag_activation_web_only_and_after_smoke(self) -> None:
        """Ativação da flag: somente web, somente após o smoke com flag desligada."""
        runbook = _read(RUNBOOK_PATH)
        passo9 = _section(runbook, "### Passo 9", "### Passo 10")
        assert "force-recreate web" in passo9
        assert "worker" not in passo9, "Ativação da flag não pode recriar workers como leitores"
        passo8 = _section(runbook, "### Passo 8", "### Passo 9")
        assert "flag desligada" in passo8.lower() or "false" in passo8.lower(), (
            "Smoke inicial deve rodar com a flag desligada"
        )


# ── R5: Smoke e monitoramento ──────────────────────────────────────────────


class TestRunbookSmokeAndMonitoring:
    def test_smoke_matrix_complete(self) -> None:
        """Checklist cobre EDA, Colon, combinado, upgrade, retorno, parcial, casado, resposta."""
        runbook = _read(RUNBOOK_PATH).lower()
        for required in (
            "eda simples",
            "colon simples",
            "combinado declarado",
            "upgrade automático",
            "combinado→single",
            "decisão parcial",
            "inclusão",
            "agendamento casado",
            "resposta",
            "1 caso / 2 componentes",
        ):
            assert required in runbook, f"Smoke matrix deve cobrir: {required}"

    def test_auto_upgrade_event_monitored(self) -> None:
        """Monitoramento consulta o evento PROCEDURE_SELECTION_AUTO_UPGRADED."""
        runbook = _read(RUNBOOK_PATH)
        assert "PROCEDURE_SELECTION_AUTO_UPGRADED" in runbook

    def test_monitoring_does_not_expose_clinical_text(self) -> None:
        """Consultas/eventos de monitoramento sem expor texto clínico."""
        runbook = _read(RUNBOOK_PATH)
        assert "sem expor texto clínico" in runbook.lower() or "sem expor texto clinico" in runbook.lower()
        monitor = _section(runbook, "### Passo 11", "## 4.")
        assert "CaseProcedure" in monitor
        assert "em voo" in monitor.lower() or "voo" in monitor.lower(), (
            "Monitoramento deve acompanhar casos em voo (não CLEANED)"
        )


# ── R6: Rollback preferencial ──────────────────────────────────────────────


class TestRunbookPreferredRollback:
    def _preferred(self) -> str:
        return _section(_read(RUNBOOK_PATH), "### 4.1", "### 4.2")

    def test_preferred_rollback_keeps_new_image(self) -> None:
        """Rollback preferencial: desligar flag e manter a imagem nova/schema novo."""
        preferred = self._preferred()
        assert "imagem nova" in preferred
        assert "desligar a flag" in preferred.lower() or "flag false" in preferred.lower()
        assert "force-recreate web" in preferred

    def test_preferred_rollback_drains_and_preserves_prompts(self) -> None:
        """Drena casos em voo e preserva prompts neutros enquanto houver v2 em voo."""
        preferred = self._preferred()
        assert "drenar" in preferred.lower() or "drenagem" in preferred.lower()
        assert "prompts neutros" in preferred.lower() or "prompts" in preferred.lower()
        assert "em voo" in preferred.lower()

    def test_preferred_rollback_is_not_destructive(self) -> None:
        """Não apaga CaseProcedure/JSON/histórico de prompts no rollback."""
        preferred = self._preferred()
        assert "CaseProcedure" in preferred
        assert "JSON" in preferred
        assert "histórico" in preferred.lower() or "historia" in preferred.lower()


# ── R7: Bridge para imagem antiga + forward ────────────────────────────────


class TestRunbookOldImageBridge:
    def _bridge(self) -> str:
        return _section(_read(RUNBOOK_PATH), "### 4.2", "### 4.3")

    def test_bridge_requires_writers_stopped(self) -> None:
        """Bridge exige writers parados antes de qualquer escrita de schema."""
        bridge = self._bridge()
        assert "stop web worker pdf_worker" in bridge or "writers parados" in bridge.lower()
        stop_pos = bridge.find("stop web worker pdf_worker")
        alter_pos = bridge.find("ALTER TABLE")
        assert stop_pos != -1 and alter_pos != -1 and stop_pos < alter_pos, (
            "Writers devem estar parados antes do ALTER da bridge"
        )

    def test_bridge_refuses_combined_and_ambiguous(self) -> None:
        """Bridge recusa eda_colonoscopy/ambiguidade com fail binário."""
        bridge = self._bridge()
        assert "eda_colonoscopy" in bridge or "combinad" in bridge.lower()
        assert "ambígu" in bridge.lower() or "ambig" in bridge.lower(), "Bridge deve recusar seleção ambígua"
        assert "exit 1" in bridge

    def test_bridge_uses_on_error_stop_and_at(self) -> None:
        """Bridge usa psql -v ON_ERROR_STOP=1 e saída -At para asserts binários."""
        bridge = self._bridge()
        assert "ON_ERROR_STOP=1" in bridge
        assert "-At" in bridge

    def test_bridge_reactivates_exactly_one_version_per_legacy_name(self) -> None:
        """Bridge reativa exatamente uma versão por nome legado e verifica antes do up."""
        bridge = self._bridge()
        for name in LEGACY_PROMPT_NAMES:
            assert name in bridge, f"Bridge deve listar o nome legado {name}"
        assert "exatamente uma" in bridge.lower() or "uma versão" in bridge.lower(), (
            "Bridge deve exigir exatamente uma versão ativa por nome legado"
        )

    def test_bridge_fail_fast_blocks_old_image_up(self) -> None:
        """Imagem antiga só sobe após asserts binários; falha bloqueia o up."""
        bridge = self._bridge()
        assert "exit 1" in bridge
        assert "NÃO subir" in bridge.upper() or "não subir" in bridge.lower() or "PARAR" in bridge.upper()

    def test_bridge_backfills_only_unambiguous_single_selection(self) -> None:
        """Backfill de exam_type somente para seleção única inequívoca."""
        bridge = self._bridge()
        assert "exam_type" in bridge
        assert "backfill" in bridge.lower()
        assert "UPDATE" in bridge


class TestRunbookForward:
    def _forward(self) -> str:
        return _section(_read(RUNBOOK_PATH), "### 4.3", "## 5.")

    def test_forward_sequence_is_serialized(self) -> None:
        """Forward: build → stop → neutros ativos → legados inativos → drop bridge → assert → up."""
        forward = self._forward()
        build = forward.find("build")
        stop = forward.find("stop web worker pdf_worker")
        seed = forward.find("seed_prompts")
        drop = forward.find("DROP COLUMN")
        up = forward.find("up -d --force-recreate")
        assert -1 < build < stop < seed < drop < up, (
            "Ordem segura do forward violada: build, stop, seed, drop, assert, up"
        )

    def test_forward_reestablishes_neutral_mode(self) -> None:
        """Forward garante uma versão ativa por nome neutro e desativa legados antes do up."""
        forward = self._forward()
        for name in NEUTRAL_PROMPT_NAMES:
            assert name in forward
        assert "inativ" in forward.lower() or "desativ" in forward.lower()

    def test_forward_asserts_schema_and_prompts_before_up(self) -> None:
        """Assert binário de schema (coluna removida) e prompts antes de subir."""
        forward = self._forward()
        assert "information_schema" in forward or "exam_type" in forward
        assert "exit 1" in forward
        drop_pos = forward.find("DROP COLUMN")
        up_pos = forward.find("up -d --force-recreate")
        assert drop_pos != -1 and up_pos != -1 and drop_pos < up_pos


# ── Blocos autocontidos: cada bloco mutável com fail-fast próprio ──────────


class TestRunbookSelfContainedBlocks:
    def test_each_mutable_block_has_own_pipefail(self) -> None:
        """Pelo menos backup, preflight, bridge e forward têm set -euo pipefail próprio."""
        runbook = _read(RUNBOOK_PATH)
        count = runbook.count("set -euo pipefail") + runbook.count("set -o pipefail")
        assert count >= 4, f"Esperado >= 4 blocos fail-fast próprios, obtido {count}"

    def test_no_shell_block_depends_on_previous_session(self) -> None:
        """Blocos não dependem de variáveis de shell de blocos anteriores."""
        runbook = _read(RUNBOOK_PATH)
        # DPROD/PROJECT_DIR são definidos em cada bloco que os usa.
        for block_start in ("### Passo 1", "### Passo 2", "### Passo 4", "### 4.2", "### 4.3"):
            block = _section(runbook, block_start, "## ")
            if "$DPROD" in block:
                assert "DPROD=" in block or "--project-directory" in block, f"Bloco {block_start} usa DPROD sem definir"


# ── R8: Manual/contexto/ADR/índice ─────────────────────────────────────────


class TestManualAligned:
    def test_manual_covers_combined_intake_and_auto_upgrade(self) -> None:
        """Manual: seleção EDA + Colonoscopia, lote com seleção única e upgrade automático."""
        manual = _read(MANUAL_PATH)
        assert "EDA + Colonoscopia" in manual
        assert "upgrade automático" in manual.lower()
        assert "um por tipo" not in manual, "Manual não pode mais exigir separação obrigatória de PDFs mistos"

    def test_manual_covers_decision_per_component(self) -> None:
        """Manual: médico decide cada procedimento; negativa/inclusão com razão."""
        manual = _read(MANUAL_PATH)
        assert "por componente" in manual.lower() or "cada procedimento" in manual.lower()
        assert "inclusão" in manual.lower() or "incluir" in manual.lower()

    def test_manual_covers_paired_appointment(self) -> None:
        """Manual: combinado aprovado gera um único agendamento casado."""
        manual = _read(MANUAL_PATH)
        assert "Agendamento casado" in manual
        assert "uma única" in manual.lower() or "um único" in manual.lower()

    def test_manual_covers_final_response_dimensions(self) -> None:
        """Manual: resposta final mostra solicitado/detectado/autorizado."""
        manual = _read(MANUAL_PATH)
        for term in ("Solicitado", "Detectado", "Autorizado"):
            assert term.lower() in manual.lower(), f"Resposta final deve citar {term}"


class TestProjectContextAligned:
    def test_context_covers_schema_v2_and_neutral_prompts(self) -> None:
        """Contexto: CaseProcedure autoritativo, prompts neutros, semântica de filtros."""
        context = _read(CONTEXT_PATH)
        assert "CaseProcedure" in context
        assert "exam_llm1_system" in context
        for dim in ("declarado", "detectado", "autorizado"):
            assert dim in context, f"Contexto deve citar a dimensão {dim}"

    def test_context_no_longer_claims_exam_type_is_current(self) -> None:
        """Contexto não descreve Case.exam_type como campo atual do modelo."""
        context = _read(CONTEXT_PATH)
        assert "`exam_type` (`eda`/`colonoscopy`" not in context, (
            "Case.exam_type foi removido (0016); contexto não pode descrevê-lo como campo atual"
        )

    def test_context_lists_adr_0004_and_current_change(self) -> None:
        """Contexto lista ADR-0004 aceita e o change ativo."""
        context = _read(CONTEXT_PATH)
        assert "ADR-0004" in context
        assert "support-combined-eda-colonoscopy-workflow" in context


class TestADRAndDeployIndex:
    def test_adr_0003_superseded_in_part_by_adr_0004(self) -> None:
        """ADR-0003 marcada como parcialmente superada pela ADR-0004, com link."""
        adr3 = _read(ADR3_PATH)
        assert "parcialmente superada" in adr3.lower()
        assert "ADR-0004" in adr3
        assert "ADR-0004-procedimentos-multiplos-e-contrato-llm-neutro.md" in adr3, (
            "ADR-0003 deve linkar o arquivo da ADR-0004"
        )

    def test_adr_0004_accepted_with_link_to_adr_0003(self) -> None:
        """ADR-0004 aceita e referencia a ADR-0003 que supera parcialmente."""
        adr4 = _read(ADR4_PATH)
        assert "Accepted" in adr4
        assert "ADR-0003" in adr4
        assert "supera parcialmente" in adr4.lower()

    def test_deploy_readme_index_lists_new_runbook(self) -> None:
        """Índice docs/deploy/README.md lista o runbook do change."""
        readme = _read(DEPLOY_README_PATH)
        assert "support-combined-eda-colonoscopy-workflow.md" in readme


# ── R9: Contratos cruzados com a implementação ─────────────────────────────


class TestCrossImplementationContracts:
    def test_prompt_names_match_seed_command_and_runbook(self) -> None:
        """Nomes neutros/legados do runbook batem com seed_prompts."""
        seed = _read(SEED_PROMPTS_PATH)
        runbook = _read(RUNBOOK_PATH)
        for name in ALL_PROMPT_NAMES:
            assert name in seed, f"seed_prompts deve conter {name}"
            assert name in runbook, f"Runbook deve conter {name}"

    def test_flag_reference_matches_settings_and_intake(self) -> None:
        """Flag documentada existe em settings e no intake (único leitor web)."""
        runbook = _read(RUNBOOK_PATH)
        assert "COLONOSCOPY_INTAKE_ENABLED" in runbook
        settings = _read(PROJECT_ROOT / "config" / "settings" / "base.py")
        intake_services = _read(PROJECT_ROOT / "apps" / "intake" / "services.py")
        assert "COLONOSCOPY_INTAKE_ENABLED" in settings
        assert "COLONOSCOPY_INTAKE_ENABLED" in intake_services

    def test_migrations_named_in_runbook(self) -> None:
        """Runbook nomeia as migrations reais do cutover."""
        runbook = _read(RUNBOOK_PATH)
        assert "0015_caseprocedure" in runbook
        assert "0016_remove_case_exam_type" in runbook
