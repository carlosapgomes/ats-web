# Proposal: Runbook de deploy para `supervisor-appointment-follow-up`

**Change ID**: `followup-deploy-runbook`
**Tipo**: QUICK docs (runbook de deploy)

## Why

A convenção de `docs/deploy/` (README) pede um runbook por change (`<change-id>.md`) — existe para colonoscopia, combinado, resubmission corrigido — mas o change `supervisor-appointment-follow-up` (entregue na rc `v0.6.0-rc.1`, com migration `cases/0017`) não tem o seu. O evidence pack da rc traz checklist genérico; o runbook operacional detalhado (backup, quick reference, análise de risco, smoke da feature, rollback em níveis) falta para o deploy de produção.

## What Changes

- Novo `docs/deploy/supervisor-appointment-follow-up.md` no formato da casa (modelos: `corrected-case-resubmission-linkage.md` e `shared-postgres-production.md`), cobrindo: análise de risco (migration `0017` aditiva, zero downtime, sem env vars novas, FSM intocada), quick reference de comandos (`DPROD` build/migrate/up, `showmigrations cases` esperando `[X] 0017`), pré-requisitos, passos de deploy com **smoke funcional específico** (aba `/dashboard/follow-ups/` para manager/admin; papéis nir/doctor/scheduler barrados; registro cria versão 1 + `CaseEvent FOLLOWUP_RECORDED`; atualização cria versão 2 + `FOLLOWUP_UPDATED`; histórico visível; filas/worker inalterados), pós-deploy e **rollback em níveis** (suave: redeploy da imagem anterior, tabelas inertes, dados append-only preservados; completo: `migrate cases 0016` quando não houver dados a preservar).
- `docs/deploy/README.md`: incluir o novo runbook na lista.

### Impact

- Apenas docs (`docs/deploy/`). Sem código, sem specs (`skip_specs: true`), sem migrations.

## Sucesso

Operador consegue executar o deploy de produção do follow-up seguindo só o runbook; comandos e saídas esperadas batem com o repo real; lista do README atualizada; testes de documentação de release verdes.
