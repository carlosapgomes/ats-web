# Proposal: Corrigir apresentação de agendamento cancelado após intercorrência

**Change ID**: `fix-post-schedule-cancelled-presentation`  
**Fase**: bugfix operacional pós-Fase 3  
**Risco**: ESSENCIAL/baixo (corrige apresentação SSR; não altera FSM, banco, serviços nem dados)  
**Dependências**: `post-schedule-intercurrence`, `dashboard-supervisor`

## Problema

Casos que passaram pelo fluxo de intercorrência pós-agendamento e foram respondidos com ação `cancel` terminam novamente em `CLEANED` com:

```text
appointment_status = "cancelled"
```

A apresentação atual do dashboard não trata esse status:

- o card da lista gerencial pode cair no fallback de `doctor_decision="accept"` e mostrar **“Aguardando Agendamento”**;
- o detalhe gerencial pode tratar qualquer caso terminal aceito como `accepted_scheduled` e mostrar **“Agendamento Confirmado”**, mesmo com `appointment_status="cancelled"`.

Isso confunde supervisor/admin e sugere que o caso ainda está pendente ou confirmado quando, na verdade, houve cancelamento após intercorrência.

## Objetivo

Corrigir a semântica visual para casos encerrados após intercorrência cancelada, sem alterar o fluxo operacional:

```text
Caso CLEANED + accepted scheduled + appointment_status="cancelled"
→ Dashboard/lista e detalhe mostram cancelamento após intercorrência
```

Casos reagendados (`reschedule`) ou mantidos (`maintain`) continuam com `appointment_status="confirmed"` e devem permanecer apresentados como **Agendamento Confirmado**.

## Escopo

### Incluído

- Ajustar card da lista do dashboard gerencial (`apps/dashboard/views.py::_compute_result`).
- Ajustar resultado final do detalhe gerencial (`dashboard_case_detail` + template compartilhado se necessário).
- Cobrir regressões com testes de dashboard:
  - caso `cancelled` não aparece como “Aguardando Agendamento” nem como “Agendamento Confirmado”;
  - caso confirmado/reagendado/mantido continua como “Agendamento Confirmado”.
- Documentar slice vertical enxuto com handoff para LLM implementador.

### Fora de escopo

- Alterar FSM ou criar novo status.
- Alterar `respond_post_schedule_issue`/`acknowledge_post_schedule_issue`.
- Migrar dados ou editar casos em produção.
- Criar novas telas, filtros, notificações ou relatórios.
- Diferenciar visualmente `reschedule` versus `maintain` além de manter o resultado confirmado.

## Critérios de sucesso

- Caso `appointment_status="cancelled"` aparece no card como **Agendamento cancelado após intercorrência**.
- Detalhe do caso com `appointment_status="cancelled"` mostra resultado final de cancelamento, não confirmação.
- Casos com `appointment_status="confirmed"` continuam mostrando **Agendamento Confirmado**.
- Nenhuma fila operacional ou transição FSM é alterada.
- Quality gate do `AGENTS.md` executado.
- Relatório temporário do slice gerado para revisão por terceiro LLM.
