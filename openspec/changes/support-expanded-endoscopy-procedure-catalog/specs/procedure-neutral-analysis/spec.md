## MODIFIED Requirements

### Requirement: História clínica comum é extraída uma única vez

Cada novo processamento MUST executar uma única extração LLM1 procedure-neutral 4.0 por caso e MUST representar as dez identidades atômicas do catálogo como coleção tipada sujeita à matriz fechada. EDA + Colonoscopia SHALL continuar representada por dois itens no mesmo artefato; cada pacote SHALL ocupar um único item.

#### Scenario: Solicitação especializada válida

- **GIVEN** o texto contém solicitação atual sustentada de Ecoendoscopia ou CPRE
- **WHEN** LLM1 4.0 processa o caso
- **THEN** produz uma única história/pré-operatório comum
- **AND** `requested_procedures` contém exatamente o procedimento especializado
- **AND** não o representa também como EDA.

#### Scenario: Solicitação de pacote válida

- **GIVEN** o texto contém solicitação atual sustentada de EDA + GTT, EDA + Cápsula ou EDA + Dilatação
- **WHEN** LLM1 4.0 processa o caso
- **THEN** produz uma única história/pré-operatório comum
- **AND** `requested_procedures` contém exatamente a identidade atômica correspondente
- **AND** não inclui EDA base pela mesma solicitação.

#### Scenario: Solicitação combinada válida

- **GIVEN** o texto contém solicitações atuais sustentadas de EDA e Colonoscopia
- **WHEN** LLM1 4.0 processa o caso
- **THEN** produz uma única história/pré-operatório comum
- **AND** `requested_procedures` contém exatamente EDA e Colonoscopia.

#### Scenario: Procedimento inventado

- **GIVEN** apenas uma identidade possui evidência de solicitação atual
- **WHEN** a resposta LLM1 inclui outra identidade sem evidência válida
- **THEN** contrato/reconciliação rejeita ou encaminha para revisão
- **AND** o procedimento inventado não se torna detectado silenciosamente.

### Requirement: Policy e recomendação são por procedimento

O sistema MUST avaliar separadamente cada procedimento reconciliado segundo seu profile e MUST executar uma única análise LLM2 4.0 conjunta por caso. A chamada MUST receber somente itens do conjunto reconciliado e uma lista fechada explícita. O artefato LLM1 persistido MUST permanecer inalterado.

A resposta LLM2 MUST conter exatamente uma recomendação para cada procedimento reconciliado, sem omissão, duplicata ou adição. Diante exclusivamente de resposta schema-válida com conjunto divergente, o serviço MAY realizar no máximo um retry corretivo específico. Um segundo mismatch MUST falhar explicitamente e MUST NOT produzir artefato parcial.

#### Scenario: Recomendação de Ecoendoscopia

- **GIVEN** somente Ecoendoscopia foi reconciliada
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** o prompt declara `["echoendoscopy"]` como conjunto fechado
- **AND** a resposta contém exatamente uma recomendação Ecoendoscopia.

#### Scenario: Recomendação de CPRE

- **GIVEN** somente CPRE foi reconciliada
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** o prompt declara `["cpre"]` como conjunto fechado
- **AND** a resposta contém exatamente uma recomendação CPRE.

#### Scenario: Recomendação de pacote atômico

- **GIVEN** somente EDA + GTT foi reconciliada
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** o prompt declara `["eda_gastrostomy"]` como conjunto fechado
- **AND** resposta válida contém exatamente uma recomendação para essa identidade.

#### Scenario: Recomendações divergentes no combinado

- **GIVEN** caso EDA + Colonoscopia possui resultados de policy diferentes
- **WHEN** LLM2 4.0 responde
- **THEN** há uma recomendação por procedimento
- **AND** suporte global sugerido é o nível mais restritivo.

#### Scenario: LLM1 contém ambos mas somente EDA é reconciliada

- **GIVEN** o artefato LLM1 contém EDA e Colonoscopia
- **AND** somente EDA integra o conjunto reconciliado
- **WHEN** o orchestrator monta LLM2
- **THEN** a cópia efêmera e a lista fechada contêm somente EDA
- **AND** o artefato persistido continua inalterado.

#### Scenario: LLM1 contém ambos mas somente Colonoscopia é reconciliada

- **GIVEN** o artefato LLM1 contém EDA e Colonoscopia
- **AND** somente Colonoscopia integra o conjunto reconciliado
- **WHEN** o orchestrator monta LLM2
- **THEN** a cópia efêmera e a lista fechada contêm somente Colonoscopia
- **AND** o artefato persistido continua inalterado.

#### Scenario: Conjunto combinado permanece completo

- **GIVEN** EDA e Colonoscopia foram reconciliadas
- **WHEN** o orchestrator monta LLM2
- **THEN** a cópia efêmera mantém os dois itens
- **AND** a resposta válida contém duas recomendações.

#### Scenario: Conjunto combinado permanece convencional

- **GIVEN** EDA e Colonoscopia foram reconciliadas
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** o prompt declara `["eda", "colonoscopy"]` como conjunto fechado
- **AND** nenhuma opção especializada ou variação é adicionada.

#### Scenario: Artefato bruto contém identidade removida pela reconciliação

- **GIVEN** o artefato LLM1 contém mais itens que o conjunto reconciliado
- **WHEN** o orchestrator monta LLM2
- **THEN** a cópia efêmera contém somente o conjunto reconciliado
- **AND** o artefato persistido continua inalterado.

#### Scenario: Primeiro mismatch é corrigido

- **GIVEN** o conjunto reconciliado foi incluído explicitamente no prompt
- **AND** a primeira resposta schema-válida omite ou adiciona procedimento
- **WHEN** o serviço detecta mismatch
- **THEN** executa exatamente uma tentativa corretiva com o mesmo conjunto
- **AND** aceita a segunda resposta somente se todas as validações passarem.

#### Scenario: Mismatch persiste após retry

- **GIVEN** a tentativa corretiva já foi consumida
- **WHEN** a resposta ainda diverge
- **THEN** o pipeline segue tratamento fail-closed
- **AND** nenhuma recomendação parcial chega ao médico.

#### Scenario: Erro não relacionado ao conjunto

- **GIVEN** a resposta é inválida por JSON, schema, duplicata, ids ou idioma
- **WHEN** a validação falha
- **THEN** o retry específico de conjunto não é executado
- **AND** o erro permanece explícito.

### Requirement: Artefatos legados continuam legíveis

Presenters e auditoria MUST ler schemas 1.1, 2.0 e 3.0 históricos e schema 4.0 novo sem reescrever JSON antigo. Subtipos/sinais históricos SHALL continuar apresentáveis segundo sua versão, mas novos artefatos 4.0 MUST usar identidades independentes e MUST NOT duplicar GTT, cápsula ou dilatação como procedimento e sinal derivado equivalente.

#### Scenario: Caso antigo de Ecoendoscopia

- **GIVEN** caso 1.1/2.0 possui subtipo ou sinal `echoendoscopy`
- **WHEN** usuário autorizado abre detalhe/histórico após cutover
- **THEN** o conteúdo continua renderizável
- **AND** nenhuma row `echoendoscopy` é criada automaticamente.

#### Scenario: Caso antigo com sinal de gastrostomia

- **GIVEN** caso 1.1/2.0/3.0 possui EDA e sinal/subtipo legado de gastrostomia
- **WHEN** usuário autorizado abre detalhe/histórico após cutover
- **THEN** o conteúdo continua renderizável
- **AND** nenhuma row `eda_gastrostomy` é criada automaticamente.

#### Scenario: Caso antigo aberto após cutover

- **GIVEN** caso possui `structured_data` anterior a 4.0
- **WHEN** usuário autorizado abre detalhe/histórico
- **THEN** o conteúdo continua renderizável
- **AND** nenhuma migration altera o JSON clínico.

## ADDED Requirements

### Requirement: Dispatch LLM de produção SHALL vincular strict schema ao contrato 4.0

O pipeline de produção, sem cliente LLM injetado, SHALL vincular novos processamentos exclusivamente aos strict schemas 4.0. Schemas 1.1/2.0/3.0 SHALL permanecer somente em adapters e leitores históricos após o cutover.

#### Scenario: LLM1 de produção recebe strict schema 4.0

- **GIVEN** o pipeline cria o cliente LLM1 sem injeção de teste após o cutover
- **WHEN** a chamada à API é montada
- **THEN** `response_format` usa `json_schema` strict
- **AND** o schema vinculado fixa `schema_version` em `"4.0"`
- **AND** aceita as dez identidades e detalhes clínicos tipados aplicáveis.

#### Scenario: LLM2 de produção recebe strict schema 4.0

- **GIVEN** o pipeline cria o cliente LLM2 sem injeção de teste após o cutover
- **WHEN** a chamada à API é montada
- **THEN** `response_format` usa `json_schema` strict
- **AND** `procedure_recommendations` aceita as dez identidades.

#### Scenario: Schema 4.0 é compatível com strict mode

- **GIVEN** o JSON Schema de LLM1 ou LLM2 4.0
- **WHEN** a normalização strict é aplicada
- **THEN** todo nó objeto declara `additionalProperties: false`
- **AND** todo nó objeto lista todas as propriedades em `required`
- **AND** nenhuma construção incompatível permanece.

## MODIFIED Requirements

### Requirement: Evidência abdominal SHALL separar modalidade, anatomia e achado

LLM1 4.0 SHALL preservar a extração 3.0 de imagens do relatório principal em coleção tipada com modalidade, localização anatômica, presença de conclusão/achado, trecho-fonte e data opcional. `tracked_exams` textual e anexos MUST NOT satisfazer a hard rule de Ecoendoscopia/CPRE.

#### Scenario: TC sem anatomia

- **GIVEN** o relatório menciona resultado de TC sem indicar abdome/abdome superior
- **WHEN** evidência é normalizada
- **THEN** localização permanece não especificada
- **AND** a imagem não satisfaz Ecoendoscopia nem CPRE.

#### Scenario: Mera solicitação de imagem

- **GIVEN** o relatório apenas solicita ou agenda uma imagem
- **WHEN** LLM1 extrai o documento
- **THEN** `report_finding_present` não é verdadeiro
- **AND** a imagem não satisfaz a policy.

#### Scenario: Data antiga disponível

- **GIVEN** imagem qualificante possui conclusão/achado e data antiga
- **WHEN** a policy executa
- **THEN** a data é preservada
- **AND** antiguidade não invalida o requisito.

## REMOVED Requirements

### Requirement: Dispatch LLM de produção SHALL vincular strict schema ao contrato 3.0

**Reason:** O writer 3.0 é fechado em quatro identidades e não pode representar os pacotes atômicos nem os detalhes clínicos deste change.

**Migration:** Drenar jobs 3.0, ativar web/workers/prompts 4.0 de forma coordenada e manter 3.0 somente nos adapters/leitores históricos.

## ADDED Requirements

### Requirement: Detalhe de EDA + Dilatação SHALL ser anatômico e informativo

Para `eda_dilation`, LLM1 4.0 SHALL extrair exatamente um local entre `esophagus`, `pylorus`, `duodenum`, `anastomosis`, `jejunum`, `other` e `unknown`, acompanhado de trecho-fonte quando documentado. O local SHALL NOT criar identidade nova, modificar profile/policy, sugestão ou disposição e SHALL permanecer `unknown` quando o texto não sustentar uma opção.

#### Scenario: Local explícito

- **GIVEN** a solicitação atual de EDA + Dilatação informa dilatação de piloro
- **WHEN** LLM1 4.0 é validado e apresentado
- **THEN** o local é `pylorus`
- **AND** o procedimento continua `eda_dilation`.

#### Scenario: Local ausente

- **GIVEN** a solicitação pede EDA + Dilatação sem informar local
- **WHEN** LLM1 4.0 é validado
- **THEN** o local é `unknown`
- **AND** nenhuma pendência clínica é criada.

#### Scenario: Local não ancorado

- **GIVEN** a resposta declara um local cujo trecho não existe no relatório principal
- **WHEN** a evidência é verificada
- **THEN** o local apresentado cai para `unknown`
- **AND** a policy permanece inalterada.

### Requirement: Writers 3.0 SHALL encerrar antes do primeiro write 4.0

O cutover SHALL drenar jobs de análise, ativar web, workers e prompts 4.0 de forma coordenada e MUST NOT permitir writers 3.0 e 4.0 concorrentes. Nenhuma nova flag de produto SHALL mediar o rollout das identidades deste change.

#### Scenario: Job 3.0 em voo

- **GIVEN** existe job 3.0 ainda executando
- **WHEN** a operação tenta iniciar o writer 4.0
- **THEN** o cutover é interrompido até a drenagem
- **AND** nenhum write 4.0 é iniciado.

#### Scenario: Primeiro write 4.0 concluído

- **GIVEN** ao menos um artefato 4.0 foi persistido
- **WHEN** ocorre incidente após o cutover
- **THEN** rollback para writer 3.0 não é suportado
- **AND** a recuperação preserva dados e corrige para frente.
