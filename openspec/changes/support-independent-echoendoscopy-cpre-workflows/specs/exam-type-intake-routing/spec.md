## MODIFIED Requirements

### Requirement: NIR declara um tipo por lote

Todo novo upload MUST escolher exatamente uma seleção válida — EDA, Colonoscopia, EDA + Colonoscopia, Ecoendoscopia ou CPRE — aplicada a todos os PDFs do lote. Cada PDF MUST criar um único `Case`; somente EDA + Colonoscopia MUST criar dois procedimentos associados ao mesmo caso.

#### Scenario: Upload sem seleção

- **GIVEN** NIR selecionou PDFs mas não selecionou procedimento
- **WHEN** envia o formulário
- **THEN** nenhum caso é criado
- **AND** interface informa obrigatoriedade.

#### Scenario: Lote especializado válido

- **GIVEN** a flag correspondente está ativa e NIR escolheu Ecoendoscopia ou CPRE
- **WHEN** envia vários PDFs válidos
- **THEN** cada PDF cria exatamente um caso
- **AND** cada caso possui somente o procedimento especializado declarado.

#### Scenario: Lote combinado válido

- **GIVEN** flag de Colonoscopia ativa e NIR escolheu EDA + Colonoscopia
- **WHEN** envia vários PDFs válidos
- **THEN** cada PDF cria exatamente um caso
- **AND** cada caso possui EDA e Colonoscopia declaradas
- **AND** não são criados casos irmãos nem duas agendas.

#### Scenario: POST manipulado

- **GIVEN** request contém tipo ou combinação não suportada
- **WHEN** backend valida
- **THEN** nenhum caso ou procedimento parcial é criado.

### Requirement: Histórico é classificado como EDA sem reprocessamento

A projeção histórica criada pelo change anterior MUST ser preservada exatamente como está. Este change MUST NOT executar nova data migration, inferir Ecoendoscopia a partir do subtipo/sinal legado, criar CPRE retrospectiva nem reprocessar casos históricos. A única migration de `ProcedureType.choices` será alteração de schema state, sem backfill.

> Nota de identidade OpenSpec: o título histórico é preservado. EDA/Colonoscopia já foram projetadas por migration anterior; este change apenas mantém essas rows e proíbe nova classificação retrospectiva.

#### Scenario: Caso histórico EDA ou Colonoscopia

- **GIVEN** caso já projetado pelo change anterior
- **WHEN** migration deste change executa
- **THEN** suas rows, status, eventos, decisões, agenda, documentos e JSON permanecem inalterados
- **AND** nenhum LLM é reexecutado.

#### Scenario: Caso histórico com sinal Ecoendoscopia

- **GIVEN** caso 1.1/2.0 possui subtipo ou sinal legado `echoendoscopy`
- **WHEN** este change é implantado
- **THEN** nenhuma row `echoendoscopy` é criada automaticamente
- **AND** o sinal histórico continua apenas legível.

### Requirement: Flag global bloqueia somente intake

`COLONOSCOPY_INTAKE_ENABLED`, `ECHOENDOSCOPY_INTAKE_ENABLED` e `CPRE_INTAKE_ENABLED` MUST bloquear apenas novos uploads, correções e reenvios que dependam do respectivo procedimento, sem interromper casos existentes nem impedir substituição médica. Cada flag MUST operar independentemente.

#### Scenario: Ecoendoscopia ativa e CPRE desativada

- **GIVEN** flag de Ecoendoscopia verdadeira e flag de CPRE falsa
- **WHEN** NIR abre o upload
- **THEN** Ecoendoscopia está disponível e CPRE não
- **AND** POST manipulado de CPRE é rejeitado.

#### Scenario: Caso especializado existente após desligamento

- **GIVEN** caso de Ecoendoscopia ou CPRE já criado
- **WHEN** a flag correspondente é desligada
- **THEN** pipeline, médico, CHD e NIR continuam o fluxo.

#### Scenario: Divergência detectada com flag desligada

- **GIVEN** uma flag especializada está desligada e outro tipo foi declarado
- **WHEN** a análise detecta o procedimento especializado
- **THEN** o caso permanece fail-closed em revisão NIR
- **AND** não é convertido silenciosamente para EDA.

#### Scenario: Flag desligada

- **GIVEN** flag de Colonoscopia falsa
- **WHEN** NIR tenta Colonoscopia ou EDA + Colonoscopia
- **THEN** backend rejeita o upload
- **AND** EDA isolada continua disponível.

#### Scenario: Combinado existente após desligamento

- **GIVEN** caso EDA + Colonoscopia já criado
- **WHEN** flag de Colonoscopia é desligada
- **THEN** pipeline, médico, CHD e NIR continuam o fluxo.

### Requirement: Seleção exibida é derivada dos procedimentos

Interfaces MUST formar labels a partir do conjunto da dimensão relevante e MUST exibir `EDA`, `Colonoscopia`, `EDA + Colonoscopia`, `Ecoendoscopia` ou `CPRE`. Somente a igualdade exata com EDA + Colonoscopia MUST usar label de combinado.

#### Scenario: Caso especializado no acompanhamento NIR

- **GIVEN** caso possui Ecoendoscopia ou CPRE declarada
- **WHEN** NIR abre card ou detalhe
- **THEN** vê um único caso com badge próprio do procedimento
- **AND** não vê badge simultâneo de EDA por identidade ou sinal legado.

#### Scenario: Caso combinado no acompanhamento NIR

- **GIVEN** caso possui EDA e Colonoscopia declaradas
- **WHEN** NIR abre card ou detalhe
- **THEN** vê um único caso com badge `EDA + Colonoscopia`
- **AND** não vê dois cards do mesmo PDF.

## ADDED Requirements

### Requirement: Intake SHALL reconhecer solicitações especializadas atuais

O detector SHALL reconhecer aliases aprovados somente em contexto de solicitação atual e SHALL distinguir histórico, negação, mera menção e procedimento realizado.

#### Scenario: Alias de Ecoendoscopia

- **WHEN** solicitação atual contém `ecoendoscopia`, `eco-endoscopia`, `ultrassonografia endoscópica`, `ultrassom endoscópico` ou `EUS` com contexto procedimental
- **THEN** Ecoendoscopia é candidata à detecção.

#### Scenario: Alias de CPRE

- **WHEN** solicitação atual contém `CPRE` ou `colangiopancreatografia retrógrada endoscópica` com contexto procedimental
- **THEN** CPRE é candidata à detecção.

#### Scenario: Menção histórica especializada

- **WHEN** Ecoendoscopia ou CPRE aparece somente como exame passado, negado ou sem solicitação atual
- **THEN** a menção não cria procedimento detectado.
