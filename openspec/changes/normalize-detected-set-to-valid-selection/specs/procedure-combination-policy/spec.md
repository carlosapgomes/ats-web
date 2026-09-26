# procedure-combination-policy Delta

## Purpose

Esclarecer onde a matriz fechada atua: decisões e exibições pós-reconciliação
usam o conjunto detectado normalizado pela cobertura máxima (ADR-0011); a
evidência bruta permanece na auditoria.

## MODIFIED Requirements

### Requirement: Matriz de conjuntos SHALL ser fechada

Somente qualquer singleton do catálogo canônico e o conjunto exato `{eda, colonoscopy}` SHALL ser válidos após reconciliação e na declaração/autorização persistidas. A mesma matriz MUST proteger intake/reenvio/correção, detecção reconciliada e conjunto autorizado final no backend. Antes de validar a matriz detectada, o sistema SHALL aplicar apenas as precedências de pacote/especializado sustentadas por ocorrência textual `current_request`; essa redução semântica não cria combinação autorizável nova. Nas decisões e exibições pós-reconciliação, o conjunto detectado apresentado SHALL ser a seleção válida mais completa que cobre a evidência reunida (base absorvida pelo pacote presente) — o sistema MUST NOT decidir ou exibir por combinação fora da matriz; quando nenhuma seleção válida cobre a evidência, a exibição carrega a união bruta como evidência de revisão e o desfecho permanece fail-closed. A normalização de exibição/decisão MUST NOT descartar valores da evidência persistida: o evento de auditoria da detecção preserva a união bruta completa.

#### Scenario: Única combinação permitida

- **WHEN** o conjunto reconciliado contém exatamente EDA e Colonoscopia
- **THEN** ele é válido e pode ser identificado como combinado/agendamento casado.

#### Scenario: Um especializado atual com procedimentos convencionais

- **WHEN** o conjunto bruto detectado contém exatamente Ecoendoscopia ou exatamente CPRE e também EDA e/ou Colonoscopia
- **AND** há ocorrência textual do mesmo especializado qualificada como `current_request`
- **THEN** a precedência especializada existente é aplicada antes da matriz
- **AND** o conjunto reconciliado contém somente o tipo especializado.

#### Scenario: Base absorvida pelo pacote na exibição e na decisão

- **WHEN** a evidência reunida contém a base `eda` e o pacote `eda_dilation`
- **THEN** o conjunto detectado apresentado é o pacote `eda_dilation`
- **AND** nenhuma combinação fora da matriz é exibida ou usada em decisão
- **AND** o evento de auditoria preserva a união bruta `{eda, eda_dilation}`.

#### Scenario: União bruta válida passa inalterada pelo payload

- **WHEN** o conjunto detectado é o par válido `{eda, colonoscopy}`
- **THEN** o payload de revisão carrega as identidades `eda` e `colonoscopy`
- **AND** nenhuma chave interna de seleção vaza para exibição.

#### Scenario: Item estruturado sem ocorrência textual com declaração do pacote e evidência atual prossegue

- **GIVEN** LLM1 reporta `eda_dilation` sem NENHUMA ocorrência textual do termo
- **AND** o texto tem ocorrência atual de `eda` e a declaração vigente é `eda_dilation`
- **WHEN** a reconciliação avalia o conjunto `{eda, eda_dilation}` antes da matriz
- **THEN** a cobertura máxima é `eda_dilation` e igual à declaração com evidência atual não-vazia
- **AND** o caso prossegue com a declaração
- **AND** o conjunto bruto permanece no evento de auditoria.

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
