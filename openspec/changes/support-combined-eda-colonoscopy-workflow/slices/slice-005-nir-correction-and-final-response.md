# Slice 005: NIR corrige, filtra e recebe resposta comparativa

## Handoff com contexto zero

Leia todos os artefatos, ADR-0004, relatórios 001–004 e:

- `apps/intake/{forms.py,services.py,tasks.py,views.py}`;
- templates de my cases, detalhes, encerrados e corrected resubmission;
- `apps/cases/{models.py,services.py}`;
- static JS NIR relevante;
- testes de correção de exam type, corrected resubmission, my cases, closed search, receipt lease e recovery routing.

### Fluxo entregue

```text
combined declarado mas single detectado / mismatch / unknown
→ NIR corrige conjunto sob lock
→ derivados/detecção invalidados
→ mesmo Case reprocessa sem reextrair PDF

ou

caso em voo com upgrade automático
→ NIR vê `Declarado: EDA` e `Detectado: EDA + Colonoscopia`
→ não há CTA/ACK bloqueante

ou

caso concluído
→ NIR vê declarado → detectado → autorizado
→ razões por componente + agenda casada
→ confirma recebimento
```

Inclui filtros NIR por declarado e reenvio corrigido com as três seleções.

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Falha em qualquer item = INCOMPLETO; não marque task, não faça commit/push e reporte bloqueio com evidência.**

1. Confirme branch, árvore limpa, ADR-0004 e registre BASE_REF.
2. Registre matriz requisito→arquivo→teste e rode pytest completo antes de editar; baseline falho bloqueia.
3. Escreva testes primeiro e prove RED real.
4. Faça GREEN mínimo sem antecipar dashboard/cutover.
5. REFACTOR local com clean code, DRY, YAGNI, coesão e sem código morto.
6. Execute/interprete inspeções `rg` e diff.
7. Rode exatamente ruff check, format check, mypy e pytest completos; exit 0, zero failures/errors e passed final >= baseline.
8. Gere relatório factual com comandos, exit codes, snippets antes/depois e Handoff para verificador.
9. Só então marque Slice 005, commit normal, push, responda REPORT_PATH e PARE.

**Cap: 12 arquivos produto/teste.**

### Quality gate obrigatório

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Requisitos

### R1. Elegibilidade exata de correção

Permitir somente em `WAIT_R1_CLEANUP_THUMBS`, `manual_review_required`, reason de combined-incomplete/mismatch/unknown suportado e sem decisão médica. Upgrade automático single→combined não exige/mostra CTA. WAIT_DOCTOR ou posterior bloqueia.

### R2. Correção transacional do conjunto declarado

Sob `transaction.atomic`, `select_for_update`, ator NIR/active_role e lease válida: atualizar declaração via serviço, preservar histórico em evento, resetar detection statuses/dispositions pendentes e invalidar derivados v2. Falha não deixa parcial.

### R3. Recovery único pós-commit

Preservar PDF/anexos/extracted_text/ocorrência/timeline; não reextrair. Reusar execução existente no cluster `pdf`/rota correta, enfileirar uma análise após commit e permitir nova tentativa segura do mesmo case se necessário, sem colisão que suprima job.

### R4. Reenvio corrigido independente

Form aceita EDA, Colonoscopia e combinado, sem herdar rows/artefatos do original. Flag bloqueia Colon/combinado quando falsa. Um novo PDF combinado cria um novo Case com duas rows, original intacto.

### R5. Filtros NIR por declarado

Operacionais e encerrados aceitam Todos/EDA/Colonoscopia/Combinado, compõem filtros atuais, preservam polling/query string/order e não usam detected/approved.

### R6. Resposta comparativa

Detalhe/acompanhamento mostra declarado e detectado assim que a detecção estiver disponível, inclusive enquanto o caso segue para `WAIT_DOCTOR`, sem aguardar conclusão. Upgrade automático single→combined deve exibir explicitamente, por exemplo, `Declarado: EDA` e `Detectado: EDA + Colonoscopia`, sem CTA/ACK bloqueante. Quando houver decisão, mostrar também autorizado e, por procedimento, aprovado/negado/incluído pelo médico e razão própria. Combinado autorizado mostra uma agenda casada/data-hora. Nunca esconder a declaração original após upgrade.

### R7. Auditoria e ACK

Eventos de correção incluem conjuntos anterior/novo e motivo codificado, sem texto/PDF. ACK/final cleanup existentes permanecem idempotentes e não duplicam resposta por componente.

## Arquivos esperados

- intake forms/services/tasks/views (máximo 4);
- até quatro templates/JS NIR;
- cases service apenas se necessário;
- até três testes consolidados.

Proibido schemas/prompts/policy/doctor/scheduler/dashboard/model/migration/FSM.

## TDD RED mínimo

1. combined→single elegível corrige e reprocessa;
2. unique mismatch/unknown continuam;
3. caso em voo após auto-upgrade mostra declarado single + detectado combinado e não mostra correction CTA/ACK;
4. a comparação em voo permanece visível em polling/refresh antes da decisão médica;
5. WAIT_DOCTOR/decisão existente bloqueia;
6. ator/role/lease inválidos bloqueiam;
7. concurrent requests serializam, um job;
8. derivados v2/detection limpos, fontes preservadas, sem extração;
9. retry do mesmo case funciona no cluster pdf;
10. corrected resubmission combinado não herda e respeita flag;
11. filtros declared em operational/closed, combinados com demais;
12. resposta final partial/inclusion/combined com razões;
13. ACK/cleanup sem duplicação;
14. eventos enxutos.

## Inspeções obrigatórias

```bash
rg -n "manual_review_required|WAIT_R1_CLEANUP_THUMBS|select_for_update|transaction\.atomic|on_commit" apps/intake
rg -n "set_declared|detection_status|doctor_disposition|CASE_PROCEDURE_DECLARATION_CORRECTED" apps/intake apps/cases
rg -n "cluster=.pdf.|Schedule|execute_pdf_extraction|run_pipeline" apps/intake/tasks.py apps/intake/services.py
rg -n "Declarado|Detectado|Autorizado|Incluído|Agendamento casado|eda_colonoscopy" templates/intake apps/intake
rg -n "exam_type" apps/intake | sort
rg -n "extract|EXTRACTING" apps/intake/services.py apps/intake/tasks.py

git diff --name-only "$BASE_REF"
git diff -- apps/pipeline apps/doctor apps/scheduler apps/dashboard apps/cases/models.py apps/cases/migrations
```

## Critérios/gates

- [ ] R1–R7 provados.
- [ ] Correção race-safe e um recovery.
- [ ] Fontes preservadas; derivados invalidados.
- [ ] Upgrade em voo exibe declarado versus detectado sem CTA/ACK.
- [ ] Reenvio e filtros por declarado.
- [ ] Resposta final completa/acessível.
- [ ] ≤12 arquivos e gates/relatório completos.

## Gates de autoavaliação

Responder no relatório:

1. Qual é a elegibilidade exata e qual teste bloqueia correção do auto-upgrade/WAIT_DOCTOR sem esconder sua comparação em voo?
2. Como atomicidade, actor, active_role e lease são revalidados?
3. Qual prova preservação de fontes e ausência de reextração?
4. Qual prova cluster pdf, um job e retry do mesmo case?
5. Qual dimensão alimenta cada filtro NIR?
6. Qual teste prova não-herança no reenvio combinado?
7. Qual teste prova `Declarado` versus `Detectado` durante o voo, antes da decisão, inclusive após polling/refresh?
8. Como resposta final apresenta cada componente/razão?
9. Quais arquivos mudaram e por quê?
10. Qual a comparação baseline-final com zero failures/errors?

### Condições automáticas de INCOMPLETO

Protocolo ausente; auto-upgrade bloqueado ou invisível durante o voo; CTA/ACK exigido para upgrade; correção após médico; role/lease relaxado; parcial/race/job duplo; reextração; fonte apagada; derived residual; retry suprimido/cluster errado; resubmission herda; filtro usa dimensão errada; resposta omite razão/transformação; app proibido/model/FSM tocado; >12 sem revisão; final falha/passed menor; relatório ausente.

## Relatório obrigatório

Criar `/tmp/support-combined-eda-colonoscopy-workflow-slice-005-report.md` com Status, matriz requisito→arquivo→teste, branch/BASE_REF/baseline, RED/GREEN/REFACTOR, snippets antes/depois de eligibility/lock/invalidation/on_commit/form/filter/response, inspeções interpretadas, diff/cap, quality gate completo, comparação pytest e respostas aos gates.

Incluir **Handoff para verificador** com arquivos alterados, comandos exatos de rerun, riscos/limitações e checklist R1–R7.

## Prompt pronto

```text
Read all artifacts, accepted ADR-0004, approved reports 001-004 and Slice 005 files. Implement ONLY Slice 005. Follow the DeepSeek4-Flash protocol exactly; any missing/failing item or cap violation means INCOMPLETE and no tasks/commit/push.

Adapt safe NIR correction/reprocessing to procedure sets, render declared-versus-detected for in-flight auto-upgrade without CTA/ACK, preserve sources and invalidate v2 derivatives without extraction, enqueue exactly one recoverable pdf-cluster job, support combined corrected resubmission, filter NIR by declared selection, and render final declared→detected→authorized with per-component reasons and paired appointment. Preserve locks, roles, ACK/cleanup and no-heredity. Do not touch LLM, doctor, CHD, dashboard, models/migrations or FSM.

Create /tmp/support-combined-eda-colonoscopy-workflow-slice-005-report.md; if complete mark only Slice 005, commit, push, reply REPORT_PATH and STOP.
```
