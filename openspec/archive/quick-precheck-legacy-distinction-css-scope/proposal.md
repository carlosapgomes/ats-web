# Proposal: Distinção fronteira-3.0 vs legado-v2 no precheck de downgrade + CSS no radar de blast radius

**Change ID**: `quick-precheck-legacy-distinction-css-scope`
**Tipo**: QUICK (dívidas operacionais do rollout v0.8.0/v0.8.1 em produção)
**Dependências**: `support-independent-echoendoscopy-cpre-workflows` (arquivado; Slice 009 entregou o precheck)

## Problema

Duas dívidas registradas durante o rollout de produção de 2026-09-13:

1. **Precheck confunde fronteira 3.0 com dado legado v2.** O comando
   `check_specialized_procedure_downgrade` reporta 5 classes bloqueantes,
   mas dois grupos com significados distintos: a fronteira real de rollback
   (`v3_artifact_write`, `specialized_case_procedure`,
   `pipeline_job_in_flight` — writes do writer 3.0) e classes que apenas
   indicam **dado histórico v2** (`legacy_echo_artifact`,
   `specialized_case_event` sobre o sinal legado de Eco). Em produção, os 14
   casos encerrados com sinal legado (ago–set/2026) fizeram o gate pré-cutover
   do runbook (Passo 3d exige `allowed`) ser **insatisfazível por construção**,
   exigindo desvio aprovado pelo operador (Opção A) para prosseguir o cutover.
   O runbook também documenta saída esperada que não corresponde à realidade
   deste banco.

2. **CSS fora do blast radius das fatias de UI.** Os badges especializados
   (Slices 005–007) projetam `exam-type-{{ declared_type_key }}` em 10
   templates, mas nenhuma fatia listou `static/css/app.css`; sem a variante,
   o `.badge` do Bootstrap 5 fica sem fundo e o badge ficou invisível —
   bug visível descoberto no piloto de produção e corrigido em v0.8.1
   (`f8b33b9`). A guarda `tests/test_exam_type_badge_css.py` pina o
   vocabulário atual, mas o processo de planejamento não pergunta por CSS.

## Objetivo

1. Precheck distingue os grupos: `status`/exit code refletem **somente** a
   fronteira 3.0; dado legado v2 é reportado em campo próprio
   (`old_image_return_available: false`) sem bloquear o gate de cutover.
   Runbook (Passos 3d/6c e §4.3) atualizado para a semântica nova.
2. Lição de processo registrada no contrato do repo: anti-padrão explícito
   em `AGENTS.md` — fatia de UI que introduz vocabulário de classe CSS deve
   incluir o CSS no blast radius e/ou guarda de teste.

## Escopo

- `apps/cases/management/commands/check_specialized_procedure_downgrade.py`
  — separação de grupos no JSON/exit/mensagem.
- `apps/cases/tests/test_specialized_procedure_downgrade_check.py` —
  cenário legado-only (allowed + exceção §4.3 indisponível) e ajuste dos
  existentes à semântica nova.
- `docs/deploy/support-independent-echoendoscopy-cpre-workflows.md` —
  Passos 3d/6c e §4.3.
- `AGENTS.md` — bullet de anti-padrão (§8).

### Fora de escopo

- Migrações, flags, mudança de UI/estilos, backfill.
- Mudança nas classes bloqueantes existentes ou nos códigos estáveis.

## Sucesso

Cenário legado-only (sinal v2, zero write 3.0) retorna exit 0 com
`old_image_return_available: false`; fronteira cruzada continua exit 1;
runbook coerente com o comando; AGENTS.md registra a lição; gate completo
verde.
