# procedure-neutral-analysis Specification (delta)

## ADDED Requirements

### Requirement: Identidade do paciente é mascarada antes de qualquer chamada LLM

O sistema MUST extrair programaticamente o nome do paciente, o nome social
(quando presente) e o CNS (quando presente) do cabeçalho do relatório e MUST
substituí-los por placeholders em todo texto enviado aos LLMs. Identidade
ambígua ou falha de extração MUST bloquear o envio (fail-closed, sem fallback
ao texto original). A identidade exibida nas filas e na auditoria MUST vir da
fonte local, nunca da resposta do modelo.

#### Scenario: Nome e CNS mascarados nos prompts

- **GIVEN** relatório com nome e CNS no cabeçalho
- **WHEN** o pipeline monta os prompts do LLM1 e do LLM2
- **THEN** nenhum prompt contém nome, nome social ou CNS
- **AND** o texto contém `[NOME_REMOVIDO]` e `[CNS_REMOVIDO]`.

#### Scenario: Cabeçalho ambíguo bloqueia o pipeline

- **GIVEN** cabeçalho com nomes ou CNS divergentes
- **WHEN** o pipeline inicia
- **THEN** nenhuma chamada LLM é feita
- **AND** o caso vai para `FAILED` com evento `PIPELINE_FAILED` auditável.

#### Scenario: Nome exibido vem da fonte local

- **GIVEN** pipeline concluído com identidade local extraída
- **WHEN** médico, agendador ou NIR abrem filas e detalhes
- **THEN** o nome exibido é o extraído programaticamente
- **AND** `structured_data.patient.document_id` é `None`.
