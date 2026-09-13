## Purpose

Restringe a cobertura do follow-up às rows `CaseProcedure` autorizadas pela decisão médica; rows negadas ficam isentas de desfecho e a disparidade pedido↔autorizado permanece na camada de decisão (ADR-0007).

## MODIFIED Requirements

### Requirement: O sistema SHALL registrar o desfecho por procedimento autorizado de casos agendados e de vinda imediata

O sistema SHALL permitir que supervisores do CHD (`manager` com papel `scheduler`, papel ativo `manager`) e `admin` registrem, por caso, o desfecho de cada `CaseProcedure` com `doctor_disposition == "approved"` (realizado / não realizado) — e, quando não realizado, a causa estruturada do conjunto fechado: absenteísmo, preparo inadequado, cancelamento por falta de recursos no dia (com submotivo) ou outras causas (texto livre) — além da ocorrência de internação no nível do caso, sem alterar o estado FSM do caso nem disparar fluxos operacionais. Rows `CaseProcedure` não autorizadas (negadas ou pendentes) SHALL ser isentas de desfecho, e desfecho informado para row não autorizada SHALL ser rejeitado.

#### Scenario: Registro inicial de desfecho

- **GIVEN** um caso elegível com procedimentos EDA e Colonoscopia declarados e ambos autorizados
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) submete o formulário de follow-up com desfechos para ambos e internação
- **THEN** uma `CaseFollowUp` versão 1 é criada com uma `ProcedureFollowUp` por procedimento autorizado
- **AND** um `CaseEvent` `FOLLOWUP_RECORDED` é criado com snapshot do desfecho contendo somente as rows autorizadas
- **AND** o `status` do caso permanece inalterado

#### Scenario: Registro com causa de preparo inadequado

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** um supervisor do CHD registra o procedimento com a causa `inadequate_prep`, sem submotivo e sem texto livre
- **THEN** a gravação é aceita com `non_performance_reason="inadequate_prep"` e submotivo/texto vazios
- **AND** o `CaseEvent` espelho carrega a mesma causa no snapshot do desfecho

#### Scenario: Validação de causa estruturada

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** o motivo é `resource_shortage` sem submotivo, `other` sem texto, ou nenhum motivo
- **THEN** a gravação é rejeitada com erro de validação específico
- **AND** nenhuma row de follow-up é criada

#### Scenario: Causa com valor ou combinação inválida

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** o submotivo informado está fora das opções previstas, ou um motivo diferente de `resource_shortage` vem acompanhado de submotivo, ou um motivo diferente de `other` vem acompanhado de texto
- **THEN** a gravação é rejeitada com erro de validação amigável (`ValueError`)
- **AND** nenhuma row é gravada e nenhum `IntegrityError` é exposto

#### Scenario: Row negada é isenta de desfecho após troca

- **GIVEN** um caso elegível com troca médica aplicada (EDA negada, Ecoendoscopia autorizada)
- **WHEN** um supervisor do CHD abre o formulário de follow-up
- **THEN** somente o bloco da Ecoendoscopia é exibido
- **AND** o POST sem qualquer desfecho para a EDA é aceito, criando `ProcedureFollowUp` apenas para a Ecoendoscopia
- **AND** o `CaseEvent` `FOLLOWUP_RECORDED` espelha somente a row autorizada

#### Scenario: Row não autorizada é isenta após aprovação parcial

- **GIVEN** um caso elegível com aprovação parcial (EDA autorizada, Colonoscopia negada)
- **WHEN** um supervisor do CHD registra desfechos cobrindo somente a EDA
- **THEN** a gravação é aceita sem exigir desfecho para a Colonoscopia negada

#### Scenario: Desfecho para row não autorizada é rejeitado

- **GIVEN** um caso elegível com rows negadas e autorizadas
- **WHEN** o POST inclui desfecho para uma row negada
- **THEN** a gravação é rejeitada com erro de validação e nenhuma row/evento é criado

#### Scenario: Caso elegível sem procedimentos autorizados

- **GIVEN** um caso elegível sem rows `CaseProcedure` autorizadas (situação defensiva; inatingível pelo fluxo atual)
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) abre o formulário de follow-up desse caso
- **THEN** a página exibe aviso orientando a correção do caso, sem campos de gravação
- **AND** qualquer tentativa de POST é rejeitada sem criar rows nem eventos
