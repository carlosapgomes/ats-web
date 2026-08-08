# Slice 011-A: Fixtures sem ponte — cases/dashboard/doctor/pipeline

## Handoff com contexto zero

Leia artefatos, ADR-0004, relatórios aprovados 001–010 e o relatório BLOQUEADO do Slice 011 original (`/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md`), que contém o inventário global classificado. Se 010 não estiver aprovado ou a árvore não estiver limpa em `feature/support-combined-eda-colonoscopy-workflow`, PARE como BLOQUEADO.

### Contexto e fluxo entregue

Os Slices 008–010 tornaram o produto (pipeline, NIR, médico, CHD, dashboard) independente da ponte `Case.exam_type`. Mas **18 arquivos de teste ainda gravam `exam_type=` em `Case.objects.create(...)`** ou assertem a coluna — herança da ponte. O cutover físico (Slice 011-C) remove a coluna; qualquer escrita/leitura ORM remanescente quebraria com `TypeError`/`AttributeError`. Este slice prepara a primeira metade das fixtures.

```text
fixtures de cases/dashboard/doctor/pipeline param de escrever/ler a coluna
→ cenários passam a construir projeção CaseProcedure explicitamente
→ asserts de coluna viram asserts de projeção (getters/selection_key/labels)
→ produto, schema, dual-write e signal permanecem intactos
→ suite continua verde com a coluna viva (prova de independência)
```

Este é um slice **somente de testes**. Nenhuma linha de produto, template, static, migration ou docs.

## Protocolo obrigatório para DeepSeek4-Flash

Este slice será implementado por um modelo rápido com tendência a concluir cedo demais. Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: matriz `Arquivo → usos da coluna encontrados → estratégia de reescrita`.
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Evidência substitutiva de RED** (ver seção TDD): para cada arquivo, cole a inspeção `rg` ANTES (com hits de coluna) e DEPOIS (zero hits).
4. **Edição mínima**: reescreva apenas o necessário para remover o acesso à coluna; não reformule cenários além disso.
5. **Inspeções obrigatórias** ao final (seção própria).
6. **Quality gate completo**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`. Final com exit code 0, zero failures/errors e `passed_final >= passed_baseline` (ver R3 para contagem).
7. **Relatório com evidência** em `/tmp/support-combined-eda-colonoscopy-workflow-slice-011a-report.md`: matriz, inspeções antes/depois por arquivo, testes reescritos com justificativa, baseline/final, handoff.

**Cap: exatamente os 8 arquivos de teste listados.** Qualquer arquivo extra = PARE antes de editar.

## Requisitos

### R1. Nenhuma escrita da coluna nos 8 arquivos

Remover todo `exam_type=` de `Case.objects.create(...)`, `.update(exam_type=...)` e atribuições `case.exam_type = ...` nos 8 arquivos. Todo cenário que precisa de projeção declarada/detectada/aprovada cria rows **explicitamente** pelos padrões já usados no próprio arquivo (`set_declared_procedures`, `CaseProcedure.objects.create`, helpers locais). Cenário que hoje depende só do valor da coluna (sem rows) deve declarar rows ou virar cenário "sem rows", conforme R3.

### R2. Nenhuma leitura da coluna nos 8 arquivos

Todo `assert ....exam_type == ...`, `filter(exam_type=...)` ou pré-condição sobre a coluna vira assert de projeção: `get_declared_procedure_types` / `get_detected_procedure_types` / `get_approved_procedure_types` (sem `fallback_to_bridge`, ou com `False` enquanto o parâmetro existe), `selection_key`, labels de badge/HTML já projetados.

### R3. Semântica preservada, sem perda líquida de cobertura

- Comportamento provado não muda: ausência de rows ⇒ `none`/vazio; combinado = 2 rows/1 caso; ponte divergente não altera projeção.
- Testes cujo propósito era "prova que a ponte é ignorada" viram "projeção vem só das rows / ausência ⇒ none".
- Se dois cenários ficarem indistinguíveis sem a coluna (ex.: dois casos legados que só diferiam pelo valor da coluna), eles podem ser fundidos **somente se** um teste substituto cobrir o mesmo comportamento operacional. Toda remoção/fusão exige justificativa no relatório.
- `passed_final >= passed_baseline`: cada teste removido exige substituto. Registre a aritmética (X reescritos, Y fundidos, Z substitutos adicionados).
- Docstrings que citam "ponte"/"bridge" devem ser atualizadas para o contrato novo.

### R4. Arquivos proibidos

- `apps/cases/tests/test_exam_type.py` — módulo dedicado da ponte; morre no cutover (011-C). Não tocar.
- Qualquer arquivo de produto/template/static/migration/docs — este slice é somente testes.
- Os 9 arquivos de teste do Slice 011-B (intake/scheduler) — não tocar.

### R5. Suite verde com a coluna viva

Ao final, a coluna, o dual-write (`set_declared_procedures`/`sync_declared_projection`) e o signal `CASE_CREATED` continuam intactos e a suite inteira passa — prova de que as fixtures já não dependem da ponte.

## Arquivos esperados (8)

- `apps/cases/tests/test_case_procedure.py`
- `apps/dashboard/tests/test_dashboard.py`
- `apps/dashboard/tests/test_procedure_analytics.py`
- `apps/doctor/tests/test_colonoscopy_doctor.py`
- `apps/doctor/tests/test_queue_exam_type_filters.py`
- `apps/doctor/tests/test_slice_003_prior_and_queue.py`
- `apps/doctor/tests/test_slice_003_procedure_decision.py`
- `apps/pipeline/tests/test_colonoscopy_pipeline.py`

Guias de reescrita por arquivo (inventário do relatório bloqueado):

| Arquivo | Hoje | Direção |
| --- | --- | --- |
| `test_case_procedure.py` | 3 creates com kwarg; 6 atribuições/asserts de ponte; pré-condição `case.exam_type == ExamType.EDA` | removes kwarg/pré-condição; em `test_case_without_rows_empty_even_with_combined_bridge`, remover só a parte da ponte (`exam_type=EDA_COLONOSCOPY`) e preservar a prova de que `doctor_decision="accept"` não recria aprovado |
| `test_dashboard.py` | 1 create + `update(exam_type=)` no teste do badge | teste do badge vira prova de projeção pura: declara rows, assert no badge dimensional e na ausência do badge singular |
| `test_procedure_analytics.py` | 4 creates de "casos legados sem rows" | manter cenários como "caso sem rows" (kwarg sai); docstrings atualizadas; asserts de `none` preservados |
| `test_colonoscopy_doctor.py` / `test_queue_exam_type_filters.py` / `test_slice_003_*` / `test_colonoscopy_pipeline.py` | creates com kwarg (7+17+1+3) | remover kwarg e garantir rows explícitas onde a fila/decisão depende de projeção |

## TDD obrigatório (adaptado — justificativa explícita)

Slice de reescrita mecânica de fixtures **sem mudança de comportamento de produto**: RED/GREEN clássico não se aplica (não há código de produto para falhar/passar). Evidência obrigatória substitutiva:

1. Inspeção `rg` por arquivo ANTES (hits) e DEPOIS (zero hits) — é o "RED" deste slice.
2. Suite baseline e final completas; `passed_final >= passed_baseline`.
3. Pelo menos 1 teste novo por módulo (4 no total) provando o fluxo canônico do módulo construído apenas com rows (passa antes e depois — é cobertura de segurança do contrato final).

## Inspeções obrigatórias

```bash
# ANTES e DEPOIS, por arquivo (zero hits depois):
rg -n "exam_type=|\.exam_type|ExamType|EDA_COLONOSCOPY" <cada um dos 8 arquivos>

# Inventário global pós-slice: writers de teste restantes devem ser APENAS
# os 9 arquivos do 011-B + test_exam_type.py (011-C); produto igual ao estado 33ed972:
rg -ln "exam_type=|\.exam_type" apps/*/tests --glob '*.py' | sort
rg -n "case\.exam_type|instance\.exam_type" apps --glob '!**/tests/**' --glob '!**/migrations/**'

uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git diff --check
git diff --name-only "$BASE_REF"
```

Interprete no relatório: liste os arquivos de teste que ainda tocam a coluna e confirme que são exatamente os destinados a 011-B/011-C.

## Critérios/gates

- [ ] Zero ocorrências de acesso ORM à coluna nos 8 arquivos (inspeção colada).
- [ ] R1–R5 provados; cenários mantêm semântica (ausência ⇒ none; combinado 1 caso/2 rows).
- [ ] `passed_final >= passed_baseline`, zero failures/errors; aritmética de testes registrada.
- [ ] Nenhum arquivo de produto/template/migration tocado (`git diff --name-only` = só os 8).
- [ ] Produto intocado: dual-write, signal e coluna continuam vivos e funcionais.

### Condições automáticas de INCOMPLETO

Qualquer edição fora dos 8 arquivos; suite final com failure/error ou `passed_final < passed_baseline` sem substituto justificado; acesso à coluna remanescente nos 8 arquivos; docstring ainda descrevendo comportamento de ponte removido do teste; inspeção antes/depois ausente do relatório; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011a-report.md` com matriz arquivo → usos → reescrita, inspeções antes/depois, snippets representativos (3–5), aritmética de testes, baseline/final, classificação do inventário residual e Handoff para o 011-B.

## Prompt pronto

```text
Read all artifacts, ADR-0004, approved reports 001-010 and the blocked Slice 011 report (/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md). If Slice 010 is not approved or the tree is dirty, STOP BLOCKED. Implement ONLY Slice 011-A.

Migrate exactly these 8 test files to stop writing/reading the Case.exam_type column: apps/cases/tests/test_case_procedure.py, apps/dashboard/tests/test_dashboard.py, apps/dashboard/tests/test_procedure_analytics.py, apps/doctor/tests/test_colonoscopy_doctor.py, apps/doctor/tests/test_queue_exam_type_filters.py, apps/doctor/tests/test_slice_003_prior_and_queue.py, apps/doctor/tests/test_slice_003_procedure_decision.py, apps/pipeline/tests/test_colonoscopy_pipeline.py. Replace exam_type= create kwargs with explicit CaseProcedure rows; replace column asserts with projection asserts (getters/selection_key/labels); keep absence=>none and combined 1-case/2-rows semantics; every deleted/merged test needs a justified replacement so passed_final >= passed_baseline. Do NOT touch product code, templates, migrations, test_exam_type.py, or the 9 intake/scheduler test files of Slice 011-B. The column, dual-write and CASE_CREATED signal stay alive and the suite must stay green.

Run the adapted TDD evidence (rg before/after per file), full quality gate, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011a-report.md; if complete mark only Slice 011-A, commit, push, reply REPORT_PATH and STOP.
```
