# procedure-combination-policy Specification

## Purpose
Define o catálogo autoritativo de procedimentos e a matriz fechada de conjuntos permitidos em declaração, detecção reconciliada, autorização e agendamento.

## Requirements

### Requirement: Catálogo e ordem canônica SHALL conter quatro procedimentos

O sistema SHALL reconhecer `eda`, `colonoscopy`, `echoendoscopy` e `cpre` como identidades independentes e SHALL usar ordem canônica única para persistência, eventos, labels, filtros e analytics.

#### Scenario: Seleção especializada simples

- **WHEN** uma seleção contém somente Ecoendoscopia ou somente CPRE
- **THEN** ela é válida e recebe label próprio
- **AND** não é projetada como subtipo de EDA.

### Requirement: Matriz de conjuntos SHALL ser fechada

Somente `{eda}`, `{colonoscopy}`, `{eda, colonoscopy}`, `{echoendoscopy}` e `{cpre}` SHALL ser válidos após a reconciliação e na declaração/autorização persistidas. A mesma matriz MUST proteger intake/reenvio/correção, detecção reconciliada e conjunto autorizado final no backend. Antes de validar a matriz detectada, o sistema SHALL aplicar a precedência de um único procedimento especializado sobre procedimentos convencionais somente quando existir ocorrência textual correspondente qualificada como `current_request`; essa redução semântica não cria uma combinação autorizável nova.

#### Scenario: Única combinação permitida

- **WHEN** o conjunto reconciliado contém exatamente EDA e Colonoscopia
- **THEN** ele é válido e pode ser identificado como combinado/agendamento casado.

#### Scenario: Um especializado atual com procedimentos convencionais

- **WHEN** o conjunto bruto detectado contém exatamente um tipo especializado e também EDA e/ou Colonoscopia
- **AND** há ocorrência textual do mesmo especializado qualificada como `current_request`
- **THEN** a precedência especializada é aplicada antes da matriz
- **AND** o conjunto reconciliado contém somente o tipo especializado.

#### Scenario: Combinação especializada incompatível

- **WHEN** o conjunto bruto de solicitações atuais contém Ecoendoscopia e CPRE, com ou sem procedimentos convencionais
- **THEN** ele é encaminhado à revisão NIR de modo fail-closed
- **AND** nenhum dos dois especializados é escolhido arbitrariamente
- **AND** não é classificado apenas pela quantidade de componentes.

#### Scenario: Tipo desconhecido não é descartado

- **WHEN** declaração ou evidência detectada contém tipo desconhecido junto de um tipo suportado
- **THEN** o conjunto completo é rejeitado ou encaminhado à revisão com motivo explícito
- **AND** o valor desconhecido não é filtrado para fazer o restante parecer válido.

### Requirement: Precedência especializada SHALL colapsar expressões de EDA

A reconciliação SHALL fazer exatamente uma Ecoendoscopia ou exatamente uma CPRE detectada predominar sobre EDA e/ou Colonoscopia somente quando `detect_procedure_occurrences()` também produzir ocorrência do mesmo especializado qualificada como `current_request`. `requested_procedures` estruturado, isoladamente, SHALL NOT autorizar a supressão. A ocorrência atual MAY estar em expressão ligada ou em seção/frase independente, e a evidência original SHALL permanecer no artefato LLM1.

#### Scenario: Cabeçalho EDA e Ecoendoscopia solicitada em outro trecho

- **GIVEN** o NIR declarou Ecoendoscopia
- **AND** o relatório contém cabeçalho administrativo de EDA
- **AND** outro trecho contém solicitação atual explícita de Ecoendoscopia
- **WHEN** a reconciliação executa
- **THEN** o conjunto detectado reconciliado é `{echoendoscopy}`
- **AND** o caso não retorna ao NIR por combinação incompatível
- **AND** pode seguir à avaliação médica.

#### Scenario: EDA ou Colonoscopia com CPRE em trechos independentes

- **GIVEN** o NIR declarou CPRE
- **AND** EDA e/ou Colonoscopia foram detectadas como solicitações convencionais atuais
- **AND** CPRE foi detectada como solicitação atual em outro trecho
- **WHEN** a reconciliação executa
- **THEN** o conjunto detectado reconciliado é `{cpre}`
- **AND** nenhum conjunto combinado especializado é persistido.

#### Scenario: EDA com Ecoendoscopia

- **WHEN** uma solicitação atual sustentada diz `EDA com ecoendoscopia` ou `EDA e ecoendoscopia`
- **THEN** o conjunto detectado reconciliado é `{echoendoscopy}`
- **AND** `{eda, echoendoscopy}` não é persistido.

#### Scenario: EDA com CPRE

- **WHEN** uma solicitação atual sustentada diz `EDA com CPRE` ou `EDA e CPRE`
- **THEN** o conjunto detectado reconciliado é `{cpre}`
- **AND** `{eda, cpre}` não é persistido.

#### Scenario: Item estruturado sem ocorrência atual não autoriza supressão

- **GIVEN** `requested_procedures` contém Ecoendoscopia ou CPRE junto de EDA e/ou Colonoscopia
- **AND** o especializado aparece no texto somente como exame histórico, negado ou mera menção
- **WHEN** detecção e reconciliação executam
- **THEN** o especializado não elimina EDA/Colonoscopia
- **AND** o conjunto misto permanece incompatível e segue à revisão NIR.

#### Scenario: Histórico e negação sem item estruturado preservam convencional

- **GIVEN** Ecoendoscopia ou CPRE aparece somente como exame histórico, negado ou mera menção
- **AND** não integra o conjunto estruturado detectado
- **WHEN** detecção e reconciliação executam
- **THEN** o especializado não integra o conjunto detectado
- **AND** o comportamento convencional existente é preservado.

### Requirement: Mismatch especializado SHALL retornar ao NIR

Não SHALL existir upgrade automático entre procedimento convencional e especializado. A precedência altera somente o conjunto detectado bruto; ela SHALL NOT sobrescrever a declaração do NIR. O upgrade automático existente SHALL permanecer restrito a EDA ou Colonoscopia única detectada como `{eda, colonoscopy}` com evidência forte.

#### Scenario: EDA declarada e Ecoendoscopia detectada

- **WHEN** NIR declarou EDA e a precedência produziu somente Ecoendoscopia
- **THEN** o caso retorna ao NIR como mismatch
- **AND** nenhuma dimensão é sobrescrita silenciosamente.

#### Scenario: Tipo especializado declarado e EDA detectada

- **WHEN** NIR declarou Ecoendoscopia ou CPRE e a análise detectou somente EDA
- **THEN** o caso retorna ao NIR como mismatch.

### Requirement: Substituição médica SHALL preservar conjunto final permitido

O médico SHALL poder substituir procedimentos e aprovar o destino sem reanálise, desde que o conjunto autorizado final pertença à matriz fechada. Uma troca parcial de caso combinado que retenha um componente e adicione procedimento especializado SHALL ser bloqueada; o sistema SHALL NOT dividir caso ou agendamento.

#### Scenario: Troca integral para procedimento especializado

- **WHEN** o médico nega todos os componentes detectados, inclui um único procedimento especializado, informa as razões e aprova o destino
- **THEN** o conjunto final simples é aceito estruturalmente
- **AND** nenhum segundo caso ou agendamento é criado.

#### Scenario: Troca parcial incompatível de combinado

- **WHEN** o médico tenta autorizar Colonoscopia + Ecoendoscopia ou qualquer outro conjunto proibido
- **THEN** o submit é rejeitado sem persistência parcial
- **AND** nenhum split automático é oferecido.

### Requirement: Aplicação da precedência especializada SHALL ser auditável e visível ao médico

Quando a precedência suprimir EDA e/ou Colonoscopia, o sistema SHALL registrar o especializado selecionado e os tipos convencionais suprimidos sem copiar texto clínico integral. A mesma informação SHALL produzir aviso não bloqueante na avaliação médica. O artefato LLM1 original MUST permanecer imutável e a visão do LLM2 SHALL conter somente o conjunto reconciliado.

#### Scenario: Precedência registrada no pipeline

- **WHEN** `{eda, echoendoscopy}` é reduzido para `{echoendoscopy}`
- **THEN** `CASE_PROCEDURES_DETECTED` registra regra, selecionado e suprimidos
- **AND** `suggested_action` carrega o mesmo metadado enxuto
- **AND** `Case.structured_data` preserva os itens extraídos originalmente
- **AND** o LLM2 recebe somente Ecoendoscopia como lista fechada.

#### Scenario: Médico recebe aviso não bloqueante para cada especializado

- **GIVEN** a precedência de Ecoendoscopia ou CPRE foi aplicada
- **WHEN** o médico abre a avaliação
- **THEN** o relatório informa com label canônico que procedimento(s) convencional(is) também foram identificados e que o especializado predominou
- **AND** orienta revisar o texto original e ajustar a decisão se necessário
- **AND** o aviso não altera policy, formulário, validação ou FSM.

#### Scenario: Singleton especializado normal não gera alerta de supressão

- **GIVEN** somente Ecoendoscopia ou somente CPRE foi detectada
- **WHEN** o médico abre a avaliação
- **THEN** nenhum aviso de precedência/supressão é exibido.
