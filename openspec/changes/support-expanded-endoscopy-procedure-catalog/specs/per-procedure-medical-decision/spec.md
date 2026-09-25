## MODIFIED Requirements

### Requirement: Médico decide cada procedimento independentemente

O médico MUST poder aprovar ou negar qualquer identidade atômica do catálogo, respeitando a matriz fechada do conjunto autorizado final. Um pacote SHALL receber uma única decisão; somente EDA + Colonoscopia SHALL manter duas rows e decisões independentes.

#### Scenario: Procedimento especializado detectado

- **GIVEN** Ecoendoscopia ou CPRE foi detectada
- **WHEN** o médico aprova o procedimento e escolhe suporte/fluxo
- **THEN** somente aquele procedimento compõe o conjunto autorizado
- **AND** o caso segue o fluxo operacional existente.

#### Scenario: Pacote detectado

- **GIVEN** EDA + GTT, EDA + Cápsula, EDA + Dilatação ou uma Retossigmoidoscopia foi detectada
- **WHEN** o médico aprova o procedimento e escolhe suporte/fluxo
- **THEN** somente aquela identidade compõe o conjunto autorizado
- **AND** o caso segue o fluxo operacional existente.

#### Scenario: Aprovação parcial de combinado

- **GIVEN** EDA e Colonoscopia foram detectadas
- **WHEN** o médico aprova EDA e nega Colonoscopia com motivo
- **THEN** somente EDA compõe o conjunto autorizado
- **AND** a negativa fica auditada na row própria.

#### Scenario: Negativa integral

- **GIVEN** um singleton ou EDA + Colonoscopia foi detectado
- **WHEN** o médico nega todos os componentes com razão própria
- **THEN** o caso segue o fluxo de negativa existente
- **AND** não há procedimento autorizado.

### Requirement: Médico pode incluir ou substituir procedimento

A decisão médica MUST permitir aprovar qualquer identidade canônica não detectada, com justificativa, sem reexecutar LLM, sem recalcular policy do destino e sem reapresentar sugestão automática. A operação MUST negar/incluir componentes atomicamente e validar somente matriz estrutural, lock, permissão e FSM.

#### Scenario: Troca de EDA para CPRE

- **GIVEN** somente EDA foi detectada
- **WHEN** o médico escolhe trocar e aprovar como CPRE, informando as razões exigidas
- **THEN** EDA fica negada e CPRE aprovada
- **AND** nenhum job LLM ou policy de CPRE é executado.

#### Scenario: Troca de EDA para EDA + Dilatação

- **GIVEN** somente EDA foi detectada
- **WHEN** o médico escolhe trocar e aprovar como `eda_dilation`, informando as razões exigidas
- **THEN** EDA fica negada e EDA + Dilatação aprovada
- **AND** nenhum job LLM ou policy de destino é executado.

#### Scenario: Ampliação de EDA para combinado

- **GIVEN** somente EDA foi detectada
- **WHEN** o médico aprova EDA e inclui Colonoscopia
- **THEN** ambos ficam autorizados
- **AND** justificativa de inclusão é obrigatória
- **AND** nenhum job LLM novo é enfileirado.

#### Scenario: Troca completa

- **GIVEN** somente EDA foi detectada
- **WHEN** o médico nega EDA e inclui Colonoscopia
- **THEN** razão de negativa e justificativa de inclusão são obrigatórias
- **AND** somente Colonoscopia fica autorizada.

#### Scenario: Troca integral de combinado para singleton

- **GIVEN** EDA + Colonoscopia foi detectada
- **WHEN** o médico nega ambos e inclui uma única Retossigmoidoscopia com as razões exigidas
- **THEN** somente o destino fica autorizado
- **AND** nenhum caso ou agendamento adicional é criado.

#### Scenario: Conjunto final incompatível

- **GIVEN** o médico tenta aprovar uma variação junto de qualquer outro procedimento
- **WHEN** envia o formulário
- **THEN** o formulário é inválido
- **AND** nenhuma disposição, transição, evento ou mensagem é persistida.

### Requirement: Validações são por componente e fail-closed

Backend MUST rejeitar decisão incompleta ou contraditória sem persistência parcial. Procedimento negado ou aprovado sem ter sido detectado MUST exigir razão própria; aceite MUST exigir suporte e fluxo de admissão válidos. Labels/aliases exibidos MUST NOT substituir códigos canônicos na validação.

#### Scenario: Destino da troca sem justificativa

- **GIVEN** o médico tenta aprovar identidade não detectada
- **WHEN** não informa justificativa própria
- **THEN** o formulário é inválido
- **AND** nenhuma análise é reexecutada.

#### Scenario: Troca válida usa qualquer fluxo existente

- **GIVEN** o médico troca para uma nova identidade e preenche as razões
- **WHEN** seleciona agendamento, vinda imediata, UTI ou pediátrico atualmente suportado
- **THEN** o submit aceita o fluxo segundo as regras operacionais existentes
- **AND** nenhuma restrição nova de sala é aplicada e nenhuma policy do destino é executada.

#### Scenario: Componente negado sem motivo

- **GIVEN** o médico marcou um procedimento como negado
- **WHEN** envia sem razão específica
- **THEN** o formulário é inválido
- **AND** nenhuma disposição, evento ou transição é persistida.

#### Scenario: Procedimento adicionado sem motivo

- **GIVEN** o médico aprova procedimento não detectado
- **WHEN** não informa justificativa própria
- **THEN** o formulário é inválido
- **AND** nenhum pipeline é reexecutado.

#### Scenario: Código desconhecido ou alias em POST

- **GIVEN** request manipulado envia código desconhecido ou alias de apresentação
- **WHEN** o backend valida
- **THEN** o formulário é inválido
- **AND** nenhum pipeline é reexecutado.

### Requirement: Histórico é separado por procedimento

O relatório médico MUST consultar contexto anterior independentemente pelo código canônico exato de cada uma das dez identidades. Compartilhar família/profile MUST NOT contaminar histórico, contadores ou razões entre EDA e suas variações, Colonoscopia e Retossigmoidoscopias, ou quaisquer outros tipos.

#### Scenario: Históricos especializados distintos

- **GIVEN** paciente possui Ecoendoscopia prévia negada e CPRE prévia aprovada
- **WHEN** novo caso chega ao médico
- **THEN** cada seção usa a disposição e razão do procedimento correspondente
- **AND** aprovação anterior não incrementa contador de negativas.

#### Scenario: Histórico distinto

- **GIVEN** paciente possui EDA prévia negada e Colonoscopia prévia aceita
- **WHEN** caso EDA + Colonoscopia chega ao médico
- **THEN** cada seção mostra disposição e razão de sua row.

#### Scenario: EDA prévia não conta para EDA + GTT

- **GIVEN** paciente possui EDA prévia negada e nenhum histórico `eda_gastrostomy`
- **WHEN** novo caso EDA + GTT chega ao médico
- **THEN** a negativa EDA não aparece como negativa prévia do pacote
- **AND** o contador do pacote permanece sem essa ocorrência.

#### Scenario: Variações de dilatação distintas

- **GIVEN** paciente possui `eda_dilation` prévia e novo caso `rectosigmoidoscopy_dilation`
- **WHEN** o histórico é consultado
- **THEN** a ocorrência de EDA + Dilatação não integra o histórico da Retossigmoidoscopia + Dilatação.

#### Scenario: Histórico combinado permanece por row

- **GIVEN** caso anterior EDA + Colonoscopia teve decisões diferentes por componente
- **WHEN** o histórico de cada tipo é consultado
- **THEN** cada row mantém sua disposição e razão
- **AND** a semântica combinada existente permanece.

#### Scenario: Negativa global de agendamento

- **GIVEN** caso anterior combinado teve EDA negada, Colonoscopia aprovada e agenda negada
- **WHEN** o histórico por procedimento é consultado
- **THEN** EDA mantém negativa médica
- **AND** somente Colonoscopia mostra negativa de agendamento
- **AND** corrected resubmissions continuam deduplicados.

## ADDED Requirements

### Requirement: Detalhes consultivos SHALL acompanhar somente o procedimento de origem

O relatório médico SHALL exibir o local de dilatação somente em EDA + Dilatação e o painel infeccioso somente em EDA + GTT. Esses detalhes MUST NOT ser copiados para destino incluído pelo médico sem nova análise nem aparecer em procedimentos da mesma família por herança.

#### Scenario: EDA trocada para EDA + GTT

- **GIVEN** o pipeline analisou EDA simples e o médico decide trocar para EDA + GTT
- **WHEN** o formulário e o resultado são exibidos
- **THEN** nenhum painel infeccioso novo é sintetizado
- **AND** a troca segue sem reanálise.

#### Scenario: EDA + Dilatação detectada

- **GIVEN** o pipeline analisou `eda_dilation` e extraiu local ancorado
- **WHEN** o relatório médico é exibido
- **THEN** o local aparece como informação clínica
- **AND** não altera sugestão nem controles de decisão.
