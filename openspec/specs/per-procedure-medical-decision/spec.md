# per-procedure-medical-decision Specification

## Purpose
TBD - created by archiving change support-combined-eda-colonoscopy-workflow. Update Purpose after archive.
## Requirements
### Requirement: Médico decide cada procedimento independentemente

O médico MUST poder aprovar ou negar EDA e Colonoscopia separadamente dentro do mesmo caso.

#### Scenario: Aprovação parcial de combinado

- **GIVEN** EDA e Colonoscopia foram detectadas
- **WHEN** médico aprova EDA e nega Colonoscopia com motivo
- **THEN** caso é aceito operacionalmente
- **AND** somente EDA compõe o conjunto autorizado
- **AND** a negativa de Colonoscopia fica auditada com razão própria.

#### Scenario: Negativa integral

- **GIVEN** um ou dois procedimentos detectados
- **WHEN** médico nega todos com razão para cada componente
- **THEN** caso segue o fluxo de negativa existente
- **AND** não há procedimento autorizado.

### Requirement: Médico pode incluir ou substituir procedimento

A decisão médica MUST permitir aprovar procedimento não declarado/detectado sem reexecutar o LLM.

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

### Requirement: Validações são por componente e fail-closed

Backend MUST rejeitar decisão incompleta ou contraditória sem persistência parcial.

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

O relatório médico MUST consultar contexto anterior de EDA e Colonoscopia independentemente pela `CaseProcedure` correspondente. Negativa médica MUST usar disposição/razão do componente; negativa global de agendamento MUST aplicar-se somente a componente previamente aprovado; aprovação anterior MUST permanecer representável. A janela temporal e a deduplicação vigentes MUST ser preservadas; aprovação anterior MUST NOT incrementar o contador de negativas.

#### Scenario: Histórico distinto

- **GIVEN** paciente possui EDA prévia negada e Colonoscopia prévia aceita
- **WHEN** caso combinado chega ao médico
- **THEN** seção EDA mostra `doctor_denied` e a razão da row EDA
- **AND** seção Colonoscopia mostra `doctor_approved` a partir da row Colonoscopia
- **AND** ambas podem referenciar o mesmo caso anterior sem compartilhar decisão ou razão.

#### Scenario: Negativa global de agendamento

- **GIVEN** caso anterior combinado teve EDA negada pelo médico e Colonoscopia aprovada, seguida de agenda negada
- **WHEN** histórico por procedimento é consultado dentro da janela vigente
- **THEN** EDA mantém `doctor_denied`
- **AND** somente Colonoscopia mostra `appointment_denied`
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
