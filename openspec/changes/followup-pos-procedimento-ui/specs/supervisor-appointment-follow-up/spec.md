## RENAMED Requirements

- FROM: `### Requirement: A aba Follow-up SHALL listar elegíveis por data com ordenação e busca previsíveis`
- TO: `### Requirement: A aba Pós-Procedimento SHALL listar elegíveis por data com ordenação e busca previsíveis`

## MODIFIED Requirements

### Requirement: A aba Pós-Procedimento SHALL listar elegíveis por data com ordenação e busca previsíveis

A aba SHALL listar, para o dia local corrente e o dia anterior (default), os casos com agendamento confirmado (`appointment_at` local na data) e os casos de vinda imediata autorizada (`doctor_admission_flow` operacional com `doctor_decided_at` local na data), ordenados por data e nome do paciente, SHALL permitir selecionar data específica e SHALL permitir busca por número da ocorrência ou nome do paciente sobre a população elegível. Cada item SHALL indicar se há follow-up registrado (badge "Pós-procedimento registrado" / "Pós-procedimento pendente").

#### Scenario: Default hoje e ontem ordenado

- **GIVEN** casos elegíveis hoje e ontem com pacientes de nomes variados
- **WHEN** o supervisor do CHD abre `/dashboard/follow-ups/` sem parâmetros
- **THEN** os casos de hoje e ontem aparecem agrupados por data ascendente
- **AND** dentro de cada data, ordenados por nome do paciente
- **AND** cada card indica "Pós-procedimento pendente" ou "Pós-procedimento registrado"

#### Scenario: Seleção de data específica

- **GIVEN** casos elegíveis em 3 datas distintas
- **WHEN** o supervisor seleciona `?date=YYYY-MM-DD` válido
- **THEN** somente os elegíveis da data informada são listados

#### Scenario: Caso reagendado aparece na data vigente

- **GIVEN** um caso com agendamento confirmado originalmente para hoje, reagendado via fluxo de intercorrência para a próxima semana
- **WHEN** o supervisor lista hoje e a semana seguinte
- **THEN** o caso não aparece na listagem de hoje
- **AND** aparece na listagem do dia da nova data de `appointment_at`

#### Scenario: Vinda imediata sem timestamp de decisão fica fora

- **GIVEN** um caso com `doctor_admission_flow` operacional e `doctor_decided_at` nulo (inexistente no fluxo atual)
- **WHEN** qualquer listagem de follow-up é calculada
- **THEN** o caso não é incluído (sem fallback para `created_at`)

#### Scenario: Busca por ocorrência ou nome

- **GIVEN** casos elegíveis em qualquer data
- **WHEN** o supervisor busca por trecho do número da ocorrência ou do nome do paciente
- **THEN** os elegíveis correspondentes são listados independentemente da data
- **AND** o resultado é limitado a 50 casos
