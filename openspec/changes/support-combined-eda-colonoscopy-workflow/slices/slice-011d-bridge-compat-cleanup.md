# Slice 011-D: Remoção do compat `fallback_to_bridge` e comentários mortos da ponte

## Handoff com contexto zero

Leia artefatos, ADR-0004 e relatório aprovado do Slice 011-C. Se 011-C não estiver aprovado (coluna `Case.exam_type` ainda existir), PARE como BLOQUEADO.

### Contexto e fluxo entregue

O Slice 010 rebaixou `fallback_to_bridge` a parâmetro no-op (`del fallback_to_bridge`) para não explodir o cap; o 011-C removeu a coluna, o enum e o dual-write, mas manteve o parâmetro por compatibilidade de call sites. Este slice encerra a última pendência mecânica da ponte: remove o parâmetro dos 3 getters e de todos os call sites (produto e testes), e limpa comentários/docstrings que ainda descrevem a ponte morta.

```text
getters ficam com assinatura limpa: get_*_procedure_types(case)
→ call sites (NIR/médico/CHD) perdem o kwarg morto
→ comentários de ponte atualizados nos arquivos tocados
→ suite verde sem nenhuma referência a fallback_to_bridge
```

Slice mecânico, sem mudança de comportamento (o parâmetro já era no-op).

## Protocolo obrigatório para DeepSeek4-Flash

Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: lista de call sites por arquivo (comece pelo inventário do relatório do 011-C).
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Evidência substitutiva de RED** (slice sem mudança de comportamento): inspeção `rg "fallback_to_bridge"` ANTES (call sites) e DEPOIS (zero ocorrências).
4. **Edição mínima**: remover parâmetro/kwarg e atualizar comentários de ponte nos arquivos tocados. Nenhuma outra mudança.
5. **Inspeções obrigatórias** ao final.
6. **Quality gate completo**: final exit code 0, zero failures/errors e `passed_final == passed_baseline` (nenhum teste é removido neste slice).
7. **Relatório** em `/tmp/support-combined-eda-colonoscopy-workflow-slice-011d-report.md`, checkbox somente 011-D, commit/push e PARE.

**Cap: exatamente os 7 arquivos listados.** Qualquer arquivo extra = PARE antes de editar.

## Requisitos

### R1. Assinatura limpa nos getters

Em `apps/cases/procedures.py`: remover o parâmetro `fallback_to_bridge` (e os `del`) de `get_declared_procedure_types`, `get_detected_procedure_types` e `get_approved_procedure_types`. Docstrings finais sem menção à ponte.

### R2. Call sites atualizados

Remover `fallback_to_bridge=False` de todos os call sites: `apps/doctor/views.py`, `apps/scheduler/views.py`, `apps/intake/services.py`, `apps/intake/views.py` e testes `apps/cases/tests/test_case_procedure.py` e `apps/doctor/tests/test_queue_exam_type_filters.py`. Comportamento idêntico (o parâmetro era no-op).

### R3. Comentários mortos da ponte

Nos 7 arquivos tocados, comentários/docstrings que descrevem a ponte (`Case.exam_type`, dual-write, "modo estrito", Slice 008/010 como exceção) são removidos ou reescritos para o contrato vigente (rows como fonte única). Comentários históricos em arquivos **não** tocados permanecem (classificar no relatório).

### R4. Suite e gates idênticos

`passed_final == passed_baseline`, zero failures/errors; ruff/format/mypy verdes; inspeção global sem `fallback_to_bridge`.

## Arquivos esperados (7)

- `apps/cases/procedures.py`
- `apps/doctor/views.py`
- `apps/scheduler/views.py`
- `apps/intake/services.py`
- `apps/intake/views.py`
- `apps/cases/tests/test_case_procedure.py`
- `apps/doctor/tests/test_queue_exam_type_filters.py`

Proibido: qualquer outro arquivo; mudança de comportamento; novos helpers/parâmetros.

## TDD obrigatório (adaptado — justificativa explícita)

Remoção de parâmetro no-op não altera comportamento: RED clássico não se aplica. Evidência obrigatória:

1. `rg -n "fallback_to_bridge" apps` ANTES (call sites) e DEPOIS (zero).
2. Baseline/final completos com contagem de `passed` idêntica.

## Inspeções obrigatórias

```bash
rg -n "fallback_to_bridge" apps config templates static
rg -n "ponte transitória|dual-write|bridge_exam_type" apps/cases/procedures.py apps/doctor/views.py apps/scheduler/views.py apps/intake/services.py apps/intake/views.py

uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git diff --check
git diff --name-only "$BASE_REF"
```

## Critérios/gates

- [ ] Zero ocorrências de `fallback_to_bridge` no repositório (inspeção colada).
- [ ] Getters com assinatura limpa e docstrings sem ponte.
- [ ] `passed_final == passed_baseline`, zero failures/errors; gates verdes.
- [ ] `git diff --name-only` = só os 7 arquivos.

### Condições automáticas de INCOMPLETO

Qualquer edição fora dos 7 arquivos; `fallback_to_bridge` remanescente; mudança de comportamento (contagem de testes diferente ou teste alterado além de remover o kwarg); gate falho; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011d-report.md` com lista de call sites removidos por arquivo, inspeções antes/depois, baseline/final e handoff final do encerramento da ponte para o Slice 012.

## Prompt pronto

```text
Read all artifacts, ADR-0004 and the approved Slice 011-C report. If Slice 011-C is not approved (Case.exam_type still exists), STOP BLOCKED. Implement ONLY Slice 011-D.

Remove the no-op fallback_to_bridge parameter from get_declared_procedure_types/get_detected_procedure_types/get_approved_procedure_types in apps/cases/procedures.py and drop the kwarg from every call site in apps/doctor/views.py, apps/scheduler/views.py, apps/intake/services.py, apps/intake/views.py, apps/cases/tests/test_case_procedure.py and apps/doctor/tests/test_queue_exam_type_filters.py. Update bridge comments/docstrings in those 7 files only. This is behavior-neutral: passed_final must equal passed_baseline with zero failures/errors.

Run the rg before/after evidence, full quality gate, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011d-report.md; if complete mark only Slice 011-D, commit, push, reply REPORT_PATH and STOP.
```
