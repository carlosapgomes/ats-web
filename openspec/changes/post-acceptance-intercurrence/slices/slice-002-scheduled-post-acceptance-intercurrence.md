<!-- markdownlint-disable MD013 -->

# Slice 002: Fluxo agendado sob o conceito pós-aceitação

## Handoff para implementador LLM com contexto zero

Pré-condição: Slice 001 concluído, revisado e presente na branch. Leia integralmente:

- `AGENTS.md`, `PROJECT_CONTEXT.md`;
- todos os artefatos em `openspec/changes/post-acceptance-intercurrence/`;
- change arquivado `openspec/archive/post-schedule-intercurrence/{proposal.md,design.md,tasks.md}`;
- `apps/cases/models.py` nos campos/transições da issue;
- `apps/cases/services.py` nos serviços, eventos sistêmicos e encerramento administrativo;
- `apps/intake/forms.py`, views históricas/ACK e templates de issue;
- `apps/scheduler/forms.py`, queue/confirm/submit e templates de issue;
- testes atuais `test_post_schedule_issue*`, `test_system_notices.py` e `test_administrative_closure.py`.

Estado atual: a feature agendada funciona e tem forte cobertura. Este slice deve renomear o conceito futuro para **intercorrência pós-aceitação**, adicionar contexto/ciclo compatíveis, criar eventos genéricos futuros e fortalecer snapshots, sem ampliar ainda a elegibilidade aos quatro fluxos sem agenda.

Implemente somente o fluxo `scheduled`. Se `doctor_admission_flow` estiver em `OPERATIONAL_NOTICE_FLOWS`, continue inelegível neste slice; o Slice 003 fará a ampliação.

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Se qualquer item falhar, o slice está INCOMPLETO**: não marque tasks, não faça commit/push.

1. Antes de editar, registre no relatório matriz `R → arquivos → testes`.
2. Registre `BASE_REF=$(git rev-parse HEAD)` e execute `uv run pytest` completo no baseline limpo; pare se houver failure/error.
3. Escreva testes primeiro e demonstre RED real.
4. Faça GREEN mínimo sem implementar fluxo `operational_notice`.
5. Faça REFACTOR apenas para clareza, coesão, DRY e YAGNI.
6. Execute checks `rg`, testes focados e quality gate completo.
7. Pytest final: exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório deve conter evidência e handoff verificável. Só então atualize task, commit/push e pare.

### Condições automáticas de INCOMPLETO

- migration/backfill sem teste;
- dados ativos legados não preservados;
- eventos append-only antigos reescritos/apagados;
- fluxo scheduled perde qualquer ação, lock ou transição;
- fluxo sem agenda torna-se elegível antes do Slice 003;
- texto visível novo continua “pós-agendamento” nas superfícies da feature;
- resposta agendada não registra snapshots before/after;
- testes exercitam apenas serviços e não comprovam NIR + CHD end-to-end;
- qualquer permissão/CSRF/lock é relaxado;
- baseline, RED, inspeção, gate ou relatório ausente/falhando;
- pytest final regressivo ou com failure/error.

## Objetivo do slice

```text
Issue agendada histórica continua legível
+ novo ciclo scheduled recebe context/cycle_id e eventos pós-aceitação
+ NIR/CHD veem a nova terminologia
+ cancelar/reagendar/manter/negar e ACK NIR continuam intactos
```

## Requisitos funcionais

### R1. Schema compatível

Adicionar ao `Case`:

```text
post_acceptance_issue_context: "" | "scheduled" | "operational_notice"
post_acceptance_issue_cycle_id: UUID nullable
```

Não renomear/remover `post_schedule_issue_*`.

### R2. Backfill de issue ativa legada

Migration deve preencher, para `post_schedule_issue_status in (opened, responded)`:

- contexto `scheduled` quando vazio;
- UUID único quando ausente.

Casos sem issue ativa permanecem vazios/nulos. Testar migration forward e, se o padrão do projeto permitir, reverse seguro dos campos novos.

### R3. API de domínio pós-aceitação

Criar nomes genéricos/coerentes para abertura, resposta scheduled e ACK NIR. Wrappers legados são permitidos para reduzir quebra, mas não podem duplicar lógica.

A abertura deve:

- permanecer transacional com `select_for_update`;
- aceitar apenas caso `CLEANED`, aceito, `scheduled`, appointment confirmado, sem issue;
- gerar UUID;
- persistir contexto `scheduled`;
- fazer `CLEANED → WAIT_APPT`.

### R4. Eventos futuros genéricos

Novos ciclos usam:

- `POST_ACCEPTANCE_ISSUE_OPENED`;
- `POST_ACCEPTANCE_ISSUE_RESPONDED`;
- `POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED`.

Todos incluem `cycle_id`, `context` e `admission_flow`. Não criar simultaneamente evento antigo e novo para a mesma ação.

Eventos antigos `POST_SCHEDULE_ISSUE_*` continuam com labels e projeções legíveis.

### R5. Snapshot de auditoria

- abertura scheduled: snapshot da agenda atual;
- resposta: `appointment_before` e `appointment_after`, além de ação/mensagem;
- ACK: ciclo/contexto no payload antes de limpar os campos ativos.

Snapshots devem ser serializáveis e não consultar estado mutável posteriormente para formatar mensagem sistêmica.

### R6. Workflow scheduled sem regressão

Preservar:

- fila `WAIT_APPT` e destaque de issue;
- lock `scheduler_confirm` e heartbeat/release;
- ações `cancel/reschedule/maintain/deny`;
- regras condicionais de formulário;
- `WAIT_R1_CLEANUP_THUMBS` após resposta;
- lock `nir_receipt` e ACK direto a `CLEANED`;
- múltiplos ciclos sequenciais quando appointment continuar confirmado.

### R7. Terminologia visual

Nas superfícies NIR/CHD/timeline/thread dessa feature, novos textos devem usar “Intercorrência pós-aceitação”. Não é obrigatório renomear identificadores internos legados nem texto dentro do arquivo OpenSpec arquivado.

### R8. System notices e timeline

Eventos novos e antigos devem ter labels/dots e projeções sistêmicas. Projeções:

- continuam idempotentes por `source_event`;
- não geram `UserNotification`;
- não criam loops;
- mostram motivo/ação sem depender do `Case.appointment_at` atual.

### R9. Encerramento administrativo

Se manager/admin encerrar caso com issue nova ativa, snapshot do evento administrativo deve preservar status, contexto e `cycle_id`, e o serviço deve limpar todos os campos ativos novos/legados.

### R10. Não antecipar Slice 003

Os quatro fluxos sem agenda continuam inelegíveis e nunca entram em `WAIT_APPT` por este slice.

## Arquivos esperados

Arquivos produtivos prováveis:

- `apps/cases/models.py`
- `apps/cases/migrations/00xx_*.py`
- `apps/cases/services.py`
- `apps/intake/forms.py`
- `apps/intake/views.py`
- `apps/scheduler/forms.py`
- `apps/scheduler/views.py`
- templates diretamente ligados à issue em `templates/intake/` e `templates/scheduler/`

Testes prováveis:

- `apps/cases/tests/test_post_schedule_issue_services.py` ou novo arquivo renomeado/coeso
- `apps/cases/tests/test_system_notices.py`
- `apps/cases/tests/test_administrative_closure.py`
- `apps/intake/tests/test_post_schedule_issue*.py`
- `apps/scheduler/tests/test_post_schedule_issue.py`
- teste de migration conforme convenção do projeto

> Justificativa para mais de cinco arquivos: o slice é vertical e preserva um workflow completo já distribuído entre domínio, NIR e CHD. Dividir migration/domínio/UI em fatias horizontais deixaria estados intermediários incompatíveis. Toque somente arquivos efetivamente necessários e justifique cada extra no relatório.

### Fora de escopo/proibido

- elegibilidade/ACK para `operational_notice`;
- alterar consulta durável do Slice 001 salvo regressão comprovada;
- remover campos/eventos legados;
- novo estado FSM;
- renomeação física ampla;
- dashboard histórico multi-dia;
- WhatsApp/e-mail/push.

## TDD obrigatório

### RED

Cobrir antes da implementação:

1. migration/backfill de issue `opened` e `responded` legada;
2. novo open scheduled persiste contexto/UUID/evento genérico;
3. tentativa em cada fluxo sem agenda continua bloqueada;
4. cancel/reschedule/maintain/deny preservados;
5. evento de resposta contém snapshots before/after corretos;
6. ACK NIR registra ciclo antes de limpar e retorna `CLEANED`;
7. dois ciclos recebem UUIDs diferentes;
8. lock inválido/expirado continua bloqueando CHD/NIR;
9. eventos novos e antigos projetam notices sistêmicos idempotentes;
10. textos NIR/CHD usam pós-aceitação;
11. encerramento administrativo limpa contexto/ciclo e audita snapshot.

Pelo menos um teste deve falhar inicialmente por evento/contexto ausente, não apenas por texto.

### GREEN

Implementar contrato mínimo scheduled. Centralizar lógica em serviço; views apenas validam formulário/lock, chamam serviço e renderizam.

### REFACTOR

- evitar duplicar serviço legado/genérico;
- helpers de snapshot pequenos e puros;
- dispatch dict para formatadores;
- nomes claros apesar do storage legado;
- sem engine genérica.

## Checks de inspeção obrigatórios

```bash
rg -n "post_acceptance_issue_context|post_acceptance_issue_cycle_id" apps/cases/models.py apps/cases/migrations apps/cases/services.py
rg -n "POST_ACCEPTANCE_ISSUE_(OPENED|RESPONDED|ACKNOWLEDGED)|POST_SCHEDULE_ISSUE_(OPENED|RESPONDED|ACKNOWLEDGED)" apps/cases apps/intake
rg -n -i "intercorrência pós-agendamento|intercorrência pós-aceitação" templates/intake templates/scheduler apps/intake apps/scheduler
rg -n "select_for_update|scheduler_confirm|nir_receipt" apps/cases/services.py apps/scheduler/views.py apps/intake/views.py
rg -n "appointment_before|appointment_after|cycle_id|context|admission_flow" apps/cases/services.py
rg -n "POST_ACCEPTANCE_ISSUE|POST_SCHEDULE_ISSUE" apps/cases/services.py apps/intake/views.py
```

Explique ocorrências legadas esperadas e confirme que nenhuma string visual antiga permanece nas superfícies ativas da feature.

## Critérios binários de sucesso

- [ ] Migration e backfill comprovados.
- [ ] Campos legados preservados.
- [ ] Novos ciclos scheduled têm contexto/UUID/eventos genéricos.
- [ ] Quatro ações e locks passam sem regressão.
- [ ] Snapshots before/after auditáveis.
- [ ] ACK NIR limpa ciclo após registrar evento.
- [ ] Eventos antigos e novos continuam legíveis/projetados.
- [ ] Terminologia visual pós-aceitação.
- [ ] Fluxos sem agenda ainda inelegíveis.
- [ ] Encerramento administrativo compatível.
- [ ] Gate completo verde, final >= baseline.

## Gates de autoavaliação

1. Deploy com issue legada ativa perde ou duplica ciclo?
2. Algum novo evento depende do estado atual mutável do Case para explicar agenda passada?
3. Cancel/reschedule/maintain/deny mantêm exatamente a semântica anterior?
4. Locks continuam obrigatórios nos mesmos endpoints?
5. Algum fluxo sem agenda entrou em `WAIT_APPT`?
6. Evento legado ainda aparece corretamente na timeline/thread?
7. Há lógica duplicada entre API antiga e nova?
8. Encerramento administrativo deixa contexto órfão?

## Relatório obrigatório

Crie `/tmp/post-acceptance-intercurrence-slice-002-report.md` com protocolo completo, migration forward/backfill evidence, RED/GREEN, snippets, inspeções, baseline/final, quality gate, gates respondidos, escopo extra e Handoff para verificador com checklist R1–R10.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md, all artifacts under openspec/changes/post-acceptance-intercurrence, the archived post-schedule-intercurrence design, and Slice 002 completely. Implement ONLY Slice 002 after confirming Slice 001 is complete.
Follow the DeepSeek4-Flash protocol: full clean baseline before edits, requirement matrix, real RED, minimal GREEN, clean-code/DRY/YAGNI refactor, mandatory rg inspections, full quality gate and baseline-vs-final comparison.
Generalize only the existing scheduled issue to post-acceptance terminology/events, add compatible context/cycle fields with tested backfill, strengthen before/after audit snapshots, preserve all locks/FSM/actions/permissions and old event readability. Do NOT enable immediate/pre_icu/ward_icu_backup/pediatric_em yet and do not remove/rename physical legacy fields.
On any missing/failing gate, report INCOMPLETE without task update/commit. If complete, mark only Slice 002, create /tmp/post-acceptance-intercurrence-slice-002-report.md, commit, push change/post-acceptance-intercurrence, reply REPORT_PATH=..., then STOP.
```
