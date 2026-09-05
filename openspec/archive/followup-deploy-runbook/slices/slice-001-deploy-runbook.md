# Slice 001 — Runbook de deploy do follow-up + índice

## Objetivo

Comportamento observável: um operador encontra em `docs/deploy/` um runbook completo para levar o change `supervisor-appointment-follow-up` (rc `v0.6.0-rc.1`) a produção, com quick reference executável, análise de risco precisa, smoke funcional da feature e plano de rollback em níveis — e o README de deploy o lista.

## Contexto necessário (ler antes de editar)

- **Modelos de formato**: `docs/deploy/corrected-case-resubmission-linkage.md` (estrutura completa: header, Quick reference, §1 Análise de risco + "O que o change entrega", §2 Pré-requisitos, §3 Passos de deploy, §4 Plano de Rollback em níveis, §5 Pós-deploy, §6 Notas operacionais) e `docs/deploy/README.md` (lista indexada).
- **Fatos do change** (não inventar): migration `apps/cases/migrations/0017_casefollowup_procedurefollowup_and_more.py` — cria `CaseFollowUp`/`ProcedureFollowUp` (2 tabelas novas, 2 uniques + 6 check constraints), aditiva, sem data migration, milissegundos, sem lock relevante. Sem env vars novas. FSM e filas intocadas. Commits principais: `0d004b6` (domínio), `8ece663` (aba), `bc07f99` (formulário), `bce62b3` (fix híbrido); ajustes de review `0a373c2`/`ac8111b`; rastreabilidade completa em `docs/releases/2026-09-05_v0.6.0-rc.1.md`.
- **Comportamento real para o smoke**: rota `/dashboard/follow-ups/` (nav "Follow-up" na área do dashboard) restrita a `manager`/`admin` (outros papéis: redirect + mensagem); listagem default hoje+ontem (timezone `America/Bahia`), `?date=`, `?q=` ocorrência/nome; badge "Follow-up registrado (vN)/pendente"; formulário por procedimento (realizado; não realizado com causa/submotivo/texto) + internação; salvar cria nova versão append-only + `CaseEvent` `FOLLOWUP_RECORDED` (v1) / `FOLLOWUP_UPDATED` (v≥2); eventos aparecem na trilha de auditoria do caso. Domínio: `apps/cases/followup.py`; spec oficial: `openspec/specs/supervisor-appointment-follow-up/spec.md`; manual: `docs/manual/manual-usuarios.md` §6.1.
- **Padrão de comandos prod**: `DPROD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"`; containers `web worker pdf_worker`; `--settings=config.settings.prod`; migrar **com app no ar** (aditiva) e só depois `up -d` com a imagem nova; verificação com `showmigrations cases` esperando `[X] 0017_...`.
- Rollback: **suave** = voltar código/rebuild (`git checkout` anterior, `$DPROD build`, `up -d`) — tabelas ficam inertes e dados de follow-up (append-only) preservados no banco, reaparecendo ao reimplantar 0.6.x; **completo** = `migrate cases 0016` apenas quando não houver dados a preservar (perderia registros de follow-up), depois rebuild. Nota: rc é validável em staging via imagem GHCR `ghcr.io/carlosapgomes/ats-web:0.6.0-rc.1`; produção compila do fonte (compose `build:`).

## Requisitos verificáveis

- **R1** — `docs/deploy/supervisor-appointment-follow-up.md` existe com as seções do modelo: header (change, commits, branch, data, risco 🟢 Baixo), Quick reference, §1 análise de risco (migration aditiva/zero downtime/sem env novas/FSM intocada) + resumo do que entrega, §2 pré-requisitos (backup em `/archive/backups/`, acesso `apps`), §3 passos com verificação imediata (`ps`, `logs`, curl 200/302, `showmigrations` com `[X] 0017`) e **smoke funcional específico** (manager/admin veem a aba e registram follow-up criando v1 + evento; atualização cria v2 + `FOLLOWUP_UPDATED`; papéis nir/doctor/scheduler barrados; filas existentes operacionais), §4 rollback em níveis (suave sem tocar DB; completo com `migrate cases 0016` + ressalva de perda de dados de follow-up), §5 pós-deploy (24–48h: observar `CaseEvent FOLLOWUP_*`, feedback supervisores), §6 notas (registro puro ≠ intercorrência; staging via imagem rc).
- **R2** — `docs/deploy/README.md` lista o novo runbook com descrição de uma linha (padrão das demais entradas).
- **R3** — Fidelidade factual: todos os comandos/saídas esperadas batem com o repo (nomes de containers, settings, migration, rotas, eventos, papéis); nada prometido que o sistema não faz.
- **R4** — `uv run pytest tests/test_release_documentation.py tests/test_user_manual_artifacts.py -q` verde.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 | `docs/deploy/supervisor-appointment-follow-up.md` | `rg "^## Quick reference|^## 1. Análise|^## 4. Plano de Rollback" docs/deploy/supervisor-appointment-follow-up.md` |
| R2 | `docs/deploy/README.md` | `rg "supervisor-appointment-follow-up" docs/deploy/README.md` |
| R3 | — | inspeção cruzada com `apps/cases/followup.py`, migration 0017, `apps/dashboard/urls.py`, spec |
| R4 | — | pytest dos docs (exit 0) |

## Escopo e expected blast radius

```yaml
expected_files:
  - docs/deploy/supervisor-appointment-follow-up.md   # novo
  - docs/deploy/README.md                             # +1 entrada na lista

allowed_incidental_files: []

out_of_scope:
  - qualquer código/spec/migration/manual
  - tasks.md (parent atualiza), commit/push (parent decide)
```

## Plano de testes do slice

### RED

Docs-only: `rg "supervisor-appointment-follow-up" docs/deploy/` → vazio antes da edição.

### GREEN / verificação local

```bash
rg "^## Quick reference|^## 4. Plano de Rollback" docs/deploy/supervisor-appointment-follow-up.md   # ambos
rg "supervisor-appointment-follow-up" docs/deploy/README.md                                        # ≥1
uv run pytest tests/test_release_documentation.py tests/test_user_manual_artifacts.py -q          # exit 0
```

## Critérios de aceitação

- [ ] R1–R3 satisfeitos (estrutura do modelo, índice, fidelidade factual).
- [ ] R4 verde; nenhum arquivo fora do blast radius.
