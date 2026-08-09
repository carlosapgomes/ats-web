# procedure-neutral-analysis Spec Delta

## ADDED Requirements

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
