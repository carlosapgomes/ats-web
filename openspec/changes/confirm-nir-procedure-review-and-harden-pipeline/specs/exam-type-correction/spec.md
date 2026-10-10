# exam-type-correction Delta

## MODIFIED Requirements

### Requirement: Divergência pode ser corrigida antes da fila médica

O NIR MUST poder confirmar a seleção vigente ou alterá-la para qualquer singleton canônico ou EDA + Colonoscopia habilitado quando o caso estiver em revisão por mismatch, combinado incompleto, conjunto incompatível, conflito de item estruturado ou unknown, antes de decisão médica. Confirmação explícita de leitura e justificativa MUST conferir autoridade à seleção para a fonte revisada, mesmo sem cobertura automática, conforme nir-procedure-review. Sem confirmação explícita, declaração/igualdade não ganham autoridade adicional.

#### Scenario: EDA declarada mas Ecoendoscopia detectada
- **GIVEN** caso em revisão, sem decisão médica, com Ecoendoscopia habilitada
- **WHEN** NIR confirma Ecoendoscopia com leitura e justificativa
- **THEN** o mesmo UUID é reprocessado em 4.0 com esse conjunto efetivo
- **AND** declaração e detecção anteriores permanecem auditáveis.

#### Scenario: EDA declarada mas EDA + GTT detectada
- **GIVEN** caso em revisão e sem decisão médica
- **WHEN** NIR confirma EDA + GTT
- **THEN** o mesmo UUID é reprocessado em 4.0
- **AND** declaração e detecção anteriores permanecem auditáveis.

#### Scenario: Correção de conflito para a seleção mais completa com evidência atual prossegue
- **GIVEN** revisão por conflicting_procedure_evidence com evidência atual e cobertura máxima EDA + Dilatação
- **WHEN** NIR confirma essa seleção com leitura e justificativa
- **THEN** análise usa o conjunto confirmado e não reabre o mesmo conflito
- **AND** união bruta permanece auditável.

#### Scenario: Correção para outra seleção reentra na revisão
- **GIVEN** correção histórica sem confirmação explícita e seleção diferente da cobertura máxima
- **WHEN** reprocessamento automático executa com o evento legado
- **THEN** regra automática continua retornando à revisão com seu motivo
- **AND** evento legado não é convertido em confirmação autoritativa.

#### Scenario: Confirmação para outra seleção resolve a revisão
- **GIVEN** revisão por conflicting_procedure_evidence com cobertura automática EDA + Dilatação
- **WHEN** NIR confirma uma seleção válida diferente após leitura e justifica
- **THEN** conjunto confirmado define a análise da fonte revisada
- **AND** divergência bruta não é apagada nem apresentada como concordância do detector.

#### Scenario: Coincidência negada ou histórica sem evidência atual não é resolvida por igualdade
- **GIVEN** texto nega/historiza item e declaração coincide sem confirmação humana explícita
- **WHEN** ocorre processamento automático
- **THEN** igualdade não resolve o conflito sozinha
- **AND** revisão permanece pelas regras automáticas atuais.

#### Scenario: Confirmação humana explícita apesar de conflito histórico
- **GIVEN** caso em revisão, ainda sem decisão médica
- **WHEN** NIR lê a fonte e confirma seleção válida com justificativa
- **THEN** escolha humana define o conjunto analisado
- **AND** médico vê a divergência, inclusive histórica/negada, sem dispensa de policy.

#### Scenario: Mesmo procedimento confirmado
- **GIVEN** seleção CPRE e revisão por conjunto incompatível
- **WHEN** NIR confirma novamente CPRE com leitura e justificativa
- **THEN** ação não é rejeitada por igualdade
- **AND** não exige relatório reescrito.

#### Scenario: Caso já na fila médica
- **GIVEN** caso em WAIT_DOCTOR ou posterior
- **WHEN** NIR tenta confirmar ou mudar seleção
- **THEN** backend rejeita
- **AND** procedimentos e artefatos permanecem íntegros.

#### Scenario: Combinado declarado mas somente EDA detectada
- **GIVEN** revisão de caso sem decisão médica inicialmente declarado EDA + Colonoscopia
- **WHEN** NIR confirma EDA
- **THEN** o mesmo UUID é reprocessado
- **AND** Colonoscopia deixa de estar declarada sem apagar eventos anteriores.

#### Scenario: Correção para conjunto proibido
- **GIVEN** request tenta confirmar variação junto de Colonoscopia
- **WHEN** backend valida
- **THEN** rejeita antes de alterar rows
- **AND** nenhuma análise é enfileirada.

### Requirement: Reprocessamento preserva fontes e invalida derivados

Confirmação MUST preservar documentos, texto, ocorrência e eventos, invalidar derivados anteriores e enfileirar uma única análise sem reextrair PDF/anexos. A confirmação humana MUST permanecer durável durante a invalidação para definir o conjunto efetivo no reprocessamento.

#### Scenario: Correção válida
- **GIVEN** caso manual com artefatos v2 e procedimentos detectados
- **WHEN** NIR confirma seleção válida
- **THEN** PDF, anexos, texto, ocorrência e eventos são preservados
- **AND** detecção operacional, structured_data, resumo, recomendações e sinais anteriores são invalidados
- **AND** evento de confirmação permanece e uma execução LLM é agendada.

### Requirement: Correção é append-only e concorrência é segura

O sistema MUST serializar confirmação de procedimento com confirmação de recebimento, registrar conjuntos anterior/confirmado e autoria, revalidar revisão/fonte e impedir efeitos parciais ou duplicados. Justificativa breve MUST NOT copiar relatório integral.

#### Scenario: Worker ou lease incompatível
- **GIVEN** worker/reserva incompatível
- **WHEN** NIR tenta confirmar
- **THEN** operação falha sem atualização parcial
- **AND** nenhuma segunda análise é enfileirada.

#### Scenario: Confirmação registra autoria e procedimento
- **WHEN** confirmação é commitada
- **THEN** CaseEvent humano registra autor e códigos canônicos anterior/confirmado
- **AND** Linha do Tempo renderiza quem confirmou qual procedimento, mesmo na seleção mantida.

### Requirement: Correção especializada SHALL reprocessar com contrato atual sem reextrair anexos

A confirmação para qualquer identidade canônica SHALL preservar PDF principal, anexos e texto, invalidar derivados e executar uma análise 4.0 sob o conjunto confirmado. Anexos SHALL permanecer fora da sugestão automática e eventos históricos SHALL NOT ganhar autoridade retroativa.

#### Scenario: Caso 2.0 aberto corrigido para CPRE
- **GIVEN** caso histórico 2.0 em revisão elegível
- **WHEN** NIR confirma CPRE explicitamente
- **THEN** o mesmo caso é reprocessado em 4.0 usando texto principal
- **AND** anexos não são enviados à automação e eventos anteriores não são reescritos.

#### Scenario: Caso 3.0 aberto corrigido para EDA + Dilatação
- **GIVEN** caso histórico 3.0 em revisão elegível
- **WHEN** NIR confirma EDA + Dilatação
- **THEN** o mesmo caso é reprocessado em 4.0 com a confirmação como autoridade do conjunto
- **AND** histórico permanece intacto.

### Requirement: Card de correção exibe pistas detectadas no corpo do relatório

O card MUST apresentar declarado, identificado automaticamente e motivo da revisão, com seletor canônico que permita manter a seleção vigente, justificativa, leitura explícita e CTA de confirmação. Pistas cruas MUST permanecer na auditoria, sem obrigar sua listagem na UI. A origem da identificação MUST ficar clara no motivo. CSS/vocabulário existente e fallback SSR MUST ser preservados.

#### Scenario: Pistas visíveis no momento da seleção
- **GIVEN** revisão elegível com detected_body_clues no payload e reserva NIR
- **WHEN** detalhe renderiza
- **THEN** card oferece confirmação da seleção atual ou outra válida
- **AND** mostra motivo, leitura e justificativa sem lista crua obrigatória de pistas.

#### Scenario: Caso legado sem pistas
- **GIVEN** revisão elegível sem detected_body_clues
- **WHEN** detalhe renderiza
- **THEN** mesmo card de confirmação está disponível
- **AND** nenhuma evidência/autoria fictícia é fabricada.

#### Scenario: Correção elegível por conflito de item estruturado
- **GIVEN** manual review com conflicting_procedure_evidence
- **WHEN** NIR abre detalhe com reserva válida
- **THEN** card permite confirmar o pedido sem exigir alteração do documento
- **AND** códigos POST continuam canônicos.
