# procedure-combination-policy Spec Delta

## MODIFIED Requirements

### Requirement: Matriz de conjuntos SHALL ser fechada

Somente `{eda}`, `{colonoscopy}`, `{eda, colonoscopy}`, `{echoendoscopy}` e `{cpre}` SHALL ser válidos após a reconciliação e na declaração/autorização persistidas. A mesma matriz MUST proteger intake/reenvio/correção, detecção reconciliada e conjunto autorizado final no backend. Antes de validar a matriz detectada, o sistema SHALL aplicar a precedência de um único procedimento especializado atual sobre procedimentos convencionais; essa redução semântica não cria uma combinação autorizável nova.

#### Scenario: Única combinação permitida

- **WHEN** o conjunto reconciliado contém exatamente EDA e Colonoscopia
- **THEN** ele é válido e pode ser identificado como combinado/agendamento casado.

#### Scenario: Um especializado com procedimentos convencionais

- **WHEN** o conjunto bruto de solicitações atuais contém exatamente um tipo especializado e também EDA e/ou Colonoscopia
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

Depois de histórico, negação e mera menção terem sido excluídos pelo detector, a reconciliação SHALL fazer exatamente uma Ecoendoscopia ou exatamente uma CPRE solicitada atualmente predominar sobre EDA e/ou Colonoscopia também solicitadas/detectadas. A precedência SHALL funcionar tanto em expressão ligada quanto em seções ou frases independentes e SHALL preservar a evidência original no artefato LLM1.

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

#### Scenario: Histórico e negação não acionam precedência

- **GIVEN** Ecoendoscopia ou CPRE aparece somente como exame histórico, negado ou mera menção
- **WHEN** detecção e reconciliação executam
- **THEN** o especializado não elimina EDA/Colonoscopia atuais
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

## ADDED Requirements

### Requirement: Aplicação da precedência especializada SHALL ser auditável e visível ao médico

Quando a precedência suprimir EDA e/ou Colonoscopia, o sistema SHALL registrar o especializado selecionado e os tipos convencionais suprimidos sem copiar texto clínico integral. A mesma informação SHALL produzir aviso não bloqueante na avaliação médica. O artefato LLM1 original MUST permanecer imutável e a visão do LLM2 SHALL conter somente o conjunto reconciliado.

#### Scenario: Precedência registrada no pipeline

- **WHEN** `{eda, echoendoscopy}` é reduzido para `{echoendoscopy}`
- **THEN** `CASE_PROCEDURES_DETECTED` registra regra, selecionado e suprimidos
- **AND** `suggested_action` carrega o mesmo metadado enxuto
- **AND** `Case.structured_data` preserva os itens extraídos originalmente
- **AND** o LLM2 recebe somente Ecoendoscopia como lista fechada.

#### Scenario: Médico recebe aviso não bloqueante

- **GIVEN** a precedência especializada foi aplicada
- **WHEN** o médico abre a avaliação
- **THEN** o relatório informa que procedimento(s) convencional(is) também foram identificados e que o especializado predominou
- **AND** orienta revisar o texto original e ajustar a decisão se necessário
- **AND** o aviso não altera policy, formulário, validação ou FSM.

#### Scenario: Singleton especializado normal não gera alerta de supressão

- **GIVEN** somente Ecoendoscopia ou somente CPRE foi detectada
- **WHEN** o médico abre a avaliação
- **THEN** nenhum aviso de precedência/supressão é exibido.
