# gastrostomy-infection-review Specification

## Purpose
Define uma revisão clínica consultiva e rastreável de possível infecção sistêmica para EDA + GTT, sem transformar evidência incompleta em hard rule ou bloqueio operacional.

## Requirements

### Requirement: Revisão infecciosa SHALL aplicar-se somente a EDA + GTT

O sistema SHALL produzir e exibir a revisão infecciosa somente quando o procedimento reconciliado exato for `eda_gastrostomy`. EDA simples, outras variações e menções históricas de GTT MUST NOT receber o painel por herança de família ou sinal legado.

#### Scenario: EDA + GTT reconciliada

- **GIVEN** `eda_gastrostomy` é o procedimento reconciliado
- **WHEN** a análise 4.0 e o relatório médico são produzidos
- **THEN** a seção de revisão infecciosa está disponível
- **AND** está associada somente àquela identidade.

#### Scenario: EDA com GTT apenas histórica

- **GIVEN** EDA é o procedimento atual e GTT aparece somente no histórico
- **WHEN** o relatório médico é exibido
- **THEN** o painel de EDA + GTT não é criado.

### Requirement: Evidências de infecção SHALL usar vocabulário fechado e trecho ancorado

A revisão SHALL aceitar somente evidências do relatório principal nas categorias leucócitos, PCR, procalcitonina, lactato, culturas, temperatura/febre, avaliação de infectologia e uso/início/escalonamento de antibióticos. Cada item MUST preservar texto de valor/estado, qualificação explícita, contexto temporal e trecho-fonte verificável; conteúdo não ancorado MUST NOT ser apresentado como fato.

#### Scenario: Laboratórios presentes

- **GIVEN** o relatório contém leucócitos, PCR e lactato com valores
- **WHEN** a revisão é construída
- **THEN** cada resultado aparece separadamente com o texto documentado e sua evidência
- **AND** unidades ausentes não são inventadas.

#### Scenario: Antibiótico e infectologia

- **GIVEN** o relatório documenta antibiótico em uso e avaliação da infectologia
- **WHEN** a revisão é exibida
- **THEN** ambos aparecem como evidências distintas
- **AND** início ou escalonamento só é afirmado quando explicitamente documentado.

#### Scenario: Resposta sem trecho real

- **GIVEN** o artefato 4.0 declara evidência cujo trecho não existe no relatório principal
- **WHEN** a ancoragem é verificada
- **THEN** o item não é apresentado como evidência confirmada
- **AND** não gera alerta visual.

### Requirement: Resultados presentes SHALL aparecer independentemente de normalidade

Todo resultado das categorias laboratoriais ou de cultura presente no relatório e ancorado SHALL aparecer no painel, inclusive quando explicitamente normal, baixo risco ou negativo. O sistema MUST NOT aplicar faixas de referência ou thresholds implícitos; `normal`, `alterado`, `positivo` ou `negativo` só podem ser afirmados quando o próprio relatório os documentar.

#### Scenario: Valor explicitamente normal

- **GIVEN** o relatório documenta leucócitos com valor e os qualifica como normais
- **WHEN** o painel é exibido
- **THEN** o valor aparece com qualificação normal
- **AND** esse item isolado não é classificado como possível infecção.

#### Scenario: Valor sem interpretação

- **GIVEN** o relatório informa PCR `12 mg/L` sem qualificá-la
- **WHEN** o painel é exibido
- **THEN** o valor textual e a unidade aparecem
- **AND** o sistema não o classifica como normal ou alterado por threshold próprio.

#### Scenario: Cultura negativa

- **GIVEN** o relatório documenta cultura negativa
- **WHEN** o painel é exibido
- **THEN** o resultado negativo permanece visível
- **AND** não gera alerta por si só.

### Requirement: Alerta visual SHALL depender de preocupação explicitamente documentada

O painel SHALL destacar possível infecção sistêmica quando ao menos uma evidência atual, ou sem temporalidade mas não explicitamente histórica, estiver ancorada e qualificada no relatório como alterada, elevada, positiva, febril ou compatível com infecção; avaliação atual de infectologia e uso, início ou escalonamento atual de antibiótico também SHALL acionar o destaque. Resultados normais/negativos isolados, valores não interpretados e evidência exclusivamente histórica SHALL permanecer visíveis quando aplicáveis, mas MUST NOT acionar o alerta.

#### Scenario: Febre atual explicitamente documentada

- **GIVEN** o relatório documenta febre atual com trecho ancorado
- **WHEN** o painel é exibido
- **THEN** apresenta alerta visual de possível infecção sistêmica
- **AND** mostra a evidência que motivou o alerta.

#### Scenario: Antibiótico atual em uso

- **GIVEN** o relatório documenta antibiótico atual em uso
- **WHEN** o painel é exibido
- **THEN** o uso aparece e aciona o alerta consultivo
- **AND** o sistema não afirma diagnóstico definitivo de infecção.

#### Scenario: Somente resultados normais

- **GIVEN** todas as evidências presentes são explicitamente normais ou negativas
- **WHEN** o painel é exibido
- **THEN** todos os resultados continuam visíveis
- **AND** nenhum alerta de possível infecção é destacado.

#### Scenario: Somente valor sem interpretação

- **GIVEN** existe valor laboratorial ancorado sem qualificação clínica explícita
- **WHEN** o painel é exibido
- **THEN** o valor permanece visível como não classificado
- **AND** não aciona alerta por threshold inferido.

### Requirement: Revisão infecciosa SHALL ser estritamente consultiva

Presença, ausência ou falha de extração da revisão MUST NOT adicionar `failed_requirements`, negar policy, alterar recomendação LLM2 reconciliada, suporte sugerido, decisão médica, validação do formulário, transição FSM, fila ou agendamento. O painel SHALL comunicar que se trata de apoio à revisão humana, não diagnóstico nem critério automático.

#### Scenario: Evidência preocupante com policy favorável

- **GIVEN** a policy de EDA + GTT não possui pendências e a revisão infecciosa gera alerta
- **WHEN** a recomendação final é reconciliada
- **THEN** o alerta fica visível
- **AND** a recomendação e a policy permanecem inalteradas.

#### Scenario: Extração infecciosa vazia

- **GIVEN** nenhuma evidência do vocabulário fechado foi extraída
- **WHEN** o caso segue pelo pipeline
- **THEN** a ausência não cria pendência nem bloqueio
- **AND** o médico ainda recebe a análise normal do procedimento.

#### Scenario: Médico decide de modo independente

- **GIVEN** o painel contém alerta de possível infecção
- **WHEN** o médico aprova ou nega o procedimento
- **THEN** a decisão segue as regras existentes
- **AND** o alerta não força nenhuma disposição.
