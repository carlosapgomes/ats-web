# Slice 008: NIR opera somente pela projeção declarada

## Handoff com contexto zero

Leia artefatos do change, ADR-0004 e relatórios aprovados 001–007. Inspecione `apps/intake/services.py`, `apps/intake/views.py`, `apps/cases/procedures.py` apenas como contrato, e todos os testes de intake que criam `Case(exam_type=...)` ou leem `case.exam_type`.

### Fluxo entregue

```text
NIR seleciona EDA/Colon/combinado
→ CaseProcedure.declared_by_nir representa a declaração
→ correção compara conjuntos e audita old/new_procedures
→ filtros e resposta NIR leem somente rows declaradas
→ testes NIR criam a projeção explicitamente
```

A coluna/dual-write ainda existe como ponte interna até o Slice 011, mas nenhum comportamento NIR pode lê-la. Médico/CHD/dashboard serão tratados nos Slices 009–010.

## Protocolo obrigatório para implementador DeepSeek4-Flash

Falha = `INCOMPLETE`, sem task/commit/push.

1. Confirme branch/árvore/ADR, registre `BASE_REF` e matriz requisito→arquivo→teste.
2. Rode `uv run pytest` antes de editar; failure/error bloqueia.
3. Inventarie todo uso de coluna versus parâmetro SSR/selection key/evento histórico.
4. Escreva teste RED real para cada comportamento alterado.
5. GREEN mínimo só no fluxo NIR.
6. REFACTOR local: helpers coesos, sem signal/default de fixture.
7. Rode inspeções e quality gate completo; final com zero failures/errors e passed >= baseline.
8. Relatório, checkbox 008, commit/push e PARE.

**Cap: 12 arquivos produto/teste.** Se exceder, pare antes de editar.

## Requisitos

### R1. Criação e reenvio explícitos

Upload e corrected resubmission continuam aceitando as três seleções e criam 1–2 rows declaradas no mesmo `Case`. O contrato de entrada pode manter o nome SSR `exam_type`, mas ele representa uma **seleção**, não a coluna. Não criar segundo caso nem herdar seleção silenciosamente.

### R2. Correção compara conjuntos

`correct_case_exam_type` pode manter nome público por compatibilidade de rota, porém igualdade, old/new e reroteamento usam conjuntos de `CaseProcedure`. Novo evento contém `old_procedures`/`new_procedures` e não grava novas chaves singulares `old_exam_type/new_exam_type`. Eventos antigos continuam legíveis e imutáveis.

### R3. Filtros NIR usam declarado sem fallback

Remover `Q(... exam_type=...)` de `_filter_by_declared_dimension` e qualquer reader da coluna em intake. EDA/Colon são buckets exclusivos; combinado exige as duas rows. Caso inválido sem row não aparece em bucket específico e não recebe default EDA.

### R4. Apresentação e resposta vêm da projeção

Detalhe, final reply, closed search e labels NIR usam helpers projetados. Nomes de campos/query params `exam_type` e o valor textual `eda_colonoscopy` podem permanecer como contrato de seleção; não são evidência de reader da coluna.

### R5. Fixtures NIR explícitas

Testes de intake que exercem seleção, correção, reenvio, filtros ou resposta criam `CaseProcedure` explicitamente por helper local existente/coeso. Remover asserts em `case.exam_type`; provar rows/eventos. Casos propositalmente inválidos devem ser nomeados e testados como fail-closed, não receber row automática.

## Arquivos esperados

Produto: `apps/intake/services.py`, `apps/intake/views.py`; template somente se existir acesso direto comprovado à coluna. Testes esperados são os arquivos de intake diretamente afetados, priorizando helpers locais para reduzir edição repetida. `apps/cases/procedures.py` não deve perder dual-write ainda.

Proibido: migration/model, pipeline/prompts, doctor/scheduler/dashboard, FSM/roles, docs rollout.

## TDD obrigatório

### RED

Provar que correção ainda aceita “igual” por coluna divergente, filtro ainda inclui fallback sem row, novo evento ainda grava singular e fixtures ainda passam sem projeção explícita.

### GREEN

Migrar readers/comparações NIR e seus testes para declaração normalizada, preservando endpoints, locks, transações, flag e enqueue único.

### REFACTOR

Centralizar conversão seleção→conjunto já existente; não criar segundo vocabulário, manager global ou signal.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|get_exam_type_display|filter\([^\n]*exam_type|Q\([^\n]*exam_type|exam_type=" apps/intake apps/intake/tests
rg -n "old_exam_type|new_exam_type|old_procedures|new_procedures|CASE_PROCEDURE_DECLARATION_CORRECTED" apps/intake apps/intake/tests
rg -n "declared_by_nir|set_declared_procedures|get_declared_procedure_types" apps/intake apps/intake/tests
rg -n "COLONOSCOPY_INTAKE_ENABLED|eda_colonoscopy" apps/intake templates/intake static/js/upload.js
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

Classifique `exam_type` residual como selection/query param, payload histórico ou erro de coluna.

## Critérios/gates

- [ ] R1–R5 provados.
- [ ] Nenhum reader/query NIR usa a coluna.
- [ ] Correção compara conjuntos e mantém lock/FSM/enqueue.
- [ ] Novos eventos não gravam old/new singular.
- [ ] Flag e três seleções regressam.
- [ ] Fixtures NIR relevantes têm rows explícitas.
- [ ] Ponte permanece somente interna até Slice 011.
- [ ] Cap/gates verdes.

Responder no relatório: quais ocorrências eram coluna; quais são apenas contrato SSR; qual teste prova filtro fail-closed; como igualdade de correção funciona; como eventos antigos permanecem legíveis; quais fixtures foram migradas; arquivos/diff; baseline-final.

### Condições automáticas de INCOMPLETO

Reader/query de coluna no intake; fallback EDA; correção compara `case.exam_type`; novo evento singular; fixture sem row mascarada; flag/lock/FSM/enqueue relaxado; outro app/migration alterado; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-008-report.md` com protocolo completo, inventário antes/depois, RED/GREEN, snippets, inspeções, cap, gates e Handoff para verificador R1–R5.

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all change artifacts, ADR-0004 and approved reports 001-007. Implement ONLY resized Slice 008. Use TDD and the exact DeepSeek protocol in this file.

Make every NIR behavior row-authoritative: creation/resubmission project explicit declared rows, correction compares procedure sets and emits only old/new_procedures, filters/presentation read declared rows without Case.exam_type fallback, and affected intake fixtures create rows explicitly. Keep the temporary column/dual-write until Slice 011. Preserve routes, SSR selection parameter names, flag, locks, FSM and enqueue behavior. Do not touch pipeline, doctor, scheduler, dashboard, migrations or rollout docs. Above 12 files or any failing gate = INCOMPLETE.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-008-report.md; if complete mark only Slice 008, commit, push, reply REPORT_PATH and STOP.
```
