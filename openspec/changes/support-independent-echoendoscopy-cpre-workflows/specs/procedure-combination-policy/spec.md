## Purpose

Define o catálogo autoritativo de procedimentos e a matriz fechada de conjuntos permitidos em declaração, detecção reconciliada, autorização e agendamento.

## ADDED Requirements

### Requirement: Catálogo e ordem canônica SHALL conter quatro procedimentos

O sistema SHALL reconhecer `eda`, `colonoscopy`, `echoendoscopy` e `cpre` como identidades independentes e SHALL usar ordem canônica única para persistência, eventos, labels, filtros e analytics.

#### Scenario: Seleção especializada simples

- **WHEN** uma seleção contém somente Ecoendoscopia ou somente CPRE
- **THEN** ela é válida e recebe label próprio
- **AND** não é projetada como subtipo de EDA.

### Requirement: Matriz de conjuntos SHALL ser fechada

Somente `{eda}`, `{colonoscopy}`, `{eda, colonoscopy}`, `{echoendoscopy}` e `{cpre}` SHALL ser válidos. A mesma matriz MUST proteger intake/reenvio/correção, detecção reconciliada e conjunto autorizado final no backend.

#### Scenario: Única combinação permitida

- **WHEN** o conjunto contém exatamente EDA e Colonoscopia
- **THEN** ele é válido e pode ser identificado como combinado/agendamento casado.

#### Scenario: Combinação especializada incompatível

- **WHEN** o conjunto contém Ecoendoscopia ou CPRE com qualquer outro procedimento, ou contém três ou mais tipos
- **THEN** ele é rejeitado de modo fail-closed
- **AND** não é classificado apenas pela quantidade de componentes.

#### Scenario: Tipo desconhecido não é descartado

- **WHEN** declaração ou evidência detectada contém tipo desconhecido junto de um tipo suportado
- **THEN** o conjunto completo é rejeitado ou encaminhado à revisão com motivo explícito
- **AND** o valor desconhecido não é filtrado para fazer o restante parecer válido.

### Requirement: Precedência especializada SHALL colapsar expressões de EDA

A reconciliação SHALL interpretar `EDA com ecoendoscopia` e `EDA e ecoendoscopia` como somente Ecoendoscopia, e `EDA com CPRE` e `EDA e CPRE` como somente CPRE, preservando evidência da expressão original.

#### Scenario: EDA com Ecoendoscopia

- **WHEN** uma solicitação atual sustentada diz `EDA com ecoendoscopia` ou `EDA e ecoendoscopia`
- **THEN** o conjunto detectado reconciliado é `{echoendoscopy}`
- **AND** `{eda, echoendoscopy}` não é persistido.

#### Scenario: EDA com CPRE

- **WHEN** uma solicitação atual sustentada diz `EDA com CPRE` ou `EDA e CPRE`
- **THEN** o conjunto detectado reconciliado é `{cpre}`
- **AND** `{eda, cpre}` não é persistido.

### Requirement: Mismatch especializado SHALL retornar ao NIR

Não SHALL existir upgrade automático entre procedimento convencional e especializado. O upgrade automático existente SHALL permanecer restrito a EDA ou Colonoscopia única detectada como `{eda, colonoscopy}` com evidência forte.

#### Scenario: EDA declarada e Ecoendoscopia detectada

- **WHEN** NIR declarou EDA e a análise detectou somente Ecoendoscopia
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
