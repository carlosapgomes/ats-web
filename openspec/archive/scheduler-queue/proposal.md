# Proposal: Fila do Agendador (Scheduler Queue)

**Change ID**: `scheduler-queue`
**Fase**: 4 — Fila do Agendador
**Risco**: PROFISSIONAL (nova app, views, templates, FSM transitions — sem mudança em modelos existentes)
**Dependências**: Fase 3 (doctor queue) — casos chegam ao scheduler via `DOCTOR_ACCEPTED → R3_POST_REQUEST`

## Objetivo

Implementar a fila do agendador: scheduler visualiza casos aceitos pelo médico (`WAIT_APPT`),
confirma o agendamento com data/hora, ou nega com motivo. O resultado transiciona o FSM para
`APPT_CONFIRMED` ou `APPT_DENIED`.

## Escopo

### Funcionalidades

1. **Fila do agendador** (`/scheduler/`) — lista de casos em `WAIT_APPT` com:
   - Cards com dados do paciente, decisão médica, suporte, fluxo
   - Tempo de espera
   - Abas: Pendentes / Confirmados Hoje

2. **Tela de confirmação** (`/scheduler/<case_id>/`) — duas colunas:
   - Esquerda: dados do caso + decisão médica
   - Direita: formulário com:
     - Radio: confirmar agendamento / negar
     - Se confirmar: data + horário + observações (opcional)
     - Se negar: motivo (textarea)
   - Modal de confirmação

3. **Decisão do scheduler** — FSM transition + persistência:
   - `WAIT_APPT → APPT_CONFIRMED` (com appointment_at + instructions)
   - `WAIT_APPT → APPT_DENIED` (com reason)
   - Campos `appointment_status`, `appointment_at`, `appointment_instructions`,
     `appointment_reason` já existem no modelo Case

4. **Fluxo automático pós-doctor accept**:
   - Quando o doctor aceita (`doctor_submit`), já fazemos `ready_for_scheduler()`
   - Precisamos adicionar `scheduler_request_posted()` para avançar `R3_POST_REQUEST → WAIT_APPT`
   - Isso deve acontecer automaticamente após `ready_for_scheduler()` no submit do doctor

### Mocks de referência

- `demo-reference/scheduler/queue.html` — fila do agendador
- `demo-reference/scheduler/confirm.html` — tela de confirmação

## Fora de escopo

- Resultado NIR (Fase 5)
- Dashboard (Fase 6)
- Notificações push/email (in-app only)
- Admin (Fase 7)
