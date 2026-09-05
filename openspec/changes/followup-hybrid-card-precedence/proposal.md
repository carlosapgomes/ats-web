# Proposal: Precedência de apresentação do card para casos híbridos no Follow-up

**Change ID**: `followup-hybrid-card-precedence`
**Tipo**: QUICK bugfix (P2 diferido do change `supervisor-appointment-follow-up`)
**Dependências**: `supervisor-appointment-follow-up` (Slices 001–003, commits `0d004b6`..`564ad94`)

## Problema

P2 diferido registrado na execução do Slice 002 (item "a") e confirmado nos reviews dos Slices 002/003: `_enrich_followup_item` (`apps/dashboard/views.py`) calcula `is_immediate` apenas por `is_operational_notice_flow(case.doctor_admission_flow)`, ignorando a precedência "ramo agendado válido vence" já unificada em `is_followup_eligible`/`_followup_group_date`/`_followup_event_time` e no formulário (`_followup_form_context`).

Efeito: num **caso híbrido** (agendamento confirmado com `appointment_at` **e** fluxo operacional), o card da listagem exibe ⚡ label do fluxo (com decisão possivelmente vazia) enquanto o agrupamento/ordenação e o formulário usam a data do agendamento — inconsistência visível na mesma tela para o mesmo caso.

Secundário (mesmo arquivo, zero risco): docstring de `followup_list` ainda afirma que "os cards não linkam para o formulário neste slice" — defasada desde o Slice 003 (R6 adicionou o link).

## Objetivo

Alinhar a apresentação do card à precedência canônica: se o ramo agendado é válido (`appointment_status="confirmed"` e `appointment_at` não nulo), o card exibe 📅 data/hora do agendamento; ⚡ label do fluxo apenas quando o caso cai no ramo operacional. Corrigir a docstring defasada.

## Escopo

- `apps/dashboard/views.py::_enrich_followup_item` — precedência unificada (R1).
- Teste de regressão do card híbrido + inalterabilidade dos casos puros (R2).
- Docstring de `followup_list` (R3).

### Fora de escopo (P2s que permanecem diferidos)

- Centralizar o classificador de ramo (duplicação em `_followup_form_context` etc.).
- Truncamento de `agency_record_number`; pill sem estado ativo; `EVENT_DOT_CSS` sem entrada para `FOLLOWUP_*`.

## Sucesso

Card híbrido confirmado mostra data do agendamento; casos puros agendado/imediato inalterados; suíte dashboard/cases verde; sem spec delta (comportamento passa a aderir ao design D4 do change pai, que já é o aprovado).
