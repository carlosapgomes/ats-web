# procedure-neutral-analysis Spec Delta

## ADDED Requirements

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
