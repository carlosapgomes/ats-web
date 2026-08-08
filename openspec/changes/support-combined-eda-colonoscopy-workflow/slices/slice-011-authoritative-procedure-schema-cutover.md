# Slice 011: Migration remove Case.exam_type e encerra a ponte

## Handoff com contexto zero

Leia artefatos, ADR-0004, migrations 0014+, relatórios aprovados 001–008, 009-A, 009-B e 010, além da evidência `INCOMPLETE` do 009 original e do inventário final do Slice 010. Confirme que pipeline, NIR, médico, CHD e dashboard já não leem a coluna. Se 009-A, 009-B ou 010 não estiver aprovado, PARE como BLOQUEADO. Inspecione model, serviço de procedimentos, writers de criação e fixtures residuais.

### Fluxo entregue

```text
precheck de migration exige 1–2 CaseProcedure válidos por Case
→ migration falha diante de ausência/duplicidade/tipo inválido
→ remove Case.exam_type e seu índice/enum duplicado
→ declaração escreve somente CaseProcedure
→ CaseProcedure é a única fonte operacional
→ suite passa sem coluna/default/dual-write
```

Este é o cutover físico. Não inclua prompts (Slice 007), consumers (008–010) ou runbook (012).

## Protocolo obrigatório para DeepSeek4-Flash

1. Confirme branch limpa, ADR e `BASE_REF`; registre matriz e baseline completo.
2. Refaça inventário global antes de editar. Reader residual bloqueia: não esconda no cutover.
3. Escreva testes de migration/contrato primeiro e prove RED real.
4. GREEN mínimo para precheck, remoção de campo e writers.
5. REFACTOR local sem signal/default automático.
6. Classifique toda ocorrência residual de `exam_type`/`ExamType`.
7. Rode quality gate, makemigrations check, OpenSpec strict e diff check; final zero failures/errors e passed >= baseline.
8. Relatório, checkbox 011/DoD de cutover, commit/push e PARE.

**Cap: 10 arquivos produto/teste/migration.** Se o inventário mostrar mais, pare antes de editar. Nenhuma remoção parcial.

## Requisitos

### R1. Precondição fail-closed na migration

Antes de `RemoveField`, validar no banco histórico:

- cada `Case` possui 1–2 rows;
- tipos pertencem a `eda|colonoscopy`;
- não há duplicata por caso/tipo;
- ao menos uma row é declarada por caso.

Qualquer violação aborta a migration com erro explícito e não remove a coluna. Não inventar EDA nem ler JSON/texto para reparar.

### R2. Remoção preservadora

Migration remove somente `Case.exam_type` e artefatos diretamente associados. Preserva Case, CaseProcedure, CaseEvent, JSON 1.1/2.0, PDF, anexos, decisões e agenda. Forward é determinístico; rollback para imagem antiga pertence à bridge documentada no Slice 012, não a uma reverse migration silenciosa.

### R3. Modelo final sem duplicação

Remover o field e `ExamType` duplicado. `ProcedureType` permanece enum de componentes. O valor `eda_colonoscopy` pode continuar como **selection key derivada** para SSR/badge/filtro; não pode ser field choice, row ou fonte persistida.

### R4. Dual-write eliminado

Remover `bridge_exam_type_for_types`, atribuições `case.exam_type=...`, kwargs de criação e comentários de ponte. `set_declared_procedures`/`sync_declared_projection` escrevem apenas rows/eventos dentro das transações/locks existentes.

### R5. Fixtures/APIs finais

Nenhum teste cria/atualiza/lê a coluna. Factories/helpers de domínio relevantes criam rows explicitamente. Caso isolado pode existir apenas em teste de migration/admin claramente justificado; boundary operacional de pipeline/intake falha sem projeção. Não adicionar default, signal ou manager mágico.

### R6. Compatibilidade histórica legítima

JSON 1.1, payload de evento e parâmetros/forms SSR com chave/nome `exam_type` continuam legíveis quando seu contrato exige. Classificar cada ocorrência. Nenhuma delas pode resultar em acesso ORM ao field removido.

### R7. Schema e gates

`makemigrations --check --dry-run` retorna “No changes detected”. MigrationExecutor cobre falha e sucesso. Índices/constraints dimensionais continuam. Suite completa e inspeções sem reader/write residual.

## Arquivos esperados

- `apps/cases/models.py`;
- nova migration `apps/cases/migrations/0016_*.py` (usar próximo número real);
- `apps/cases/procedures.py`;
- `apps/intake/services.py` para remover kwargs finais de criação;
- teste novo de migration e testes de contrato residuais estritamente necessários.

Proibido: alterar comportamentos/filas/templates, prompts/pipeline, FSM/roles, docs/runbook, apagar JSON/eventos/prompt history.

## TDD obrigatório

RED mínimo:

1. MigrationExecutor com Case sem rows aborta antes de remover field.
2. Estado válido migra e introspecção prova ausência da coluna.
3. Dados não relacionados sobrevivem.
4. Writers funcionam sem kwarg/atribuição.
5. introspecção/model não expõe `ExamType`/field.
6. fixtures finais explícitas e legacy JSON/event renderiza.
7. makemigrations sem drift.

GREEN mínimo e REFACTOR removem apenas ponte morta.

## Inspeções obrigatórias

```bash
rg -n "Case\.exam_type|case\.exam_type|self\.exam_type|get_exam_type_display|ExamType|exam_type=|exam_type__|filter\([^\n]*exam_type|Q\([^\n]*exam_type" apps config templates static tests --glob '!**/migrations/0014_*' --glob '!**/migrations/0015_*'
rg -n "bridge_exam_type_for_types|dual-write|ponte transitória|locked\.exam_type|new_case.*exam_type" apps tests
rg -n "eda_colonoscopy" apps templates static tests
rg -n "schema_version.*1\.1|preop_screening.*exam_type|old_exam_type|new_exam_type" apps tests
rg -n "CaseProcedure|declared_by_nir|uniq_case_procedure_type|proc_(declared|detection|disposition)_idx" apps/cases
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

## Critérios/gates

- [ ] R1–R7 provados.
- [ ] Precheck aborta dados inválidos.
- [ ] Coluna/enum/dual-write/default removidos.
- [ ] Nenhum reader/write/query ORM residual.
- [ ] Selection key combinada permanece apenas derivada.
- [ ] Dados/eventos/JSON/PDF/agenda preservados.
- [ ] Fixtures finais explícitas.
- [ ] Migration/makemigrations/gates verdes.
- [ ] Cap respeitado.

Responder: qual teste comprova fail-closed; qual introspecção prova remoção; como dados foram preservados; quais resíduos são payload/SSR legítimos; como combined key difere de coluna; fixtures; arquivos; baseline-final.

### Condições automáticas de INCOMPLETO

Reader residual encontrado; migration inventa row/default, remove campo antes do precheck ou perde dados; dual-write/field/ExamType permanece; JSON/evento histórico quebrado; selection key volta a ser persistida; fixture mágica; schema drift; cap/gate falha; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md` com matriz, inventário antes/depois, baseline, RED/GREEN/REFACTOR, snippets model/migration/writer/test, todas as ocorrências residuais classificadas, makemigrations/gates, cap, baseline-final e Handoff R1–R7.

## Prompt pronto

```text
Read all artifacts, ADR-0004, approved reports 001-008 plus 009-A, 009-B and 010, and the original 009 INCOMPLETE evidence. If 009-A, 009-B or 010 is not approved, STOP BLOCKED. Implement ONLY resized Slice 011. Follow the DeepSeek protocol and stop before editing if any operational reader remains or cap exceeds 10.

Add a fail-closed migration precheck requiring 1-2 valid CaseProcedure rows with a declaration for every Case, then remove Case.exam_type without inventing data or damaging events/JSON/PDF/decisions/appointments. Remove ExamType duplication, dual-write helpers/assignments/defaults and final Case creation kwargs. Keep eda_colonoscopy only as a derived SSR/selection key. Make residual fixtures explicit and classify historical JSON/event/parameter names. Run migration tests, makemigrations check, full gates and global inspections. Do not touch consumers/prompts/docs or mask residual readers.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-011-report.md; if complete mark only Slice 011 and true cutover DoD items, commit, push, reply REPORT_PATH and STOP.
```
