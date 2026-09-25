# Slice 010 — Cutover coordenado e gate final

## Objetivo

Fechar o change com runbook executável, prechecks de drenagem/compatibilidade, inventário de pressupostos, smoke das onze seleções (dez singletons + EDA/Colonoscopia), acessibilidade do combobox e quality gate global único. Não adicionar comportamento clínico.

## Contexto necessário

- `design.md`: D14–D15, Migration Plan e Risks;
- todas as specs/slices e relatórios aceitos;
- management command de downgrade/precheck existente;
- documentação operacional/prompt seeding do projeto;
- `AGENTS.md` seção 2 e Stop Rule.

## Requisitos verificáveis

- **R1:** runbook exige pausa de intake, drenagem de LLM_STRUCT/LLM_SUGGEST 3.0, migration, prompts 4.0 únicos, mesma imagem web/worker, smoke e reabertura.
- **R2:** precheck bloqueia downgrade após qualquer artefato 4.0 ou row de identidade nova e orienta fix-forward sem apagar/reclassificar dados.
- **R3:** não existem writers 3.0 ativos, nova flag, backfill, threshold infeccioso, regra paired por cardinalidade/label ou lista operacional bloqueante fora do catálogo.
- **R4:** smoke documentado cobre dez singletons, EDA + Colonoscopia, conjunto proibido, GTT normal/preocupante, dilatação com/sem local e filtros/analytics.
- **R5:** smoke acessível confirma busca sem acentos, teclado, foco/ARIA, erro e fallback sem JavaScript nas superfícies migradas.
- **R6:** quality gate global, OpenSpec strict, diff check e status são executados e registrados sem esconder falhas.
- **R7:** specs/tasks/PROJECT_CONTEXT/ADR refletem estado final; nenhum checkbox é marcado sem evidência.

## Escopo e expected blast radius

```yaml
expected_files:
  - docs/operations/expanded-endoscopy-procedure-catalog-cutover.md
  - apps/cases/management/commands/check_specialized_procedure_downgrade.py
  - apps/cases/tests/test_specialized_procedure_downgrade_check.py
  - PROJECT_CONTEXT.md
  - openspec/changes/support-expanded-endoscopy-procedure-catalog/tasks.md
allowed_incidental_files:
  - docs operacionais/prompt docs existentes diretamente relacionados
  - correções mínimas identificadas pelos gates, após RED/review proporcional
out_of_scope:
  - novo comportamento clínico ou UI
  - nova flag/rollout gradual
  - data migration/backfill
  - arquivar o change sem aprovação humana
```

Qualquer falha funcional descoberta que exija alteração substancial volta ao slice responsável; não fazer refactor amplo no fechamento.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1, R4–R5 | runbook | revisão + checklist/smoke registrado |
| R2 | command/test de precheck | teste focado de downgrade |
| R3 | código inteiro | inventários `rg` classificados |
| R6 | repo inteiro | quality gate global + OpenSpec/diff/status |
| R7 | ADR/context/tasks/specs | revisão de consistência |

## RED

Para qualquer mudança no precheck, criar teste antes e executar:

```bash
uv run pytest apps/cases/tests/test_specialized_procedure_downgrade_check.py -q
```

Falha esperada: comando atual não reconhece schema 4.0 nem as seis identidades novas. Documentação ausente é comprovada por inspeção de path/conteúdo, não por teste artificial.

## GREEN / verificação local

```bash
uv run pytest apps/cases/tests/test_specialized_procedure_downgrade_check.py -q
uv run ruff check apps/cases/management/commands apps/cases/tests/test_specialized_procedure_downgrade_check.py
uv run ruff format --check apps/cases/management/commands apps/cases/tests/test_specialized_procedure_downgrade_check.py
```

Inventário obrigatório, com cada ocorrência classificada no relatório:

```bash
rg -n "ProcedureType\.|SUPPORTED_PROCEDURE_TYPES|SELECTABLE_PROCEDURE_TYPES|eda_colonoscopy|len\([^)]*proced|schema_version.*3\.0|llm[12]_v3|gastrostomy|esophageal_dilation" apps templates static
rg -n "THRESHOLD|threshold|reference.range|normal_range|INFECTION.*FLAG|GASTROSTOMY.*FLAG|RECTOSIGMO.*FLAG" apps config
rg -n "RunPython|RunSQL" apps/cases/migrations/0021_*.py
```

Gate final — executar uma única vez após todos os fixes/reviews:

```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run mypy . && \
uv run pytest
openspec validate support-expanded-endoscopy-procedure-catalog --strict
git diff --check
git status --short
```

Smoke manual/operacional deve registrar ambiente, ator, seleção, case id e resultado sem copiar texto clínico sensível. Se não houver ambiente de smoke, marcar explicitamente como gate pendente e não concluir R4/R5.

## Critérios de aceitação

- [ ] R1/R2: runbook/precheck tornam cutover e fix-forward inequívocos.
- [ ] R3: inventário não contém bloqueio não classificado nem regra proibida.
- [ ] R4/R5: smoke funcional e acessível completo está registrado.
- [ ] R6: gate global/OpenSpec/diff/status passaram com outputs reais.
- [ ] R7: artefatos e checkboxes correspondem às evidências.

## Handoff

Parent/orquestrador coleta reviews de todos os slices, atualiza checkboxes comprovados, gera relatório final com snippets antes/depois, faz commit/push conforme AGENTS.md e informa `REPORT_PATH`. Parar para aprovação humana; não arquivar nem iniciar outro change sem confirmação explícita.
