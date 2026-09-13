# exam-type-correction Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.

## Requirements

### Requirement: Divergência pode ser corrigida antes da fila médica

O NIR MUST corrigir a seleção declarada do mesmo caso para EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia ou CPRE quando o caso estiver em revisão por mismatch, combinado incompleto, conjunto incompatível ou unknown, antes de qualquer decisão médica e respeitando a flag de intake correspondente.

#### Scenario: EDA declarada mas Ecoendoscopia detectada

- **GIVEN** caso está em revisão, sem decisão médica, e a flag de Ecoendoscopia está ativa
- **WHEN** NIR corrige a declaração para Ecoendoscopia
- **THEN** o mesmo UUID é reprocessado sob o contrato gravável vigente
- **AND** declaração e detecção anteriores permanecem auditáveis.

#### Scenario: Caso já na fila médica

- **GIVEN** caso em `WAIT_DOCTOR` ou posterior
- **WHEN** NIR tenta mudar declaração
- **THEN** backend rejeita
- **AND** procedimentos e artefatos permanecem íntegros.

#### Scenario: Combinado declarado mas somente EDA detectada

- **GIVEN** caso está em revisão e não possui decisão médica
- **WHEN** NIR corrige declaração para EDA
- **THEN** o mesmo UUID é reprocessado
- **AND** Colonoscopia deixa de estar declarada sem apagar eventos anteriores.

### Requirement: Reprocessamento preserva fontes e invalida derivados

Correção MUST preservar documentos e texto, limpar detecção/recomendações derivadas e enfileirar uma única nova análise sem reextrair PDF.

#### Scenario: Correção válida

- **GIVEN** caso manual com artefatos v2 e procedimentos detectados
- **WHEN** declaração é corrigida
- **THEN** PDF, anexos, texto, ocorrência e eventos são preservados
- **AND** estados de detecção, `structured_data`, resumo, recomendações e sinais derivados são invalidados
- **AND** uma única execução LLM é agendada.

### Requirement: Correção é append-only e concorrência é segura

O sistema MUST serializar correção e registrar conjunto anterior/novo sem texto clínico integral.

#### Scenario: Worker ou lease incompatível

- **GIVEN** worker/reserva incompatível
- **WHEN** NIR tenta corrigir
- **THEN** operação falha sem atualização parcial
- **AND** nenhuma segunda análise é enfileirada.

### Requirement: Reenvio corrigido pode escolher tipo diferente

Novo caso corrigido MUST aceitar EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia ou CPRE sem herdar procedimentos do original e respeitando as flags de novos intakes.

#### Scenario: EDA original reenviada como CPRE

- **GIVEN** NIR inicia reenvio corrigido de EDA e a flag de CPRE está ativa
- **WHEN** escolhe CPRE e envia novo PDF
- **THEN** novo caso possui somente CPRE declarada
- **AND** original permanece inalterado.

#### Scenario: EDA original reenviada como combinado

- **GIVEN** NIR inicia reenvio corrigido de EDA
- **WHEN** escolhe EDA + Colonoscopia e envia novo PDF
- **THEN** novo caso possui dois procedimentos declarados
- **AND** original permanece inalterado.

### Requirement: Upgrade automático não requer correção NIR

Single→combined confirmado MUST seguir ao médico e apenas informar o NIR.

#### Scenario: Upgrade visível

- **GIVEN** NIR declarou EDA e análise detectou ambos
- **WHEN** NIR consulta acompanhamento
- **THEN** vê declaração EDA e análise EDA + Colonoscopia
- **AND** não há CTA obrigatório de correção/ACK para o caso prosseguir.

### Requirement: Resposta final compara as três dimensões

Resultado ao NIR MUST listar declarado, detectado, autorizado e razões por procedimento para todos os quatro tipos suportados.

#### Scenario: Procedimento especializado incluído pelo médico

- **GIVEN** EDA foi detectada e o médico a substituiu por CPRE
- **WHEN** NIR recebe o resultado
- **THEN** a resposta mostra EDA como detectada e negada
- **AND** CPRE como incluída e autorizada
- **AND** a justificativa médica é explícita.

#### Scenario: Negativa de Ecoendoscopia

- **GIVEN** Ecoendoscopia foi declarada/detectada e negada pelo médico
- **WHEN** a resposta final é exibida
- **THEN** declaração, detecção, negativa e motivo próprio permanecem visíveis.

#### Scenario: Aprovação parcial

- **GIVEN** EDA + Colonoscopia detectada foi autorizada somente para EDA
- **WHEN** resposta final é exibida
- **THEN** EDA aparece autorizada
- **AND** Colonoscopia aparece negada com motivo
- **AND** seleção declarada/detectada permanece visível.

#### Scenario: Procedimento incluído pelo médico

- **GIVEN** somente EDA foi detectada e médico incluiu Colonoscopia
- **WHEN** NIR recebe resultado
- **THEN** inclusão de Colonoscopia e sua justificativa são explícitas.

### Requirement: Correção especializada SHALL reprocessar com contrato atual sem reextrair anexos

A correção para Ecoendoscopia ou CPRE SHALL preservar PDF principal, anexos e texto extraído, invalidar derivados e executar uma única análise com o contrato gravável atual. Anexos SHALL permanecer fora da sugestão automática no primeiro rollout.

#### Scenario: Caso 2.0 aberto corrigido para CPRE

- **GIVEN** caso histórico aberto possui artefato 2.0 e está elegível à correção
- **WHEN** NIR corrige a declaração para CPRE
- **THEN** o mesmo caso é reprocessado em 3.0 usando o texto do relatório principal
- **AND** nenhum anexo é enviado à análise automática
- **AND** nenhum JSON histórico é reescrito.
