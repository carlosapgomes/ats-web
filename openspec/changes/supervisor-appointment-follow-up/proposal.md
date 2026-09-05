# Proposal: Follow-up de agendamentos pelo Supervisor

**Change ID**: `supervisor-appointment-follow-up`
**Fase**: pós-ciclo operacional — registro de desfecho (outcome)
**Risco**: PROFISSIONAL (novos models + service + nova área UI com gating de papel; não altera FSM, filas ou fluxos existentes)
**Dependências**: `scheduler-queue` (campos de agendamento), `per-procedure-medical-decision` (`CaseProcedure`), `dashboard-case-list` (área do supervisor)

## Problema

Hoje o ciclo do caso encerra em `CLEANED` sem nunca registrar **o que aconteceu no dia do exame/procedimento**:

1. Não existe registro estruturado de se o exame/procedimento **foi realizado** ou não.
2. Não existe registro de **internação** decorrente do exame ou de sua suspensão.
3. Não realizada, a causa fica no escuro: **absenteísmo**, **cancelamento por falta de recursos no dia** (urgência que ocupou o horário, falta de tempo hábil, equipamento indisponível) ou **outras causas** não têm dimensão própria — aparecem apenas como texto livre em `appointment_reason` ou intercorrências operacionais.
4. O supervisor (`manager`) não tem nenhum ponto de entrada para informar esses desfechos, e o dashboard perde a métrica mais importante do serviço (produção real vs. programada).

## Objetivo

Criar uma aba **Follow-up** na área do supervisor (`manager` + `admin`) que:

- lista os casos **agendados para hoje e ontem** (e permite selecionar data específica), ordenados por data e nome do paciente;
- inclui também os casos de **vinda imediata autorizada** na data (fluxos `immediate`, `pre_icu`, `ward_icu_backup`, `pediatric_em`), que podem ser suspensos por falta de recursos;
- permite buscar por **número da ocorrência** (`agency_record_number`) ou **nome do paciente**;
- ao selecionar um caso, abre formulário de desfecho **por procedimento** (realizado / não realizado + causa estruturada) e **internação** no nível do caso;
- permite **atualizar** o follow-up criando nova versão, preservando histórico completo (dados anteriores, quem preencheu, quem atualizou) via rows append-only + `CaseEvent`.

O follow-up é **puramente registro** (informativo/métrica): não reabre caso, não dispara intercorrência/reagendamento e não altera a FSM.

## Escopo

### Funcionalidades

1. **Domínio (apps/cases)**: modelos `CaseFollowUp` (versão por caso) e `ProcedureFollowUp` (desfecho por `CaseProcedure`), service `record_case_follow_up` com validações, constraints de integridade e espelho em `CaseEvent` (`FOLLOWUP_RECORDED`/`FOLLOWUP_UPDATED`).
2. **Aba de listagem (dashboard)**: rota `/dashboard/follow-ups/` com default hoje+ontem (timezone `America/Bahia`), seletor de data, busca por ocorrência/nome, badge pendente/registrado.
3. **Formulário (dashboard)**: rota de detalhe por caso com desfecho por procedimento, internação no nível do caso, criação/atualização versionada e histórico compacto na própria página.

### Fora de escopo

- Integração com intercorrência pós-agendamento / reagendamento (decisão do domínio: fluxos permanecem independentes).
- Métricas/agregações no dashboard (produção real vs. programada) — change futuro.
- Notificações sobre follow-up.
- Alteração de FSM, filas operacionais ou fluxo de mensagens.

## Sucesso

- Supervisor registra desfecho de todos os procedimentos de um caso agendado/vinda imediata em < 1 minuto, com causas estruturadas consultáveis.
- Toda atualização preserva versões anteriores com autor e timestamp; auditoria unificada em `CaseEvent`.
- Nenhuma mudança de comportamento nas filas existentes (suite atual permanece verde).
