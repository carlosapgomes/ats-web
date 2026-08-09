# Deploy Runbooks

Runbooks de deploy por change. Cada arquivo documenta o procedimento de
produção (backup, build, migration, smoke tests, rollback) para uma
entrega específica.

## Convenção de nome

`<change-id>.md` — mesmo ID usado em `openspec/changes/<change-id>/`.

## Runbooks

- [`corrected-case-resubmission-linkage.md`](./corrected-case-resubmission-linkage.md)
  — Reenvio corrigido explícito NIR + visibilidade médico/NIR.
- [`introduce-colonoscopy-exam-workflow.md`](./introduce-colonoscopy-exam-workflow.md)
  — Tipo de exame explícito EDA/Colonoscopia (8 slices, arquivado).
- [`support-combined-eda-colonoscopy-workflow.md`](./support-combined-eda-colonoscopy-workflow.md)
  — Fluxo combinado EDA + Colonoscopia: backup fail-closed, preflight
    machine-readable, deploy serializado com todos os writers parados,
    smoke matrix EDA/Colon/Combinado, flag web-only, monitoramento sem texto
    clínico, rollback preferencial mantendo a imagem nova e bridge binária
    fail-fast para imagem antiga com forward serializado.
