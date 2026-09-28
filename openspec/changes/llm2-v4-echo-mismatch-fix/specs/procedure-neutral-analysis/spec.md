# procedure-neutral-analysis Delta

## Purpose

Endurecer o contrato LLM2 após o incidente de 2026-09-28 (caso `cab6a0a8`, CPRE):
resposta schema-válida com `case_id` ecoado divergente falhava sem retry e sem registrar
o valor recebido. Este delta exige erro observável (`got` + metadados do raw, sem PHI)
e um retry corretivo único para echo mismatch, coexistindo com os retries existentes
de conjunto e idioma.

## ADDED Requirements

### Requirement: Echo mismatch do LLM2 é observável e tem retry único

Diante de resposta schema-válida com `case_id` ou `agency_record_number` divergentes
(echo mismatch), o serviço LLM2 MUST realizar no máximo um retry corretivo cuja chamada
contenha os IDs exatos esperados. Um segundo echo mismatch MUST falhar explicitamente e
MUST NOT produzir artefato parcial. O erro final MUST conter os valores `expected` e `got`
integrais, mais `raw_len` e `raw_sha256` (hash curto do payload bruto), e MUST NOT conter
texto clínico do payload (`rationale`, `details` ou raw integral). O retry de eco MUST NOT
consumir nem bloquear os retries de conjunto e idioma (cada um no máximo uma vez).

#### Scenario: Echo mismatch expõe got e metadados sem PHI

- **GIVEN** resposta LLM2 schema-válida com `case_id` divergente do caso
- **WHEN** validação de eco falha definitivamente (retry consumido ou segundo mismatch)
- **THEN** erro contém `expected` e `got` integrais, `raw_len` e `raw_sha256`
- **AND** erro não contém texto de `rationale`/`details`
- **AND** `PIPELINE_FAILED` registra a mensagem via `str(exc)` sem mudança no orchestrator.

#### Scenario: Primeiro echo mismatch dispara retry único com IDs exatos

- **GIVEN** primeira resposta schema-válida com IDs divergentes
- **WHEN** serviço detecta echo mismatch
- **THEN** executa exatamente uma tentativa corretiva contendo `case_id` e
  `agency_record_number` esperados
- **AND** aceita a segunda resposta somente se todas as validações passarem.

#### Scenario: Segundo echo mismatch aborta sem terceira chamada

- **GIVEN** tentativa corretiva de eco já foi consumida
- **WHEN** segunda resposta ainda diverge nos IDs
- **THEN** pipeline segue tratamento fail-closed (`PIPELINE_FAILED` + `LLM2_FAILED` → `FAILED`)
- **AND** nenhuma recomendação parcial chega ao médico
- **AND** nenhuma terceira chamada é executada.
