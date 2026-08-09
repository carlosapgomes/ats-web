# Slice 011-C (revisado): Cutover físico — migration remove Case.exam_type e encerra a ponte

> **REVISÃO após bloqueio legítimo** (relatório BLOQUEADO `/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md`,
> BASE_REF `fbb6772`): o desenho original removia também a **classe** `ExamType` (R3 antigo),
> mas 4 arquivos de teste de intake a importam como fonte de valores de contrato
> (`test_exam_type_correction.py`, `test_slice_001_correction_projection.py`,
> `test_slice_005_nir_correction_and_response.py`, `test_slice_008_nir_declared_projection_authority.py`)
> — 13 arquivos no total, acima do cap 10. A atomicidade real é apenas
> **RemoveField ↔ acessos ORM**; a remoção da classe é limpeza de símbolo independente.
> Este slice revisado faz somente o cutover físico (9 arquivos) e preserva a classe
> `ExamType`, cuja remoção vai para o Slice 011-E junto com o parâmetro `fallback_to_bridge`.

## Handoff com contexto zero

Leia artefatos, ADR-0004, migrations `0014_case_exam_type` e `0015_caseprocedure`, relatórios aprovados 001–010, 011-A e 011-B, os relatórios BLOQUEADOS do 011 original (`/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md`) e do 011-C original (`/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md`), e o padrão de teste de migration em `apps/cases/tests/test_post_acceptance_issue_migration.py` (MigrationExecutor). Se 011-A ou 011-B não estiver aprovado, PARE como BLOQUEADO. Confirme por inspeção que nenhum teste fora de `test_exam_type.py` acessa a coluna via ORM (011-A/B garantiram isso) e que os únicos leitores/escritores ORM de produto são `apps/cases/signals.py:18` (payload `CASE_CREATED`), os kwargs `exam_type=` dos creates em `apps/intake/services.py` e `templates/intake/case_detail.html` (radios).

### Fluxo entregue

```text
precheck de migration exige 1–2 CaseProcedure válidos por Case (fail-closed)
→ migration falha com erro explícito diante de ausência/tipo inválido/duplicidade
→ RemoveIndex + RemoveField: some Case.exam_type e o índice composto
→ dual-write/signal param de tocar a coluna
→ tela de correção NIR marca "(atual)" pela projeção, nunca pela coluna
→ suite passa sem coluna/default/dual-write (classe ExamType ainda existe, removida no 011-E)
```

Este é o cutover físico. Não inclua prompts (007), consumers (008–010 já feitos), remoção do parâmetro compat `fallback_to_bridge` (Slice 011-D), remoção da classe `ExamType` (Slice 011-E) ou runbook (012).

## Decisões de contrato registradas (obrigatórias neste slice)

1. **Payload `CASE_CREATED`**: eventos novos passam a ter somente `{"status": ...}`. A chave `exam_type` sai do payload de criação porque (a) nenhum reader operacional a consome (verificado por inventário), (b) a declaração é auditada por `CASE_PROCEDURES_DECLARED` e (c) o sinal dispara antes das rows existirem. Eventos já persistidos preservam a chave (append-only, R6).
2. **Tela de correção NIR** (`templates/intake/case_detail.html`): os radios usam o valor **projetado** já disponível na view (`_declared_badge` → `declared_type_key` = `selection_key` do conjunto declarado: `eda|colonoscopy|eda_colonoscopy`), adicionado ao `correction_form_context`. Nunca `case.exam_type`.
3. **Constante `EDA_COLONOSCOPY`**: permanece em `apps/cases/models.py` como chave de seleção derivada (não é field choice nem membro de enum). Seu comentário é reescrito: a coluna que ele descreve deixa de existir neste slice.
4. **Classe `ExamType` PRESERVADA neste slice**: seus valores (`eda|colonoscopy`) ainda são referência de contrato em `apps/intake/services.py`, `apps/intake/views.py` e 4 testes de intake. Removê-la agora exigiria 13 arquivos (acima do cap). Ela recebe docstring de deprecação ("valores mantidos por compat; remoção no Slice 011-E") e o Slice 011-E a elimina.
5. **Parâmetro `fallback_to_bridge`**: permanece no-op nos 3 getters neste slice. O Slice 011-D remove o kwarg dos call sites; o 011-E remove o parâmetro.
6. **Rollback**: forward determinístico; rollback para imagem antiga pertence à bridge documentada no Slice 012 — sem reverse migration silenciosa.

## Protocolo obrigatório para DeepSeek4-Flash

Este slice será implementado por um modelo rápido com tendência a concluir cedo demais. Siga literalmente; qualquer falha = INCOMPLETO (não marque tasks.md, não faça commit, responda com bloqueio + evidência).

1. **Plano antes de editar**: matriz `Requisito → arquivo(s) → teste(s)`.
2. **Baseline**: registre `BASE_REF=$(git rev-parse HEAD)` e rode `uv run pytest`. Cole exit code e resumo. `failed/error` no baseline = PARE.
3. **Inventário antes de editar**: re rode os `rg` da seção de inspeções; o único teste com acesso ORM à coluna deve ser `test_exam_type.py`, e os readers/writers de produto devem ser apenas `signals.py` (payload), `services.py` (kwargs de create) e `case_detail.html` (radios). Leitura diferente disso = PARE.
4. **RED real**: escreva os testes de migration/contrato primeiro e prove falha pelo motivo esperado (ver TDD).
5. **GREEN mínimo**: precheck + RemoveField + writers + template. Sem refactor amplo.
6. **REFACTOR local**: remover código morto de ponte nos arquivos tocados; nenhum signal/default automático novo.
7. **Quality gate completo** + `makemigrations --check` + OpenSpec strict; final zero failures/errors e `passed_final >= passed_baseline` (ver R5 sobre aritmética).
8. **Relatório**, checkbox somente 011-C + itens DoD de cutover efetivamente provados, commit/push e PARE.

**Cap: exatamente os 9 arquivos listados.** Acima disso, pare antes de editar. Nenhuma remoção parcial.

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

### R3. Modelo final sem a coluna (classe preservada)

Remover de `apps/cases/models.py`: field `exam_type`, entrada do índice `cases_status_exam_type_idx` e comentários/docstrings que descrevem a coluna (bloco da `EDA_COLONOSCOPY` L30–35 e docstring de `CaseProcedure` L96–97 são reescritos para o contrato de rows). `ProcedureType` permanece enum de componentes. `EDA_COLONOSCOPY` permanece como constante de seleção derivada com docstring atualizado (decisão 3). **A classe `ExamType` permanece** com docstring de deprecação (decisão 4) — removê-la é do Slice 011-E.

### R4. Dual-write eliminado

Em `apps/cases/procedures.py`: remover `bridge_exam_type_for_types` e as atribuições `case.exam_type = ...` / `locked.exam_type = ...` de `sync_declared_projection` e `set_declared_procedures`. Transações/locks/eventos existentes preservados. Em `apps/intake/services.py`: remover os kwargs `exam_type=` dos creates (criação continua criando rows via `set_declared_procedures`, como hoje). Usos restantes da classe `ExamType` em `services.py`/`views.py` (literais de seleção) permanecem neste slice — são valores de contrato, não acessam a coluna, e saem no 011-E. Em `apps/intake/views.py`: adicionar `declared_type_key` ao `correction_form_context` (única mudança deste arquivo no slice).

### R5. Módulo de ponte e fixtures finais

`apps/cases/tests/test_exam_type.py`: testes de enum/field/índice morrem com a coluna; cada teste removido é substituído por teste do contrato final (ex.: payload `CASE_CREATED` sem chave `exam_type` e com `status`; modelo sem field; radios pela projeção) de modo que `passed_final >= passed_baseline`. **A reescrita não pode importar `ExamType`** (a classe sai no 011-E; importar agora obrigaria reeditar o arquivo lá). Nenhum outro teste acessa a coluna (011-A/B garantiram). Caso isolado sem rows pode existir apenas em teste de migration claramente justificado.

### R6. Signal e tela de correção

`apps/cases/signals.py`: payload `CASE_CREATED` vira `{"status": instance.status}` (decisão 1). `templates/intake/case_detail.html`: os usos de `case.exam_type` nos radios viram comparação com a chave projetada do contexto (decisão 2). Comportamento visível preservado: opção atual fica `disabled` e marcada "(atual)".

### R7. Compatibilidade histórica legítima

JSON 1.1/2.0 (`preop_screening.exam_type` etc.), payloads de eventos já persistidos (incl. `CASE_CREATED` antigos e eventos de correção com chaves `exam_type`), parâmetros/forms SSR (`name="exam_type"`, `?exam_type=`), nomes de parâmetro, atributos de presenter 1.1 (`{{ c.exam_type }}` em templates doctor/scheduler) e a classe `ExamType` preservada continuam legíveis/intactos. Nenhuma dessas ocorrências pode resultar em acesso ORM ao field removido. Classificar cada ocorrência no relatório.

### R8. Schema e gates

`makemigrations --check --dry-run` retorna "No changes detected". Teste com `MigrationExecutor` cobre falha e sucesso. Índices/constraints dimensionais do Slice 001 continuam. Suite completa e inspeções sem reader/write residual.

## Arquivos esperados (9 ≤ cap 10)

| # | Arquivo | Papel |
| --- | --- | --- |
| 1 | `apps/cases/models.py` | R3: field/índice/comentários (classe preservada) |
| 2 | `apps/cases/migrations/0016_*.py` (novo) | R1/R2: precheck + RemoveIndex + RemoveField |
| 3 | `apps/cases/procedures.py` | R4: bridge/dual-write |
| 4 | `apps/cases/signals.py` | R6: payload CASE_CREATED |
| 5 | `apps/intake/services.py` | R4: kwargs de criação |
| 6 | `apps/intake/views.py` | R4/R6: `declared_type_key` no contexto da correção |
| 7 | `templates/intake/case_detail.html` | R6: radios pela projeção |
| 8 | `apps/cases/tests/test_exam_type.py` | R5: reescrita para contrato final (sem importar ExamType) |
| 9 | `apps/cases/tests/test_migration_0016_cutover.py` (novo) | R1/R2/R8: MigrationExecutor falha/sucesso/preservação |

Proibido: doctor/scheduler/pipeline/dashboard (produto e testes), prompts, FSM/roles, docs/runbook, remoção de `fallback_to_bridge` (011-D), remoção da classe `ExamType` e substituição de literais `ExamType.X` em services/views/testes de intake (011-E), apagar JSON/eventos/histórico.

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
rg -n "Case\.exam_type|case\.exam_type|instance\.exam_type|get_exam_type_display|exam_type__|filter\([^\n]*exam_type=|Q\([^\n]*exam_type=" apps config templates static --glob '!**/migrations/0014_*' --glob '!**/migrations/0015_*' --glob '!**/migrations/0016_*'
# Classe ExamType permanece neste slice (remoção no 011-E) — inventariar usos, não remover:
rg -ln "ExamType" apps config --glob '!**/migrations/**'
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

Interprete no relatório: resíduos permitidos = JSON 1.1/2.0, payloads históricos, params/forms SSR, atributos de presenter 1.1, nomes de parâmetro, `EDA_COLONOSCOPY` como chave derivada, classe `ExamType` preservada (011-E) e migrations antigas. Qualquer acesso ORM = INCOMPLETO.

## Critérios/gates

- [ ] R1–R8 provados; precheck aborta dados inválidos com erro explícito.
- [ ] Coluna/índice/dual-write removidos; introspecção prova ausência.
- [ ] Classe `ExamType` preservada com docstring de deprecação (remoção é do 011-E).
- [ ] Payload CASE_CREATED novo sem chave `exam_type`; eventos antigos intactos.
- [ ] Tela de correção marca "(atual)" pela projeção.
- [ ] Dados/eventos/JSON/PDF/agenda preservados (teste de preservação).
- [ ] Selection key combinada permanece apenas derivada (`EDA_COLONOSCOPY` constante; sem field choice).
- [ ] `makemigrations --check` limpo; MigrationExecutor falha+sucesso; gates verdes.
- [ ] Cap respeitado (exatamente 9 arquivos); `passed_final >= passed_baseline` com aritmética registrada.

### Condições automáticas de INCOMPLETO

Reader/writer ORM residual fora das migrations antigas; migration inventa row/default ou remove campo antes do precheck; perde dados/eventos/JSON; dual-write/field permanece; payload novo ainda grava a chave; radios ainda leem a coluna; classe `ExamType` removida neste slice (é do 011-E); `fallback_to_bridge` removido neste slice (011-D/011-E); schema drift; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md` com matriz, inventário antes/depois, baseline, RED/GREEN/REFACTOR, snippets (model/migration/writers/signal/template/testes), resíduos classificados (incl. inventário de usos `ExamType` que o 011-E removerá), `makemigrations`/`showmigrations`, gates, aritmética de testes, baseline-final e handoff para o 011-D (lista de call sites de `fallback_to_bridge`).

## Prompt pronto

```text
Read all artifacts, ADR-0004, migrations 0014-0015, approved reports 001-010, 011-A and 011-B, the blocked Slice 011 and Slice 011-C original reports (/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md and /tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md) and the MigrationExecutor pattern in apps/cases/tests/test_post_acceptance_issue_migration.py. If 011-A or 011-B is not approved, STOP BLOCKED. Implement ONLY the revised Slice 011-C (physical cutover, exactly 9 files).

Add migration 0016 with a fail-closed RunPython precheck (every Case has 1-2 valid CaseProcedure rows, types eda|colonoscopy, no duplicates, at least one declared row; any violation aborts with explicit error BEFORE schema changes), then RemoveIndex cases_status_exam_type_idx and RemoveField Case.exam_type. Remove the exam_type field, the composite index entry and the column-describing comments from models.py (keep EDA_COLONOSCOPY as derived selection-key constant with rewritten docstring; KEEP the ExamType class with a deprecation note — its removal belongs to Slice 011-E), remove bridge_exam_type_for_types and all column assignments from procedures.py, remove the exam_type create kwargs from intake/services.py (leave remaining ExamType literal usages for 011-E), add the already-projected declared_type_key to correction_form_context in intake/views.py so templates/intake/case_detail.html radios use the projection instead of case.exam_type. Change the CASE_CREATED signal payload to status only (old events keep the key). Rewrite test_exam_type.py into final-contract tests WITHOUT importing ExamType, and add a MigrationExecutor test covering precheck failure, successful migration and data preservation. Do NOT remove the fallback_to_bridge parameter (011-D/011-E), do NOT replace ExamType.X literals in services/views/intake tests (011-E), and do not touch doctor/scheduler/pipeline/dashboard/prompts/docs.

Run the RED tests first, full gates including makemigrations --check, classify every residual occurrence, create /tmp/support-combined-eda-colonoscopy-workflow-slice-011c-report.md; if complete mark only Slice 011-C and the true cutover DoD items, commit, push, reply REPORT_PATH and STOP.
```
