# Slice 009 — Rollout, rollback e gate final

## Objetivo

Tornar a entrega operável: documentar cutover/flags, smoke Eco→CPRE, prechecks de downgrade e executar o quality gate global uma única vez.

## Contexto necessário

- `AGENTS.md`, `PROJECT_CONTEXT.md`
- `design.md`: Risks e Migration Plan
- runbook combinado existente, manual e relatórios aprovados dos Slices 001–008

## Requisitos verificáveis

- **R1:** env/settings documentam flags false e independentes.
- **R2:** runbook descreve drain, prompts 3.0, migration, smoke EDA/Colon, Eco antes de CPRE e monitoramento.
- **R3:** após qualquer write 3.0, rollback suportado é flags off + imagem/schema 3.0 + fix-forward.
- **R4:** downgrade antigo só é possível antes do cutover e falha diante de qualquer artefato/job 3.0, row/evento especializado.
- **R5:** manual informa identidade, policy, troca-aprovação, anexos fora da automação, comunicação e ausência de regra de sala.
- **R6:** ADR/OpenSpec/contexto/docs permanecem consistentes.
- **R7:** gate global e validações documentais passam.

## Escopo e blast radius

```yaml
expected_files:
  - .env.example
  - docs/deploy/support-independent-echoendoscopy-cpre-workflows.md
  - docs/deploy/README.md
  - docs/manual/manual-usuarios.md
  - PROJECT_CONTEXT.md
  - apps/cases/management/commands/check_specialized_procedure_downgrade.py
  - apps/cases/tests/test_specialized_procedure_downgrade_check.py
allowed_incidental_files:
  - config/settings/base.py
file_cap: 8
out_of_scope:
  - nova regra clínica
  - ativação real sem aprovação humana
  - archive do change
  - deleção para downgrade
```

`tasks.md` é metadata pós-review fora do ownership/cap do worker: somente o parent marca evidências comprovadas e inclui essa atualização no commit do slice.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1–R3 | env/runbook | inspeção e comandos não destrutivos |
| R4 | command/test | pré-cutover permite; qualquer write 3.0 bloqueia |
| R5/R6 | manual/contexto/ADR/OpenSpec | consistency review |
| R7 | repositório | quality gate/OpenSpec/diff/status |

## RED

1. Criar `test_specialized_procedure_downgrade_check.py` com cenários pré/pós-cutover.
2. `uv run pytest apps/cases/tests/test_specialized_procedure_downgrade_check.py -q`
3. RED válido: assertions sobre command ausente/comportamento falham; arquivo inexistente/collection não vale.

## GREEN / verificação local

- Mesmo comando RED com exit code 0.
- Executar smoke/prechecks não destrutivos do runbook em teste.
- `openspec validate support-independent-echoendoscopy-cpre-workflows --strict`
- `git diff --check`

## Gate final único

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-independent-echoendoscopy-cpre-workflows --strict
git diff --check
git status --short
```

Qualquer falha bloqueia conclusão; contagem de testes não substitui correção.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Fronteira de rollback é o primeiro write 3.0, não o intake especializado.
- [ ] Smoke exige Eco antes de CPRE.
- [ ] Gate global tem exit code zero.

## Handoff

Gerar `/tmp/support-independent-echoendoscopy-cpre-final-report.md`, informar `REPORT_PATH`, entregar ao parent e parar. O parent revisa evidências, atualiza `tasks.md`, faz commit/push e solicita aprovação humana; não arquivar sem confirmação.

## Prompt para implementador com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, ADR-0006, `proposal.md`, `design.md`, `tasks.md` e este arquivo. Implemente **somente o Slice 009**: runbook, prechecks, rollout Eco antes de CPRE, rollback pela fronteira do primeiro write 3.0, smoke e gate global. Crie/ajuste testes RED antes do código, alcance GREEN, refatore, rode integralmente os comandos deste slice, atualize apenas os artefatos operacionais permitidos pelo blast radius e gere o `REPORT_PATH`. Não altere `tasks.md`, não faça commit/push e não arquive nem inicie novo change; entregue o handoff ao parent, que atualizará tasks e fará commit/push após review.
