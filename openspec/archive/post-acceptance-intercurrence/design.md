<!-- markdownlint-disable MD013 -->

# Design: Intercorrência pós-aceitação

## Estado atual

### Dois workflows já distintos

1. `scheduled`: aceite médico entra em `WAIT_APPT`; após decisão do CHD, NIR confirma resultado e o caso chega a `CLEANED`.
2. `immediate/pre_icu/ward_icu_backup/pediatric_em`: aceite registra `ADMISSION_FLOW_OPERATIONAL_NOTICE`, não entra em `WAIT_APPT`, envia resultado ao NIR e o CHD apenas confirma ciência.

A intercorrência atual é exclusivamente pós-agendamento. Campos `post_schedule_issue_*` guardam o ciclo ativo/latest; `CaseEvent` guarda histórico. A abertura faz `CLEANED → WAIT_APPT`, a resposta faz `WAIT_APPT → WAIT_R1_CLEANUP_THUMBS` via `final_reply_posted`, e o ACK NIR retorna diretamente a `CLEANED`.

### Fragilidade de notices

`unacknowledged_operational_notice_qs()` usa janela do dia local no timestamp do notice. Um aviso não confirmado desaparece na virada do dia. A exclusão por qualquer ACK histórico serve para o notice inicial único, mas não para ciclos recorrentes.

### Encerramento administrativo

`administratively_close_case()` é intervenção de manager/admin para retirar casos travados, limpa issue ativa e classifica o caso separadamente nas métricas. Mensagem sistêmica não gera notificação. Não é alternativa para comunicar mudança pós-aceitação.

## Decisões arquiteturais

### D1. “Pós-aceitação” é o conceito; há dois modos de resolução

```text
scheduled           → ação sobre agenda + retorno ao NIR
operational_notice  → ACK de ciência pelo CHD, sem agenda
```

Não criar workflow genérico. Serviços e views devem fazer branching explícito pelo contexto.

### D2. Preservar os 17 estados

- Contexto `scheduled` mantém o ciclo FSM existente.
- Contexto `operational_notice` permanece `CLEANED` durante abertura e ACK.

`CLEANED` continua significando encerramento do fluxo clínico/NIR. Assim como no notice inicial atual, pode existir uma pendência externa de ciência CHD sobre caso já concluído sem recolocar o caso nas filas clínicas.

### D3. Notices iniciais ficam pendentes até ACK

Remover da consulta ativa somente a restrição de data do **evento de notice**. Manter:

- fluxo em `OPERATIONAL_NOTICE_FLOWS`;
- evento novo ou legado presente;
- sem ACK novo ou legado;
- exclusão de `WAIT_APPT`;
- `distinct()`.

O histórico “ciências confirmadas hoje” continua filtrando o timestamp do ACK pelo dia local. Badge e fila devem continuar chamando o mesmo helper.

Para impedir duplicidade no Slice 003, a consulta inicial deve excluir caso com intercorrência ativa de contexto `operational_notice`; o card mais recente substitui o inicial.

### D4. Compatibilidade progressiva de nomes

Não renomear fisicamente nesta entrega os campos `post_schedule_issue_*`: há dados possíveis, migration existente, related names, testes e muitas referências. Adicionar apenas:

```python
post_acceptance_issue_context = CharField(max_length=30, blank=True, default="")
post_acceptance_issue_cycle_id = UUIDField(null=True, blank=True)
```

Nomes válidos de contexto:

```text
scheduled
operational_notice
```

Novos serviços e textos usam `post_acceptance`. Os campos legados ficam documentados como storage compatível, candidatos a cleanup futuro.

### D5. Migration e backfill de ciclo ativo legado

A migration deve:

1. adicionar os dois campos;
2. localizar casos com `post_schedule_issue_status in (opened, responded)` e contexto vazio;
3. definir contexto `scheduled`;
4. gerar UUID por caso quando `cycle_id` estiver ausente;
5. ser reversível apenas para os campos novos, sem apagar eventos/dados legados.

Não reescrever eventos históricos.

### D6. Eventos novos e compatibilidade append-only

Novos ciclos usam:

```text
POST_ACCEPTANCE_ISSUE_OPENED
POST_ACCEPTANCE_ISSUE_RESPONDED
POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED
```

Payload comum mínimo:

```json
{
  "cycle_id": "uuid",
  "context": "scheduled|operational_notice",
  "admission_flow": "scheduled|immediate|pre_icu|ward_icu_backup|pediatric_em"
}
```

Abertura também guarda motivo/mensagem. Para `scheduled`, snapshot da agenda atual. Resposta agendada deve guardar `appointment_before` e `appointment_after`, além da ação/mensagem. ACK guarda ator via `CaseEvent.actor` e payload de ciclo/contexto.

Formatadores, timeline e thread suportam eventos novos e antigos. Eventos antigos não são renomeados, duplicados ou apagados. Mensagens sistêmicas continuam sem `UserNotification`.

**Projeção de ACK (C6, Slice 002):** `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` (legado) continua omitido da thread por payload vazio. `POST_ACCEPTANCE_ISSUE_ACKNOWLEDGED` é projetado com mensagem genérica "Ciência da intercorrência pós-aceitação confirmada." pois possui `cycle_id`, `context` e `admission_flow` úteis para auditoria.

### D7. Elegibilidade

Regras comuns:

- `status == CLEANED`;
- `doctor_decision == "accept"`;
- sem issue ativa;
- fluxo reconhecido.

Regras por contexto:

- `scheduled`: `doctor_admission_flow == "scheduled"` e `appointment_status == "confirmed"`;
- `operational_notice`: fluxo em `OPERATIONAL_NOTICE_FLOWS`; não exigir nem preencher `appointment_status`.

A restrição a `CLEANED` evita conflito com lock `nir_receipt` e confirmação do resultado original. Ampliar para estado anterior exige change futuro.

### D8. Motivos oficiais

Preservar motivos atuais e adicionar:

```text
patient_absconded   → Paciente evadiu-se da unidade de origem
accepted_elsewhere  → Paciente aceito/transferido para unidade mais próxima
origin_cancelled    → Demanda cancelada pela unidade de origem
```

Mensagem:

- opcional para `death`;
- obrigatória para os demais motivos, inclusive `accepted_elsewhere`, para identificar destino/contexto quando pertinente;
- `external_regulation` continua existindo sem ser usado como substituto semântico dos novos motivos.

### D9. Fluxo scheduled preserva lock e retorno NIR

A nova API genérica pode expor funções coesas, por exemplo:

```python
open_post_acceptance_issue(...)
respond_scheduled_post_acceptance_issue(...)
acknowledge_scheduled_post_acceptance_issue(...)
```

Wrappers legados podem permanecer temporariamente se reduzirem risco, mas toda nova UI chama o serviço genérico. O scheduler continua usando `scheduler_confirm` lock em `WAIT_APPT`.

### D10. Fluxo operational_notice não usa lock de agenda

Abertura transacional:

1. `select_for_update()` no `Case`;
2. validar elegibilidade;
3. gerar `cycle_id`;
4. preencher storage ativo + contexto;
5. manter `status=CLEANED` e todos os `appointment_*` intactos;
6. criar evento de abertura.

ACK CHD:

1. POST protegido por papel `scheduler`;
2. `select_for_update()`;
3. validar `opened + operational_notice`;
4. criar exatamente um evento ACK;
5. limpar storage ativo/contexto/cycle_id;
6. manter FSM e agenda intactas.

Não é necessário lease de vários minutos para um botão idempotente de ACK; usar atomicidade como no `immediate_ack`.

### D11. Fila e contagem CHD

Adicionar queryset/helper único para intercorrências operacionais abertas. A fila CHD mostra seção/card próprio com:

- badge “Intercorrência pós-aceitação”;
- motivo e mensagem do NIR;
- fluxo original;
- paciente/registro/origem;
- CTA “Confirmar ciência”.

`queue_count` soma:

```text
WAIT_APPT
+ notices iniciais pendentes (já sem duplicata)
+ intercorrências operational_notice abertas
```

A mesma fonte deve alimentar fila e badge. ACKs de notices iniciais não entram no critério do ciclo novo; o campo ativo + `cycle_id` é a fonte da pendência.

### D12. Histórico e acesso

- NIR continua usando busca/detalhe de casos encerrados, agora com elegibilidade dos dois contextos.
- Scheduler não depende de `_is_scheduler_historical_case()` para executar ACK da pendência nova; a própria view faz escopo estrito por issue ativa e papel.
- Após ACK, histórico auditável permanece na timeline/thread e no dashboard.
- Busca histórica CHD multi-dia continua fora do escopo.

### D13. Semântica de dashboard e encerramento administrativo

- Contexto operacional nunca grava `appointment_status="cancelled"` ou `confirmed` artificialmente.
- Métrica de fluxo de admissão continua baseada em `doctor_admission_flow`.
- `_compute_stage_waiting().waiting_appt` não inclui contexto operacional porque o caso permanece `CLEANED`.
- Nenhum evento `CASE_ADMINISTRATIVELY_CLOSED` é criado.
- Encerramento administrativo continua limpando storage ativo; snapshot/payload deve incluir novos contexto/cycle_id se houver.

## Dimensionamento em slices

### Slice 001 — Notice inicial durável

Valor observável: CHD não perde pendência na virada do dia. Sem migration ou mudança de feature nova.

### Slice 002 — Scheduled sob o conceito pós-aceitação

Valor observável: fluxo já existente passa a usar terminologia/eventos genéricos, preserva locks/FSM e melhora auditoria. Introduz migration compatível e contrato de ciclo/contexto.

### Slice 003 — Quatro fluxos sem agenda

Valor observável: NIR comunica evasão/aceite externo/etc.; CHD confirma ciência sem WhatsApp/telefone e sem agenda fictícia. Inclui deduplicação com notice inicial e badge.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Notice antigo reaparecer indevidamente | Exigir evento de notice e ausência de ACK; testes com eventos novos/legados e múltiplos casos |
| Crescimento da consulta sem janela diária | Índices de `CaseEvent(event_type,timestamp)` já existem; medir query count/SQL em teste e evitar N+1 |
| Perder issue ativa em deploy | Migration/backfill de contexto e UUID por caso |
| Quebrar fluxo agendado | Slice dedicado com regressão de quatro ações, locks e FSM |
| Agenda fictícia em fluxo operacional | Snapshot antes/depois e asserção de todos os campos `appointment_*` inalterados |
| Card duplicado | Helper inicial exclui issue operacional ativa; teste de exatamente um card/count |
| ACK antigo ocultar ciclo novo | `cycle_id` + storage ativo, sem query “qualquer ACK histórico” para ciclos novos |
| Eventos novos sumirem da thread | Atualizar dispatch/labels mantendo eventos legados |
| Renomeação ampla gerar regressão | Campos físicos legados preservados nesta entrega |

## Rollback

- Slice 001 pode reverter apenas a consulta; nenhum dado é migrado.
- Slice 002: rollback de aplicação deve continuar lendo campos legados. Antes de reverter migration, confirmar ausência de issue ativa criada na versão nova ou preservar export dos campos context/cycle; eventos novos permanecem append-only e devem continuar legíveis por fallback cru.
- Slice 003 pode ocultar endpoints/seção nova e manter eventos/dados; não alterar `appointment_*` facilita rollback.

## Validações obrigatórias por slice

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Cada slice compara pytest completo baseline/final, exige zero failures/errors, inspeções `rg`, relatório temporário, commit/push e parada para revisão.
