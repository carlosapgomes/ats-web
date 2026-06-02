# Slice 003 — Contrato Pydantic LLM2

## Handoff para Implementador LLM

Leia os arquivos do change e confirme que os slices 001 e 002 estão aplicados.

Implemente somente este slice.

## Problema

O `Llm2Service` atual aceita JSON livre e não valida o contrato legado. Além disso, testes atuais aceitam payloads simplificados que não representam `Llm2Response` schema 1.1.

## Objetivo

Portar o contrato Pydantic v2 do LLM2 do legado para o Django e validar a resposta do LLM2 antes da reconciliation/policy synthesis.

## Escopo Preferencial

Arquivos prováveis:

- `apps/pipeline/schemas/llm2.py` ou arquivo de schemas existente do slice 002
- `apps/pipeline/llm2_service.py`
- `apps/pipeline/tests/test_llm2_service.py`
- possivelmente `apps/pipeline/tests/test_orchestrator.py` para fixtures válidas

## Fonte Legada

Copiar/adaptar de:

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/dto/llm2_models.py`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm2_service.py`

## Requisitos Funcionais

1. Portar `Llm2Response` e modelos auxiliares.
2. Validar:
   - `schema_version == "1.1"`;
   - `language == "pt-BR"`;
   - `case_id` obrigatório e igual ao esperado;
   - `agency_record_number` obrigatório e igual ao esperado;
   - `suggestion: accept | deny`;
   - `support_recommendation: none | anesthesist | anesthesist_icu | unknown`;
   - `rationale`;
   - `policy_alignment`;
   - `confidence`.
3. `Llm2Service.run()` deve renderizar prompt final com instruções legadas e incluir:
   - `case_id`;
   - `agency_record_number`;
   - JSON LLM1;
   - contexto de caso anterior, se houver.
4. Retornar `suggested_action` via `model_dump(mode="json")`.
5. Atualizar fixtures de orchestrator para schema 1.1 válido.
6. Não mudar scope gate neste slice.

## TDD — Testes RED Esperados

1. payload LLM2 válido legado passa;
2. payload sem `case_id` falha;
3. `case_id` divergente falha;
4. `agency_record_number` divergente falha;
5. enum inválido de `support_recommendation` falha;
6. campo extra falha;
7. prompt final inclui dados LLM1 e `prior_case` serializados.

## Critérios de Sucesso

- LLM2 validado conforme contrato legado.
- Testes simplificados antigos são removidos ou adaptados.
- Happy path do orchestrator continua chegando em `WAIT_DOCTOR` para EDA válida.

## Comandos de Validação Focados

```bash
uv run pytest apps/pipeline/tests/test_llm2_service.py apps/pipeline/tests/test_orchestrator.py -q
uv run ruff check apps/pipeline
uv run mypy apps/pipeline
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-003-llm2-pydantic-report.md
```

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-003-llm2-pydantic-report.md
```

## Stop Rule

Não implemente scope gate, presenter médico ou role guard neste slice.
