# Slice 008 — Rollout, rollback e gate final

## Objetivo

Tornar a entrega operável: documentar cutover/prompts/flags, smoke sequencial Eco→CPRE, prechecks de downgrade e executar uma única vez o quality gate global do change.

## Contexto necessário

- `AGENTS.md` e `PROJECT_CONTEXT.md`
- `design.md`: Risks e Migration Plan
- `docs/deploy/support-combined-eda-colonoscopy-workflow.md`
- `docs/manual/manual-usuarios.md`, `.env.example`, arquivos compose/settings
- todos os relatórios aprovados dos Slices 001–007

## Requisitos verificáveis

- **R1:** env/settings documentam flags false por padrão e independentes.
- **R2:** runbook descreve drain, prompts 3.0, migration, smoke EDA/Colon antes de especializados, Eco antes de CPRE e monitoramento.
- **R3:** rollback suportado é flags off + imagem/schema novos + fix-forward.
- **R4:** downgrade antigo falha se houver row especializada, artefato/evento/job 3.0; não há deleção/backfill reverso.
- **R5:** manual informa identidades, policy, troca-aprovação, anexos fora da automação, comunicação e ausência de regra de sala.
- **R6:** ADR/OpenSpec/contexto/docs não contradizem matriz, policy ou ausência de repolicy na troca.
- **R7:** quality gate global, OpenSpec strict, diff check e status são registrados.

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
  - openspec/changes/support-independent-echoendoscopy-cpre-workflows/tasks.md
allowed_incidental_files:
  - docker-compose.dev.yml
  - docker-compose.prod.yml
  - config/settings/base.py
file_cap: 11
out_of_scope:
  - novo comportamento clínico
  - ativar flags em produção sem aprovação humana
  - arquivar o change
  - apagar rows/artefatos para downgrade
```

Escalar qualquer divergência de docs para specs/design; não “resolver” mudando regra clínica neste slice.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivos esperados | Teste/check |
| --- | --- | --- |
| R1/R2/R3 | env/runbook | inspeção + comandos documentados executáveis |
| R4 | management command + teste | banco vazio permite; qualquer incompatibilidade bloqueia |
| R5/R6 | manual/contexto/ADR/OpenSpec | consistency review e `rg` de termos proibidos |
| R7 | repositório inteiro | gate global + OpenSpec strict |

## RED

- `uv run pytest apps/cases/tests/test_specialized_procedure_downgrade_check.py -q`
- Falha esperada: precheck binário de downgrade ainda não existe.

## GREEN / verificação local

- Mesmo comando RED deve passar.
- Executar comandos de smoke/precheck não destrutivos descritos no runbook em ambiente de teste.
- `openspec validate support-independent-echoendoscopy-cpre-workflows --strict`
- `git diff --check`

## Gate final único do change

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-independent-echoendoscopy-cpre-workflows --strict
git diff --check
git status --short
```

Não substituir falhas por comparação de contagem de testes. Qualquer falha bloqueia conclusão.

## Critérios de aceitação

- [ ] R1–R7 provados.
- [ ] Smoke explicita Eco antes de CPRE e mantém flags off até aprovação.
- [ ] Rollback não propõe imagem antiga após dado 3.0.
- [ ] Gate global tem exit code zero.
- [ ] `tasks.md` marca somente evidências realmente aprovadas.

## Handoff

Gerar relatório final detalhado em `/tmp/support-independent-echoendoscopy-cpre-final-report.md`, informar `REPORT_PATH`, commit/push rastreáveis e parar para aprovação humana. Não arquivar nem iniciar outro change sem confirmação explícita.
