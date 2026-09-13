# exam-type-intake-routing Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.

## Requirements

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

Um documento com solicitações atuais de EDA e Colonoscopia MUST ser tratado como combinado quando reconciliado pelas regras de detecção.

> Nota de identidade OpenSpec: o título corresponde ao requisito canônico anterior. O comportamento modificado aceita a combinação atual quando a reconciliação comprova ambos os procedimentos.

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
