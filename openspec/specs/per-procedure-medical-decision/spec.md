# per-procedure-medical-decision Specification

## Purpose
TBD - created by archiving change support-combined-eda-colonoscopy-workflow. Update Purpose after archive.

## Requirements

### Requirement: Médico decide cada procedimento independentemente

O médico MUST poder aprovar ou negar EDA, Colonoscopia, Ecoendoscopia e CPRE, respeitando a matriz fechada do conjunto autorizado final.

#### Scenario: Procedimento especializado detectado

- **GIVEN** Ecoendoscopia ou CPRE foi detectada
- **WHEN** médico aprova o procedimento e escolhe suporte/fluxo
- **THEN** somente aquele procedimento compõe o conjunto autorizado
- **AND** o caso segue o fluxo operacional existente.

#### Scenario: Aprovação parcial de combinado

- **GIVEN** EDA e Colonoscopia foram detectadas
- **WHEN** médico aprova EDA e nega Colonoscopia com motivo
- **THEN** caso é aceito operacionalmente
- **AND** somente EDA compõe o conjunto autorizado
- **AND** a negativa de Colonoscopia fica auditada com razão própria.

#### Scenario: Negativa integral

- **GIVEN** um ou dois procedimentos válidos foram detectados
- **WHEN** médico nega todos com razão para cada componente
- **THEN** caso segue o fluxo de negativa existente
- **AND** não há procedimento autorizado.

### Requirement: Médico pode incluir ou substituir procedimento

A decisão médica MUST permitir aprovar qualquer procedimento suportado não detectado, com justificativa, sem reexecutar LLM, sem recalcular policy do destino e sem reapresentar sugestão automática. A operação MUST negar/incluir os componentes atomicamente e validar somente regras estruturais, lock, permissão e FSM.

#### Scenario: Troca de EDA para CPRE

- **GIVEN** somente EDA foi detectada
- **WHEN** médico escolhe trocar e aprovar como CPRE, informando as razões exigidas
- **THEN** EDA fica negada e CPRE aprovada
- **AND** nenhum job LLM é enfileirado
- **AND** nenhuma policy de CPRE é executada ou exibida novamente.

#### Scenario: Ampliação de EDA para combinado

- **GIVEN** somente EDA foi detectada
- **WHEN** médico aprova EDA e inclui Colonoscopia
- **THEN** ambos ficam autorizados
- **AND** justificativa de inclusão de Colonoscopia é obrigatória
- **AND** nenhum job LLM novo é enfileirado.

#### Scenario: Troca completa

- **GIVEN** somente EDA foi detectada
- **WHEN** médico nega EDA e inclui Colonoscopia
- **THEN** razão de negativa EDA e justificativa de inclusão Colonoscopia são obrigatórias
- **AND** somente Colonoscopia fica autorizada.

#### Scenario: Conjunto final incompatível

- **GIVEN** médico tenta aprovar Ecoendoscopia ou CPRE junto de outro procedimento
- **WHEN** envia o formulário
- **THEN** formulário é inválido
- **AND** nenhuma disposição, transição, evento ou mensagem é persistida.

### Requirement: Validações são por componente e fail-closed

Backend MUST rejeitar decisão incompleta ou contraditória sem persistência parcial. Procedimento negado ou aprovado sem ter sido detectado MUST exigir razão própria; aceite MUST exigir suporte e fluxo de admissão válidos.

#### Scenario: Destino da troca sem justificativa

- **GIVEN** médico tenta aprovar Ecoendoscopia ou CPRE não detectada
- **WHEN** não informa justificativa própria
- **THEN** formulário é inválido
- **AND** nenhuma análise é reexecutada.

#### Scenario: Troca válida usa qualquer fluxo existente

- **GIVEN** médico troca para procedimento especializado e preenche razões
- **WHEN** seleciona agendamento, vinda imediata, fluxo de UTI ou pediátrico atualmente suportado
- **THEN** submit aceita o fluxo segundo as regras operacionais existentes
- **AND** nenhuma restrição de sala é aplicada.

#### Scenario: Componente negado sem motivo

- **GIVEN** médico marcou um procedimento como negado
- **WHEN** envia sem razão específica
- **THEN** formulário é inválido
- **AND** nenhuma disposição, evento ou transição é persistida.

#### Scenario: Procedimento adicionado sem motivo

- **GIVEN** médico aprova procedimento não detectado
- **WHEN** não informa justificativa própria
- **THEN** formulário é inválido
- **AND** nenhum pipeline é reexecutado.

### Requirement: Suporte global permanece decisão médica

O sistema MUST sugerir o nível mais restritivo entre recomendações por procedimento, mas MUST preservar a seleção final do médico.

#### Scenario: Recomendações diferentes

- **GIVEN** EDA sugere nenhum suporte e Colonoscopia sugere anestesista
- **WHEN** relatório/formulário é exibido
- **THEN** sugestão global é anestesista
- **AND** médico ainda escolhe o suporte final.

### Requirement: Histórico é separado por procedimento

O relatório médico MUST consultar contexto anterior de EDA, Colonoscopia, Ecoendoscopia e CPRE independentemente pela projeção correspondente. Decisões de um tipo MUST NOT contaminar o histórico de outro.

#### Scenario: Históricos especializados distintos

- **GIVEN** paciente possui Ecoendoscopia prévia negada e CPRE prévia aprovada
- **WHEN** novo caso chega ao médico
- **THEN** cada seção usa a disposição e razão do procedimento correspondente
- **AND** aprovação anterior não incrementa contador de negativas.

#### Scenario: Histórico distinto

- **GIVEN** paciente possui EDA prévia negada e Colonoscopia prévia aceita
- **WHEN** caso EDA + Colonoscopia chega ao médico
- **THEN** seção EDA mostra a negativa e razão da row EDA
- **AND** seção Colonoscopia mostra a aprovação da row Colonoscopia.

#### Scenario: Negativa global de agendamento

- **GIVEN** caso anterior combinado teve EDA negada, Colonoscopia aprovada e agenda negada
- **WHEN** histórico por procedimento é consultado na janela vigente
- **THEN** EDA mantém negativa médica
- **AND** somente Colonoscopia mostra negativa de agendamento
- **AND** corrected resubmissions continuam deduplicados.

### Requirement: Concorrência, permissão e FSM são preservadas

Decisão por procedimento MUST reutilizar role guard, lease/lock e transições atuais.

#### Scenario: Submit sem lock válido

- **GIVEN** caso combinado em `WAIT_DOCTOR`
- **WHEN** submit não possui lease válida
- **THEN** nenhuma decisão por componente é persistida
- **AND** FSM permanece inalterada.

### Requirement: Re-renderização com erro de validação SHALL reposicionar o médico no formulário

A página de decisão médica SHALL exibir um banner de erro no topo do conteúdo sempre que uma submissão falhar por validação, com mensagem clara e botão de âncora para o formulário, de modo que os erros fiquem visíveis sem depender de rolagem automática.

#### Scenario: Submit com erro de validação

- **GIVEN** o médico preencheu o formulário de decisão em um caso `WAIT_DOCTOR`
- **WHEN** o submit é rejeitado por validação e a página é re-renderizada
- **THEN** o topo do conteúdo exibe um banner de erro com a contagem de campos com erro
- **AND** o banner contém um botão de âncora apontando para o formulário de decisão
- **AND** a página não depende de rolagem automática para revelar os erros

#### Scenario: Página sem erros

- **GIVEN** o médico abre a tela de decisão sem submissão inválida
- **WHEN** a página é renderizada
- **THEN** nenhum banner de erro é exibido

### Requirement: Relatório SHALL mostrar pendências automáticas agregadas

Para procedimento analisado pelo pipeline, o relatório médico SHALL exibir todas as pendências determinísticas em uma única apresentação, preservando a sugestão reconciliada. O relatório SHALL informar que anexos não participaram da sugestão automática no primeiro rollout.

#### Scenario: Laboratório e imagem ausentes em CPRE

- **GIVEN** análise de CPRE encontra mais de um exame mínimo ausente e nenhuma imagem abdominal qualificante
- **WHEN** relatório médico é exibido
- **THEN** todas as pendências aparecem juntas
- **AND** a sugestão é negar
- **AND** o médico ainda pode aprovar.

#### Scenario: Troca médica não reapresenta checklist

- **GIVEN** o pipeline analisou EDA e o médico decidiu trocar para CPRE
- **WHEN** confirma a troca
- **THEN** o sistema não calcula nem reapresenta pendências de CPRE
- **AND** segue diretamente com a decisão aprovada.
