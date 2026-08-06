# Slice 002: Pipeline neutro analisa um ou dois procedimentos e entrega ao médico

## Handoff com contexto zero

Leia AGENTS/PROJECT_CONTEXT, todos os artefatos do change, ADR-0004, relatório aprovado do Slice 001 e:

- `apps/cases/{models.py,exam_profiles.py,priority_signals.py,services.py}`;
- `apps/pipeline/{orchestrator.py,scope_detection.py,llm1_service.py,llm2_service.py,prior_case.py,tasks.py}`;
- `apps/pipeline/schemas/{llm1.py,llm2.py}` e `apps/pipeline/policy/**`;
- `apps/llm/models.py`, `apps/llm/management/commands/seed_prompts.py`;
- `apps/admin_ui/forms.py`;
- `apps/doctor/{presenters.py,reporting.py,views.py}` apenas para chegada/render mínimo;
- testes LLM/pipeline/colonoscopia atuais.

### Estado e fluxo entregue

Slice 001 persiste conjunto declarado; pipeline ainda é schema 1.1/singular. Entregue o núcleo completo:

```text
Case com 1–2 declarados
→ uma chamada LLM1 v2 extrai história comum + procedures
→ detector reconcilia
→ auto-upgrade single→combined OU review NIR
→ policy por componente
→ uma chamada LLM2 v2 com recomendações por componente
→ suporte global mais restritivo
→ WAIT_DOCTOR com relatório neutro legível
```

Decisão por componente e prior histories completos são Slice 003.

## Protocolo obrigatório DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marcar task/commit/push.**

1. Verifique branch/árvore/ADR, registre BASE_REF e matriz requisito→arquivos→testes.
2. Rode `uv run pytest` completo antes de editar; baseline falho bloqueia.
3. Escreva testes e prove RED real por contratos v2/reconciliação.
4. GREEN mínimo; não implemente forms médicos/CHD/NIR/dashboard futuros.
5. REFACTOR restrito, com clean code, DRY, YAGNI, funções pequenas e sem cópia de pipeline.
6. Execute inspeções e interprete igualdade de conjuntos, número de chamadas, prompts e ausência de flag downstream.
7. Rode ruff check, format check, mypy e pytest completos; exit 0, zero failures/errors, final passed >= baseline.
8. Relatório factual + handoff verificável.
9. Só então task, commit normal, push, REPORT_PATH e STOP.

Este é o slice central. **Cap: 18 arquivos produto/teste**, ignorando tasks. Acima do cap exige revisão prévia; não omita requisito para caber.

### Quality gate obrigatório

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Requisitos

### R1. Schema LLM1 v2 procedure-neutral

Criar contrato estrito com common clinical/preop data e `requested_procedures[]` sem duplicatas, apenas EDA/Colonoscopia, evidence spans limitados e dados específicos tipados. Uma chamada por caso. Manter adapter de leitura 1.1; não reescrever JSON antigo.

### R2. Quatro prompts neutros

Adicionar seed/admin/fallback idempotentes para `exam_llm1_system/user` e `exam_llm2_system/user`. Novos jobs usam nomes neutros. Prompts extraem evidência, não codificam thresholds nem autorizam invenção. Não apagar versões antigas.

### R3. Detecção/reconciliação completa

Implementar matriz D7. Single→both com evidência forte marca ambos, evento de upgrade e segue sem ACK NIR. Declared both→single, single→other, unknown/non-supported retornam ao NIR. Histórico/negação não combinam. Payload enxuto inclui conjuntos e reason code.

### R4. Projeção detectada atômica

Atualizar `CaseProcedure.detection_status` via serviço/lock, criando row não declarada quando segundo procedimento é detectado. Falha não deixa parte do conjunto. LLM nunca altera `declared_by_nir`.

### R5. Policy por procedimento

Rodar base comum para cada detectado. Exceção de corpo estranho só EDA. Priority signals e textos são por procedimento/compatíveis. Não criar cópia de policy para combinado.

### R6. Schema/serviço LLM2 v2

Uma chamada recebe exatamente os detectados e resultados de policy; resposta contém exatamente um item por tipo, sem duplicata/omissão/adição. Reconciliar deterministicamente cada item. Suporte global é máximo explícito `none < anesthesist < anesthesist_icu`.

### R7. Chegada ao médico

Happy paths EDA, Colonoscopia e combinado chegam `WAIT_DOCTOR`. Relatório mínimo mostra história comum, dois procedimentos/recomendações quando combinados e alerta medicamentoso existente. Não alterar form/submit médico ainda.

### R8. Auditoria/falha/flag

Eventos de LLM/detecção/policy carregam schema/prompt versions e conjuntos, sem texto clínico integral. Resposta inválida falha explicitamente sem artefato parcial. Pipeline/workers não consultam `COLONOSCOPY_INTAKE_ENABLED`.

### R9. Regressão legada

Casos/artefatos 1.1 históricos continuam renderizáveis. Testes EDA/Colonoscopia atuais são atualizados conscientemente, não apagados em massa. Nenhum reset de banco.

## Arquivos esperados

- schemas LLM1/LLM2 (preferir arquivos novos v2 + adapters estreitos, máximo 3);
- services LLM1/LLM2;
- orchestrator e scope detector;
- até dois arquivos policy/profile/signals;
- serviço de projeção de procedimentos;
- seed prompts e admin form;
- presenter/reporting mínimo;
- até quatro arquivos de testes consolidados.

Justifique cada arquivo. Não tocar scheduler/dashboard/intake templates/correction.

## TDD obrigatório

### RED mínimo

1. LLM1 v2 aceita EDA, Colon e ambos; rejeita vazio/duplicata/outro tipo/evidence inválida;
2. uma chamada LLM1 em combinado;
3. quatro prompts neutros seed/admin/fallback e idempotência;
4. matriz D7 completa;
5. histórico/negação não combina;
6. upgrade cria row detectada não declarada, evento e chega médico sem ACK;
7. combined→single e mismatch não chegam médico/LLM2;
8. policy executa uma vez por componente e foreign-body não vaza;
9. uma chamada LLM2; igualdade exata do conjunto;
10. suporte mais restritivo;
11. combinado chega WAIT_DOCTOR com duas recomendações;
12. EDA/Colon simples continuam;
13. invalid v2 não persiste parcial;
14. schema 1.1 ainda renderiza;
15. flag falsa após criação não bloqueia pipeline.

### GREEN/REFACTOR

Implementar dispatch por coleção, não `if combined` espalhado. Extrair somente helpers necessários. Não migrar prior-case completo nem form médico.

## Inspeções obrigatórias

```bash
rg -n "schema_version.*2\.0|requested_procedures|procedure_recommendations|common_preop" apps/pipeline apps/doctor
rg -n "exam_llm[12]_(system|user)" apps/pipeline apps/llm apps/admin_ui
rg -n "PROCEDURE_SELECTION_AUTO_UPGRADED|CASE_PROCEDURES_DETECTED|detection_status" apps/cases apps/pipeline
rg -n "foreign_body|allows_foreign_body|evaluate_preop_policy" apps/pipeline/policy apps/pipeline/orchestrator.py
rg -n "COLONOSCOPY_INTAKE_ENABLED" apps/pipeline apps/doctor apps/llm || true
rg -n "run\(|complete\(" apps/pipeline/orchestrator.py apps/pipeline/llm1_service.py apps/pipeline/llm2_service.py
rg -n "CPRE|ERCP|preparo intestinal|polipect|suspender" apps/pipeline apps/doctor || true

git diff --name-only "$BASE_REF"
git diff -- apps/doctor/forms.py templates/doctor apps/scheduler apps/dashboard apps/intake
```

Inspecione que número de chamadas é garantido por teste (rg sozinho não prova), flag ausente, apps proibidas sem mudança e prompts antigos não apagados.

## Critérios binários

- [ ] R1–R9 provados.
- [ ] Uma chamada por estágio em combinado.
- [ ] Matriz de reconciliação completa.
- [ ] Combined happy path chega médico; incompatíveis não.
- [ ] LLM2 conjunto exato e suporte máximo.
- [ ] Foreign-body apenas EDA.
- [ ] Legacy 1.1 legível.
- [ ] Nenhum form médico/CHD/dashboard antecipado.
- [ ] ≤18 arquivos ou revisão.
- [ ] Gates/relatório completos.

## Gates de autoavaliação

1. Quais testes contam chamadas LLM1/LLM2?
2. Qual validator prova igualdade exata de conjuntos?
3. Qual evidência autoriza auto-upgrade?
4. Qual teste prova combined→single retorna NIR?
5. Como declaration fica imutável?
6. Como policy diverge sem duplicação?
7. Como suporte global é ordenado?
8. Como 1.1 continua legível?
9. Alguma flag aparece downstream?
10. Arquivos/cap e baseline vs final?

### Condições automáticas de INCOMPLETO

Ausência de baseline/RED/gate/relatório; duas chamadas por estágio; schema aceita duplicata/outro tipo; upgrade apaga declaração ou depende só de afirmação sem evidência; combined→single chega médico; mismatch passa; LLM2 altera conjunto; foreign-body vaza; suporte não usa máximo; 1.1 quebra; flag downstream; form médico/CHD antecipado; CPRE/preparo/hard rule; >18 sem revisão; teste removido para ficar verde; final falha/passed menor.

## Relatório obrigatório

`/tmp/support-combined-eda-colonoscopy-workflow-slice-002-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets dos schemas/prompts/reconciliação/policy/orchestrator/presenter, contagem de chamadas, inspeções, diff/cap, quality gate, baseline-final, gates e Handoff para verificador com reruns/checklist R1–R9.

## Prompt pronto

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all OpenSpec artifacts for support-combined-eda-colonoscopy-workflow, accepted ADR-0004, approved Slice 001 report, and every implementation/test file listed in Slice 002. Implement ONLY Slice 002 on the required branch.

Follow the DeepSeek4-Flash protocol exactly: clean BASE_REF, full pytest baseline before edits, requirement matrix, real RED, minimal GREEN, narrow clean-code/DRY/YAGNI refactor, all rg/diff checks, exact full gate and passed comparison. Any missing/failing evidence, final failure/error, passed_final < baseline, or >18 files without approval means INCOMPLETE: no task update/commit/push.

Deliver schema 2.0 with one shared-history LLM1 call, conservative procedure reconciliation including audited single→combined upgrade, per-procedure deterministic policy, one exact-set LLM2 call, strictest global support, neutral managed prompts and combined arrival at WAIT_DOCTOR. Preserve EDA/Colon simple and legacy schema 1.1. Do not implement doctor per-component decisions, prior histories UI, CHD, NIR correction, dashboard, CPRE or FSM changes.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-002-report.md, then if complete mark only Slice 002, commit, push, reply REPORT_PATH=... and STOP.
```
