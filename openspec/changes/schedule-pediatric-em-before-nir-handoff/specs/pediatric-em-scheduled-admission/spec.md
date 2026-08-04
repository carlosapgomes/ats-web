# Capability: Agendamento com entrada pela Emergência Pediátrica

## MODIFIED Requirements

### Requirement: Novas decisões pediátricas exigem agendamento

Quando o médico aceitar um caso escolhendo o item funcional de compartilhamento/entrada pela Emergência Pediátrica, o sistema MUST encaminhar o caso ao CHD para agendamento antes de produzir o resultado final ao NIR.

#### Scenario: Aceite médico abre agendamento

- **GIVEN** caso em `WAIT_DOCTOR`
- **WHEN** o médico aceita e escolhe o fluxo de entrada pela Emergência Pediátrica
- **THEN** o sistema persiste o código interno agendado `pediatric_appt`
- **AND** transiciona o caso até `WAIT_APPT`
- **AND** registra `SCHEDULER_REQUEST_POSTED`
- **AND** não registra `ADMISSION_FLOW_OPERATIONAL_NOTICE` para essa nova decisão.

#### Scenario: Resultado não é finalizado antes do CHD

- **GIVEN** nova decisão `pediatric_appt` em `WAIT_APPT`
- **WHEN** o NIR consulta o caso antes de o CHD decidir
- **THEN** o caso aparece aguardando agendamento
- **AND** não aparece como resultado final pronto para confirmação de recebimento.

### Requirement: CHD agenda ou nega pelo fluxo normal

O CHD MUST processar `pediatric_appt` pelas mesmas regras, formulário, lock, auditoria e transições usadas pelo agendamento normal.

#### Scenario: CHD confirma data e hora

- **GIVEN** caso `pediatric_appt` em `WAIT_APPT`
- **WHEN** o CHD confirma uma data e hora válidas
- **THEN** `appointment_status` fica `confirmed`
- **AND** `appointment_at` contém a data/hora informada
- **AND** o sistema registra `APPT_CONFIRMED` e `FINAL_REPLY_POSTED`
- **AND** o caso retorna ao NIR em `WAIT_R1_CLEANUP_THUMBS`.

#### Scenario: CHD nega o agendamento

- **GIVEN** caso `pediatric_appt` em `WAIT_APPT`
- **WHEN** o CHD nega o agendamento e informa o motivo obrigatório
- **THEN** `appointment_status` fica `denied`
- **AND** `appointment_reason` preserva o motivo
- **AND** o sistema registra `APPT_DENIED` e `FINAL_REPLY_POSTED`
- **AND** o caso retorna ao NIR em `WAIT_R1_CLEANUP_THUMBS`.

### Requirement: NIR recebe via de entrada e resultado da agenda

O resultado final ao NIR MUST comunicar de forma explícita a via de entrada pela Emergência Pediátrica e o desfecho do CHD.

#### Scenario: Agendamento confirmado

- **GIVEN** caso `pediatric_appt` confirmado pelo CHD
- **WHEN** o NIR abre o detalhe operacional ou o detalhe histórico após encerramento
- **THEN** vê “Agendamento Confirmado”
- **AND** vê a data/hora agendada
- **AND** vê a informação explícita “Entrada pela Emergência Pediátrica”
- **AND** entende que o NIR comunicará essa equipe sobre a chegada da criança.

#### Scenario: Agendamento negado

- **GIVEN** caso `pediatric_appt` negado pelo CHD
- **WHEN** o NIR abre o resultado
- **THEN** vê “Agendamento Negado”
- **AND** vê o motivo informado pelo CHD
- **AND** pode confirmar o recebimento conforme o fluxo normal.

### Requirement: Casos históricos preservam a semântica anterior

Casos já persistidos com `doctor_admission_flow="pediatric_em"` MUST permanecer como fluxo histórico de ciência operacional sem agendamento.

#### Scenario: Notice histórico ainda pendente

- **GIVEN** caso `pediatric_em` com `ADMISSION_FLOW_OPERATIONAL_NOTICE` e sem ACK
- **WHEN** o CHD abre sua fila
- **THEN** o card histórico continua na seção de ciência operacional
- **AND** o CHD consegue confirmar ciência
- **AND** o caso não é movido para `WAIT_APPT`.

#### Scenario: Resultado histórico do NIR

- **GIVEN** caso `pediatric_em` encerrado sem `appointment_at`
- **WHEN** o NIR consulta o histórico
- **THEN** o resultado continua sendo apresentado como compartilhamento operacional com a EM Pediátrica
- **AND** não aparece como agendamento confirmado sem data.

#### Scenario: Sem backfill

- **GIVEN** implantação deste change
- **WHEN** existem casos `pediatric_em` em qualquer estado
- **THEN** nenhum caso é reaberto, migrado para `pediatric_appt` ou recebe agenda artificial.

## ADDED Requirements

### Requirement: Lifecycle posterior respeita a versão do fluxo

As projeções posteriores MUST tratar `pediatric_appt` como agendado e `pediatric_em` como operacional histórico.

#### Scenario: Intercorrência de novo caso agendado

- **GIVEN** caso `pediatric_appt` `CLEANED` com agendamento confirmado
- **WHEN** o NIR abre uma intercorrência pós-aceitação
- **THEN** o contexto é `scheduled`
- **AND** o caso retorna a `WAIT_APPT` para ação do CHD.

#### Scenario: Intercorrência de caso histórico

- **GIVEN** caso histórico `pediatric_em` `CLEANED`
- **WHEN** o NIR abre uma intercorrência pós-aceitação
- **THEN** o contexto permanece `operational_notice`
- **AND** o CHD apenas confirma ciência
- **AND** os campos `appointment_*` não são alterados.

### Requirement: Histórico e dashboard mantêm semântica consistente

O histórico do CHD e o dashboard MUST reconhecer a nova variante agendada sem apagar a categoria funcional histórica.

#### Scenario: Histórico CHD

- **GIVEN** caso `pediatric_appt` confirmado ou negado pelo CHD
- **WHEN** um usuário CHD pesquisa o histórico permitido
- **THEN** o caso é encontrado como caso agendado/processado.

#### Scenario: Próximo responsável

- **GIVEN** caso `pediatric_appt` em `WAIT_APPT`
- **WHEN** o dashboard calcula o próximo passo
- **THEN** mostra “Pendente: agendador”
- **AND** não mostra “Pendente: NIR”.

#### Scenario: Métrica funcional consolidada

- **GIVEN** um caso histórico `pediatric_em` e um novo caso `pediatric_appt` no período
- **WHEN** o dashboard calcula a categoria de EM Pediátrica
- **THEN** a contagem funcional é 2
- **AND** cada caso é contado uma única vez.
