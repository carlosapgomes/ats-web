# Capability: Intake e roteamento por conjunto de procedimentos

## MODIFIED Requirements

### Requirement: NIR declara um tipo por lote

Todo novo upload MUST escolher exatamente uma seleção válida — EDA, Colonoscopia ou EDA + Colonoscopia — aplicada a todos os PDFs do lote. Cada PDF MUST criar um único `Case`; combinado MUST criar dois procedimentos associados ao mesmo caso.

#### Scenario: Upload sem seleção

- **GIVEN** NIR selecionou PDFs mas não selecionou procedimento
- **WHEN** envia o formulário
- **THEN** nenhum caso é criado
- **AND** interface informa obrigatoriedade.

#### Scenario: Lote combinado válido

- **GIVEN** flag ativa e NIR escolheu EDA + Colonoscopia
- **WHEN** envia vários PDFs válidos
- **THEN** cada PDF cria exatamente um caso
- **AND** cada caso possui EDA e Colonoscopia declaradas
- **AND** não são criados casos irmãos nem duas agendas.

#### Scenario: POST manipulado

- **GIVEN** request contém seleção/tipo não suportado
- **WHEN** backend valida
- **THEN** nenhum caso ou procedimento parcial é criado.

### Requirement: Histórico é classificado como EDA sem reprocessamento

Migration MUST criar uma projeção de procedimento declarado a partir do `exam_type` atual e MUST preservar todos os demais dados.

#### Scenario: Caso histórico EDA ou Colonoscopia

- **GIVEN** caso anterior ao change
- **WHEN** migration executa
- **THEN** possui exatamente um procedimento declarado correspondente ao valor anterior
- **AND** status, eventos, decisões, agenda, documentos e JSON permanecem inalterados
- **AND** nenhum LLM é reexecutado.

### Requirement: Flag global bloqueia somente intake

`COLONOSCOPY_INTAKE_ENABLED` MUST bloquear novos uploads de Colonoscopia isolada e EDA + Colonoscopia, sem interromper casos existentes.

#### Scenario: Flag desligada

- **GIVEN** flag falsa
- **WHEN** NIR tenta Colonoscopia ou combinado
- **THEN** backend rejeita o upload
- **AND** EDA isolada continua disponível.

#### Scenario: Combinado existente após desligamento

- **GIVEN** caso combinado já criado
- **WHEN** flag é desligada
- **THEN** pipeline, médico, CHD e NIR continuam o fluxo.

### Requirement: Solicitações atuais mistas são bloqueadas

Um documento com solicitações atuais de EDA e Colonoscopia MUST ser tratado como combinado quando reconciliado pelas regras de detecção.

#### Scenario: Combinado declarado e confirmado

- **GIVEN** NIR declarou EDA + Colonoscopia
- **AND** ambas são solicitações atuais detectadas
- **WHEN** pipeline executa
- **THEN** caso segue à avaliação médica como combinado.

#### Scenario: Único declarado e combinado detectado

- **GIVEN** NIR declarou somente um procedimento
- **AND** ambos são detectados com evidência forte
- **WHEN** reconciliação executa
- **THEN** análise recebe upgrade automático para combinado
- **AND** declaração original permanece auditável.

### Requirement: EDA suportada em documento com outro exame

EDA atual MUST permanecer única quando a menção a Colonoscopia for histórica, negada ou não constituir solicitação atual.

#### Scenario: EDA atual e Colonoscopia histórica

- **GIVEN** documento solicita EDA e relata Colonoscopia anterior
- **WHEN** detector executa
- **THEN** somente EDA fica detectada
- **AND** não ocorre upgrade automático.

## ADDED Requirements

### Requirement: Seleção exibida é derivada dos procedimentos

Interfaces MUST formar labels a partir do conjunto da dimensão relevante e MUST exibir `EDA + Colonoscopia` quando ambos estiverem presentes.

#### Scenario: Caso combinado no acompanhamento NIR

- **GIVEN** caso possui dois procedimentos declarados
- **WHEN** NIR abre card ou detalhe
- **THEN** vê um único caso com badge `EDA + Colonoscopia`
- **AND** não vê dois cards do mesmo PDF.
