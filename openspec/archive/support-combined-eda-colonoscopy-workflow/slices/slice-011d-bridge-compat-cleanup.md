# Slice 011-D (revisado): Remoção do kwarg `fallback_to_bridge` de todos os call sites

> **REVISÃO após bloqueio legítimo do 011-C original:** o 011-D antigo listava 7 arquivos,
> mas o inventário real de `fallback_to_bridge` tem **11** arquivos de código
> (definição em `procedures.py` + 10 call sites — incluindo 4 testes de intake que o
> desenho antigo omitia). Remover o parâmetro da definição com call sites ainda passando
> o kwarg quebraria a suite num único passo acima do cap. Este slice revisado remove
> apenas o **kwarg dos call sites** (10 arquivos) enquanto o parâmetro permanece aceito
> como no-op — comportamento idêntico, suite verde. O Slice 011-E remove o parâmetro da
> definição junto com a classe `ExamType`.

## Handoff com contexto zero

Leia artefatos, ADR-0004 e o relatório aprovado do Slice 011-C revisado. Se 011-C não estiver aprovado (coluna `Case.exam_type` ainda existir), PARE como BLOQUEADO.

### Contexto e fluxo entregue

O Slice 010 rebaixou `fallback_to_bridge` a parâmetro no-op (`del fallback_to_bridge`) para não explodir o cap; o 011-C removeu a coluna e o dual-write, mas manteve o parâmetro por compatibilidade de call sites. Este slice remove o kwarg morto de todos os call sites (produto e testes) e atualiza comentários que o citam nos arquivos tocados. O parâmetro na definição permanece (aceito, sem efeito) até o 011-E.

```text
call sites (NIR/médico/CHD/testes) perdem o kwarg morto
→ chamadas ficam get_*_procedure_types(case)
→ comentários/docstrings que citam o kwarg são reescritos nos arquivos tocados
→ suite verde; única referência restante é a definição em procedures.py (sai no 011-E)
```

Slice mecânico, sem mudança de comportamento (o parâmetro já era no-op).

## Protocolo obrigatório para DeepSeek4-Flash

Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: lista de call sites por arquivo (comece pelo inventário do relatório do 011-C revisado; re rode o `rg` abaixo e confira que os call sites são exatamente os 10 arquivos listados).
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Evidência substitutiva de RED** (slice sem mudança de comportamento): inspeção `rg -n "fallback_to_bridge" apps` ANTES (call sites + definição) e DEPOIS (somente a definição em `apps/cases/procedures.py`).
4. **Edição mínima**: remover o kwarg `fallback_to_bridge=False` de cada chamada e reescrever comentários/docstrings que o citam **nos arquivos tocados**. Nenhuma outra mudança.
5. **Inspeções obrigatórias** ao final.
6. **Quality gate completo**: final exit code 0, zero failures/errors e `passed_final == passed_baseline` (nenhum teste é removido neste slice).
7. **Relatório** em `/tmp/support-combined-eda-colonoscopy-workflow-slice-011d-report.md`, checkbox somente 011-D, commit/push e PARE.

**Cap: exatamente os 10 arquivos listados.** Qualquer arquivo extra (incluindo `apps/cases/procedures.py`) = PARE antes de editar.

## Requisitos

### R1. Call sites de produto atualizados

Remover `fallback_to_bridge=False` de todas as chamadas em `apps/doctor/views.py`, `apps/scheduler/views.py`, `apps/intake/views.py` e `apps/intake/services.py`. Docstrings/comentários desses arquivos que citam o kwarg (ex.: `doctor/views.py` L221, `scheduler/views.py` L158) são reescritos para o contrato vigente (rows como fonte única; ausência ⇒ `()`).

### R2. Call sites de teste atualizados

Remover o kwarg das chamadas em `apps/cases/tests/test_case_procedure.py`, `apps/doctor/tests/test_queue_exam_type_filters.py`, `apps/intake/tests/test_exam_type_correction.py`, `apps/intake/tests/test_exam_type_intake.py`, `apps/intake/tests/test_slice_001_correction_projection.py` e `apps/intake/tests/test_slice_005_nir_correction_and_response.py`. Nenhum assert muda de sentido: `get_*_procedure_types(case)` já devolve exatamente o que `fallback_to_bridge=False` devolvia (o parâmetro era no-op).

### R3. Definição intacta até o 011-E

`apps/cases/procedures.py` **não é editado** neste slice: o parâmetro continua aceito como no-op (`del fallback_to_bridge`) para manter a compatibilidade enquanto os call sites migram em commit único. O Slice 011-E remove o parâmetro.

### R4. Suite e gates idênticos

`passed_final == passed_baseline`, zero failures/errors; ruff/format/mypy verdes; inspeção global mostra `fallback_to_bridge` somente na definição (`apps/cases/procedures.py`).

## Arquivos esperados (10)

- `apps/doctor/views.py`
- `apps/scheduler/views.py`
- `apps/intake/views.py`
- `apps/intake/services.py`
- `apps/cases/tests/test_case_procedure.py`
- `apps/doctor/tests/test_queue_exam_type_filters.py`
- `apps/intake/tests/test_exam_type_correction.py`
- `apps/intake/tests/test_exam_type_intake.py`
- `apps/intake/tests/test_slice_001_correction_projection.py`
- `apps/intake/tests/test_slice_005_nir_correction_and_response.py`

Proibido: `apps/cases/procedures.py` (definição — 011-E); `apps/cases/models.py` e classe `ExamType` (011-E); qualquer outro arquivo; mudança de comportamento; novos helpers/parâmetros.

## TDD obrigatório (adaptado — justificativa explícita)

Remoção de kwarg no-op não altera comportamento: RED clássico não se aplica. Evidência obrigatória:

1. `rg -n "fallback_to_bridge" apps` ANTES (call sites nos 10 arquivos + definição) e DEPOIS (somente `apps/cases/procedures.py`).
2. Baseline/final completos com contagem de `passed` idêntica.

## Inspeções obrigatórias

```bash
rg -n "fallback_to_bridge" apps config templates static
rg -n "get_(declared|detected|approved)_procedure_types\(" apps --glob '!**/migrations/**' | rg "fallback"   # esperado: vazio

uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git diff --check
git diff --name-only "$BASE_REF"
```

## Critérios/gates

- [ ] Nenhuma chamada passa `fallback_to_bridge` (inspeção colada); única ocorrência restante é a definição em `procedures.py`.
- [ ] Comentários/docstrings que citavam o kwarg reescritos nos arquivos tocados.
- [ ] `passed_final == passed_baseline`, zero failures/errors; gates verdes.
- [ ] `git diff --name-only` = só os 10 arquivos.

### Condições automáticas de INCOMPLETO

Qualquer edição fora dos 10 arquivos (incl. `procedures.py`); kwarg remanescente em call site; mudança de comportamento (contagem de testes diferente ou assert alterado além de remover o kwarg); gate falho; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011d-report.md` com lista de call sites removidos por arquivo (contagem antes/depois), inspeções antes/depois, baseline/final e handoff para o 011-E (definição restante em `procedures.py` + inventário `ExamType`).

## Prompt pronto

```text
Read all artifacts, ADR-0004 and the approved revised Slice 011-C report. If revised Slice 011-C is not approved (Case.exam_type still exists), STOP BLOCKED. Implement ONLY revised Slice 011-D.

Drop the dead fallback_to_bridge=False kwarg from every call site in apps/doctor/views.py, apps/scheduler/views.py, apps/intake/views.py, apps/intake/services.py, apps/cases/tests/test_case_procedure.py, apps/doctor/tests/test_queue_exam_type_filters.py, apps/intake/tests/test_exam_type_correction.py, apps/intake/tests/test_exam_type_intake.py, apps/intake/tests/test_slice_001_correction_projection.py and apps/intake/tests/test_slice_005_nir_correction_and_response.py, and rewrite the comments/docstrings mentioning the kwarg in those files only. Do NOT edit apps/cases/procedures.py (the parameter definition stays until Slice 011-E) and do not touch the ExamType class. This is behavior-neutral: passed_final must equal passed_baseline with zero failures/errors.

Run the rg before/after evidence, full quality gate, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011d-report.md; if complete mark only Slice 011-D, commit, push, reply REPORT_PATH and STOP.
```
