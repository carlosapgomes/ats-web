# supervisor-appointment-follow-up Spec Delta

## MODIFIED Requirements

### Requirement: O sistema SHALL registrar o desfecho por procedimento de casos agendados e de vinda imediata

O sistema SHALL permitir que supervisores do CHD (`manager` com papel `scheduler`, papel ativo `manager`) e `admin` registrem, por caso, o desfecho de cada `CaseProcedure` com `doctor_disposition == "approved"` (realizado / não realizado) e a ocorrência de internação no nível do caso, sem alterar o estado FSM nem disparar fluxos operacionais. Para procedimento não realizado, a causa SHALL pertencer ao conjunto fechado, na ordem oficial: Ausência do preenchimento do TCLE para realização de exame; Ausência do preenchimento do TCLE anestésico; Condições clínicas desfavoráveis; Erro na programação do procedimento; Falta de médico gastroenterologista; Falta de anestesiologista; Falta de equipamentos; Falta de exames; Falta de hemoderivados; Falta de jejum; Falta de material/OPME; Falta de vaga na UTI; Preparo inadequado; Intubação difícil; Mudança de conduta médica; Não comparecimento do paciente; Paciente foi a óbito; Prioridade para urgência; Tempo excedido; Transferência para outro hospital; Atraso do paciente; Relatório divergente; Recusa do paciente; ou Outras causas. **Outras causas** SHALL exigir descrição textual; nenhuma outra causa SHALL aceitar texto livre ou submotivo. Rows `CaseProcedure` não autorizadas (negadas ou pendentes) SHALL ser isentas de desfecho, e desfecho informado para row não autorizada SHALL ser rejeitado.

#### Scenario: Registro inicial de desfecho

- **GIVEN** um caso elegível com procedimentos EDA e Colonoscopia declarados e ambos autorizados
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) submete o formulário de pós-procedimento com desfechos para ambos e internação
- **THEN** uma `CaseFollowUp` versão 1 é criada com uma `ProcedureFollowUp` por procedimento autorizado
- **AND** um `CaseEvent` `FOLLOWUP_RECORDED` é criado com snapshot do desfecho contendo somente as rows autorizadas
- **AND** o `status` do caso permanece inalterado

#### Scenario: Registro com qualquer causa oficial

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** o supervisor escolhe qualquer uma das 23 causas oficiais diferentes de **Outras causas**
- **THEN** a gravação é aceita com o código estruturado correspondente
- **AND** submotivo e texto livre ficam vazios
- **AND** o `CaseEvent` espelho carrega a mesma causa no snapshot do desfecho

#### Scenario: Registro com causa de preparo inadequado

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** um supervisor registra a causa `inadequate_prep`, sem submotivo e sem texto livre
- **THEN** a gravação é aceita com `non_performance_reason="inadequate_prep"` e submotivo/texto vazios
- **AND** o `CaseEvent` espelho carrega a mesma causa no snapshot do desfecho

#### Scenario: Validação de causa estruturada

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** o supervisor não informa causa ou escolhe **Outras causas** sem descrição não vazia
- **THEN** a gravação é rejeitada com erro específico
- **AND** nenhuma row nem evento de pós-procedimento é criado
- **WHEN** **Outras causas** recebe descrição não vazia
- **THEN** a gravação é aceita e preserva o texto normalizado

#### Scenario: Causa com valor ou combinação inválida

- **GIVEN** um procedimento autorizado marcado como não realizado
- **WHEN** a submissão usa `absenteeism`, `resource_shortage`, causa desconhecida, qualquer submotivo, ou texto livre com causa diferente de `other`
- **THEN** a gravação é rejeitada com erro de validação amigável
- **AND** nenhuma row é gravada e nenhum `IntegrityError` é exposto

#### Scenario: Formulário compacto mantém a ordem oficial

- **GIVEN** um caso elegível com procedimento autorizado
- **WHEN** o supervisor abre o formulário de pós-procedimento
- **THEN** a causa é apresentada em um único seletor compacto com placeholder
- **AND** as 23 causas aparecem na ordem da ficha oficial e **Outras causas** aparece por último
- **AND** os códigos legados não aparecem como opções
- **AND** selecionar **Outras causas** revela o campo de descrição
- **AND** marcar **Realizado** desabilita e limpa a causa

#### Scenario: Row negada é isenta de desfecho após troca

- **GIVEN** um caso elegível com troca médica aplicada (EDA negada, Ecoendoscopia autorizada)
- **WHEN** um supervisor do CHD abre o formulário de pós-procedimento
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
- **WHEN** um supervisor do CHD (`manager` com papel `scheduler`) abre o formulário de pós-procedimento desse caso
- **THEN** a página exibe aviso orientando a correção do caso, sem campos de gravação
- **AND** qualquer tentativa de POST é rejeitada sem criar rows nem eventos
