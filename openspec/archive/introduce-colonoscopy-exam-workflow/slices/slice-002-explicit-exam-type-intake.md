# Slice 002: Tipo explícito no intake e rastreabilidade inicial

## Handoff para implementador LLM com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, proposal/design/tasks deste change, `specs/exam-type-intake-routing/spec.md`, este slice e depois:

- `apps/cases/models.py`, última migration;
- `apps/cases/signals.py`;
- `apps/intake/services.py::process_uploaded_files` e `create_corrected_resubmission`;
- `apps/intake/views.py::intake_home` e contextos de detalhe/lista;
- `templates/intake/intake_home.html`, `_my_cases_content.html`, `case_detail.html`;
- `config/settings/base.py`, `.env.example` e compose dev/prod;
- testes de upload/model/intake.

### Estado atual e objetivo

Todo `Case` é implicitamente EDA. Entregue:

```text
NIR escolhe explicitamente EDA/Colonoscopia para um lote
→ backend valida um tipo único
→ Case persiste tipo; histórico vira EDA
→ flag pode bloquear somente novos uploads colonoscopia
→ NIR e detalhe médico mínimo mostram o tipo
```

Colonoscopia ainda não deve ser prometida como processável pelo pipeline neste slice; a flag fica desligada por default. Não implementar scope/prompt/policy (Slice 003).

## Protocolo obrigatório DeepSeek4-Flash

**Falha em qualquer item = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF`.
2. Monte matriz `R → arquivos → testes`; rode `uv run pytest` baseline antes de editar. Baseline com failures/errors bloqueia.
3. Testes primeiro e RED real pelo comportamento ausente.
4. GREEN mínimo, sem Slice 003+.
5. REFACTOR limitado com clean code, DRY, YAGNI.
6. Rode/registre/interprete todas as inspeções.
7. Rode `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exit 0, zero failures/errors, `passed_final >= passed_baseline`.
8. Gere relatório factual com snippets e Handoff para verificador.
9. Só então marque Slice 002, commit/push e PARE.

## Requisitos funcionais

### R1. Enum, campo e migration

- criar `ExamType` com somente `eda` e `colonoscopy`;
- adicionar `Case.exam_type` indexado;
- backfill **todos** os casos existentes como EDA sem consultar artefatos;
- índice composto `(status, exam_type)` ou equivalente justificado;
- nenhuma decisão/status/evento histórico alterado.

### R2. Upload obrigatório e homogêneo

- radio/fieldset com label acessível e nenhuma opção `checked`;
- backend exige tipo válido;
- um valor se aplica a todos os PDFs do lote;
- `process_uploaded_files(..., exam_type=...)` cria todos com esse tipo;
- JS só habilita submit com arquivos + tipo, mas backend é fonte de verdade;
- copy exige lotes separados para tipos diferentes.

### R3. Flag somente de intake

Adicionar `COLONOSCOPY_INTAKE_ENABLED`, default false. Quando false:

- UI não oferece colonoscopia ativa ou explica indisponibilidade;
- POST manipulado é rejeitado sem criar casos;
- EDA continua;
- nenhum worker/pipeline consulta a flag.

Documentar env em `.env.example` e compose somente onde necessário para web; se propagada ao worker, provar que não é usada para interromper processamento.

### R4. Auditoria e exibição inicial

- `CASE_CREATED.payload` de novos casos inclui `exam_type` sem reescrever eventos antigos;
- badges `EDA`/`Colonoscopia` aparecem em casos recentes, Meus Casos e detalhe NIR;
- adicionar badge mínimo no topo/identificação da decisão médica para que o tipo persistido seja rastreável, sem filtros ainda.

### R5. Compatibilidade de criação

Atualizar todos os caminhos de criação atingidos pelos testes. `create_corrected_resubmission` pode aceitar tipo explícito já neste slice ou preservar o original temporariamente; a escolha livre ficará no Slice 007. Não alterar regras de não herança.

## Arquivos esperados

Este é um slice vertical estrutural; máximo esperado **9 arquivos de produto/teste** mais migration/tasks:

1. `apps/cases/models.py`
2. `apps/cases/migrations/0014_*.py`
3. `apps/cases/signals.py`
4. `apps/intake/services.py`
5. `apps/intake/views.py`
6. `templates/intake/intake_home.html`
7. um partial/template NIR já existente para badge
8. `config/settings/base.py` e/ou `.env.example` (contar configuração como um grupo, justificar compose extra)
9. testes focados (preferir 1–2 arquivos consolidados)

Tocar template médico somente se necessário para R4 e justificar como entrega vertical. Atualizar `static/js/upload.js` pode substituir outro template de badge na lista, não ampliar silenciosamente.

## Proibido

- `apps/pipeline/**`, policy/scope/prompts
- filtros médico/CHD/dashboard
- FSM/reprocessamento
- inferir histórico por texto
- habilitar flag por default

## TDD RED → GREEN → REFACTOR

Testes mínimos:

1. migration backfill EDA e preservação de campos;
2. form/POST sem tipo não cria caso;
3. tipo inválido não cria;
4. lote EDA cria todos EDA;
5. com override flag true, lote colonoscopia cria todos colonoscopia;
6. flag false rejeita POST colonoscopia mas caso colonoscopia preexistente pode ser lido/processado por helper não-intake;
7. nenhuma opção marcada por default no HTML;
8. CASE_CREATED contém tipo;
9. badges NIR aparecem;
10. upload/fixtures EDA existentes continuam.

RED alvo sugerido:

```bash
uv run pytest apps/intake/tests -q
uv run pytest apps/cases/tests/test_models.py -q
```

GREEN: implementação mínima. REFACTOR: centralize validação de choice/flag em service/form; não na template.

## Checks de inspeção

```bash
rg -n "ExamType|exam_type|status.*exam_type" apps/cases/models.py apps/cases/migrations
rg -n "exam_type|COLONOSCOPY_INTAKE_ENABLED|lote" apps/intake config/settings/base.py .env.example templates/intake static/js/upload.js
rg -n "COLONOSCOPY_INTAKE_ENABLED" apps/pipeline apps/intake/tasks.py apps/pipeline/tasks.py || true
rg -n "checked" templates/intake/intake_home.html

git diff --name-only "$BASE_REF"
git diff -- apps/pipeline apps/doctor/views.py apps/scheduler apps/dashboard
```

Interpretar: nenhuma consulta da flag no pipeline/worker; nenhuma opção pré-marcada; diff proibido vazio salvo badge médico explicitamente justificado.

## Critérios binários e gates

- [ ] R1–R5 comprovados.
- [ ] Migration sem inferência/reprocessamento.
- [ ] Backend, não JS, exige tipo.
- [ ] Flag bloqueia só intake e default false.
- [ ] Lote inteiro recebe o mesmo tipo.
- [ ] Badges iniciais visíveis.
- [ ] Sem scope/policy antecipado.
- [ ] Limite de arquivos respeitado/justificado.
- [ ] Baseline/final/quality gate válidos.

## Gates de autoavaliação

Responder no relatório:

1. Qual teste prova que histórico é EDA sem reprocessamento?
2. Qual teste prova homogeneidade do lote?
3. O POST manipulado burla a flag?
4. Algum worker consulta a flag? Esperado: não.
5. Há radio prechecked? Esperado: não.
6. Como corrected resubmission se comporta temporariamente?
7. Quais extras foram tocados?
8. Comparação pytest final?

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/relatório ausentes; histórico inferido/reprocessado; default visual marcado; tipo validado só em JS; lote com tipos por arquivo; flag true por default; worker bloqueado pela flag; colonoscopia anunciada como pipeline suportado neste slice; pipeline/policy alterado; requirement sem prova; arquivo extra sem justificativa; final falhando ou passed menor; task/commit prematuros.

## Relatório obrigatório

Criar `/tmp/introduce-colonoscopy-exam-workflow-slice-002-report.md` com status, BASE_REF/branch/status, matriz, baseline, RED/GREEN/REFACTOR, snippets antes/depois (model/migration/upload/flag/badge), inspeções, quality gate, baseline vs final, gates, escopo, commit e **Handoff para verificador** com rerun exato e checklist R1–R5.

## Prompt pronto

```text
Read every file in the handoff of slice-002-explicit-exam-type-intake.md. Implement ONLY Slice 002 on feature/colonoscopy-exam-workflow. Follow the DeepSeek4-Flash protocol: clean branch and BASE_REF, full pytest baseline before edits, real RED, minimal GREEN, narrow clean-code/DRY/YAGNI refactor, all inspections, exact full quality gate and baseline-vs-final evidence. Any failure means INCOMPLETE: no tasks update and no commit/push.

Deliver explicit homogeneous exam type selection and persistence, all-history EDA backfill, CASE_CREATED audit, intake-only global flag default false, and initial type badges. Do not touch pipeline/scope/policy/prompts, do not enable colonoscopy processing, do not infer/reprocess history and do not implement future filters/reprocessing.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-002-report.md with RED/GREEN, snippets, quality gate, rerun commands and Handoff para verificador. If complete, mark only Slice 002, commit, push, reply REPORT_PATH=/tmp/introduce-colonoscopy-exam-workflow-slice-002-report.md and STOP.
```
