<!-- markdownlint-disable MD013 -->

# Slice 003: Intercorrência pós-aceitação apenas para ciência

## Handoff para implementador LLM com contexto zero

Pré-condições: Slices 001 e 002 concluídos/revisados na branch. Leia integralmente todos os artefatos do change e, no código:

- `apps/cases/admission.py` (quatro fluxos e copies);
- serviços pós-aceitação criados no Slice 002;
- helper durável de notices do Slice 001;
- fila/ACK operacional em `apps/scheduler/views.py`;
- `queue_counts()`;
- busca e detalhe histórico NIR em `apps/intake/views.py`;
- templates `closed_cases_search.html`, `closed_case_detail.html`, `_queue_content.html`;
- testes dos quatro fluxos, issue scheduled, context processors, system notices e dashboard.

Estado esperado após Slice 002: novos ciclos scheduled possuem `context`, `cycle_id` e eventos `POST_ACCEPTANCE_ISSUE_*`; campos `post_schedule_issue_*` continuam como storage compatível; os quatro fluxos sem agenda ainda são inelegíveis.

Este slice entrega o caso de uso novo completo. Em `operational_notice`, o CHD **só confirma ciência**. Não reutilize formulário de cancelar/reagendar/manter/negar e não mova o caso para `WAIT_APPT`.

## Protocolo obrigatório para implementador DeepSeek4-Flash

**Qualquer falha torna o slice INCOMPLETO**: não atualizar task, não commit/push.

1. Matriz `R → arquivos → testes` no relatório antes de editar.
2. `BASE_REF=$(git rev-parse HEAD)` + `uv run pytest` completo no baseline limpo; pare se falhar.
3. Testes RED primeiro, incluindo asserção de agenda e FSM imutáveis.
4. GREEN mínimo somente para este fluxo.
5. REFACTOR clean code/DRY/YAGNI, sem engine genérica.
6. Inspeções `rg`, testes focados e quality gate completo.
7. Final com exit 0, zero failures/errors e `passed_final >= passed_baseline`.
8. Relatório verificável; somente depois task/commit/push e STOP.

### Condições automáticas de INCOMPLETO

- algum dos quatro fluxos sem agenda não coberto;
- caso sai de `CLEANED` na abertura ou ACK;
- qualquer campo `appointment_*` muda;
- CHD recebe ações de agenda em contexto operacional;
- notice inicial e issue aparecem duplicados;
- ACK antigo oculta ciclo novo;
- ciclo novo não tem UUID/contexto nos eventos;
- segundo ACK cria evento duplicado;
- fila e badge divergem;
- NIR/CHD permissions não testadas;
- encerramento administrativo é usado;
- baseline/RED/gates/relatório ausente ou falhando;
- pytest final regressivo ou com falhas.

## Objetivo do slice

```text
Caso aceito sem agenda e CLEANED
→ NIR registra evasão/óbito/aceite próximo/etc.
→ CHD recebe exatamente uma pendência durável de pós-aceitação
→ CHD confirma ciência
→ pendência some, auditoria permanece, caso/agenda não mudam
→ novo ciclo futuro continua possível
```

## Requisitos funcionais

### R1. Elegibilidade dos quatro fluxos

Permitir `operational_notice` quando:

- `status == CLEANED`;
- `doctor_decision == "accept"`;
- `doctor_admission_flow` em `immediate/pre_icu/ward_icu_backup/pediatric_em`;
- sem issue ativa.

Não exigir `appointment_status`. Casos denied, não `CLEANED`, fluxo desconhecido ou issue ativa continuam bloqueados com mensagem compreensível.

### R2. Motivos

Adicionar e exibir:

- `patient_absconded` — Paciente evadiu-se da unidade de origem;
- `accepted_elsewhere` — Paciente aceito/transferido para unidade mais próxima;
- `origin_cancelled` — Demanda cancelada pela unidade de origem.

Preservar motivos anteriores. Mensagem obrigatória para novos motivos; `accepted_elsewhere` deve permitir informar destino/contexto. Backend e form aplicam a mesma regra.

### R3. Abertura NIR

Pela busca/detalhe histórico:

- usar papel ativo `nir`;
- abrir transacionalmente;
- gerar/persistir contexto `operational_notice` e UUID;
- preencher storage ativo de motivo/mensagem/ator/horário;
- criar `POST_ACCEPTANCE_ISSUE_OPENED` com ciclo/contexto/flow;
- manter `Case.status=CLEANED`;
- preservar byte a byte/logicamente todos os campos `appointment_*`;
- mostrar sucesso e estado “aguardando ciência do CHD”.

### R4. Query própria e durável da pendência

Criar helper único para issues `operational_notice + opened`. Não filtrar pela data de abertura e não usar ausência de qualquer ACK histórico como fonte de pendência; storage ativo + `cycle_id` é autoritativo.

Fila scheduler e `queue_counts()` usam o mesmo helper.

### R5. Sem duplicidade com notice inicial

Enquanto issue operacional estiver aberta, `unacknowledged_operational_notice_qs()` não retorna o mesmo caso, mesmo se notice inicial ainda não tiver ACK. Queue count e HTML devem representar exatamente uma pendência.

Após ACK da issue, o notice inicial antigo não deve reaparecer como pendência fantasma. A operação de ACK deve registrar/considerar a ciência de forma que o caso permaneça sem duplicidade; documente no relatório a estratégia adotada e prove por teste nos cenários “notice inicial já confirmado” e “notice inicial ainda pendente”.

> Diretriz: no segundo cenário, o ACK da intercorrência mais recente pode também satisfazer a ciência do notice inicial, desde que isso seja explícito, atômico e auditado; não apague evento antigo.

### R6. Card CHD específico

Fila exibe seção/card com:

- “Intercorrência pós-aceitação”;
- paciente, registro e origem;
- fluxo de admissão original;
- motivo e mensagem NIR;
- abertura por/horário;
- CTA único “Confirmar ciência”.

Não mostrar “Agendar”, cancelar, reagendar, manter ou negar nesse card.

### R7. ACK CHD atômico e idempotente

Endpoint POST com `@login_required` e `@role_required("scheduler")`:

- `select_for_update` no Case;
- valida ciclo `opened + operational_notice`;
- registra exatamente um `POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED` com ciclo/contexto/flow;
- limpa todos os campos ativos legados e novos após capturar payload;
- mantém status e agenda;
- repetição/concor­rência não duplica evento nem corrompe caso;
- redireciona para fila com feedback.

Não usar lease `scheduler_confirm`, porque não há tela longa de edição.

### R8. Múltiplos ciclos

Depois do ACK, o mesmo caso continua elegível. Novo ciclo recebe UUID diferente e aparece mesmo com ACKs históricos do notice inicial/ciclo anterior.

### R9. Timeline/thread e NIR histórico

- timeline distingue abertura e ciência;
- mensagem sistêmica usa motivo/flow/cycle do payload, sem consultar estado ativo já limpo;
- não gera `UserNotification`;
- busca/detalhe NIR continuam acessíveis porque o caso permanece `CLEANED`;
- após ACK, detalhes históricos mostram eventos mesmo sem storage ativo.

### R10. Sem regressão scheduled/dashboard/admin

- scheduled continua com suas quatro ações e retorno NIR;
- `waiting_appt` não aumenta para issue operacional;
- `appointment_status` não produz badge “cancelado após intercorrência”;
- métricas de fluxo mantêm o admission flow original;
- nenhum `CASE_ADMINISTRATIVELY_CLOSED` é criado;
- encerramento administrativo, se acionado durante issue por caminho permitido, continua capturando/limpando contexto/ciclo.

### R11. Documentação de estado

Após implementação validada, atualizar `PROJECT_CONTEXT.md` e artefatos operacionais/manual estritamente necessários para descrever os dois modos, a durabilidade até ACK e os eventos novos. Não editar documentos arquivados como se fossem atuais.

## Arquivos esperados

Produtivos prováveis:

- `apps/cases/services.py`
- `apps/intake/forms.py`
- `apps/intake/views.py`
- `apps/scheduler/views.py`
- `apps/scheduler/urls.py`
- `apps/accounts/context_processors.py`
- `templates/intake/closed_cases_search.html`
- `templates/intake/closed_case_detail.html`
- `templates/scheduler/_queue_content.html`
- possivelmente template pequeno dedicado ao card/partial, se reduzir duplicação
- `PROJECT_CONTEXT.md`

Testes prováveis:

- domínio em `apps/cases/tests/`;
- NIR em `apps/intake/tests/`;
- CHD em `apps/scheduler/tests/`;
- badge em `apps/accounts/tests/test_context_processors.py`;
- regressões dashboard/admin/system notices.

> Justificativa para >5 arquivos: novo fluxo é vertical entre NIR e CHD, com domínio, rota, fila, badge, auditoria e documentação. Evite arquivos extras e justifique cada um no relatório.

### Fora de escopo/proibido

- nova migration salvo blocker comprovado do contrato aprovado no Slice 002;
- novos estados FSM;
- fluxo antes de `CLEANED`;
- ações decisórias do CHD em contexto operacional;
- histórico CHD multi-dia pesquisável;
- framework JS/API/DRF/HTMX novo;
- notificações externas;
- renomear campos legados.

## TDD obrigatório

### RED

Criar matriz parametrizada para os quatro flows e cobrir:

1. elegibilidade + abertura NIR por flow;
2. status permanece `CLEANED`;
3. snapshot de todos os `appointment_*` antes/depois da abertura e ACK é idêntico;
4. três motivos novos e validação de mensagem;
5. card/badge CHD persistem além do dia;
6. CTA único sem verbos/inputs de agenda;
7. ACK cria evento/payload e limpa ciclo;
8. ACK repetido/concor­rente não duplica;
9. novo ciclo após ACK com UUID diferente aparece apesar de ACK antigo;
10. notice inicial pendente + issue ativa = um card/count; após ACK = zero;
11. notice inicial já confirmado não bloqueia issue;
12. permissões NIR/scheduler e métodos HTTP;
13. scheduled continua funcionando;
14. dashboard não conta issue como `waiting_appt` nem cancelamento;
15. system notice não cria `UserNotification`.

Pelo menos um RED deve falhar por mutação/roteamento de domínio ausente, não somente por copy.

### GREEN

Implementar helpers coesos e views finas. Reutilizar parser/labels/mapeamentos existentes. Manter ACK numa transação única.

### REFACTOR

- fonte única de eligibility/reason labels/query count;
- deduplicação explícita entre notice inicial e issue;
- funções pequenas, sem booleanos ambíguos;
- nenhum acesso a appointment em formatter operacional;
- sem abstração de workflow genérica.

## Checks de inspeção obrigatórios

```bash
rg -n "patient_absconded|accepted_elsewhere|origin_cancelled" apps/cases apps/intake templates/intake
rg -n "operational_notice|post_acceptance_issue_cycle_id|POST_ACCEPTANCE_ISSUE_(OPENED|ACKNOWLEDGED)" apps/cases apps/intake apps/scheduler apps/accounts
rg -n "def .*operational.*issue.*qs|queue_count|unacknowledged_operational_notice_qs" apps/cases/services.py apps/scheduler/views.py apps/accounts/context_processors.py
rg -n "Confirmar ciência|Agendar|Cancelar agendamento|Reagendar|Manter agendamento|Negar solicitação" templates/scheduler
rg -n "@login_required|@role_required\(\"scheduler\"\)|select_for_update" apps/scheduler/views.py
rg -n "appointment_status|appointment_at|appointment_location|appointment_instructions|appointment_reason|appointment_decided_at" apps/cases/services.py
rg -n "CASE_ADMINISTRATIVELY_CLOSED|POST_ACCEPTANCE_ISSUE" apps/cases/services.py apps/dashboard/views.py
```

No relatório, diferencie ocorrências válidas no fluxo scheduled de ocorrências proibidas no branch operacional. Inspeção textual sozinha não substitui testes de imutabilidade.

## Critérios binários de sucesso

- [ ] Quatro flows elegíveis e parametrizados em testes.
- [ ] Três motivos novos validados/exibidos.
- [ ] Abertura operacional mantém `CLEANED` e agenda intacta.
- [ ] Fila/badge duráveis usam helper único.
- [ ] Exatamente um card/count com notice inicial concorrente.
- [ ] CHD apenas confirma ciência.
- [ ] ACK atômico/idempotente com payload completo.
- [ ] Ciclo futuro não é bloqueado por ACK antigo.
- [ ] Timeline/thread auditáveis sem notificações.
- [ ] Scheduled/dashboard/admin sem regressão.
- [ ] Documentação atualizada.
- [ ] Quality gate completo e final >= baseline.

## Gates de autoavaliação

1. Algum caminho escreve qualquer `appointment_*` em contexto operacional?
2. Algum caminho chama transição FSM na abertura/ACK operacional?
3. Um ACK inicial antigo pode ocultar issue nova?
4. Notice inicial sem ACK reaparece depois do ACK da issue?
5. Fila e badge podem contar o mesmo Case duas vezes?
6. Repetição/concor­rência cria dois ACKs?
7. Usuário doctor/manager/admin/nir consegue acionar ACK scheduler indevidamente?
8. O card contém qualquer CTA ambíguo de agenda?
9. Um segundo ciclo tem UUID próprio e histórico íntegro?
10. Métrica/admin closure mudou sem requisito?

## Relatório obrigatório

Crie `/tmp/post-acceptance-intercurrence-slice-003-report.md` com protocolo completo, matriz, baseline, RED/GREEN, tabela dos quatro flows, snapshots de agenda antes/depois, evidência de deduplicação/count, inspeções, quality gate, comparação pytest, gates e Handoff para verificador com checklist R1–R11.

## Prompt pronto para implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and every artifact under openspec/changes/post-acceptance-intercurrence. Confirm Slices 001-002 are complete, then implement ONLY Slice 003.
Follow the DeepSeek4-Flash protocol literally: clean full baseline, requirement matrix, real RED, minimal GREEN, clean-code/DRY/YAGNI refactor, mandatory inspections, full quality gate and baseline-vs-final evidence.
Enable post-acceptance issues for immediate/pre_icu/ward_icu_backup/pediatric_em only on accepted CLEANED cases. Keep Case CLEANED and every appointment_* field unchanged. Give CHD one durable, deduplicated card with only Confirmar ciência; use active context/cycle rather than absence of historical ACK, make ACK atomic/idempotent, support repeated cycles, preserve scheduled/admin/dashboard behavior, permissions and audit/system notices.
If any gate/evidence is missing or failing, report INCOMPLETE without task update/commit. If complete, mark only Slice 003, update current docs, create /tmp/post-acceptance-intercurrence-slice-003-report.md, commit, push change/post-acceptance-intercurrence, reply REPORT_PATH=..., then STOP.
```
