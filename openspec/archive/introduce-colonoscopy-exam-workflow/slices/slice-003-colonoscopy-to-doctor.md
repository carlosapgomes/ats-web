# Slice 003: Colonoscopia percorre pipeline e decisão médica

## Handoff com contexto zero

Leia todos os artefatos do change, ADR-0003, specs `exam-type-intake-routing` e `medication-safety`, este slice e implementação:

- `apps/pipeline/{orchestrator.py,scope_detection.py,llm1_service.py,llm2_service.py}`;
- `apps/pipeline/schemas/{llm1.py,llm2.py}`;
- `apps/pipeline/policy/**`;
- `apps/llm/management/commands/seed_prompts.py`;
- `apps/admin_ui/forms.py`;
- `apps/doctor/{views.py,presenters.py,reporting.py}`;
- `apps/cases/priority_signals.py`;
- `apps/pipeline/prior_case.py`;
- testes atuais correspondentes.

### Estado e objetivo

Slice 002 tornou tipo explícito, mas colonoscopia ainda é `non_eda`. Entregue o menor fluxo clínico completo:

```text
NIR envia colonoscopia com flag ativa
→ LLM1/prompt colonoscopia valida
→ scope confirma solicitação atual
→ policy comum sem foreign-body bypass
→ LLM2/presenter usam nomenclatura correta
→ WAIT_DOCTOR
→ médico aceita ou nega pelo form/FSM existente
```

Downstream genérico deve continuar funcionando; filtros especializados ficam nos Slices 004–005.

## Protocolo DeepSeek4-Flash obrigatório

Este modelo tende a concluir cedo. **Qualquer falha = INCOMPLETO; não marque task/commit/push.**

1. Confirme branch `feature/colonoscopy-exam-workflow`, árvore limpa e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Antes de editar, registre matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest`; baseline com failure/error bloqueia.
3. Escreva testes primeiro e prove RED real pelo comportamento esperado.
4. Faça GREEN mínimo sem antecipar slices.
5. Faça REFACTOR somente no trecho tocado com clean code, DRY, YAGNI, coesão e sem código morto.
6. Execute e interprete todos os `rg`/diff deste slice.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exige exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Gere relatório factual com comandos/exit codes, snippets antes/depois, comparação e seção **Handoff para verificador**.
9. Só então marque Slice 003, commit, push, responda REPORT_PATH e PARE.

Este é o slice central e pode ultrapassar 5 arquivos, mas cada arquivo deve mapear a requisito. **Mais de 14 arquivos de produto/teste (ignorando tasks) torna INCOMPLETO sem revisão do planner.** Não criar refactor genérico não necessário.

## Requisitos

### R1. Perfil de procedimento pequeno

Criar dispatch explícito EDA/colonoscopia com diferenças reais: labels, nomes de prompts, aliases, exceções e sinais permitidos. Regras comuns permanecem em funções compartilhadas. Não adicionar CPRE ou engine configurável abstrata.

### R2. Contrato/prompt colonoscopia

- `preop_screening.exam_type` aceita `colonoscopy`;
- colonoscopia usa procedimento `standard/unknown` sem subtipo especial;
- prompts separados LLM1/LLM2, defaults/fallbacks/seed/admin;
- instruções exigem mesmos exames, medicamentos do Slice 001 e pt-BR;
- não avaliar preparo/biópsia/diagnóstica-terapêutica como gate;
- prompts EDA existentes continuam canônicos.

### R3. Scope conservador

Reconhecer aliases aprovados; EDB só contextual. Histórico/negação do outro exame não cria mixed. Duas solicitações atuais EDA+colonoscopia retornam `manual_review_required`, `reason_code=mixed_exam_request`, sem LLM2/WAIT_DOCTOR. Mismatch declarado/detectado e unknown também voltam ao NIR com payload genérico.

Este requisito modifica a precedência antiga em que EDA atual prevalecia sobre colonoscopia atual; atualizar testes de regressão conscientemente.

### R4. Policy por tipo

Colonoscopia usa exatamente exames/thresholds/gates comuns, mas nunca `foreign_body_exception`, mesmo que texto/estrutura contenha corpo estranho histórico/ruído. Textos não podem afirmar rulebook EDA em caso colonoscopia. EDA preserva comportamento atual.

### R5. Reconciliação e suporte

LLM2, reconciliação e suporte/ASA funcionam para colonoscopia com mesmos enums. Nenhuma opção médica nova. Não duplicar policy.

### R6. Presenter e decisão

Fila/relatório identificam `Colonoscopia`; procedimento canônico não diz EDA. Os sete blocos e alerta medicamentoso permanecem. Médico usa form, lock e transições atuais para accept/deny. Teste integrado cobre pelo menos deny e accept agendado até `WAIT_APPT` ou fluxo equivalente existente sem branch por exame.

### R7. Prior-case e sinais type-aware

Lookup anterior filtra mesmo `exam_type`. EDA anterior não contamina colonoscopia da mesma ocorrência. Sinais colonoscopia persistem apenas `pediatric`; Dias em tela continua ordenando. EDA mantém todos os sinais.

### R8. Auditoria/flag

Flag é consultada somente para criar caso, não para continuar pipeline. Eventos de scope/policy incluem tipo sem texto longo. Desligar flag após criação não impede caso de chegar ao médico.

## Arquivos esperados

Planeje consolidar testes e manter até 14 arquivos produto/teste:

1. perfil novo em `apps/pipeline/` ou `apps/cases/` (um arquivo)
2. `apps/pipeline/schemas/llm1.py`
3. `apps/pipeline/llm1_service.py`
4. `apps/pipeline/orchestrator.py`
5. `apps/pipeline/scope_detection.py`
6. policy pré-operatória/reconciliação (máximo dois arquivos)
7. `apps/pipeline/prior_case.py`
8. `apps/cases/priority_signals.py`
9. `apps/doctor/presenters.py` e/ou reporting (máximo dois)
10. `apps/llm/management/commands/seed_prompts.py`
11. `apps/admin_ui/forms.py`
12. testes focados consolidados (até três arquivos)

Se o limite não comportar, pare e peça revisão; não omita requisitos.

## Proibido

- novos models/migrations/FSM/roles/forms médicos/CHD
- filtros UX dos slices seguintes
- correção/reprocessamento
- dashboard/NIR search
- CPRE/preparo intestinal/hard rule medicamentosa
- copiar pipeline por exame

## TDD

### RED obrigatório

Cobertura mínima:

1. schema estrito aceita colonoscopy e rejeita valor desconhecido;
2. seed/admin expõem quatro prompts colonoscopy e são idempotentes;
3. cada alias positivo, EDB contextual e EDB isolado;
4. EDA histórica + colon atual passa;
5. colon histórica + EDA atual passa;
6. EDA+colon atuais bloqueiam sem LLM2;
7. mismatch/unknown bloqueiam com declared/detected;
8. colon policy criteria_met/nega mínimo ausente;
9. corpo estranho não bypassa colon;
10. EDA foreign body continua bypassando;
11. prior case mesmo tipo apenas;
12. sinais colon apenas pediatric;
13. pipeline colon chega WAIT_DOCTOR e usa prompts colon;
14. presenter diz Colonoscopia e não “procedimento EDA”;
15. doctor accept/deny usa fluxo atual;
16. flag desligada após criação não bloqueia pipeline.

Rodar subconjuntos RED focados e registrar falha funcional, não só import error acidental.

### GREEN/REFACTOR

Implementar dispatch mínimo. Remover apenas duplicação criada no slice. Não renomear todo o domínio EDA se adapters explícitos resolvem.

## Inspeções obrigatórias

```bash
rg -n "colonoscopy|Colonoscopia|endoscopia digestiva baixa|videocolonoendoscopia|\\bEDB\\b" apps/pipeline apps/doctor apps/llm apps/admin_ui
rg -n "foreign_body_exception|evaluate_.*preop|exam_type" apps/pipeline/policy apps/pipeline/orchestrator.py
rg -n "mixed_exam_request|declared_exam_type|detected_exam_type" apps/pipeline apps/pipeline/tests
rg -n "colonoscopy_llm[12]_(system|user)" apps/llm apps/admin_ui apps/pipeline
rg -n "COLONOSCOPY_INTAKE_ENABLED" apps/pipeline apps/doctor apps/scheduler || true
rg -n "CPRE|preparo intestinal|polipect|suspender" apps/pipeline apps/doctor || true

git diff --name-only "$BASE_REF"
git diff -- apps/cases/models.py apps/cases/migrations apps/scheduler apps/dashboard static/js templates/doctor/queue.html
```

Interpretar cada ocorrência; flag ausente do processamento; proibidos sem diff; nenhuma implementação CPRE/preparo/suspensão.

## Critérios e gates

- [ ] R1–R8 provados.
- [ ] Colonoscopia happy path chega ao médico.
- [ ] Mixed/mismatch não chegam.
- [ ] EDA regressions preservadas.
- [ ] Corpo estranho nunca bypassa colon.
- [ ] Prompts separados administráveis.
- [ ] Prior lookup e sinais type-aware.
- [ ] Nenhum downstream duplicado.
- [ ] ≤14 arquivos ou revisão.
- [ ] Baseline/gate/relatório completos.

## Gates de autoavaliação

Responder no relatório:

1. Qual teste prova colonoscopia end-to-end até decisão?
2. Qual prova que mixed não chama LLM2?
3. Qual prova histórico não causa mixed?
4. Qual prova ausência de foreign-body bypass?
5. Qual prova EDA não regrediu?
6. Como prompts são selecionados/versionados?
7. Lookup anterior cruza tipos? Esperado: não.
8. Quais sinais colon preserva?
9. Algum fluxo médico/CHD foi duplicado?
10. Arquivos e comparação pytest?

### Condições automáticas de INCOMPLETO

Baseline/RED/gate/relatório ausentes; colon ainda scope-gated quando válida; mixed chega médico; EDB isolado confirma; histórico causa mixed; colon recebe foreign-body bypass/sinal EDA; EDA regressa; prompts não seed/admin/fallback; prior case cruza tipo; flag bloqueia caso existente; CPRE/preparo/hard medication implementados; model/FSM/form duplicado; requisito sem prova; >14 arquivos sem revisão; final falha/passed menor; commit prematuro.

## Relatório obrigatório

`/tmp/introduce-colonoscopy-exam-workflow-slice-003-report.md` com matriz, baseline, RED/GREEN/REFACTOR, snippets de profile/schema/prompt/scope/policy/presenter, inspeções interpretadas, full gate, baseline vs final, gates, diff/justificativa por arquivo e Handoff para verificador com rerun/checklist R1–R8.

## Prompt pronto

```text
Read all change artifacts, ADR-0003 and implementation files listed by slice-003-colonoscopy-to-doctor.md. Implement ONLY Slice 003 on feature/colonoscopy-exam-workflow. Follow the DeepSeek4-Flash protocol exactly: clean BASE_REF/branch, full pytest baseline first, real RED, minimal GREEN, narrow clean-code/DRY/YAGNI refactor, all rg/diff checks, exact full gate and passed baseline comparison. Any missing/failing gate means INCOMPLETE: no tasks update/commit/push.

Deliver the complete colonoscopy intake-to-doctor path using explicit profiles and separate managed prompts. Support approved aliases and current-request provenance; block current EDA+colonoscopy mixed PDFs and mismatches; share preop rules but never apply EDA foreign-body bypass to colonoscopy; preserve EDA; keep prior lookup/signals type-aware; reuse existing doctor/FSM/downstream. Do not implement filters, correction UI, dashboard, CPRE, bowel prep or medication decisions. Respect the 14-file cap or stop for planner review.

Create /tmp/introduce-colonoscopy-exam-workflow-slice-003-report.md with all evidence and Handoff para verificador. If complete, mark only Slice 003, commit, push, reply REPORT_PATH=... and STOP.
```
