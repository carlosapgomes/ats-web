<!-- markdownlint-disable MD013 -->

# procedure-neutral-analysis Spec Delta

## MODIFIED Requirements

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
