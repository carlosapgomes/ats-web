# Slice 011-C: Cutover físico — migration remove Case.exam_type e encerra a ponte

## Handoff com contexto zero

Leia artefatos, ADR-0004, migrations `0014_case_exam_type` e `0015_caseprocedure`, relatórios aprovados 001–010, 011-A e 011-B, o relatório BLOQUEADO do 011 original (`/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md`) e o padrão de teste de migration em `apps/cases/tests/test_post_acceptance_issue_migration.py` (MigrationExecutor). Se 011-A ou 011-B não estiver aprovado, PARE como BLOQUEADO. Confirme por inspeção que nenhum teste fora de `test_exam_type.py` acessa a coluna via ORM (011-A/B garantiram isso).

### Fluxo entregue

```text
precheck de migration exige 1–2 CaseProcedure válidos por Case (fail-closed)
→ migration falha com erro explícito diante de ausência/tipo inválido/duplicidade
→ RemoveIndex + RemoveField: some Case.exam_type e o índice composto
→ ExamType duplicado removido; dual-write/signal param de tocar a coluna
→ tela de correção NIR marca "(atual)" pela projeção, nunca pela coluna
→ suite passa sem coluna/default/dual-write
```

Este é o cutover físico. Não inclua prompts (007), consumers (008–010 já feitos), remoção do parâmetro compat `fallback_to_bridge` (Slice 011-D) ou runbook (012).

## Decisões de contrato registradas (obrigatórias neste slice)

1. **Payload `CASE_CREATED`**: eventos novos passam a ter somente `{"status": ...}`. A chave `exam_type` sai do payload de criação porque (a) nenhum reader operacional a consome (verificado por inventário), (b) a declaração é auditada por `CASE_PROCEDURES_DECLARED` e (c) o sinal dispara antes das rows existirem. Eventos já persistidos preservam a chave (append-only, R6).
2. **Tela de correção NIR** (`templates/intake/case_detail.html`): os radios usam o valor **projetado** já disponível na view (`_declared_badge` → `declared_type_key` = `selection_key` do conjunto declarado: `eda|colonoscopy|eda_colonoscopy`), adicionado ao `correction_form_context`. Nunca `case.exam_type`.
3. **Constante `EDA_COLONOSCOPY`**: permanece em `apps/cases/models.py` como chave de seleção derivada (não é field choice nem membro de enum). Isso evita tocar em `apps/pipeline/procedure_reconciliation.py` e `apps/scheduler/views.py` neste slice.
4. **Parâmetro `fallback_to_bridge`**: permanece no-op nos 3 getters neste slice (aceito por compat; R6 permite nome de parâmetro). O Slice 011-D o remove.
5. **Rollback**: forward determinístico; rollback para imagem antiga pertence à bridge documentada no Slice 012 — sem reverse migration silenciosa.

## Protocolo obrigatório para DeepSeek4-Flash

Este slice será implementado por um modelo rápido com tendência a concluir cedo demais. Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: matriz `Requisito → arquivo(s) → teste(s)`.
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Inventário antes de editar**: re rode os `rg` da seção de inspeções; o único teste com acesso ORM à coluna deve ser `test_exam_type.py`. Leitura diferente disso = PARE.
4. **RED real**: escreva os testes de migration/contrato primeiro e prove falha pelo motivo esperado (ver TDD).
5. **GREEN mínimo**: precheck + RemoveField + writers + template. Sem refactor amplo.
6. **REFACTOR local**: remover código morto de ponte nos arquivos tocados; nenhum signal/default automático novo.
7. **Quality gate completo** + `makemigrations --check` + OpenSpec strict; final zero failures/errors e `passed_final >= passed_baseline` (ver R5 sobre aritmética).
8. **Relatório**, checkbox somente 011-C + itens DoD de cutover efetivamente provados, commit/push e PARE.

**Cap: 10 arquivos produto/teste/template/migration.** Acima disso, pare antes de editar. Nenhuma remoção parcial.

## Requisitos

### R1. Precondição fail-closed na migration

Antes de `RemoveIndex`/`RemoveField`, `RunPython` valida no banco histórico:

- cada `Case` possui 1–2 rows `CaseProcedure`;
- tipos pertencem a `eda|colonoscopy`;
- não há duplicata por caso/tipo;
- ao menos uma row é `declared_by_nir=True` por caso.

Qualquer violação aborta a migration com erro explícito (identificador do caso incluído) **antes** de remover o índice/coluna. Não inventar EDA nem ler JSON/texto para reparar.

### R2. Remoção preservadora

Migration remove somente o índice `cases_status_exam_type_idx` e o field `exam_type`. Preserva Case, CaseProcedure, CaseEvent, JSON 1.1/2.0, PDF, anexos, decisões e agenda. Forward determinístico; sem reverse migration silenciosa.

### R3. Modelo final sem duplicação

Remover de `apps/cases/models.py`: field `exam_type`, enum `ExamType`, entrada do índice composto e comentários de ponte. `ProcedureType` permanece enum de componentes. `EDA_COLONOSCOPY` permanece como constante de seleção derivada com docstring (decisão 3). Nenhuma ocorrência de `ExamType` pode restar fora de migrations antigas.

### R4. Dual-write eliminado

Em `apps/cases/procedures.py`: remover `bridge_exam_type_for_types` e as atribuições `case.exam_type = ...` / `locked.exam_type = ...` de `sync_declared_projection` e `set_declared_procedures`. Transações/locks/eventos existentes preservados. Em `apps/intake/services.py`: remover kwargs `exam_type=` dos creates (criação continua criando rows via `set_declared_procedures`, como hoje) e trocar usos de `ExamType` por `ProcedureType`/literais equivalentes (`_DECLARED_SELECTION_VALUES`, `ensure_exam_type_allowed`, `_procedure_types_for_selection`). Em `apps/intake/views.py`: remover import `ExamType` e trocar `_NIR_DECLARED_DIMENSIONS` para literais/`ProcedureType`.

### R5. Módulo de ponte e fixtures finais

`apps/cases/tests/test_exam_type.py`: testes de enum/field/índice morrem com a coluna; cada teste removido é substituído por teste do contrato final (ex.: payload `CASE_CREATED` sem chave `exam_type` e com `status`; modelo sem field) de modo que `passed_final >= passed_baseline`. Nenhum outro teste acessa a coluna (011-A/B garantiram). Caso isolado sem rows pode existir apenas em teste de migration claramente justificado.

### R6. Signal e tela de correção

`apps/cases/signals.py`: payload `CASE_CREATED` vira `{"status": instance.status}` (decisão 1). `apps/intake/views.py`: adicionar o valor projetado já existente (`declared_type_key` de `_declared_badge`) ao `correction_form_context`. `templates/intake/case_detail.html`: os 6 usos de `case.exam_type` nos radios viram comparação com a chave projetada do contexto. Comportamento visível preservado: opção atual fica `disabled` e marcada "(atual)".

### R7. Compatibilidade histórica legítima

JSON 1.1/2.0 (`preop_screening.exam_type` etc.), payloads de eventos já persistidos (incl. `CASE_CREATED` antigos e eventos de correção com chaves `exam_type`), parâmetros/forms SSR (`name="exam_type"`, `?exam_type=`) e nomes de parâmetro continuam legíveis/intactos. Nenhuma dessas ocorrências pode resultar em acesso ORM ao field removido. Classificar cada ocorrência no relatório.

### R8. Schema e gates

`makemigrations --check --dry-run` retorna "No changes detected". Teste com `MigrationExecutor` cobre falha e sucesso. Índices/constraints dimensionais do Slice 001 continuam. Suite completa e inspeções sem reader/write residual.

## Arquivos esperados (9 ≤ cap 10)

| # | Arquivo | Papel |
| --- | --- | --- |
| 1 | `apps/cases/models.py` | R3: field/enum/índice/comentários |
| 2 | `apps/cases/migrations/0016_*.py` (novo) | R1/R2: precheck + RemoveIndex + RemoveField |
| 3 | `apps/cases/procedures.py` | R4: bridge/dual-write |
| 4 | `apps/cases/signals.py` | R6: payload CASE_CREATED |
| 5 | `apps/intake/services.py` | R4: kwargs de criação/`ExamType` |
| 6 | `apps/intake/views.py` | R4/R6: `ExamType`/`_NIR_DECLARED_DIMENSIONS` + contexto projetado |
| 7 | `templates/intake/case_detail.html` | R6: radios pela projeção |
| 8 | `apps/cases/tests/test_exam_type.py` | R5: reescrita para contrato final |
| 9 | `apps/cases/tests/test_migration_0016_cutover.py` (novo) | R1/R2/R8: MigrationExecutor falha/sucesso/preservação |

Proibido: doctor/scheduler/pipeline/dashboard (produto e testes), prompts, FSM/roles, docs/runbook, remoção de `fallback_to_bridge` (011-D), apagar JSON/eventos/histórico.

## TDD obrigatório

### RED (testes escritos antes, falhando pelo motivo esperado)

1. MigrationExecutor: `Case` sem rows → precheck aborta antes de remover o field (introspecção prova coluna presente após falha).
2. MigrationExecutor: estado válido (1 caso com 1 row declarada, 1 caso com 2 rows) → migra; introspecção prova ausência da coluna e do índice `cases_status_exam_type_idx`.
3. Preservação: eventos (incl. payload `CASE_CREATED` legado com `exam_type`), `structured_data`, decisões e agendamento sobrevivem à migration.
4. Writers: upload/reenvio/declaração funcionam sem kwarg/atribuição de coluna e mantêm rows/eventos.
5. Payload `CASE_CREATED` novo tem `status` e não tem chave `exam_type`.
6. Tela de correção: caso com projeção `eda` marca radio EDA como atual/disabled mesmo com histórico legado; valor projetado, nunca coluna.
7. `makemigrations --check --dry-run` sem drift.

### GREEN

Implementar precheck, migration, remoções R3/R4, signal e template — mínimo para os testes passarem.

### REFACTOR

Eliminar código/comentários de ponte mortos nos arquivos tocados; não criar signal, default, manager mágico ou segundo vocabulário.

## Inspeções obrigatórias

```bash
# Após o cutover, nenhum acesso ORM à coluna em parte alguma (comentários/docstrings
# restantes devem ser classificados; ocorrências em migrations 0014/0015 são esperadas):
rg -n "Case\.exam_type|case\.exam_type|self\.exam_type|get_exam_type_display|exam_type__|filter\([^\n]*exam_type|Q\([^\n]*exam_type" apps config templates static --glob '!**/migrations/0014_*' --glob '!**/migrations/0015_*' --glob '!**/migrations/0016_*'
rg -n "class ExamType|ExamType\." apps config --glob '!**/migrations/**'
rg -n "bridge_exam_type_for_types|dual-write|ponte transitória" apps templates static
rg -n "case\.exam_type" templates
rg -n "eda_colonoscopy" apps/cases/models.py apps/cases/procedures.py
rg -n "proc_(declared|detection|disposition)_idx|uniq_case_procedure_type" apps/cases

uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
uv run python manage.py showmigrations cases --settings=config.settings.test
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
openspec validate support-combined-eda-colonoscopy-workflow --strict
git diff --check
git diff --name-only "$BASE_REF"
```

Interprete no relatório: resíduos permitidos = JSON 1.1/2.0, payloads históricos, params/forms SSR, nomes de parâmetro, `EDA_COLONOSCOPY` como chave derivada e migrations antigas. Qualquer acesso ORM = INCOMPLETO.

## Critérios/gates

- [ ] R1–R8 provados; precheck aborta dados inválidos com erro explícito.
- [ ] Coluna/enum/índice/dual-write removidos; introspecção prova ausência.
- [ ] Payload CASE_CREATED novo sem chave `exam_type`; eventos antigos intactos.
- [ ] Tela de correção marca "(atual)" pela projeção.
- [ ] Dados/eventos/JSON/PDF/agenda preservados (teste de preservação).
- [ ] Selection key combinada permanece apenas derivada (`EDA_COLONOSCOPY` constante; sem field choice).
- [ ] `makemigrations --check` limpo; MigrationExecutor falha+sucesso; gates verdes.
- [ ] Cap respeitado (≤ 10 arquivos); `passed_final >= passed_baseline` com aritmética registrada.

### Condições automáticas de INCOMPLETO

Reader/writer ORM residual fora das migrations antigas; migration inventa row/default ou remove campo antes do precheck; perde dados/eventos/JSON; dual-write/field/`ExamType` permanece; payload novo ainda grava a chave; radios ainda leem a coluna; `fallback_to_bridge` removido neste slice (é do 011-D); schema drift; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md` com matriz, inventário antes/depois, baseline, RED/GREEN/REFACTOR, snippets (model/migration/writers/signal/template/testes), resíduos classificados, `makemigrations`/`showmigrations`, gates, aritmética de testes, baseline-final e Handoff R1–R8 + handoff para o 011-D (lista de call sites de `fallback_to_bridge`).

## Prompt pronto

```text
Read all artifacts, ADR-0004, migrations 0014-0015, approved reports 001-010, 011-A and 011-B, the blocked Slice 011 report (/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md) and the MigrationExecutor pattern in apps/cases/tests/test_post_acceptance_issue_migration.py. If 011-A or 011-B is not approved, STOP BLOCKED. Implement ONLY Slice 011-C.

Add migration 0016 with a fail-closed RunPython precheck (every Case has 1-2 valid CaseProcedure rows, types eda|colonoscopy, no duplicates, at least one declared row; any violation aborts with explicit error BEFORE schema changes), then RemoveIndex cases_status_exam_type_idx and RemoveField Case.exam_type. Remove the ExamType enum and bridge comments from models.py (keep EDA_COLONOSCOPY as derived selection-key constant), remove bridge_exam_type_for_types and all column assignments from procedures.py, remove exam_type create kwargs from intake/services.py, switch intake/views.py to ProcedureType/literals and add the already-projected declared_type_key to correction_form_context so templates/intake/case_detail.html radios use the projection instead of case.exam_type. Change the CASE_CREATED signal payload to status only (old events keep the key). Rewrite test_exam_type.py into final-contract tests and add a MigrationExecutor test covering precheck failure, successful migration and data preservation. Do NOT remove the fallback_to_bridge parameter (Slice 011-D) and do not touch doctor/scheduler/pipeline/dashboard/prompts/docs.

Run the RED tests first, full gates including makemigrations --check, classify every residual occurrence, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md; if complete mark only Slice 011-C and the true cutover DoD items, commit, push, reply REPORT_PATH and STOP.
```
