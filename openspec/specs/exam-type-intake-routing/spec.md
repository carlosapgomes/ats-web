# exam-type-intake-routing Specification

## Purpose
TBD - created by archiving change introduce-colonoscopy-exam-workflow. Update Purpose after archive.

## Requirements

### Requirement: NIR declara um tipo por lote

Todo novo upload MUST escolher exatamente uma seleção válida entre as dez identidades atômicas do catálogo ou EDA + Colonoscopia, aplicada a todos os PDFs do lote. Cada PDF MUST criar um único `Case`; somente EDA + Colonoscopia MUST criar duas rows `CaseProcedure` associadas ao mesmo caso. As novas variações SHALL estar disponíveis no cutover sem flag adicional; as flags preexistentes de Colonoscopia, Ecoendoscopia e CPRE mantêm sua semântica atual.

#### Scenario: Upload sem seleção

- **GIVEN** NIR selecionou PDFs mas não selecionou procedimento
- **WHEN** envia o formulário
- **THEN** nenhum caso é criado
- **AND** a interface informa obrigatoriedade.

#### Scenario: Lote especializado válido

- **GIVEN** a flag correspondente está ativa e NIR escolheu Ecoendoscopia ou CPRE
- **WHEN** envia vários PDFs válidos
- **THEN** cada PDF cria exatamente um caso
- **AND** cada caso possui somente o procedimento especializado declarado.

#### Scenario: Lote com pacote válido

- **GIVEN** NIR escolheu uma das variações atômicas
- **WHEN** envia vários PDFs válidos
- **THEN** cada PDF cria exatamente um caso
- **AND** cada caso possui somente a identidade atômica declarada.

#### Scenario: Lote combinado válido

- **GIVEN** a flag de Colonoscopia está ativa e NIR escolheu EDA + Colonoscopia
- **WHEN** envia vários PDFs válidos
- **THEN** cada PDF cria exatamente um caso com EDA e Colonoscopia declaradas
- **AND** não são criados casos irmãos nem duas agendas.

#### Scenario: POST manipulado

- **GIVEN** o request contém tipo desconhecido ou combinação não suportada
- **WHEN** backend valida
- **THEN** nenhum caso ou procedimento parcial é criado.

### Requirement: Histórico é classificado como EDA sem reprocessamento

A projeção histórica existente MUST ser preservada exatamente como está. Este change MUST NOT inferir novas identidades a partir de subtipo, sinal, texto ou procedimento antigo, MUST NOT reprocessar casos históricos e MUST NOT executar data migration. A migration de `ProcedureType.choices`/comprimento SHALL alterar somente schema state.

> Nota de identidade OpenSpec: o título histórico é preservado; o comportamento agora também proíbe promover GTT, cápsula, dilatação ou Retossigmoidoscopia retrospectivamente.

#### Scenario: Caso histórico EDA ou Colonoscopia

- **GIVEN** caso já projetado como EDA ou Colonoscopia
- **WHEN** a migration deste change executa
- **THEN** suas rows e dimensões permanecem inalteradas
- **AND** nenhum LLM é reexecutado.

#### Scenario: Caso histórico com sinal Ecoendoscopia

- **GIVEN** caso 1.1/2.0 possui subtipo ou sinal legado `echoendoscopy`
- **WHEN** este change é implantado
- **THEN** nenhuma row `echoendoscopy` é criada automaticamente
- **AND** o sinal histórico continua legível.

#### Scenario: EDA histórica com sinal de gastrostomia ou dilatação

- **GIVEN** caso antigo possui row EDA e sinal/subtipo legado de gastrostomia ou dilatação
- **WHEN** o change é implantado
- **THEN** a row continua `eda`
- **AND** nenhuma row de variação é criada.

#### Scenario: Caso histórico preservado

- **GIVEN** caso já possui procedimentos, status, eventos, decisões, agenda, documentos ou JSON clínico
- **WHEN** a migration executa
- **THEN** esses dados permanecem inalterados
- **AND** nenhum LLM é reexecutado.

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

Interfaces MUST formar labels a partir do conjunto da dimensão relevante e SHALL suportar as dez labels canônicas e `EDA + Colonoscopia`. Somente a igualdade exata com `{eda, colonoscopy}` MUST usar label de combinado ou sufixo de agendamento casado; cada pacote SHALL ser exibido como uma identidade única.

#### Scenario: Caso especializado no acompanhamento NIR

- **GIVEN** caso possui Ecoendoscopia ou CPRE declarada
- **WHEN** NIR abre card ou detalhe
- **THEN** vê um único caso com badge próprio do procedimento
- **AND** não vê badge simultâneo de EDA por identidade ou sinal legado.

#### Scenario: Pacote no acompanhamento NIR

- **GIVEN** caso possui `eda_dilation` declarada
- **WHEN** NIR abre card ou detalhe
- **THEN** vê um único badge `EDA + Dilatação`
- **AND** não vê badge simultâneo de EDA.

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

### Requirement: Intake SHALL reconhecer pacotes somente como solicitações atuais sustentadas

O detector SHALL reconhecer nomes canônicos e somente os aliases aprovados `GTT`, `cápsula` e `dilatação` em solicitações atuais, em dois regimes: `GTT`/`gastrostomia` e `cápsula` são marcadores autoevidentes da família EDA e detectam o pacote por ocorrência atual mesmo isolada em trecho próprio; `dilatação` e `argônio`/`plasma de argônio` são ambíguos e exigem vínculo local (mesma expressão) com EDA ou Retossigmoidoscopia solicitada. Histórico, negação, procedimento realizado, mera menção e achado anatômico SHALL NOT criar uma nova identidade. O sistema MUST NOT inventar abreviações operacionais adicionais.

#### Scenario: Dilatação ligada à EDA

- **WHEN** o texto contém solicitação atual de EDA com dilatação
- **THEN** `eda_dilation` é candidata à detecção
- **AND** EDA base não é candidata separada pela mesma expressão.

#### Scenario: Dilatação de colédoco

- **WHEN** o texto relata somente dilatação do colédoco como achado
- **THEN** nenhuma EDA + Dilatação ou Retossigmoidoscopia + Dilatação é detectada.

#### Scenario: Variação apenas histórica ou negada

- **WHEN** GTT, cápsula, dilatação ou argônio aparece somente em contexto histórico, realizado ou negado
- **THEN** a menção não cria procedimento detectado.

#### Scenario: Dilatação sem vínculo procedimental

- **WHEN** a palavra dilatação aparece sem vínculo local inequívoco com EDA ou Retossigmoidoscopia solicitada
- **THEN** nenhuma variação é inferida
- **AND** a ambiguidade não é resolvida por proximidade global no documento.

#### Scenario: GTT solicitada isoladamente

- **WHEN** o texto contém solicitação atual de GTT sem menção a EDA
- **THEN** `eda_gastrostomy` é candidata à detecção
- **AND** nenhuma row EDA base é criada.

#### Scenario: Cápsula solicitada isoladamente

- **WHEN** o texto contém solicitação atual de cápsula endoscópica sem menção a EDA
- **THEN** `eda_capsule` é candidata à detecção
- **AND** nenhuma row EDA base é criada.

#### Scenario: Argônio sem vínculo com Retossigmoidoscopia

- **WHEN** plasma de argônio aparece em solicitação atual sem vínculo local com Retossigmoidoscopia
- **THEN** `rectosigmoidoscopy_argon` não é inferida
- **AND** a ambiguidade não é resolvida por proximidade global no documento.

### Requirement: Retossigmoidoscopia SHALL ser distinta de Colonoscopia

Solicitação atual de Retossigmoidoscopia, isolada ou nas duas variações canônicas, SHALL produzir a identidade correspondente e MUST NOT ser convertida em Colonoscopia apesar de compartilhar seu profile clínico.

#### Scenario: Retossigmoidoscopia simples

- **WHEN** o relatório solicita Retossigmoidoscopia sem variação
- **THEN** somente `rectosigmoidoscopy` é detectada
- **AND** Colonoscopia não é adicionada.

#### Scenario: Colonoscopia apenas histórica

- **GIVEN** o relatório solicita Retossigmoidoscopia e cita Colonoscopia anterior
- **WHEN** a detecção executa
- **THEN** somente Retossigmoidoscopia atual integra o conjunto detectado.
