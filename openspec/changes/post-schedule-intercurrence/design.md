# Design: Intercorrência pós-agendamento

## Estado atual

O projeto é greenfield: ainda não há uso em produção nem dados assistenciais
reais a preservar. Não é necessário criar compatibilidade retrógrada para
versões anteriores deste fluxo.

`CaseStatus` preserva os estados legados, incluindo:

```text
WAIT_APPT → APPT_CONFIRMED/APPT_DENIED → WAIT_R1_CLEANUP_THUMBS → CLEANUP_RUNNING → CLEANED
```

Casos `CLEANED` saem das filas operacionais. A auditoria é feita por `CaseEvent` append-only. O NIR já possui confirmação de recebimento em `WAIT_R1_CLEANUP_THUMBS`; o agendador possui fila para `WAIT_APPT` e formulário para confirmar/negar agendamento.

## Decisões de arquitetura

### D1: Não criar novos estados FSM

A feature deve preservar os 17 estados. A intercorrência ativa será metadado de negócio no `Case`, não novo estado.

Motivo: a fila do agendador já é representada por `WAIT_APPT` e o retorno ao NIR por `WAIT_R1_CLEANUP_THUMBS`. O comportamento novo é um ciclo pós-fechamento, não uma fase clínica nova.

### D2: Permitir ciclo explícito `CLEANED → WAIT_APPT`

Adicionar transição dedicada, com nome claro, por exemplo:

```python
@transition(field=status, source=CaseStatus.CLEANED, target=CaseStatus.WAIT_APPT)
def open_post_schedule_issue(self, *, reason: str, message: str = "", user=None): ...
```

Ela deve validar antes da chamada, em serviço/form/view, que o caso é elegível:

```text
status == CLEANED
doctor_decision == accept
doctor_admission_flow == scheduled
appointment_status == confirmed
sem intercorrência ativa
```

### D3: Usar campos leves no `Case` para a intercorrência ativa/latest

Adicionar apenas o necessário para controlar a intercorrência aberta/respondida. Sugestão:

```python
post_schedule_issue_status = models.CharField(max_length=20, blank=True, default="")
post_schedule_issue_reason = models.CharField(max_length=50, blank=True)
post_schedule_issue_message = models.TextField(blank=True)
post_schedule_issue_opened_by = models.ForeignKey(... related_name="post_schedule_issues_opened", null=True, blank=True)
post_schedule_issue_opened_at = models.DateTimeField(null=True, blank=True)
post_schedule_issue_response_action = models.CharField(max_length=30, blank=True)
post_schedule_issue_response_message = models.TextField(blank=True)
post_schedule_issue_responded_by = models.ForeignKey(... related_name="post_schedule_issues_responded", null=True, blank=True)
post_schedule_issue_responded_at = models.DateTimeField(null=True, blank=True)
```

Status sugeridos:

```text
"" / none: sem intercorrência ativa
opened: aguardando agendador
responded: aguardando ciência NIR
```

Não criar tabela separada nesta entrega: múltiplos ciclos serão preservados por `CaseEvent`. Os campos do `Case` armazenam apenas o estado ativo/latest necessário para renderização e bloqueio.

### D4: Eventos são a fonte histórica

Registrar eventos com payload completo suficiente para auditoria:

```text
POST_SCHEDULE_ISSUE_OPENED
POST_SCHEDULE_ISSUE_RESPONDED
POST_SCHEDULE_ISSUE_ACKNOWLEDGED
```

Payload de abertura deve incluir motivo, mensagem, snapshot do agendamento atual e dados mínimos do ator. Payload de resposta deve incluir ação, mensagem/motivo, e para reagendamento/cancelamento/manutenção, snapshot anterior e novo dos campos de agendamento.

### D5: Campos principais de agendamento representam o estado atual

Regras de atualização pelo agendador:

- `reschedule`: `appointment_status="confirmed"` e atualiza `appointment_at`, `appointment_location`, `appointment_instructions`.
- `cancel`: `appointment_status="cancelled"`; mantém ou limpa data/local conforme UX escolhida, mas registra snapshot anterior em evento. Preferência: manter dados visíveis e usar status cancelado.
- `maintain`: `appointment_status="confirmed"`; não altera data/local, salvo instrução/mensagem se fizer sentido.
- `deny`: preserva `appointment_status="confirmed"` e data/local atuais; a negativa é da solicitação de alteração, não do agendamento original.

### D6: Mensagem NIR condicional

Motivos oficiais:

```text
death
clinical_condition
transport_unavailable
external_regulation
reschedule_request
other
```

Mensagem NIR:

- opcional para `death` e `external_regulation`;
- obrigatória para `clinical_condition`, `transport_unavailable`, `reschedule_request`, `other`.

Isso reduz atrito para casos óbvios sem perder contexto nos motivos que normalmente exigem orientação operacional.

### D7: Reaproveitar locks existentes

Ao voltar para `WAIT_APPT`, o caso deve usar o mesmo mecanismo de lease do agendador (`scheduler_confirm`) já existente. Não criar lock novo para este slice além do que já existe.

Quando o agendador responde e o caso volta para `WAIT_R1_CLEANUP_THUMBS`, deve usar o lock NIR de confirmação já existente, se aplicável.

### D8: Busca NIR separada da fila operacional

Criar rota/página de busca de casos encerrados para NIR, distinta da lista operacional atual. A lista operacional continua focada em `status != CLEANED`. A busca pós-agendamento pode listar `CLEANED`, mas sem expor ações indevidas.

Busca mínima:

- número da ocorrência;
- nome do paciente extraído de `structured_data`.

Implementação simples para nome: filtro `icontains` em JSON/texto conforme viável; se PostgreSQL JSON path complicar, usar abordagem enxuta e testada sem criar busca avançada.

## Serviços/helpers recomendados

Criar helpers pequenos em `apps/cases/services.py` ou módulo coeso equivalente:

```python
def is_post_schedule_issue_eligible(case: Case) -> bool: ...

def get_post_schedule_issue_ineligibility_reason(case: Case) -> str: ...

def open_post_schedule_issue(*, case: Case, user: User, reason: str, message: str) -> Case: ...

def respond_post_schedule_issue(*, case: Case, user: User, action: str, ...) -> Case: ...

def acknowledge_post_schedule_issue(*, case: Case, user: User) -> Case: ...
```

Manter nomes explícitos. Não criar workflow engine genérico.

## Impactos esperados

- `CLEANED` deixa de ser terminal absoluto, mas continua significando “fora das filas operacionais sem pendência ativa”.
- Filas e métricas que contam `WAIT_APPT` devem tolerar casos de agendamento inicial e intercorrência. Cards devem distinguir os dois.
- Timeline ganha múltiplos ciclos, sem sobrescrever histórico.
- A busca NIR deve impedir abertura duplicada enquanto `post_schedule_issue_status` estiver `opened` ou `responded`.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Duplicar intercorrência ativa | Campo de status + validação transacional com `select_for_update` no serviço de abertura |
| Confundir agendamento inicial com intercorrência | Badge e ramificação explícita em formulário/cards |
| Sobrescrever histórico de datas | Snapshot em `CaseEvent` antes/depois |
| Negação de solicitação apagar agendamento confirmado | Regra D5: `deny` preserva campos principais |
| Busca por nome ficar cara | Limitar escopo inicial, usar índice futuro apenas se necessário |

## Plano de ajuste em greenfield

Como ainda não há produção, não é necessário desenhar rollback para dados reais
ou compatibilidade retrógrada. Se a modelagem se mostrar inadequada durante a
demonstração/homologação, ajustar por nova migration e manter os eventos
gerados nos ambientes de desenvolvimento/teste apenas como evidência técnica.
