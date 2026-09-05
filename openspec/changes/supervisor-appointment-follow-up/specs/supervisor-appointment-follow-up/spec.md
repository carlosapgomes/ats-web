# supervisor-appointment-follow-up Spec Delta

## ADDED Requirements

### Requirement: O sistema SHALL registrar o desfecho por procedimento de casos agendados e de vinda imediata

O sistema SHALL permitir que papéis `manager` e `admin` registrem, por caso, o desfecho de cada `CaseProcedure` (realizado / não realizado) e a ocorrência de internação no nível do caso, sem alterar o estado FSM do caso nem disparar fluxos operacionais.

#### Scenario: Registro inicial de desfecho

- **GIVEN** um caso elegível com procedimentos EDA e Colonoscopia declarados
- **WHEN** um `manager` submete o formulário de follow-up com desfechos para ambos e internação
- **THEN** uma `CaseFollowUp` versão 1 é criada com uma `ProcedureFollowUp` por procedimento
- **AND** um `CaseEvent` `FOLLOWUP_RECORDED` é criado com snapshot do desfecho
- **AND** o `status` do caso permanece inalterado

#### Scenario: Validação de causa estruturada

- **GIVEN** um procedimento marcado como não realizado
- **WHEN** o motivo é `resource_shortage` sem submotivo, `other` sem texto, ou nenhum motivo
- **THEN** a gravação é rejeitada com erro de validação específico
- **AND** nenhuma row de follow-up é criada

### Requirement: O follow-up SHALL preservar histórico versionado append-only

Cada atualização de follow-up SHALL criar nova versão (nova row) preservando as anteriores com autor e timestamp, e SHALL registrar `CaseEvent` `FOLLOWUP_UPDATED` com snapshot. A versão corrente SHALL ser a de maior número.

#### Scenario: Atualização preserva versão anterior

- **GIVEN** um caso com follow-up versão 1 gravado por usuário A
- **WHEN** o usuário B atualiza o desfecho
- **THEN** existe versão 2 com `recorded_by` = B e a versão 1 permanece imutável com `recorded_by` = A
- **AND** um `CaseEvent` `FOLLOWUP_UPDATED` é criado com o snapshot da versão 2

### Requirement: A aba Follow-up SHALL listar elegíveis por data com ordenação e busca previsíveis

A aba SHALL listar, para o dia local corrente e o dia anterior (default), os casos com agendamento confirmado (`appointment_at` local na data) e os casos de vinda imediata autorizada (`doctor_admission_flow` operacional com `doctor_decided_at` local na data), ordenados por data e nome do paciente, SHALL permitir selecionar data específica e SHALL permitir busca por número da ocorrência ou nome do paciente sobre a população elegível. Cada item SHALL indicar se há follow-up registrado.

#### Scenario: Default hoje e ontem ordenado

- **GIVEN** casos elegíveis hoje e ontem com pacientes de nomes variados
- **WHEN** o supervisor abre `/dashboard/follow-ups/` sem parâmetros
- **THEN** os casos de hoje e ontem aparecem agrupados por data ascendente
- **AND** dentro de cada data, ordenados por nome do paciente
- **AND** cada card indica "Follow-up pendente" ou "Follow-up registrado"

#### Scenario: Seleção de data específica

- **GIVEN** casos elegíveis em 3 datas distintas
- **WHEN** o supervisor seleciona `?date=YYYY-MM-DD` válido
- **THEN** somente os elegíveis da data informada são listados

#### Scenario: Busca por ocorrência ou nome

- **GIVEN** casos elegíveis em qualquer data
- **WHEN** o supervisor busca por trecho do número da ocorrência ou do nome do paciente
- **THEN** os elegíveis correspondentes são listados independentemente da data
- **AND** o resultado é limitado a 50 casos

### Requirement: A aba e o formulário SHALL ser acessíveis apenas a manager e admin

As rotas de follow-up SHALL exigir autenticação e papel ativo `manager` ou `admin`; demais papéis SHALL ser redirecionados com mensagem de erro, sem alterar o guard de intranet existente.

#### Scenario: Papel sem permissão

- **GIVEN** um usuário autenticado com papel ativo `scheduler`
- **WHEN** ele acessa `/dashboard/follow-ups/`
- **THEN** é redirecionado com mensagem de erro e nenhum dado de follow-up é exposto
