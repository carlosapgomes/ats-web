# Capability: Correção NIR de conjunto de procedimentos

## MODIFIED Requirements

### Requirement: Divergência pode ser corrigida antes da fila médica

O NIR MUST corrigir a seleção declarada do mesmo caso em revisão por mismatch, combinado incompleto ou unknown, antes de qualquer decisão médica.

#### Scenario: Combinado declarado mas somente EDA detectada

- **GIVEN** caso está em revisão e não possui decisão médica
- **WHEN** NIR corrige declaração para EDA
- **THEN** o mesmo UUID é reprocessado
- **AND** Colonoscopia deixa de estar declarada sem apagar eventos anteriores.

#### Scenario: Caso já na fila médica

- **GIVEN** caso em `WAIT_DOCTOR` ou posterior
- **WHEN** NIR tenta mudar declaração
- **THEN** backend rejeita
- **AND** procedimentos e artefatos permanecem íntegros.

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

Novo caso corrigido MUST aceitar EDA, Colonoscopia ou combinado sem herdar procedimentos do original.

#### Scenario: EDA original reenviada como combinado

- **GIVEN** NIR inicia reenvio corrigido de EDA
- **WHEN** escolhe EDA + Colonoscopia e envia novo PDF
- **THEN** novo caso possui dois procedimentos declarados
- **AND** original permanece inalterado.

## ADDED Requirements

### Requirement: Upgrade automático não requer correção NIR

Single→combined confirmado MUST seguir ao médico e apenas informar o NIR.

#### Scenario: Upgrade visível

- **GIVEN** NIR declarou EDA e análise detectou ambos
- **WHEN** NIR consulta acompanhamento
- **THEN** vê declaração EDA e análise EDA + Colonoscopia
- **AND** não há CTA obrigatório de correção/ACK para o caso prosseguir.

### Requirement: Resposta final compara as três dimensões

Resultado ao NIR MUST listar declarado, detectado, autorizado e razões por procedimento.

#### Scenario: Aprovação parcial

- **GIVEN** combinado detectado foi autorizado somente para EDA
- **WHEN** resposta final é exibida
- **THEN** EDA aparece autorizada
- **AND** Colonoscopia aparece negada com motivo
- **AND** seleção declarada/detectada permanece visível.

#### Scenario: Procedimento incluído pelo médico

- **GIVEN** somente EDA foi detectada e médico incluiu Colonoscopia
- **WHEN** NIR recebe resultado
- **THEN** inclusão de Colonoscopia e sua justificativa são explícitas.
