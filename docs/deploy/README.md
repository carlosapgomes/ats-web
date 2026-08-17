# Deploy Runbooks

Runbooks gerais e por change. Cada arquivo documenta procedimentos de
produção como preparação de infraestrutura, backup, migration, smoke tests e
rollback.

## Convenção de nome

Runbooks gerais usam um nome operacional descritivo. Runbooks de uma entrega
específica usam `<change-id>.md`, o mesmo ID de
`openspec/changes/<change-id>/`.

## Runbooks

- [`shared-postgres-production.md`](./shared-postgres-production.md)
  — Implantação e migração de produção com PostgreSQL compartilhado, redes
    separadas de banco, ingress e egress do worker LLM, validação e rollback.
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
