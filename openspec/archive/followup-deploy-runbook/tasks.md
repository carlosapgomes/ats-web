# Tasks: Runbook de deploy para supervisor-appointment-follow-up

## Slice vertical

- [x] Slice 001 — Runbook `docs/deploy/supervisor-appointment-follow-up.md` + índice no README (`slices/slice-001-deploy-runbook.md`)

## Preflight

- [x] Working tree limpa em `main` @ `f50eba1` (BASE_REF; tag `v0.6.0-rc.1` sobre este commit)
- [x] rc publicada com imagem no GHCR; produção NÃO tocada (runbook é preparação do deploy)

## Definition of Done

- [x] Runbook no formato da casa com smoke funcional específico do follow-up e rollback em níveis.
- [x] `docs/deploy/README.md` lista o novo runbook.
- [x] Testes de documentação verdes (10 passed); nenhum arquivo fora do blast radius.
- [x] Commit atômico + archive versionado (ADR-0005) + push.

## Registro de execução

- 2 rodadas de review. Rodada 1: BLOCK com 1×P1 — §4.2 afirmava falsamente que o rollback completo destruiria os espelhos `CaseEvent FOLLOWUP_*` (a reversão de 0017 dropa apenas `CaseFollowUp`/`ProcedureFollowUp`; os eventos append-only permanecem consultáveis). Corrigido. Rodada 2: **OK**, nenhum finding.
