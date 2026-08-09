# Slice 011-C0 (QUICK): TestBackfillD3Table independente do schema leaf (sandbox de migration)

> **Micro-slice descoberto pelo gate R8 do 011-C revisado** (relatório BLOQUEADO
> `/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md`, BASE_REF `097492e`):
> com a coluna removida pela migration 0016, `TestBackfillD3Table`
> (`apps/cases/tests/test_case_procedure.py`) quebra porque roda o backfill da migration
> 0015 via `importlib` contra o **estado leaf** (`project_state(leaf_nodes())`) e cria
> casos pelo ORM atual — o acesso `case.exam_type` está no corpo da migration 0015,
> invisível ao inventário textual (zero ocorrências de `exam_type` no arquivo de teste).
> Aprovado o fix **antes** do cutover para manter o commit do 011-C com exatamente os
> 9 arquivos planejados (regra do change: não aprovar footprint expandido em commit único).

## Handoff com contexto zero

Leia o relatório BLOQUEADO do 011-C revisado (§3 causa raiz e §8 nota técnica do banco de teste), o teste atual `TestBackfillD3Table` em `apps/cases/tests/test_case_procedure.py` e o padrão de sandbox já usado em `apps/cases/tests/test_migration_0016_cutover.py` e `apps/cases/tests/test_post_acceptance_issue_migration.py`. A migration 0015 expõe `backfill_case_procedures` e `reverse_backfill_case_procedures`; a 0016 tem `reverse_code=migrations.RunPython.noop` — migrate down/up é reversível nos dois mundos (com e sem coluna no leaf).

**Atenção — árvore de trabalho:** o trabalho do 011-C revisado (9 arquivos) pode estar sujo na árvore, sem commit. Antes de editar: `git stash push -u -m "wip-011c"` (preserva os 9 arquivos, incl. não rastreados). Implemente o 011-C0 na árvore limpa (`HEAD == 097492e`), commit, depois `git stash pop` para devolver o cutover ao implementador do 011-C.

### Fluxo entregue

```text
fixture da classe migra o schema down até 0014 (estado histórico com a coluna)
→ casos criados/inspecionados pelos modelos históricos (apps.get_model)
→ backfill/reverse da 0015 invocados contra o estado 0014 (não o leaf)
→ migrate up de volta ao leaf no teardown (rollback total, sem poluição)
→ teste verde com a coluna viva (hoje) e após o cutover (011-C)
```

Slice de teste sem mudança de produto: evidência substitutiva de RED (inspeções antes/depois + baseline/final), justificativa explícita registrada no relatório.

## Protocolo obrigatório para DeepSeek4-Flash

Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo (`3071 passed` esperado). `failed/error` no baseline = PARE.
2. **Evidência substitutiva de RED**: inspeção ANTES — `rg -n "leaf_nodes" apps/cases/tests/test_case_procedure.py` (fixture acoplada ao leaf). DEPOIS o fixture deve usar estado histórico explícito (`0014`), e a classe deve passar nos dois mundos (ver critério 4).
3. **Edição mínima**: reescrever somente o fixture/helpers da classe `TestBackfillD3Table` (e os pontos em que os testes leem via ORM atual onde necessário). Os 5 testes preservam o sentido (mesma cobertura D3: 18 estados, marcadores condicionais, preservação, determinismo forward/reverse). Nenhum teste removido/renomeado/adicionado.
4. **Quality gate completo**: ruff/format/mypy/pytest; `passed_final == passed_baseline` (3071), zero failed/error.
5. **Relatório**, checkbox somente 011-C0, commit/push e PARE.

**Cap: exatamente 1 arquivo** (`apps/cases/tests/test_case_procedure.py`). Qualquer outro arquivo (incl. a migration 0015) = PARE.

## Requisitos

### R1. Sandbox de schema no fixture

Substituir `_historical_apps` baseado em `leaf_nodes()` por sandbox explícito: migrate down até `("cases", "0014_case_exam_type")` (a 0015 é revertida por `reverse_backfill_case_procedures` + remoção da tabela; após o cutover, a 0016 também é revertida — `reverse_code` noop), casos criados e lidos pelos modelos históricos, backfill/reverse invocados contra o estado 0014, migrate up ao leaf no teardown. Transação com rollback total (padrão do 0016: `transaction.atomic()` + `set_rollback(True)`; `SET CONSTRAINTS ALL IMMEDIATE` onde houver DDL com FKs deferradas — ver §8 do relatório do 011-C).

### R2. Cobertura preservada

Os 5 testes mantêm o que provam: cobertura dos 18 estados + marcadores condicionais; `appointment_status`/eventos como marcadores downstream; disposição médica na tabela fechada; preservação de campos/eventos; determinismo forward/reverse. Asserts podem trocar ORM atual → modelo histórico onde o sandbox exigir.

### R3. Independência do leaf

A classe não pode depender de o leaf ter ou não a coluna: nenhuma leitura `case.exam_type` pelo ORM atual; o único acesso à coluna ocorre dentro do backfill da migration 0015 executado no estado histórico (onde ela sempre existe).

### R4. Suite idêntica

`passed_final == passed_baseline`, zero failed/error. O erro em cascata em `test_post_acceptance_issue_migration.py` (transação abortada) desaparece como consequência.

## Arquivos esperados (1)

- `apps/cases/tests/test_case_procedure.py`

Proibido: migration 0015/0016; qualquer produto; outro teste; remover/renomear/adicionar teste.

## Inspeções obrigatórias

```bash
rg -n "leaf_nodes" apps/cases/tests/test_case_procedure.py      # esperado: vazio após
rg -n "0014_case_exam_type|MigrationExecutor" apps/cases/tests/test_case_procedure.py
uv run pytest apps/cases/tests/test_case_procedure.py apps/cases/tests/test_post_acceptance_issue_migration.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git diff --check
git diff --name-only "$BASE_REF"
```

## Critérios/gates

- [ ] Fixture usa sandbox de schema (migrate down até 0014) — inspeção colada.
- [ ] 5 testes preservados no sentido; nenhuma remoção/renomeação.
- [ ] `passed_final == passed_baseline` (3071), zero failed/error; cascata do 0012 resolvida.
- [ ] `git diff --name-only` = 1 arquivo.

### Condições automáticas de INCOMPLETO

Edição fora do arquivo; teste removido/renomeado/adicionado; dependência do leaf permanecer (`leaf_nodes` ou ORM atual lendo a coluna); mudança de comportamento (contagem diferente); gate falho; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011c0-report.md` com fixture antes/depois, evidência substitutiva de RED, baseline/final, handoff para o 011-C (restaurar o stash dos 9 arquivos e concluir; expectativa 3074 passed após o cutover).

## Prompt pronto

```text
Read the blocked revised Slice 011-C report (/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md, sections 3 and 8), TestBackfillD3Table in apps/cases/tests/test_case_procedure.py, and the migration-sandbox pattern in apps/cases/tests/test_migration_0016_cutover.py and apps/cases/tests/test_post_acceptance_issue_migration.py. If the working tree has uncommitted 011-C work, first run: git stash push -u -m "wip-011c". Implement ONLY Slice 011-C0.

Rewrite the TestBackfillD3Table fixture to a schema sandbox: migrate down to ("cases","0014_case_exam_type"), create/inspect cases via historical models, invoke the 0015 backfill/reverse functions against the 0014 state (never the leaf), migrate back to leaf in teardown with full transaction rollback (atomic + set_rollback; SET CONSTRAINTS ALL IMMEDIATE where deferred-FK DDL requires). Keep all 5 tests with unchanged meaning; do not touch migration 0015, product code or any other file. Behavior-neutral: passed_final == passed_baseline (3071) with zero failed/error.

Run the before/after rg evidence and full quality gate, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011c0-report.md; if complete mark only Slice 011-C0, commit, push, reply REPORT_PATH and STOP. Do not pop the stash — the 011-C implementer resumes from it.
```
