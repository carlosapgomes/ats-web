## MODIFIED Requirements

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

## ADDED Requirements

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
