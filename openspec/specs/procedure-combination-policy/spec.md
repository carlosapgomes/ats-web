# procedure-combination-policy Specification

## Purpose
Define o catálogo autoritativo de procedimentos e a matriz fechada de conjuntos permitidos em declaração, detecção reconciliada, autorização e agendamento.

## Requirements

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

### Requirement: Pacotes SHALL permanecer indivisíveis em todas as dimensões

EDA + GTT, EDA + Cápsula, EDA + Dilatação, Retossigmoidoscopia + Dilatação e Retossigmoidoscopia + Argônio SHALL permanecer uma única identidade em declaração, detecção, policy, recomendação, autorização, histórico, fila, follow-up e analytics. Os termos GTT, cápsula, dilatação e argônio SHALL NOT gerar um segundo componente, e abreviações operacionais não aprovadas MUST NOT ser inventadas. `GTT`/`gastrostomia` e `cápsula` são marcadores autoevidentes da família EDA e detectam o pacote por ocorrência atual mesmo isolada; `dilatação` e `argônio` exigem vínculo local com a base. Exatamente uma variação atual suprime a base detectada em qualquer trecho (mesma expressão ou independente), no mesmo regime de proveniência da precedência especializada; o item estruturado sem ocorrência textual atual não autoriza supressão.

#### Scenario: EDA com GTT atual

- **WHEN** uma solicitação atual sustentada pede EDA com GTT
- **THEN** o conjunto reconciliado é `{eda_gastrostomy}`
- **AND** `{eda, eda_gastrostomy}` não é persistido.

#### Scenario: Cabeçalho EDA e GTT solicitada em outro trecho

- **GIVEN** o NIR declarou `eda_gastrostomy`
- **AND** o relatório contém cabeçalho administrativo ou solicitação atual de EDA em um trecho
- **AND** outro trecho contém solicitação atual de GTT
- **WHEN** a reconciliação executa
- **THEN** o conjunto detectado reconciliado é `{eda_gastrostomy}`
- **AND** o caso não retorna ao NIR por combinação incompatível
- **AND** a supressão da base fica registrada como metadado auditável.

#### Scenario: Marcador autoevidente sem base no documento

- **WHEN** a solicitação atual sustentada contém somente GTT (ou somente cápsula endoscópica), sem menção a EDA
- **THEN** o conjunto detectado é `{eda_gastrostomy}` (ou `{eda_capsule}`)
- **AND** nenhuma row EDA base é criada.

#### Scenario: Item estruturado sem ocorrência atual não autoriza supressão

- **GIVEN** `requested_procedures` contém `eda_dilation` junto de EDA
- **AND** dilatação aparece no texto somente como histórico, negação ou mera menção
- **WHEN** detecção e reconciliação executam
- **THEN** a variação não suprime a EDA base
- **AND** o conjunto permanece incompatível e segue à revisão NIR.

#### Scenario: Retossigmoidoscopia com dilatação atual

- **WHEN** uma solicitação atual sustentada pede Retossigmoidoscopia com dilatação
- **THEN** o conjunto reconciliado é `{rectosigmoidoscopy_dilation}`
- **AND** a identidade base não é persistida separadamente.

#### Scenario: Duas variações solicitadas

- **WHEN** o documento sustenta duas variações atuais distintas
- **THEN** nenhuma precedência escolhe uma arbitrariamente
- **AND** o caso segue à revisão NIR por conjunto incompatível.

### Requirement: Famílias SHALL reutilizar profiles sem compartilhar identidade

`eda_gastrostomy`, `eda_capsule` e `eda_dilation` SHALL aplicar o profile pré-operatório de EDA. `rectosigmoidoscopy`, `rectosigmoidoscopy_dilation` e `rectosigmoidoscopy_argon` SHALL aplicar o profile pré-operatório de Colonoscopia. Reutilizar profile MUST NOT fazer uma identidade contar como histórico, filtro ou volume de outra. Textos determinísticos persistidos pela policy (pendências e critérios atendidos) SHALL usar a label canônica da identidade; o profile da família contribui somente as regras clínicas.

#### Scenario: Retossigmoidoscopia sem requisito da Colonoscopia

- **WHEN** uma Retossigmoidoscopia não atende a requisito determinístico do profile de Colonoscopia
- **THEN** a policy produz a mesma pendência aplicável
- **AND** a recomendação continua identificada como Retossigmoidoscopia
- **AND** o texto persistido da pendência menciona Retossigmoidoscopia, não Colonoscopia.

#### Scenario: Pendência de pacote usa label do pacote

- **GIVEN** `eda_gastrostomy` não atende a um requisito do profile de EDA
- **WHEN** a policy executa
- **THEN** o texto persistido da pendência usa a label de EDA + Gastrostomia (GTT)
- **AND** a regra aplicada permanece exatamente a do profile de EDA.

#### Scenario: EDA + Cápsula satisfaz profile EDA

- **WHEN** EDA + Cápsula atende aos requisitos de EDA
- **THEN** nenhuma exigência adicional é inferida apenas pela variação
- **AND** o resultado permanece vinculado a `eda_capsule`.
