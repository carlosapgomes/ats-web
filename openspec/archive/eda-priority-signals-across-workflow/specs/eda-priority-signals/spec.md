# Capability: Sinalizações prioritárias de EDA

## ADDED Requirements

### Requirement: Ecoendoscopia é EDA suportada

O sistema MUST reconhecer solicitação explícita de ecoendoscopia como EDA suportada, mesmo sem a palavra literal `EDA`.

#### Scenario: Ecoendoscopia por nome completo

- **GIVEN** relatório cuja solicitação atual contém `ecoendoscopia`
- **WHEN** LLM1 e o scope gate processam o caso
- **THEN** o subtipo efetivo é `echoendoscopy`
- **AND** o caso não recebe `manual_review_required` por tipo desconhecido
- **AND** segue para avaliação médica.

#### Scenario: Sinônimos e acrônimo contextual

- **GIVEN** solicitação atual contendo `eco-endoscopia`, `ultrassonografia endoscópica`, `ultrassom endoscópico` ou `EUS` em contexto procedimental
- **WHEN** o detector de escopo classifica o exame
- **THEN** o exame é tratado como ecoendoscopia suportada.

#### Scenario: Ecoendoscopia com punção

- **GIVEN** solicitação de ecoendoscopia com punção, PAAF, biópsia, FNA ou FNB
- **WHEN** o caso é classificado
- **THEN** permanece no subtipo/sinal `echoendoscopy`
- **AND** nenhum subtipo adicional é exigido.

### Requirement: EDA suportada prevalece em solicitação mista

Uma solicitação atual que contenha EDA suportada ou ecoendoscopia MUST seguir o fluxo EDA, mesmo quando também menciona exame atualmente fora do escopo.

#### Scenario: Ecoendoscopia e CPRE

- **GIVEN** solicitação atual que contém ecoendoscopia e CPRE
- **WHEN** o scope gate reconcilia os sinais
- **THEN** o caso segue o fluxo EDA.

#### Scenario: EDA e colonoscopia

- **GIVEN** solicitação atual que contém EDA e colonoscopia
- **WHEN** o scope gate reconcilia os sinais
- **THEN** o caso segue o fluxo EDA.

#### Scenario: Somente exame fora do escopo

- **GIVEN** solicitação atual que contém somente colonoscopia ou CPRE e nenhuma EDA/ecoendoscopia suportada
- **WHEN** o scope gate classifica o caso
- **THEN** o comportamento de revisão manual existente é preservado.

### Requirement: Ecoendoscopia usa policy padrão

Ecoendoscopia MUST seguir as mesmas exigências pré-procedimento da EDA padrão.

#### Scenario: Exames mínimos ausentes

- **GIVEN** ecoendoscopia com exame mínimo obrigatório ausente
- **WHEN** a policy determinística é avaliada
- **THEN** aplica a mesma negativa/pendência que seria aplicada à EDA padrão
- **AND** não usa `foreign_body_exception`.

#### Scenario: Critérios padrão atendidos

- **GIVEN** ecoendoscopia com critérios padrão atendidos
- **WHEN** policy e reconciliação são executadas
- **THEN** o caso permanece elegível para sugestão/avaliação médica usual.

### Requirement: Sinalizações canônicas persistidas

O sistema MUST persistir no caso uma coleção versionada, ordenada e deduplicada de sinalizações prioritárias.

Códigos permitidos:

- `foreign_body`;
- `caustic_ingestion`;
- `pediatric`;
- `echoendoscopy`;
- `esophageal_dilation`;
- `gastrostomy`.

#### Scenario: Múltiplos sinais coexistem

- **GIVEN** paciente pediátrico com ingestão cáustica e solicitação de ecoendoscopia
- **WHEN** os sinais são resolvidos
- **THEN** os três códigos são persistidos
- **AND** aparecem na ordem canônica
- **AND** nenhum enum combinatório é criado.

#### Scenario: Payload malformado

- **GIVEN** caso legado com valor de sinalização ausente ou malformado
- **WHEN** uma tela tenta projetar badges
- **THEN** nenhum erro 500 ocorre
- **AND** itens desconhecidos/inválidos são ignorados.

### Requirement: Detecção conservadora com negação

Detectores textuais MUST normalizar acentos/case/whitespace e evitar sinais positivos quando houver negação explícita aplicável.

#### Scenario: Corpo estranho negado

- **GIVEN** texto `sem corpo estranho`, `corpo estranho descartado`, `nega ingestão de corpo estranho` ou equivalente
- **WHEN** os sinais são resolvidos
- **THEN** o fallback textual não cria `foreign_body`, salvo existência de sinal estruturado positivo independente e válido.

#### Scenario: Ingestão cáustica negada

- **GIVEN** texto com negação explícita de ingestão cáustica/corrosiva
- **WHEN** os sinais são resolvidos
- **THEN** `caustic_ingestion` não é criado.

#### Scenario: Dilatação genérica

- **GIVEN** texto contendo somente a palavra genérica `dilatação`, sem contexto esofágico/procedimental
- **WHEN** os sinais são resolvidos
- **THEN** `esophageal_dilation` não é criado.

#### Scenario: EUS sem contexto

- **GIVEN** acrônimo `EUS` sem contexto de exame, solicitação ou procedimento
- **WHEN** os sinais são resolvidos
- **THEN** `echoendoscopy` não é criado apenas pelo acrônimo isolado.

### Requirement: Backfill limitado a casos abertos

A implantação MUST classificar casos existentes ainda abertos sem reexecutar LLM e sem alterar casos históricos encerrados.

#### Scenario: Caso aberto elegível

- **GIVEN** caso com `status != CLEANED`, texto/dados suficientes e sinais ainda vazios
- **WHEN** a migration de backfill é executada
- **THEN** os sinais canônicos são persistidos.

#### Scenario: Caso encerrado preexistente

- **GIVEN** caso `CLEANED` criado antes do change e sem sinais
- **WHEN** a migration é executada
- **THEN** a coleção permanece vazia.

#### Scenario: Idempotência

- **GIVEN** caso aberto com sinais já persistidos
- **WHEN** o backfill é invocado defensivamente
- **THEN** os sinais existentes não são sobrescritos
- **AND** status, decisões, eventos e agenda não mudam.

### Requirement: Continuidade visual no fluxo

O mesmo conjunto persistido de sinalizações MUST ser exibido ao médico, CHD e NIR por um partial SSR compartilhado.

#### Scenario: Fila e avaliação médica

- **GIVEN** caso com sinalizações persistidas em `WAIT_DOCTOR`
- **WHEN** o médico vê a fila e abre a avaliação
- **THEN** os mesmos badges aparecem na fila e no topo do relatório.

#### Scenario: CHD

- **GIVEN** caso aceito para agendamento com sinalizações persistidas
- **WHEN** o CHD vê a fila, abre a confirmação ou consulta o detalhe
- **THEN** os mesmos badges permanecem visíveis.

#### Scenario: NIR

- **GIVEN** caso com sinalizações persistidas durante processamento, resultado ou encerramento posterior
- **WHEN** o NIR vê lista ou detalhe
- **THEN** os mesmos badges permanecem visíveis.

#### Scenario: Caso sem sinais

- **GIVEN** caso cuja coleção persistida está vazia
- **WHEN** qualquer uma das telas é renderizada
- **THEN** nenhum container vazio de sinalizações é exibido.

### Requirement: Hierarquia visual e corpo do relatório

Corpo estranho e ingestão cáustica MUST ter a mesma ênfase de alerta. Procedimentos especiais MUST ter ênfase operacional consistente. O corpo do relatório médico MUST receber informação determinística.

#### Scenario: Alertas clínicos

- **GIVEN** caso com `foreign_body` e `caustic_ingestion`
- **WHEN** o relatório médico é renderizado
- **THEN** ambos usam a mesma classe/nível visual de alerta
- **AND** ambos aparecem no início de `Achados críticos`.

#### Scenario: Contextos prioritários

- **GIVEN** caso com pediatria, ecoendoscopia, dilatação e/ou gastrostomia
- **WHEN** o relatório médico é renderizado
- **THEN** os badges aparecem no topo
- **AND** uma linha determinística de contextos prioritários aparece no `Resumo clínico`.

### Requirement: Badges não automatizam operação

As sinalizações MUST ser exclusivamente informativas neste change.

#### Scenario: Ecoendoscopia aceita

- **GIVEN** médico aceita ecoendoscopia com fluxo `scheduled`
- **WHEN** a decisão é submetida
- **THEN** o caso segue o FSM normal até `WAIT_APPT`
- **AND** o CHD agenda pelo formulário existente
- **AND** o NIR recebe o resultado pelo fluxo existente.

#### Scenario: Ausência de automação adicional

- **GIVEN** qualquer sinal prioritário
- **WHEN** o caso percorre o sistema
- **THEN** não há atribuição automática de médico/executor
- **AND** nenhuma permissão é restringida
- **AND** nenhum turno de agenda é validado ou bloqueado pelo badge.
