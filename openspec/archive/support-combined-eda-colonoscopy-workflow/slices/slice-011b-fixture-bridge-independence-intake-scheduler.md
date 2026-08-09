# Slice 011-B: Fixtures sem ponte — intake/scheduler

## Handoff com contexto zero

Leia artefatos, ADR-0004, relatórios aprovados 001–010, o relatório BLOQUEADO do Slice 011 original (`/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md`) e o relatório aprovado do Slice 011-A. Se 011-A não estiver aprovado ou a árvore não estiver limpa em `feature/support-combined-eda-colonoscopy-workflow`, PARE como BLOQUEADO.

### Contexto e fluxo entregue

O Slice 011-A removeu o acesso à coluna das fixtures de cases/dashboard/doctor/pipeline. Este slice faz o mesmo para a segunda metade (intake/scheduler), incluindo dois contratos especiais: o payload do evento `CASE_CREATED` e a "ponte oposta" do Slice 008. Após este slice, **nenhum teste fora do módulo de ponte (`test_exam_type.py`) acessa `Case.exam_type` via ORM**, e o cutover físico (011-C) fica limitado a produto + migration.

```text
fixtures de intake/scheduler param de escrever/ler a coluna
→ asserts de correção NIR viram projeção declarada
→ assert do payload CASE_CREATED migra para contrato que sobrevive ao cutover
→ "ponte oposta" (008) vira cenário de ausência de rows
→ produto, schema, dual-write e signal permanecem intactos
→ suite verde com a coluna viva
```

Este é um slice **somente de testes**. Nenhuma linha de produto, template, static, migration ou docs.

## Protocolo obrigatório para DeepSeek4-Flash

Este slice será implementado por um modelo rápido com tendência a concluir cedo demais. Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: matriz `Arquivo → usos da coluna encontrados → estratégia de reescrita`.
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Evidência substitutiva de RED** (ver seção TDD): para cada arquivo, cole a inspeção `rg` ANTES (com hits de coluna) e DEPOIS (zero hits).
4. **Edição mínima**: reescreva apenas o necessário para remover o acesso à coluna.
5. **Inspeções obrigatórias** ao final (seção própria).
6. **Quality gate completo**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`. Final com exit code 0, zero failures/errors e `passed_final >= passed_baseline` (ver R3).
7. **Relatório com evidência** em `/tmp/support-combined-eda-colonoscopy-workflow-slice-011b-report.md`.

**Cap: exatamente os 9 arquivos de teste listados.** Qualquer arquivo extra = PARE antes de editar.

## Requisitos

### R1. Nenhuma escrita/leitura da coluna nos 9 arquivos

Remover todo `exam_type=` de creates/POSTs de fixture que criam a coluna diretamente, atribuições `case.exam_type = ...`, asserts `reloaded.exam_type == ...` e `filter(exam_type=...)`. Cenários passam a construir rows explicitamente pelos padrões já usados no arquivo. **Atenção**: parâmetros de formulário/URL (`client.post(..., {"exam_type": ...})`, `?exam_type=`) são contrato SSR legítimo (R6 do 011 original) e **permanecem** — só o acesso ORM à coluna sai.

### R2. Correção NIR assertida pela projeção

`test_exam_type_correction.py` (~24 asserts de coluna), `test_corrected_resubmission.py`, `test_slice_001_correction_projection.py` e `test_slice_005_nir_correction_and_response.py`: todo `reloaded.exam_type == ExamType.X` vira `get_declared_procedure_types(reloaded, fallback_to_bridge=False) == (...)` (ou assert de evento `CASE_PROCEDURE_DECLARATION_CORRECTED` com `old_procedures`/`new_procedures`, onde for o foco do teste). Igualdade/diferença de conjuntos continua sendo o contrato.

### R3. Payload CASE_CREATED sem dependência da chave `exam_type`

`test_exam_type_intake.py` hoje asserta `event.payload.get("exam_type") == ...`. O cutover (011-C) removerá essa chave de eventos novos (decisão registrada no slice 011-C; nenhum reader operacional a consome e a declaração já é auditada por `CASE_PROCEDURES_DECLARED`). Reescreva agora para contrato que sobrevive: evento `CASE_CREATED` existe com `status`, e o caso projeta o conjunto declarado correto via rows.

### R4. "Ponte oposta" do Slice 008 vira cenário de ausência

`test_slice_008_nir_declared_projection_authority.py` atribui `case.exam_type = ExamType.EDA` com rows divergentes para provar que o NIR ignora a coluna. Sem coluna, a prova equivalente é: caso sem rows declaradas projeta vazio para o NIR mesmo com outros sinais preenchidos (ex.: `doctor_decision`). Reescreva mantendo o comportamento provado.

### R5. Sem perda líquida de cobertura

`passed_final >= passed_baseline`: cada teste removido/fundido exige substituto justificado no relatório (aritmética registrada). Docstrings que citam "ponte" devem ser atualizadas.

### R6. Arquivos proibidos e suite verde com a coluna viva

- Proibido: qualquer produto/template/static/migration/docs; `apps/cases/tests/test_exam_type.py` (morre no 011-C); os 8 arquivos já migrados no 011-A.
- Ao final, coluna/dual-write/signal continuam vivos e a suite inteira passa.

## Arquivos esperados (9)

- `apps/intake/tests/test_corrected_resubmission.py`
- `apps/intake/tests/test_exam_type_correction.py`
- `apps/intake/tests/test_exam_type_intake.py`
- `apps/intake/tests/test_my_cases.py`
- `apps/intake/tests/test_slice_001_correction_projection.py`
- `apps/intake/tests/test_slice_005_nir_correction_and_response.py`
- `apps/intake/tests/test_slice_008_nir_declared_projection_authority.py`
- `apps/scheduler/tests/test_exam_type_filters.py`
- `apps/scheduler/tests/test_slice_004_paired_scheduler_appointment.py`

## TDD obrigatório (adaptado — justificativa explícita)

Slice de reescrita mecânica de fixtures **sem mudança de comportamento de produto**: RED/GREEN clássico não se aplica. Evidência obrigatória substitutiva:

1. Inspeção `rg` por arquivo ANTES (hits) e DEPOIS (zero hits de acesso ORM à coluna).
2. Suite baseline e final completas; `passed_final >= passed_baseline`.
3. Pelo menos 1 teste novo por módulo (2 no total: intake e scheduler) provando o fluxo canônico construído apenas com rows.

## Inspeções obrigatórias

```bash
# ANTES e DEPOIS, por arquivo (zero hits ORM depois; params SSR "exam_type" em
# client.post/GET podem permanecer — classifique cada ocorrência no relatório):
rg -n "exam_type=|\.exam_type|ExamType|EDA_COLONOSCOPY" <cada um dos 9 arquivos>

# Inventário global pós-slice: ÚNICO arquivo de teste com acesso ORM à coluna
# deve ser apps/cases/tests/test_exam_type.py (destinado ao 011-C):
rg -ln "\.exam_type|Case\.objects\.create\([^)]*exam_type|exam_type=" apps/*/tests --glob '*.py' | sort
rg -n "case\.exam_type|instance\.exam_type" apps --glob '!**/tests/**' --glob '!**/migrations/**'

uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
git diff --check
git diff --name-only "$BASE_REF"
```

## Critérios/gates

- [ ] Zero acesso ORM à coluna nos 9 arquivos (inspeção colada); params SSR preservados e classificados.
- [ ] Correção NIR assertida por projeção/evento (R2); payload CASE_CREATED migrado (R3); ponte oposta reescrita (R4).
- [ ] `passed_final >= passed_baseline`, zero failures/errors; aritmética registrada.
- [ ] `git diff --name-only` = só os 9 arquivos; produto intocado.
- [ ] Suite verde com coluna/dual-write/signal vivos.

### Condições automáticas de INCOMPLETO

Qualquer edição fora dos 9 arquivos; acesso ORM à coluna remanescente neles; suite final com failure/error ou `passed_final < passed_baseline` sem substituto justificado; param SSR legítimo removido (quebra de contrato de formulário/URL); inspeção antes/depois ausente; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011b-report.md` com matriz arquivo → usos → reescrita, inspeções antes/depois, snippets representativos (3–5), aritmética de testes, baseline/final, inventário residual (deve restar apenas `test_exam_type.py` + produto destinado ao 011-C) e Handoff para o 011-C.

## Prompt pronto

```text
Read all artifacts, ADR-0004, approved reports 001-010 plus 011-A, and the blocked Slice 011 report (/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md). If Slice 011-A is not approved or the tree is dirty, STOP BLOCKED. Implement ONLY Slice 011-B.

Migrate exactly these 9 test files to stop writing/reading the Case.exam_type column via ORM: apps/intake/tests/test_corrected_resubmission.py, test_exam_type_correction.py, test_exam_type_intake.py, test_my_cases.py, test_slice_001_correction_projection.py, test_slice_005_nir_correction_and_response.py, test_slice_008_nir_declared_projection_authority.py, apps/scheduler/tests/test_exam_type_filters.py, test_slice_004_paired_scheduler_appointment.py. Replace column asserts with projection/event asserts; keep form/URL exam_type params intact (SSR contract); migrate the CASE_CREATED payload assert to the surviving contract (event exists with status + declared rows) and the Slice 008 opposite-bridge scenario to a rows-absence scenario. Every deleted/merged test needs a justified replacement so passed_final >= passed_baseline. Do NOT touch product code, templates, migrations or test_exam_type.py. The column, dual-write and signal stay alive and the suite must stay green.

Run the adapted TDD evidence (rg before/after per file), full quality gate, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011b-report.md; if complete mark only Slice 011-B, commit, push, reply REPORT_PATH and STOP.
```
