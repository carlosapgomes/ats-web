# Delta: supervisor-appointment-follow-up

## MODIFIED Requirements

### Requirement: O sistema SHALL registrar o desfecho por procedimento de casos agendados e de vinda imediata

O sistema SHALL permitir que supervisores do CHD (`manager` com papel `scheduler`, papel ativo `manager`) e `admin` registrem, por caso, o desfecho de cada `CaseProcedure` (realizado / não realizado) — e, quando não realizado, a causa estruturada do conjunto fechado: absenteísmo, preparo inadequado, cancelamento por falta de recursos no dia (com submotivo) ou outras causas (texto livre) — além da ocorrência de internação no nível do caso, sem alterar o estado FSM do caso nem disparar fluxos operacionais.

#### Scenario: Registro inicial de desfecho

- **GIVEN** um caso elegível com procedimentos EDA e Colonoscopia declarados
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) submete o formulário de follow-up com desfechos para ambos e internação
- **THEN** uma `CaseFollowUp` versão 1 é criada com uma `ProcedureFollowUp` por procedimento
- **AND** um `CaseEvent` `FOLLOWUP_RECORDED` é criado com snapshot do desfecho
- **AND** o `status` do caso permanece inalterado

#### Scenario: Registro com causa de preparo inadequado

- **GIVEN** um caso elegível com um procedimento declarado
- **WHEN** um supervisor do CHD registra o procedimento como não realizado com a causa `inadequate_prep`, sem submotivo e sem texto livre
- **THEN** a gravação é aceita com `non_performance_reason="inadequate_prep"` e submotivo/texto vazios
- **AND** o `CaseEvent` espelho carrega a mesma causa no snapshot do desfecho

#### Scenario: Validação de causa estruturada

- **GIVEN** um procedimento marcado como não realizado
- **WHEN** o motivo é `resource_shortage` sem submotivo, `other` sem texto, ou nenhum motivo
- **THEN** a gravação é rejeitada com erro de validação específico
- **AND** nenhuma row de follow-up é criada

#### Scenario: Causa com valor ou combinação inválida

- **GIVEN** um procedimento marcado como não realizado
- **WHEN** o submotivo informado está fora das opções previstas, ou um motivo diferente de `resource_shortage` vem acompanhado de submotivo, ou um motivo diferente de `other` vem acompanhado de texto
- **THEN** a gravação é rejeitada com erro de validação amigável (`ValueError`)
- **AND** nenhuma row é gravada e nenhum `IntegrityError` é exposto
