## MODIFIED Requirements

### Requirement: Médico filtra pendências sem perder a busca

A aba médica `Pendentes` MUST manter lifecycle primário e filtrar por `Todos`, qualquer singleton canônico ou `EDA + Colonoscopia`, usando procedimentos detectados e labels do catálogo.

#### Scenario: Ecoendoscopia e nome compostos

- **GIVEN** o médico digitou termo e selecionou Ecoendoscopia
- **WHEN** filtro é aplicado ou polling atualiza cards
- **THEN** somente casos com Ecoendoscopia detectada e termo correspondente aparecem
- **AND** termo e seleção permanecem.

#### Scenario: Pacote e nome compostos

- **GIVEN** o médico digitou termo e selecionou EDA + GTT
- **WHEN** filtro é aplicado ou polling atualiza cards
- **THEN** somente casos com `eda_gastrostomy` detectada e termo correspondente aparecem
- **AND** termo e seleção permanecem.

#### Scenario: Combinado e nome compostos

- **GIVEN** o médico digitou termo e selecionou EDA + Colonoscopia
- **WHEN** filtro é aplicado ou polling atualiza cards
- **THEN** somente casos com ambas detectadas e termo correspondente aparecem
- **AND** termo e seleção permanecem.

### Requirement: Decididos Hoje tem badge e filtro simples

A aba médica `Decididos Hoje` MUST identificar e filtrar pelo conjunto autorizado entre qualquer singleton canônico, EDA + Colonoscopia ou Nenhum autorizado. Pacotes SHALL aparecer por sua label única.

#### Scenario: EDA substituída por CPRE

- **GIVEN** caso detectado como EDA terminou autorizado somente como CPRE
- **WHEN** o médico abre Decididos Hoje
- **THEN** o badge principal é CPRE
- **AND** a transformação EDA → CPRE permanece visível.

#### Scenario: EDA substituída por Retossigmoidoscopia

- **GIVEN** caso detectado como EDA terminou autorizado somente como Retossigmoidoscopia
- **WHEN** o médico abre Decididos Hoje
- **THEN** o badge principal é Retossigmoidoscopia
- **AND** a transformação EDA → Retossigmoidoscopia permanece visível.

#### Scenario: Combinado parcialmente aprovado

- **GIVEN** caso detectado EDA + Colonoscopia terminou autorizado somente para EDA
- **WHEN** o médico abre Decididos Hoje
- **THEN** o badge principal é EDA
- **AND** a transformação combinado → EDA permanece visível.

### Requirement: CHD filtra todas as pendências pelo mesmo universo do contador

O filtro CHD MUST usar procedimentos aprovados em todos os grupos de Pendentes e MUST aceitar qualquer singleton canônico ou EDA + Colonoscopia. O predicado e o contador MUST consumir a mesma seleção canônica.

#### Scenario: CPRE em grupo operacional

- **GIVEN** caso de CPRE autorizado pertence a grupo elegível
- **WHEN** CHD seleciona CPRE
- **THEN** o mesmo predicado do contador é aplicado
- **AND** somente CPRE autorizada aparece.

#### Scenario: Variação em grupo operacional

- **GIVEN** caso de Retossigmoidoscopia + Dilatação autorizado pertence a grupo elegível
- **WHEN** CHD seleciona essa identidade
- **THEN** o mesmo predicado do contador é aplicado
- **AND** somente essa identidade autorizada aparece.

#### Scenario: Agendamento casado em grupos operacionais

- **GIVEN** casos EDA + Colonoscopia autorizados em grupos elegíveis
- **WHEN** CHD seleciona EDA + Colonoscopia
- **THEN** todos os grupos exigem exatamente ambos aprovados
- **AND** contadores fecham com o universo primário.

### Requirement: Processados Hoje tem badge e filtro

Processados Hoje MUST exibir o snapshot autorizado/agendado e permitir filtro por qualquer singleton canônico ou EDA + Colonoscopia. Somente EDA + Colonoscopia MUST usar o sufixo `Agendamento casado`.

#### Scenario: Ecoendoscopia confirmada

- **GIVEN** CHD confirmou caso autorizado como Ecoendoscopia
- **WHEN** consulta Processados Hoje
- **THEN** vê `Ecoendoscopia` e uma única data/hora
- **AND** não vê EDA nem `Agendamento casado`.

#### Scenario: EDA + Cápsula confirmada

- **GIVEN** CHD confirmou caso autorizado como EDA + Cápsula
- **WHEN** consulta Processados Hoje
- **THEN** vê `EDA + Cápsula` e uma única data/hora
- **AND** não vê badge EDA separado nem `Agendamento casado`.

#### Scenario: Combinado confirmado

- **GIVEN** CHD confirmou caso com EDA e Colonoscopia aprovadas
- **WHEN** consulta Processados Hoje
- **THEN** vê `EDA + Colonoscopia · Agendamento casado`
- **AND** uma única data/hora.

### Requirement: Histórico CHD combina tipo e busca

A busca histórica MUST aceitar `all`, cada código atômico e `eda_colonoscopy`, usar dimensão autorizada e manter limite/ordering atuais. O backend SHALL rejeitar filtros desconhecidos em vez de reclassificá-los — rejeição intencional e deliberadamente distinta do fallback para `all` mantido nos filtros NIR, que permanece inalterado.

#### Scenario: CPRE sem termo

- **GIVEN** CHD seleciona CPRE sem termo
- **WHEN** submete
- **THEN** vê até os 50 casos históricos mais recentes autorizados como CPRE.

#### Scenario: EDA + Dilatação sem termo

- **GIVEN** CHD seleciona `eda_dilation` sem termo
- **WHEN** submete
- **THEN** vê até os 50 casos históricos mais recentes autorizados exatamente como EDA + Dilatação
- **AND** EDA simples não entra no resultado.

#### Scenario: Combinado sem termo

- **GIVEN** CHD seleciona EDA + Colonoscopia sem termo
- **WHEN** submete
- **THEN** vê até os 50 casos históricos mais recentes com ambos autorizados.

### Requirement: Alterações ficam explícitas nas filas downstream

Quando declaração, detecção e autorização diferirem, médico, CHD e NIR MUST receber comparação textual por labels canônicas, sem depender apenas de cor. Mudança do conjunto autorizado MUST gerar evento append-only e mensagem sistêmica idempotente na thread, sem criar notificação global.

#### Scenario: Médico substituiu EDA por Ecoendoscopia

- **GIVEN** caso detectado EDA foi autorizado como Ecoendoscopia
- **WHEN** CHD ou NIR abre card/detalhe
- **THEN** vê `Detectado: EDA` e `Autorizado: Ecoendoscopia`
- **AND** a justificativa correspondente e a mensagem sistêmica ficam disponíveis.

#### Scenario: Médico substituiu EDA por Colonoscopia

- **GIVEN** caso detectado EDA foi autorizado como Colonoscopia
- **WHEN** CHD abre card/detalhe
- **THEN** vê `Detectado: EDA` e `Autorizado: Colonoscopia`
- **AND** as justificativas médicas correspondentes ficam disponíveis.

#### Scenario: Médico substituiu EDA por EDA + GTT

- **GIVEN** caso detectado EDA foi autorizado como EDA + GTT
- **WHEN** CHD ou NIR abre card/detalhe
- **THEN** vê `Detectado: EDA` e `Autorizado: EDA + GTT`
- **AND** a justificativa correspondente e a mensagem sistêmica ficam disponíveis.

#### Scenario: Mensagem sistêmica não gera inbox

- **GIVEN** evento de mudança do conjunto médico foi criado
- **WHEN** sua mensagem sistêmica é projetada
- **THEN** nenhuma `UserNotification` é criada
- **AND** nenhum badge global aumenta.

#### Scenario: Pacote permanece uma identidade

- **GIVEN** `rectosigmoidoscopy_argon` foi detectada e autorizada
- **WHEN** qualquer fila a projeta
- **THEN** exibe somente `Retossigmoidoscopia + Argônio`
- **AND** não representa base e variação como dois componentes.
