# Proposal: Fila Médica (Doctor Queue)

**Change ID**: `doctor-queue`
**Fase**: 3 — Fila Médica
**Risco**: PROFISSIONAL (nova app, views, templates, FSM transitions — sem mudança em modelos existentes)
**Dependências**: Fase 2 (pipeline LLM) + Fase 2b (UI alinhada)

## Objetivo

Implementar a fila médica: médico visualiza casos em `WAIT_DOCTOR`, acessa detalhe com
dados estruturados + sugestão IA + PDF inline, e submite decisão (accept/deny) que
transiciona o FSM para `DOCTOR_ACCEPTED` ou `DOCTOR_DENIED`.

## Escopo

### Funcionalidades

1. **Fila médica** (`/doctor/`) — lista de casos em `WAIT_DOCTOR` com:
   - Cards com dados do paciente, sugestão IA (suporte + fluxo), tempo de espera
   - Badge de prioridade (casos com `support_recommendation=anesthesist_icu`)
   - Abas: Pendentes / Decididos Hoje

2. **Tela de decisão** (`/doctor/<case_id>/`) — duas colunas:
   - Esquerda: dados do paciente, extração IA, PDF inline
   - Direita: formulário de decisão com:
     - Radio: accept / deny
     - Se accept: suporte (none/anesthesist/anesthesist_icu) + fluxo (scheduled/immediate)
     - Se deny: motivo (textarea)
   - Modal de confirmação antes de submeter

3. **Decisão médica** — FSM transition + persistência:
   - `WAIT_DOCTOR → DOCTOR_ACCEPTED` (com support_flag + admission_flow)
   - `WAIT_DOCTOR → DOCTOR_DENIED` (com reason)
   - Campos `doctor_decision`, `doctor_support_flag`, `doctor_admission_flow`, `doctor_reason` já existem no modelo Case

4. **Fluxo pós-decisão**:
   - Accept → `DOCTOR_ACCEPTED → ready_for_scheduler → R3_POST_REQUEST → WAIT_APPT`
   - Deny → `DOCTOR_DENIED` → resultado volta ao NIR (Fase 5)

### Mocks de referência

- `demo-reference/doctor/queue.html` — fila médica
- `demo-reference/doctor/decision.html` — tela de decisão com formulário + modal

## Fora de escopo

- Prior case lookup (Fase 9)
- Scheduler queue (Fase 4)
- Resultado NIR (Fase 5)
- Dashboard (Fase 6)
- Admin (Fase 7)
