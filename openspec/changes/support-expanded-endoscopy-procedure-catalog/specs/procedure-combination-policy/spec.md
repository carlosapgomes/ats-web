## RENAMED Requirements

- FROM: `### Requirement: Catálogo e ordem canônica SHALL conter quatro procedimentos`
- TO: `### Requirement: Catálogo e ordem canônica SHALL conter dez procedimentos`

## MODIFIED Requirements

### Requirement: Catálogo e ordem canônica SHALL conter dez procedimentos

O sistema SHALL reconhecer `eda`, `eda_gastrostomy`, `eda_capsule`, `eda_dilation`, `colonoscopy`, `rectosigmoidoscopy`, `rectosigmoidoscopy_dilation`, `rectosigmoidoscopy_argon`, `echoendoscopy` e `cpre` como identidades atômicas e SHALL usar uma única ordem, label e família canônicas em persistência, eventos, seletores, filtros e analytics.

#### Scenario: Pacote de EDA selecionado

- **WHEN** uma seleção contém EDA + GTT, EDA + Cápsula ou EDA + Dilatação
- **THEN** ela corresponde a exatamente uma identidade atômica
- **AND** não cria uma row EDA adicional.

#### Scenario: Variação de Retossigmoidoscopia selecionada

- **WHEN** uma seleção contém Retossigmoidoscopia + Dilatação ou Retossigmoidoscopia + Argônio
- **THEN** ela corresponde a exatamente uma identidade atômica
- **AND** não cria uma row Retossigmoidoscopia adicional.

#### Scenario: Seleção especializada simples

- **WHEN** uma seleção contém somente Ecoendoscopia ou somente CPRE
- **THEN** ela continua válida e recebe label próprio
- **AND** não é projetada como subtipo de EDA.

#### Scenario: Procedimentos especializados existentes

- **WHEN** Ecoendoscopia ou CPRE é consultada no catálogo ampliado
- **THEN** a identidade e o label existentes permanecem estáveis
- **AND** nenhuma variação os converte em EDA.

### Requirement: Matriz de conjuntos SHALL ser fechada

Somente qualquer singleton do catálogo canônico e o conjunto exato `{eda, colonoscopy}` SHALL ser válidos após reconciliação e na declaração/autorização persistidas. A mesma matriz MUST proteger intake/reenvio/correção, detecção reconciliada e conjunto autorizado final no backend. Antes de validar a matriz detectada, o sistema SHALL aplicar apenas as precedências de pacote/especializado sustentadas por ocorrência textual `current_request`; essa redução semântica não cria combinação autorizável nova.

#### Scenario: Única combinação permitida

- **WHEN** o conjunto reconciliado contém exatamente EDA e Colonoscopia
- **THEN** ele é válido e pode ser identificado como combinado/agendamento casado.

#### Scenario: Um especializado atual com procedimentos convencionais

- **WHEN** o conjunto bruto detectado contém exatamente Ecoendoscopia ou exatamente CPRE e também EDA e/ou Colonoscopia
- **AND** há ocorrência textual do mesmo especializado qualificada como `current_request`
- **THEN** a precedência especializada existente é aplicada antes da matriz
- **AND** o conjunto reconciliado contém somente o tipo especializado.

#### Scenario: Combinação especializada incompatível

- **WHEN** o conjunto bruto contém Ecoendoscopia e CPRE, com ou sem procedimentos convencionais
- **THEN** ele é encaminhado à revisão NIR de modo fail-closed
- **AND** nenhum especializado é escolhido arbitrariamente.

#### Scenario: Variação com Colonoscopia

- **WHEN** o conjunto contém uma variação de EDA ou Retossigmoidoscopia junto de Colonoscopia
- **THEN** ele é rejeitado ou encaminhado à revisão NIR de modo fail-closed
- **AND** nenhum componente é descartado para tornar o conjunto válido.

#### Scenario: Duas identidades atômicas fora do combinado

- **WHEN** o conjunto contém quaisquer duas identidades distintas fora de `{eda, colonoscopy}`
- **THEN** ele é incompatível
- **AND** não é classificado como combinado apenas pela quantidade de componentes.

#### Scenario: Tipo desconhecido não é descartado

- **WHEN** declaração ou evidência detectada contém tipo desconhecido junto de tipo suportado
- **THEN** o conjunto completo é rejeitado ou encaminhado à revisão com motivo explícito
- **AND** o valor desconhecido não é filtrado.

### Requirement: Substituição médica SHALL preservar conjunto final permitido

O médico SHALL poder substituir procedimentos e aprovar o destino sem reanálise, desde que o conjunto autorizado final seja um singleton canônico ou exatamente `{eda, colonoscopy}`. Uma troca parcial que retenha um componente e adicione pacote/variação SHALL ser bloqueada; o sistema SHALL NOT dividir caso ou agendamento.

#### Scenario: Troca integral para procedimento especializado

- **WHEN** o médico nega todos os componentes detectados, inclui somente Ecoendoscopia ou somente CPRE, informa as razões e aprova o destino
- **THEN** o conjunto final singleton é aceito estruturalmente
- **AND** nenhum segundo caso ou agendamento é criado.

#### Scenario: Troca integral para pacote atômico

- **WHEN** o médico nega todos os componentes detectados, inclui um único pacote suportado, informa as razões e aprova o destino
- **THEN** o conjunto final singleton é aceito estruturalmente
- **AND** nenhum segundo caso ou agendamento é criado.

#### Scenario: Troca parcial incompatível de combinado

- **WHEN** o médico tenta autorizar Colonoscopia junto de EDA + GTT, EDA + Cápsula, EDA + Dilatação ou qualquer Retossigmoidoscopia
- **THEN** o submit é rejeitado sem persistência parcial
- **AND** nenhum split automático é oferecido.

## ADDED Requirements

### Requirement: Pacotes SHALL permanecer indivisíveis em todas as dimensões

EDA + GTT, EDA + Cápsula, EDA + Dilatação, Retossigmoidoscopia + Dilatação e Retossigmoidoscopia + Argônio SHALL permanecer uma única identidade em declaração, detecção, policy, recomendação, autorização, histórico, fila, follow-up e analytics. Os termos GTT, cápsula, dilatação e argônio SHALL NOT gerar um segundo componente, e abreviações operacionais não aprovadas MUST NOT ser inventadas.

#### Scenario: EDA com GTT atual

- **WHEN** uma solicitação atual sustentada pede EDA com GTT
- **THEN** o conjunto reconciliado é `{eda_gastrostomy}`
- **AND** `{eda, eda_gastrostomy}` não é persistido.

#### Scenario: Retossigmoidoscopia com dilatação atual

- **WHEN** uma solicitação atual sustentada pede Retossigmoidoscopia com dilatação
- **THEN** o conjunto reconciliado é `{rectosigmoidoscopy_dilation}`
- **AND** a identidade base não é persistida separadamente.

#### Scenario: Duas variações solicitadas

- **WHEN** o documento sustenta duas variações atuais distintas
- **THEN** nenhuma precedência escolhe uma arbitrariamente
- **AND** o caso segue à revisão NIR por conjunto incompatível.

### Requirement: Famílias SHALL reutilizar profiles sem compartilhar identidade

`eda_gastrostomy`, `eda_capsule` e `eda_dilation` SHALL aplicar o profile pré-operatório de EDA. `rectosigmoidoscopy`, `rectosigmoidoscopy_dilation` e `rectosigmoidoscopy_argon` SHALL aplicar o profile pré-operatório de Colonoscopia. Reutilizar profile MUST NOT fazer uma identidade contar como histórico, filtro ou volume de outra.

#### Scenario: Retossigmoidoscopia sem requisito da Colonoscopia

- **WHEN** uma Retossigmoidoscopia não atende a requisito determinístico do profile de Colonoscopia
- **THEN** a policy produz a mesma pendência aplicável
- **AND** a recomendação continua identificada como Retossigmoidoscopia.

#### Scenario: EDA + Cápsula satisfaz profile EDA

- **WHEN** EDA + Cápsula atende aos requisitos de EDA
- **THEN** nenhuma exigência adicional é inferida apenas pela variação
- **AND** o resultado permanece vinculado a `eda_capsule`.
