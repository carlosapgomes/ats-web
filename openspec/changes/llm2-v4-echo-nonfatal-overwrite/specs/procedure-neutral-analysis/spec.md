# procedure-neutral-analysis Delta

## Purpose

Supersede o hardening `llm2-v4-echo-mismatch-fix` (observabilidade + retry one-shot com abort no segundo mismatch) após a recorrência de 2026-10-05 (`fbee1873`, `abac`→`abec`, retry esgotado → `FAILED`). Transcrição exata de UUID pelo LLM é superfície de falha evitável; a atribuição é garantida pelo request HTTP isolado (precedente: `Llm1ResponseV4` sem `case_id`). Este delta exige tratamento não-fatal com overwrite auditável, sem chamada extra.

## ADDED Requirements

### Requirement: Echo mismatch do LLM2 é não-fatal com overwrite auditável

Diante de resposta schema-válida com `case_id` ou `agency_record_number` divergentes, o serviço LLM2 MUST NOT falhar nem executar retry corretivo. MUST emitir warning com os valores `expected` e `got` integrais, mais `raw_len` e `raw_sha256` (12 hex do payload bruto), MUST NOT incluir texto clínico (`rationale`, `details` ou raw integral), MUST sobrescrever os IDs com os valores esperados e MUST prosseguir para as validações seguintes (conjunto → idioma). O orçamento físico passa a ser no máximo 3 chamadas (inicial + 1 conjunto + 1 idioma).

#### Scenario: case_id com 1 char divergente prossegue com overwrite

- **GIVEN** resposta LLM2 schema-válida com `case_id` divergente por erro de cópia (ex.: `abac` vs `abec`)
- **AND** restante válido (conjunto reconciliado + pt-BR)
- **WHEN** validação de eco executa
- **THEN** serviço emite warning contendo `expected`, `got`, `raw_len` e `raw_sha256`
- **AND** substrings `case_id mismatch` preservadas para grep
- **AND** nenhuma segunda chamada é executada por causa do eco
- **AND** pipeline prossegue e pode chegar a `LLM2_OK`.

#### Scenario: agency_record_number divergente prossegue com overwrite

- **GIVEN** resposta schema-válida com `agency_record_number` divergente
- **WHEN** validação de eco executa
- **THEN** mesmo comportamento: warning observável + overwrite + prosseguimento, sem retry de eco.

#### Scenario: Overwrite não mascara as demais validações

- **GIVEN** resposta com eco divergente mas conjunto errado ou narrativa em inglês
- **WHEN** overwrite de IDs aplica
- **THEN** validações de conjunto e idioma executam normalmente (com seus retries existentes)
- **AND** `PIPELINE_FAILED` continua para falhas reais de conjunto/idioma/schema/non-JSON.
