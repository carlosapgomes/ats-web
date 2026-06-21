# Deploy Runbooks

Runbooks de deploy por change. Cada arquivo documenta o procedimento de
produção (backup, build, migration, smoke tests, rollback) para uma
entrega específica.

## Convenção de nome

`<change-id>.md` — mesmo ID usado em `openspec/changes/<change-id>/`.

## Runbooks

- [`corrected-case-resubmission-linkage.md`](./corrected-case-resubmission-linkage.md)
  — Reenvio corrigido explícito NIR + visibilidade médico/NIR.
