# Capability: Tipo explícito e roteamento multi-exame

## ADDED Requirements

### Requirement: NIR declara um tipo por lote

Todo novo upload MUST ter exatamente um tipo válido aplicado a todos os PDFs do lote.

#### Scenario: Upload sem seleção

- **GIVEN** NIR selecionou PDFs mas não selecionou tipo
- **WHEN** envia o formulário
- **THEN** nenhum caso é criado
- **AND** a interface informa que o tipo é obrigatório.

#### Scenario: Lote colonoscopia válido

- **GIVEN** flag de intake ativa e NIR selecionou Colonoscopia
- **WHEN** envia vários PDFs válidos
- **THEN** cada `Case` criado possui `exam_type=colonoscopy`
- **AND** todos entram no pipeline normal.

#### Scenario: POST manipulado com tipo inválido

- **GIVEN** request contém tipo não suportado
- **WHEN** backend valida o upload
- **THEN** nenhum caso é criado para esse request.

### Requirement: Histórico é classificado como EDA sem reprocessamento

A migration MUST classificar todo caso preexistente como EDA e MUST NOT inferir tipo a partir de artefatos clínicos.

#### Scenario: Caso histórico de qualquer status

- **GIVEN** caso existente antes da migration
- **WHEN** migration é aplicada
- **THEN** `exam_type=eda`
- **AND** status, eventos, decisões, agenda, PDF e JSON permanecem inalterados.

### Requirement: Flag global bloqueia somente intake

`COLONOSCOPY_INTAKE_ENABLED` MUST impedir novos uploads quando desligada e MUST NOT interromper colonoscopias já criadas.

#### Scenario: Flag desligada no upload

- **GIVEN** flag falsa
- **WHEN** NIR tenta POST manual com `colonoscopy`
- **THEN** backend rejeita o upload
- **AND** EDA continua disponível.

#### Scenario: Caso existente com flag desligada

- **GIVEN** colonoscopia criada antes de desligar a flag
- **WHEN** worker, médico ou CHD processa o caso
- **THEN** o fluxo continua normalmente.

### Requirement: Colonoscopia é escopo suportado quando declarada e confirmada

O sistema MUST reconhecer aliases aprovados em contexto de solicitação atual.

#### Scenario: Alias por nome completo

- **GIVEN** tipo declarado Colonoscopia e solicitação atual contém `colonoscopia`, `endoscopia digestiva baixa` ou `videocolonoendoscopia`
- **WHEN** scope gate executa
- **THEN** o caso prossegue para policy/LLM2.

#### Scenario: EDB contextual

- **GIVEN** solicitação atual contém `Procedimento: EDB` ou construção equivalente
- **WHEN** detector classifica o documento
- **THEN** reconhece colonoscopia.

#### Scenario: EDB isolado sem contexto

- **GIVEN** texto contém apenas acrônimo `EDB` sem contexto local de exame/solicitação/procedimento
- **WHEN** detector classifica
- **THEN** o acrônimo isolado não confirma colonoscopia.

### Requirement: Referência histórica não causa divergência

O detector MUST distinguir solicitação atual de exame histórico.

#### Scenario: EDA histórica e colonoscopia atual

- **GIVEN** texto `EDA realizada em 2024. Solicito colonoscopia.` e tipo declarado Colonoscopia
- **WHEN** scope gate executa
- **THEN** o caso é aceito como colonoscopia
- **AND** não recebe `mixed_exam_request`.

### Requirement: Solicitações atuais mistas são bloqueadas

Um PDF com EDA e colonoscopia solicitadas atualmente MUST NOT entrar na fila médica.

#### Scenario: EDA e colonoscopia atuais

- **GIVEN** texto solicita atualmente EDA e colonoscopia
- **WHEN** qualquer um dos tipos é declarado
- **THEN** resultado é revisão manual com `mixed_exam_request`
- **AND** NIR é orientado a enviar PDFs/casos separados.

## MODIFIED Requirements

### Requirement: EDA suportada em documento com outro exame

EDA suportada MUST prevalecer apenas quando a menção ao outro exame for histórica, negada ou não constituir segunda solicitação atual. Duas solicitações atuais distintas MUST ser bloqueadas.

#### Scenario: Ecoendoscopia atual e colonoscopia histórica

- **GIVEN** solicitação atual de ecoendoscopia e histórico de colonoscopia realizada
- **WHEN** scope gate executa
- **THEN** segue o fluxo EDA.

#### Scenario: EDA e colonoscopia ambas atuais

- **GIVEN** ambas são solicitações atuais
- **WHEN** scope gate executa
- **THEN** não aplica precedência EDA
- **AND** retorna revisão manual para separação dos documentos.
