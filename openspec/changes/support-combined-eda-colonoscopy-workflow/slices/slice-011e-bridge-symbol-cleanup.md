# Slice 011-E: Encerramento simbólico da ponte — remoção da classe `ExamType` e do parâmetro `fallback_to_bridge`

> **Slice novo do re-split** (após bloqueio legítimo do 011-C original, relatório
> `/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md`). O cutover físico
> (011-C revisado) preservou a classe `ExamType` porque 4 testes de intake a importam como
> fonte de valores de contrato; o 011-D revisado removeu o kwarg `fallback_to_bridge` de
> todos os call sites mantendo o parâmetro na definição. Este slice encerra os dois
> últimos símbolos da ponte num único commit mecânico e sem mudança de comportamento.

## Handoff com contexto zero

Leia artefatos, ADR-0004 e os relatórios aprovados dos Slices 011-C (revisado) e 011-D (revisado). Se 011-C não estiver aprovado (coluna `Case.exam_type` ainda existir) ou 011-D não estiver aprovado (call sites ainda passando `fallback_to_bridge=`), PARE como BLOQUEADO.

### Contexto e fluxo entregue

A coluna e o dual-write já não existem (011-C); nenhum call site passa o kwarg compat (011-D). Restam dois símbolos mortos:

```text
classe ExamType (apps/cases/models.py) — valores "eda"/"colonoscopy" idênticos a ProcedureType
→ substituição mecânica ExamType.X → ProcedureType.X / literais nos 4 testes de intake + services + views
→ classe removida do modelo

parâmetro fallback_to_bridge (3 getters de apps/cases/procedures.py)
→ nenhum call site o passa mais; definição removida
→ suite verde sem nenhum símbolo da ponte
```

Slice mecânico, sem mudança de comportamento: `ExamType.EDA == ProcedureType.EDA == "eda"` e `ExamType.COLONOSCOPY == ProcedureType.COLONOSCOPY == "colonoscopy"`; o parâmetro já era no-op.

## Protocolo obrigatório para DeepSeek4-Flash

Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: inventário por arquivo (re rode os `rg` abaixo; a contagem deve bater com a tabela de arquivos).
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Evidência substitutiva de RED** (slice sem mudança de comportamento): inspeções ANTES (usos `ExamType\.` por arquivo; definição do parâmetro em `procedures.py`) e DEPOIS (zero usos fora de nomes de classe/comentários classificados; parâmetro ausente).
4. **Edição mínima e mecânica**: substituições de mesmo valor + remoção do parâmetro. Nenhuma mudança de lógica, assert ou nome de teste.
5. **Inspeções obrigatórias** ao final.
6. **Quality gate completo**: final exit code 0, zero failures/errors e `passed_final == passed_baseline`.
7. **Relatório** em `/tmp/support-combined-eda-colonoscopy-workflow-slice-011e-report.md`, checkbox somente 011-E, commit/push e PARE.

**Cap: exatamente os 9 arquivos listados.** Qualquer arquivo extra = PARE antes de editar.

## Requisitos

### R1. Classe `ExamType` removida do modelo

`apps/cases/models.py`: remover a classe `ExamType` e qualquer comentário/docstring que a cite (incl. a docstring de deprecação adicionada no 011-C). `ProcedureType` permanece enum de componentes; `EDA_COLONOSCOPY` permanece constante de seleção derivada. Migrations antigas não referenciam a classe (verificado: 0014 usa literais) — nada a ajustar nelas.

### R2. Substituição mecânica em produto

- `apps/intake/services.py`: import/`_DECLARED_SELECTION_VALUES`/`ensure_exam_type_allowed`/`_procedure_types_for_selection` e comentários passam a `ProcedureType`/literais equivalentes (mesmos valores `eda|colonoscopy|eda_colonoscopy`).
- `apps/intake/views.py`: `_NIR_DECLARED_DIMENSIONS` e comentário passam a `ProcedureType`/literais; import `ExamType` removido.
- `apps/scheduler/views.py`: comentário L~1232 que cita ``ExamType.values`` é reescrito (a validação explícita de `eda|colonoscopy|eda_colonoscopy` permanece; só o texto muda).

### R3. Substituição mecânica nos 4 testes de intake

`ExamType.EDA` → `ProcedureType.EDA` (ou `"eda"`), `ExamType.COLONOSCOPY` → `ProcedureType.COLONOSCOPY` (ou `"colonoscopy"`), removendo o import da classe em cada arquivo:

- `test_exam_type_correction.py` (~45 usos): `new_exam_type=`, forms POST `{"exam_type": ...}`, valores `old_procedures`/`new_procedures` em payloads de evento.
- `test_slice_001_correction_projection.py` (~5 usos): `new_exam_type=`.
- `test_slice_005_nir_correction_and_response.py` (~25 usos): chaves de `_PROCEDURES_BY_SELECTION`, defaults de helper, `new_exam_type=`, threads.
- `test_slice_008_nir_declared_projection_authority.py` (~7 usos): comparações, `_make_eligible_case`, loop de dimensões.

Nenhum assert muda de sentido; nenhum teste é renomeado/removido/adicionado.

### R4. Parâmetro `fallback_to_bridge` removido da definição

`apps/cases/procedures.py`: remover o parâmetro keyword-only, as linhas `del fallback_to_bridge` e as menções de compat nas docstrings dos 3 getters (`get_declared_procedure_types`, `get_detected_procedure_types`, `get_approved_procedure_types`). Assinatura final: `get_*_procedure_types(case: Case) -> tuple[str, ...]`. Nenhum call site passa o kwarg (011-D garantiu; conferir por inspeção antes de editar).

### R5. Suite e gates idênticos

`passed_final == passed_baseline`, zero failures/errors; ruff/format/mypy verdes; inspeções globais sem `ExamType` (símbolo) e sem `fallback_to_bridge`.

## Arquivos esperados (9)

| # | Arquivo | Papel |
| --- | --- | --- |
| 1 | `apps/cases/models.py` | R1: classe `ExamType` removida |
| 2 | `apps/cases/procedures.py` | R4: parâmetro removido dos 3 getters |
| 3 | `apps/intake/services.py` | R2: substituição mecânica |
| 4 | `apps/intake/views.py` | R2: substituição mecânica |
| 5 | `apps/scheduler/views.py` | R2: comentário reescrito (somente texto) |
| 6 | `apps/intake/tests/test_exam_type_correction.py` | R3 |
| 7 | `apps/intake/tests/test_slice_001_correction_projection.py` | R3 |
| 8 | `apps/intake/tests/test_slice_005_nir_correction_and_response.py` | R3 |
| 9 | `apps/intake/tests/test_slice_008_nir_declared_projection_authority.py` | R3 |

Proibido: qualquer outro arquivo; mudança de comportamento/assert/lógica; novos helpers; tocar migrations, doctor/scheduler/pipeline/dashboard fora do comentário listado.

## TDD obrigatório (adaptado — justificativa explícita)

Substituição de símbolos de mesmo valor e remoção de parâmetro no-op não alteram comportamento: RED clássico não se aplica. Evidência obrigatória:

1. `rg -on "ExamType\.\w+" apps` ANTES (contagem por membro) e DEPOIS (zero).
2. `rg -ln "ExamType" apps config --glob '!**/migrations/**'` DEPOIS: somente nomes de classe de teste (ex.: `TestSchedulerQueueExamTypeFilters`) e comentários classificados — nenhum import, nenhum `ExamType.`.
3. `rg -n "fallback_to_bridge" apps` DEPOIS: zero ocorrências.
4. Baseline/final completos com contagem de `passed` idêntica.

## Inspeções obrigatórias

```bash
rg -on "ExamType\.\w+" apps config
rg -ln "ExamType" apps config --glob '!**/migrations/**'
rg -n "from apps\.cases\.models import [^(]*ExamType" apps config
rg -n "fallback_to_bridge" apps config templates static
rg -n "class ExamType" apps

uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

## Critérios/gates

- [ ] Classe `ExamType` inexistente fora de migrations/nomes de classe/comentários classificados.
- [ ] Parâmetro `fallback_to_bridge` inexistente no repositório (inspeção colada).
- [ ] Substituições comprovadamente de mesmo valor (`eda`/`colonoscopy`); nenhum assert alterado em sentido.
- [ ] `passed_final == passed_baseline`, zero failures/errors; gates verdes.
- [ ] `git diff --name-only` = só os 9 arquivos.

### Condições automáticas de INCOMPLETO

Qualquer edição fora dos 9 arquivos; `ExamType.` remanescente como símbolo; `fallback_to_bridge` remanescente; mudança de comportamento (contagem de testes diferente ou assert alterado além da substituição de mesmo valor); classe removida antes das substituições nos importadores (ordem que quebre a coleta); gate falho; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011e-report.md` com contagem de substituições por arquivo, inspeções antes/depois, baseline/final e handoff do encerramento total da ponte para o Slice 012 (coluna ausente, classe ausente, parâmetro ausente, rows como fonte única).

## Prompt pronto

```text
Read all artifacts, ADR-0004 and the approved reports of revised Slice 011-C and revised Slice 011-D. If revised 011-C is not approved (Case.exam_type still exists) or revised 011-D is not approved (any call site still passes fallback_to_bridge=), STOP BLOCKED. Implement ONLY Slice 011-E.

Mechanically replace ExamType.EDA/ExamType.COLONOSCOPY with ProcedureType.EDA/ProcedureType.COLONOSCOPY or identical string literals ("eda"/"colonoscopy") in apps/intake/services.py, apps/intake/views.py, apps/intake/tests/test_exam_type_correction.py, apps/intake/tests/test_slice_001_correction_projection.py, apps/intake/tests/test_slice_005_nir_correction_and_response.py and apps/intake/tests/test_slice_008_nir_declared_projection_authority.py, then delete the ExamType class from apps/cases/models.py. Rewrite the scheduler/views.py comment that mentions ExamType.values (validation stays; only the text changes). Remove the fallback_to_bridge keyword-only parameter, its del lines and compat docstring mentions from the three getters in apps/cases/procedures.py. No behavior change: passed_final must equal passed_baseline with zero failures/errors; no assert may change meaning; no test renamed/removed/added.

Run the rg before/after evidence, full quality gate, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011e-report.md; if complete mark only Slice 011-E, commit, push, reply REPORT_PATH and STOP.
```
