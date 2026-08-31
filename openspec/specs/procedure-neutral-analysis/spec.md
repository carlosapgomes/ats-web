# procedure-neutral-analysis Specification

## Purpose
TBD - created by archiving change support-combined-eda-colonoscopy-workflow. Update Purpose after archive.
## Requirements
### Requirement: História clínica comum é extraída uma única vez

Cada novo processamento MUST executar uma única extração LLM1 procedure-neutral por caso e MUST representar os procedimentos solicitados como coleção tipada.

#### Scenario: Solicitação combinada válida

- **GIVEN** texto contém solicitações atuais sustentadas de EDA e Colonoscopia
- **WHEN** LLM1 v2 processa o caso
- **THEN** produz uma única história/pré-operatório comum
- **AND** `requested_procedures` contém exatamente EDA e Colonoscopia
- **AND** não existem dois artefatos concorrentes de paciente/história.

#### Scenario: Procedimento inventado

- **GIVEN** apenas EDA possui evidência de solicitação atual
- **WHEN** resposta LLM1 inclui Colonoscopia sem evidência válida
- **THEN** contrato/reconciliação rejeita ou encaminha para revisão
- **AND** Colonoscopia não se torna procedimento detectado silenciosamente.

### Requirement: Detecção reconcilia declaração sem apagar proveniência

O sistema MUST preservar a declaração do NIR e persistir detecção separadamente.

#### Scenario: Upgrade automático para combinado

- **GIVEN** NIR declarou somente EDA ou somente Colonoscopia
- **AND** evidência forte confirma duas solicitações atuais
- **WHEN** reconciliação executa
- **THEN** ambos os procedimentos ficam detectados
- **AND** caso segue ao médico sem ACK prévio do NIR
- **AND** evento registra declaração original, seleção detectada e base codificada da evidência.

#### Scenario: Combinado declarado mas somente um detectado

- **GIVEN** NIR declarou EDA + Colonoscopia
- **WHEN** apenas um procedimento é detectado
- **THEN** caso retorna à revisão do NIR
- **AND** não entra em `WAIT_DOCTOR`.

#### Scenario: Tipos únicos contraditórios

- **GIVEN** NIR declarou EDA e somente Colonoscopia é detectada, ou vice-versa
- **WHEN** reconciliação executa
- **THEN** caso retorna ao NIR como mismatch
- **AND** nenhum upgrade/swap silencioso ocorre.

### Requirement: Referências históricas e negações não criam combinação

Detecção MUST qualificar cada ocorrência por solicitação atual, histórico e negação.

#### Scenario: EDA histórica e Colonoscopia atual

- **GIVEN** texto informa EDA realizada no passado e solicita Colonoscopia agora
- **WHEN** detector executa
- **THEN** somente Colonoscopia fica detectada.

#### Scenario: Outro procedimento negado

- **GIVEN** texto solicita EDA e nega indicação de Colonoscopia
- **WHEN** detector executa
- **THEN** somente EDA fica detectada.

### Requirement: Policy e recomendação são por procedimento

O sistema MUST avaliar cada procedimento reconciliado separadamente e MUST executar uma única análise LLM2 conjunta por caso. A tentativa inicial do LLM2 MUST receber uma visão efêmera do `structured_data` cujo `requested_procedures` contenha somente itens originais pertencentes ao conjunto reconciliado, além de uma lista JSON explícita que defina esse conjunto como fechado. O artefato LLM1 persistido MUST permanecer inalterado.

A resposta LLM2 MUST conter exatamente uma recomendação para cada procedimento reconciliado, sem omissão, duplicata ou adição. Diante exclusivamente de uma resposta schema-válida cujo conjunto seja divergente, o serviço MAY realizar no máximo um retry corretivo específico. Um segundo mismatch MUST falhar de forma explícita e MUST NOT produzir artefato parcial. Erros de outra natureza MUST NOT consumir esse retry. O retry de idioma pt-BR existente MAY permanecer independente, desde que todos os orçamentos sejam finitos.

#### Scenario: Recomendações divergentes no combinado

- **GIVEN** caso combinado com resultados de policy diferentes
- **WHEN** LLM2 v2 responde
- **THEN** há uma recomendação para EDA e outra para Colonoscopia
- **AND** cada item referencia exatamente um procedimento reconciliado
- **AND** suporte global sugerido é o nível mais restritivo.

#### Scenario: LLM1 contém ambos mas somente EDA é reconciliada

- **GIVEN** o artefato validado do LLM1 contém EDA e Colonoscopia em `requested_procedures`
- **AND** detecção e reconciliação qualificam somente EDA como solicitação atual
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** a cópia efêmera contém somente o item EDA em `requested_procedures`
- **AND** o prompt declara `["eda"]` como lista fechada
- **AND** policy, prior context e validação usam somente EDA
- **AND** o `structured_data` persistido continua contendo os dois itens originais.

#### Scenario: LLM1 contém ambos mas somente Colonoscopia é reconciliada

- **GIVEN** o artefato validado do LLM1 contém EDA e Colonoscopia em `requested_procedures`
- **AND** detecção e reconciliação qualificam somente Colonoscopia como solicitação atual
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** a cópia efêmera contém somente o item Colonoscopia em `requested_procedures`
- **AND** o prompt declara `["colonoscopy"]` como lista fechada
- **AND** policy, prior context e validação usam somente Colonoscopia
- **AND** o `structured_data` persistido continua contendo os dois itens originais.

#### Scenario: Conjunto combinado permanece completo

- **GIVEN** EDA e Colonoscopia foram reconciliadas como solicitações atuais
- **WHEN** o orchestrator monta a chamada LLM2
- **THEN** a cópia efêmera mantém os dois itens originais
- **AND** o prompt declara `["eda", "colonoscopy"]` como lista fechada
- **AND** a resposta válida contém exatamente duas recomendações.

#### Scenario: Primeiro mismatch é corrigido

- **GIVEN** o conjunto reconciliado conhecido foi incluído explicitamente no prompt
- **AND** a primeira resposta schema-válida omite ou adiciona um procedimento
- **WHEN** o serviço detecta `procedure set mismatch`
- **THEN** executa exatamente uma tentativa corretiva adicional com o mesmo conjunto fechado
- **AND** aceita a segunda resposta somente se parse, schema, IDs, conjunto e idioma forem válidos.

#### Scenario: Mismatch persiste após retry

- **GIVEN** a tentativa corretiva de conjunto já foi consumida
- **WHEN** outra resposta ainda omite ou adiciona procedimento
- **THEN** a validação falha explicitamente
- **AND** o pipeline segue o tratamento fail-closed existente
- **AND** nenhuma recomendação parcial chega ao médico.

#### Scenario: Erro não relacionado ao conjunto

- **GIVEN** a resposta é inválida por JSON, schema, duplicata, `case_id` ou `agency_record_number`
- **WHEN** a validação falha
- **THEN** o retry específico de conjunto não é executado
- **AND** o erro permanece explícito.

### Requirement: Exceções permanecem locais ao procedimento

A avaliação combinada MUST compartilhar dados comuns sem vazar exceções específicas.

#### Scenario: Corpo estranho em caso combinado

- **GIVEN** componente EDA é corpo estranho e componente Colonoscopia também existe
- **WHEN** policies executam
- **THEN** exceção pode afetar somente EDA
- **AND** Colonoscopia mantém seus critérios normais.

### Requirement: Artefatos legados continuam legíveis

Presenters e auditoria MUST ler schema 1.1 histórico e schema 2.0 novo sem reescrever JSON antigo.

#### Scenario: Caso antigo aberto após cutover

- **GIVEN** caso possui `structured_data` schema 1.1
- **WHEN** usuário autorizado abre detalhe/histórico
- **THEN** conteúdo continua renderizável
- **AND** nenhum migration altera o JSON clínico.

### Requirement: Dispatch LLM de produção vincula strict schema ao contrato 2.0

O pipeline v2 em produção, sem cliente LLM injetado, SHALL vincular a chamada à API exclusivamente aos strict schemas do contrato 2.0 (`Llm1ResponseV2` e `Llm2ResponseV2`), e o vínculo SHALL ser protegido por testes que falhem caso um schema de contrato anterior seja utilizado.

#### Scenario: LLM1 de produção recebe strict schema 2.0

- **GIVEN** o pipeline v2 cria o cliente LLM1 sem injeção de teste
- **WHEN** a chamada à API é montada
- **THEN** `response_format` usa `json_schema` strict
- **AND** o schema vinculado define `schema_version` fixo em `"2.0"`
- **AND** contém `common_preop` e `requested_procedures`
- **AND** não contém chaves exclusivas do contrato 1.1 (`preop_screening`, bloco `eda` de topo)

#### Scenario: LLM2 de produção recebe strict schema 2.0

- **GIVEN** o pipeline v2 cria o cliente LLM2 sem injeção de teste
- **WHEN** a chamada à API é montada
- **THEN** `response_format` usa `json_schema` strict
- **AND** o schema vinculado define `schema_version` fixo em `"2.0"`
- **AND** contém `procedure_recommendations`
- **AND** não contém a chave de sugestão singular do contrato 1.1 no topo

#### Scenario: Schema vinculado é compatível com normalização strict

- **GIVEN** o JSON Schema de `Llm1ResponseV2` ou `Llm2ResponseV2`
- **WHEN** a normalização de strict mode é aplicada
- **THEN** todo nó objeto passa a declarar `additionalProperties: false`
- **AND** todo nó objeto lista todas as propriedades em `required`
- **AND** nenhuma construção incompatível com strict mode permanece

### Requirement: Schema enviado à API SHALL converter uniões oneOf para anyOf

O normalizador de strict schema SHALL reescrever todo nó `oneOf` como `anyOf`
e SHALL remover a chave `discriminator` do schema enviado à API, preservando
as variantes originais da união. Os modelos Pydantic e a validação local
SHALL permanecer inalterados.

#### Scenario: União discriminada do LLM1 é aceita pela API

- **GIVEN** o schema de `Llm1ResponseV2` serializado por `model_json_schema()`
- **WHEN** a normalização strict é aplicada
- **THEN** nenhuma chave `oneOf` permanece em qualquer nível
- **AND** nenhuma chave `discriminator` permanece em qualquer nível
- **AND** a união de `requested_procedures.items` continua presente como `anyOf` com as mesmas variantes

#### Scenario: Schema sintético com oneOf e discriminator é convertido

- **GIVEN** um schema contendo um nó com `oneOf` e `discriminator`
- **WHEN** a normalização strict é aplicada
- **THEN** o nó passa a conter `anyOf` com a mesma lista de variantes
- **AND** `oneOf` e `discriminator` são removidos
- **AND** o schema original não é mutado
