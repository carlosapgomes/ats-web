# Slice 009-A: Médico opera somente por projeções de procedimento

## Handoff com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, proposal/design/tasks deste change, ADR-0004, relatórios aprovados 001–008 e as evidências `INCOMPLETE` do Slice 009:

- `/tmp/support-combined-eda-colonoscopy-workflow-slice-009-report.md`;
- `/tmp/support-combined-eda-colonoscopy-workflow-slice-009-correction-report.md`.

Confirme branch `feature/support-combined-eda-colonoscopy-workflow`, árvore limpa e HEAD contendo `4423fe7`. O commit `9caf210` entregou corretamente prior-case dimensional e leitura histórica 1.1, mas foi reprovado porque cards/tela médica ainda dependem direta ou transitivamente de `Case.exam_type`. A tentativa corretiva foi revertida; não assuma código não versionado.

Este é o primeiro gate corretivo da etapa 009. Implemente somente o fluxo médico. Não toque em scheduler nem inicie 009-B/010.

### Fluxo entregue

```text
caso chega ao médico com CaseProcedure
→ Pendentes projeta somente detection_status=detected
→ tela de decisão exibe o conjunto detectado projetado
→ Decididos Hoje projeta somente doctor_disposition=approved ou none
→ JSON 1.1 deriva tipo do payload/row declarada sem default EDA
→ nenhuma leitura direta ou transitiva da ponte participa do fluxo médico
```

## Protocolo obrigatório para DeepSeek4-Flash

Se qualquer item falhar, responda `INCOMPLETE`, não marque `tasks.md`, não faça commit/push de conclusão e pare.

1. Registre `BASE_REF=$(git rev-parse HEAD)`, branch, remoto e árvore limpa.
2. Faça matriz `requisito → arquivo → teste` e inventário dos readers/getters/fixtures antes de editar.
3. Rode baseline completo `uv run pytest`; qualquer failure/error bloqueia.
4. RED real primeiro: os testes de autoridade devem falhar em `4423fe7` pelo fallback/template reader.
5. GREEN mínimo em doctor/template e fixtures médicas diretamente afetadas.
6. REFACTOR local, DRY/YAGNI; helper de teste compartilhado somente com projeções explícitas.
7. Inspeções + quality gate completo; final com zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório, checkbox somente 009-A, commit normal, push e PARE.

**Cap: 10 arquivos produto/teste/template.** Artefatos OpenSpec/relatório não contam. Acima disso, pare antes de ampliar e reporte inventário ao planner; não empurre fixtures para 009-B.

## Requisitos

### R1. Cards médicos usam getters estritos

Em todos os consumidores médicos, chamar `get_declared_procedure_types`, `get_detected_procedure_types` e `get_approved_procedure_types` com `fallback_to_bridge=False` enquanto o default global ainda existe.

- Pendentes: `selection_key`/label do detectado;
- Decididos Hoje: `selection_key`/label do autorizado; ausência = `none`/“Nenhum autorizado”;
- `exam_type`/`exam_type_label` podem permanecer como nomes de contexto/data attribute somente se receberem valores projetados, com comentário semântico correto;
- um caso inválido sem rows nunca herda EDA/Colonoscopia da ponte.

### R2. Tela de decisão não lê a coluna

Remover `case.exam_type` e `case.get_exam_type_display` de `templates/doctor/decision.html`. A view deve fornecer chave e label projetados da dimensão detectada em modo estrito. Ausência/ambiguidade renderiza label neutro e classe segura, nunca default EDA.

Preservar formulário por componente, anexos, comunicação, prior-case, lock e submit existentes.

### R3. Relatório histórico 1.1 fica comprovadamente independente

Preservar `_derive_legacy_procedure_type` e o presenter neutro já versionados. Endurecer testes para provar:

- payload `preop_screening.exam_type` válido vence quando a ponte contém o oposto;
- sem payload, uma única row declarada vence quando a ponte contém o oposto;
- zero ou duas rows declaradas sem payload válido resultam em label neutro;
- o caso ambíguo não chama `lookup_prior_case_context` (mock/spy obrigatório);
- nenhum JSON 1.1 é reescrito.

Não redesenhar reporting/presenter se os testes caracterizarem o comportamento já correto.

### R4. Fixtures médicas são explícitas

Migrar somente fixtures que exercitam cards/decisão/relatório médico e falham após R1/R2. Elas devem declarar explicitamente conjuntos `declared`, `detected` e, quando decididas, `approved`/`denied`.

É permitido adicionar helper em `tests/shared_case_fixtures.py` se:

- todos os conjuntos são argumentos explícitos no call site;
- ele não lê `case.exam_type`;
- ele não infere projeção pelo status;
- ele não é signal/autouse e não cria rows silenciosamente;
- aprovação não detectada exige razão explícita.

Fixtures inválidas de fail-closed devem ter nome/comentário que declare ausência intencional de rows.

### R5. Segurança e contrato visual preservados

Preservar `@role_required("doctor")`, lock/lease, FSM, razões por componente, inclusão sem rerun, prior-case/correction dedup, polling e filtros JS. Nenhuma alteração de model, migration, endpoint ou permissão.

## Arquivos esperados

Produto/template:

- `apps/doctor/views.py`;
- `templates/doctor/decision.html`.

Testes, somente se o RED/inventário comprovar impacto:

- `apps/doctor/tests/test_queue_exam_type_filters.py`;
- `apps/doctor/tests/test_slice_003_prior_and_queue.py`;
- `apps/doctor/tests/test_colonoscopy_doctor.py`;
- `apps/doctor/tests/test_views.py`;
- `apps/intake/tests/test_exam_type_intake.py` (somente cenário end-to-end que chega ao médico);
- `tests/shared_case_fixtures.py` (helper explícito opcional).

Arquivo extra exige justificativa binária no relatório; scheduler é proibido.

## TDD obrigatório

### RED

1. Card `WAIT_DOCTOR` sem rows, ponte `colonoscopy`, deve ser `none`/neutro.
2. Ponte oposta às rows detectadas não altera card nem tela de decisão.
3. Inspeção do template falha enquanto houver `case.exam_type`/`get_exam_type_display`.
4. Payload e row 1.1 contradizem a ponte e ainda governam o relatório; ambiguidade não chama lookup.

### GREEN

Passar getters médicos em modo estrito, projetar contexto da decisão e migrar somente fixtures médicas afetadas.

### REFACTOR

Eliminar chamadas duplicadas quando possível sem criar God helper. Nomes de contexto devem declarar dimensão; manter alias legado apenas onde o template/JS exige.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|get_exam_type_display" apps/doctor templates/doctor
rg -n "get_(declared|detected|approved)_procedure_types\(case\)" apps/doctor
rg -n "fallback_to_bridge=False|detection_status|doctor_disposition|declared_by_nir" apps/doctor
rg -n "case\.exam_type" apps/doctor/tests apps/intake/tests/test_exam_type_intake.py tests/shared_case_fixtures.py
rg -n "@role_required|assert_case_lock|claim_case_lock|release_lock|procedure_.*reason" apps/doctor
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

Classifique toda ocorrência residual: payload/parâmetro/context key projetado pode ser legítimo; acesso à coluna ou getter médico sem `fallback_to_bridge=False` é `INCOMPLETE`.

## Critérios/gates

- [ ] R1–R5 provados.
- [ ] Cards Pendentes/Decididos independem da ponte.
- [ ] `decision.html` não lê campo/get display.
- [ ] Ausência de row é neutra/none.
- [ ] JSON 1.1 contraditório/ambíguo está coberto com spy.
- [ ] Fixtures médicas afetadas são explícitas e não inferem da coluna/status.
- [ ] Roles, locks, FSM, razões e inclusão sem rerun preservados.
- [ ] Cap e gates verdes.

Responder no relatório: quais cinco chamadas médicas ficaram estritas; quais context keys permanecem e sua semântica; como decisão projeta tipo; como 1.1 falha neutro; fixtures migradas; resíduos classificados; baseline-final.

### Condições automáticas de INCOMPLETO

Getter médico default; reader de coluna/get display em doctor/template; caso sem row herdando ponte; teste com ponte sempre igual à projeção; spy ausente no caminho ambíguo; fixture inferida por status/coluna; scheduler alterado; segurança/FSM relaxada; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-009a-doctor-projection-authority-report.md` com status, matriz, baseline, RED/GREEN/REFACTOR, snippets, fixtures, inventário interpretado, cap, quality gate, baseline-final e handoff R1–R5.

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md, this change's proposal/design/tasks, ADR-0004, approved reports 001-008, and both original Slice 009 INCOMPLETE reports. Implement ONLY Slice 009-A with TDD.

Make every doctor card/context consumer strict with fallback_to_bridge=False, replace decision.html direct Case.exam_type/get display access with detected projection context, harden legacy 1.1 tests against a contradictory bridge and prove ambiguous input does not call prior lookup, and migrate only affected doctor fixtures to explicit declared/detected/approved rows. A shared test helper is allowed only with explicit arguments and no status/column inference. Preserve roles, locks, FSM, per-component reasons, no-rerun inclusion and visual contracts. Do not touch scheduler, models/migrations, dashboard, intake product, prompts or Slice 010. Above 10 product/test/template files or any gate failure = INCOMPLETE.

Create the required temporary report, mark only 009-A if complete, commit, push, reply REPORT_PATH and STOP.
```
