# Slice 003: Médico decide cada procedimento com justificativa e histórico próprio

## Handoff com contexto zero

Leia todos os artefatos, ADR-0004, relatórios aprovados 001–002 e:

- `apps/doctor/{forms.py,views.py,presenters.py,reporting.py}` e templates de queue/decision;
- `apps/cases/{models.py,services.py,admission.py}`;
- `apps/pipeline/prior_case.py`;
- `static/js/doctor_queue_filter.js`;
- testes de doctor, presenter, prior-case, locks e filtros.

### Fluxo entregue

```text
Caso com 1–2 detectados chega WAIT_DOCTOR
→ relatório mostra recomendação e histórico por componente
→ médico aprova/nega cada um
→ pode incluir o ausente com justificativa
→ suporte sugerido é o mais restritivo, mas médico decide
→ write atômico + eventos
→ nenhum aprovado: fluxo deny; ≥1 aprovado: fluxo accept
→ conjunto autorizado aparece em Decididos Hoje
```

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Qualquer falha = INCOMPLETO; não marque task, não faça commit/push e reporte bloqueio com evidência.**

1. Confirme branch exata, árvore limpa, ADR-0004 aceita e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Antes de editar, registre no relatório a matriz `Requisito → arquivo(s) → teste(s)` e rode `uv run pytest`; baseline com failed/error bloqueia.
3. Escreva testes primeiro e prove RED real pelo motivo funcional esperado.
4. Faça GREEN mínimo sem antecipar CHD/NIR/dashboard.
5. Faça REFACTOR somente no trecho tocado com clean code, DRY, YAGNI, nomes claros, coesão, baixo acoplamento e sem código morto.
6. Execute e interprete todos os checks `rg`/diff deste slice.
7. Rode exatamente `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`; final exige exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Gere relatório factual com comandos/exit codes, snippets antes/depois, inspeções e `Handoff para verificador`.
9. Só então marque Slice 003, commit normal, push, responda `REPORT_PATH` e PARE.

**Cap: 12 arquivos produto/teste.** Acima exige revisão prévia.

## Requisitos

### R1. Form por procedimento

Exibir EDA e Colonoscopia com origem declarada/detectada e recomendação quando existente. Permitir `approved|denied` para detectados e inclusão explícita do ausente. Não depender de JS para validação autoritativa.

### R2. Razões por componente

Negado exige razão específica. Aprovado não detectado exige justificativa de inclusão. Troca completa exige ambas. Aprovação original pode ter razão opcional. Erro em qualquer componente não persiste nenhum.

### R3. Serviço transacional e autorização

Persistir decisões sob `transaction.atomic`, row lock, role doctor, active role e lease existente. Revalidar status/lock na instância bloqueada. Nenhum write parcial ou rerun LLM. Eventos enxutos e ordenados.

### R4. Mapeamento para FSM existente

Zero aprovados usa `doctor_decision=deny`; um ou dois aprovados usa `accept`. Preservar support/admission flow, observação, transições e fluxos scheduled/operational atuais. Não criar estados.

### R5. Suporte global

Mostrar sugestão mais restritiva calculada no Slice 002 e manter escolha final médica. Não selecionar automaticamente no POST nem impedir override médico.

### R6. Históricos separados

Consumir o lookup procedure-aware entregue no Slice 002 e renderizar seções EDA/Colonoscopia. A fonte médica autoritativa é cada `CaseProcedure.doctor_disposition/doctor_reason`, nunca `Case.doctor_decision` isolado. Preservar a ordem D10: row negada → `doctor_denied`; row aprovada + agenda negada → `appointment_denied`; row aprovada → `doctor_approved`. Caso anterior combinado pode aparecer em ambas as seções com o mesmo `prior_case_id`, mas decisão/razão próprias. Preservar janela de sete dias, ordenação e deduplicação de corrected resubmission; aprovação pode ser contexto recente, mas não incrementa `prior_denial_count_7d`.

### R7. Queue e filtros médicos

Pendentes filtram pelo conjunto detectado; Decididos Hoje pelo autorizado, com opções Todos/EDA/Colonoscopia/Combinado e `Nenhum autorizado` onde aplicável. Busca/polling/limpar preservam comportamento. Cards mostram transformação quando diverge.

### R8. Auditoria e no-rerun

Evento `DOCTOR_PROCEDURE_DECISIONS_RECORDED` registra disposições, presença/razões conforme política e `added_by_doctor`. Inclusão não agenda tarefa LLM e não muda detecção/declaração.

## Arquivos esperados

- forms/views/presenter/reporting doctor (máximo 4);
- template decision e queue partial (máximo 2);
- cases service/model somente se campo/API do Slice001 insuficiente (máximo 2);
- prior_case;
- JS filtro;
- até três testes consolidados.

Proibido scheduler/NIR/dashboard/migration/FSM/prompts/schema LLM.

## TDD RED mínimo

1. combinado permite approve/deny independentes;
2. partial accept → Case accept e somente aprovado no conjunto;
3. all denied → deny;
4. razão obrigatória por negado;
5. inclusão sem razão inválida;
6. EDA→Colon exige duas razões;
7. EDA→both exige razão da Colon;
8. erro não persiste parcial/evento/transição;
9. inclusão não chama/enfileira LLM;
10. lock/role/status inválidos bloqueiam;
11. support sugerido estrito mas escolha final persiste;
12. EDA prévia negada + Colon prévia aprovada aparecem nas seções/decisões corretas;
13. same prior combined mantém `prior_case_id`, mas razão/disposição próprias por row;
14. agenda global negada aplica-se somente às rows previamente aprovadas;
15. janela de sete dias e deduplicação permanecem, e aprovação não incrementa `prior_denial_count_7d`;
16. filtros detectado/autorizado + busca/polling;
17. fluxos accept/deny/admission existentes regressam verdes.

## Inspeções obrigatórias

```bash
rg -n "doctor_disposition|doctor_reason|added_by_doctor|DOCTOR_PROCEDURE_DECISIONS_RECORDED" apps/doctor apps/cases
rg -n "transaction\.atomic|select_for_update|assert_case_lock|role_required" apps/doctor apps/cases
rg -n "lookup_prior.*procedure|procedure_type|doctor_disposition|doctor_approved|doctor_denied|appointment_denied" apps/pipeline/prior_case.py apps/doctor
rg -n "eda_colonoscopy|Nenhum autorizado|data-.*procedure" templates/doctor static/js/doctor_queue_filter.js
rg -n "async_task|Schedule|run_pipeline|execute_.*llm" apps/doctor apps/cases || true
rg -n "CaseStatus|@transition" apps/doctor apps/cases/models.py

git diff --name-only "$BASE_REF"
git diff -- apps/scheduler apps/intake apps/dashboard apps/pipeline/schemas apps/llm apps/cases/migrations
```

## Critérios/gates

- [ ] R1–R8 provados.
- [ ] Razões por componente fail-closed.
- [ ] Inclusão/troca funcionam sem rerun.
- [ ] Lock/role/FSM preservados.
- [ ] Histórico separado usa disposição/razão da row e semântica D10.
- [ ] Aprovação histórica, negativa médica e negativa global de agenda são distinguíveis.
- [ ] Filtros usam dimensão certa.
- [ ] ≤12 arquivos e nenhum app futuro.
- [ ] Baseline/gates/relatório completos.

## Gates de autoavaliação

Responder objetivamente no relatório:

1. Qual teste prova atomicidade sem decisão/evento parcial?
2. Qual matriz de razões cobre negativa, inclusão, ampliação e troca?
3. Qual teste prova que inclusão médica não reexecuta LLM?
4. Como disposições mapeiam para accept/deny sem FSM nova?
5. Qual teste prova sugestão restritiva com override médico?
6. Como prior lookup impede cruzamento e qual teste prova EDA negada + Colon aprovada no mesmo caso anterior?
7. Como negativa global de agenda é limitada às rows aprovadas e como janela/dedup são preservadas?
8. Quais dimensões alimentam Pendentes e Decididos Hoje?
9. Quais arquivos mudaram e por quê?
10. Qual a comparação baseline-final com zero failures/errors?

### Condições automáticas de INCOMPLETO

Qualquer protocolo ausente; decisão parcial; razão faltante aceita; inclusão altera detected/declared ou roda LLM; lock/role relaxado; FSM nova; support imposto; prior usa decisão global isolada, cruza procedimento, omite aprovação, aplica agenda negada a row médica negada ou perde janela/dedup; filtros usam legado; app futuro tocado; >12 sem revisão; regressão de flows; final falha/passed menor; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-003-report.md` contendo:

- `Status: COMPLETE|INCOMPLETE`;
- matriz requisito→arquivo→teste;
- branch, BASE_REF, árvore e baseline com comando/exit code/resumo;
- RED/GREEN/REFACTOR com comandos, falhas esperadas e resultados;
- snippets antes/depois de form, serviço, lock, evento, prior lookup e UI;
- matriz de decisões/razões e prova de no-rerun;
- checks de inspeção interpretados e diff/cap justificados;
- quality gate completo e comparação `passed_final >= passed_baseline` com zero failures/errors;
- respostas aos gates de autoavaliação;
- **Handoff para verificador**: arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R8.

## Prompt pronto

```text
Read all project/change artifacts, accepted ADR-0004, approved reports 001-002 and Slice 003 implementation files. Implement ONLY Slice 003 on the required branch. Follow the full DeepSeek4-Flash protocol: baseline, real RED, minimal GREEN, clean/DRY/YAGNI local refactor, inspections, exact quality gate, baseline comparison and evidence report. Any missing/failing item or cap violation means INCOMPLETE with no task/commit/push.

Deliver atomic per-procedure doctor decisions, per-component denial/addition reasons, doctor-added procedure without LLM rerun, existing FSM accept/deny mapping, strictest support suggestion with physician override, D10 prior-history presentation sourced from each procedure row, and doctor filters by detected/approved selection. Preserve locks, roles, admission flows and corrected-case context. Do not touch CHD, NIR, dashboard, schemas/prompts, migrations or FSM.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-003-report.md; if complete mark only Slice 003, commit, push, reply REPORT_PATH and STOP.
```
