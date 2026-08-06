# exam-type-correction Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.
## Requirements
### Requirement: Divergência pode ser corrigida antes da fila médica

O NIR MUST poder corrigir o tipo no mesmo caso quando houver revisão manual de escopo ou estado estável anterior a `WAIT_DOCTOR`.

#### Scenario: Mismatch manual

- **GIVEN** caso declarado EDA foi detectado como colonoscopia e está em revisão manual
- **WHEN** NIR confirma Colonoscopia
- **THEN** o mesmo UUID recebe o novo tipo
- **AND** o pipeline LLM é reexecutado com o perfil colonoscopia
- **AND** nenhum novo upload é exigido.

#### Scenario: Caso já na fila médica

- **GIVEN** caso em `WAIT_DOCTOR`
- **WHEN** NIR tenta alterar o tipo
- **THEN** backend rejeita a operação
- **AND** tipo e artefatos permanecem inalterados.

### Requirement: Reprocessamento preserva fontes e invalida derivados

A correção MUST preservar documentos/fontes do mesmo caso e MUST invalidar os artefatos derivados pelo perfil anterior.

#### Scenario: Correção válida

- **GIVEN** caso manual com PDF, anexos, texto extraído e artefatos LLM anteriores
- **WHEN** tipo é corrigido
- **THEN** PDF, anexos, texto extraído, ocorrência e eventos são preservados
- **AND** `structured_data`, `summary_text`, `suggested_action` e sinais derivados são invalidados
- **AND** PDF não é extraído novamente
- **AND** LLM1 é enfileirado novamente.

### Requirement: Correção é append-only e concorrência é segura

O sistema MUST auditar a alteração e MUST impedir atualização parcial ou pipeline duplicado sob concorrência.

#### Scenario: Eventos de correção

- **GIVEN** correção válida
- **WHEN** serviço conclui
- **THEN** timeline contém tipo anterior/novo e solicitação de reprocessamento
- **AND** payload não contém PDF ou texto clínico integral.

#### Scenario: Worker ou reserva incompatível

- **GIVEN** caso está sob processamento/reserva incompatível
- **WHEN** NIR tenta corrigir
- **THEN** operação falha sem atualização parcial
- **AND** nenhum segundo pipeline concorrente é enfileirado.

### Requirement: Reenvio corrigido pode escolher tipo diferente

Um novo caso criado pelo fluxo de reenvio corrigido MUST aceitar tipo diferente do original sem alterar o caso anterior.

#### Scenario: Novo caso muda o tipo

- **GIVEN** NIR inicia reenvio corrigido de uma EDA
- **WHEN** seleciona Colonoscopia e envia novo PDF
- **THEN** novo caso é Colonoscopia
- **AND** original permanece EDA
- **AND** demais regras de não herança continuam válidas.

