# Slice 002 — Contrato Pydantic LLM1

## Handoff para Implementador LLM

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `docs/investigations/2026-05-18-nir-to-doctor-flow-review.md`
4. `openspec/changes/align-llm-contract-and-doctor-routing/proposal.md`
5. `openspec/changes/align-llm-contract-and-doctor-routing/design.md`
6. `openspec/changes/align-llm-contract-and-doctor-routing/slices/slice-001-canonical-prompts.md`
7. Este arquivo.

Implemente somente este slice, assumindo que o slice 001 já alinhou nomes de prompts.

## Problema

O `Llm1Service` atual aceita qualquer JSON e não valida o schema legado. Isso permite payloads incompletos ou errados entrarem na policy e na UI.

Além disso, após o Slice 001, o seed usa prompts legados recentes, mas o fallback de código ainda pode ficar menos completo que o prompt legado mais recente. Isso cria risco de comportamento diferente quando o banco não está semeado.

## Objetivo

Portar o contrato Pydantic v2 do LLM1 do legado para o Django e fazer `Llm1Service` validar e normalizar a resposta como no sistema original.

Também alinhar o fallback/default LLM1 ao prompt legado mais recente e mais completo, evitando fallback simplificado.

## Escopo Preferencial

Arquivos prováveis:

- `pyproject.toml`
- `apps/pipeline/schemas/llm1.py` ou `apps/pipeline/schemas.py`
- `apps/pipeline/llm1_service.py`
- `apps/pipeline/tests/test_llm1_service.py`

Evite tocar no orchestrator exceto se necessário para adaptar exceções.

## Fonte Legada

Copiar/adaptar de:

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/dto/llm1_models.py`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm1_service.py`

## Requisitos Funcionais

1. Adicionar `pydantic>=2` como dependência direta se ainda não estiver em `pyproject.toml`.
2. Portar o schema `Llm1Response` e modelos auxiliares do legado.
3. Centralizar os defaults LLM1 para evitar divergência entre seed, fallback e service. O fallback/default deve ser o conteúdo legado mais recente e completo:
   - `llm1_system`: versão v6 da migration legada `0018_prompt_templates_llm1_ptbr_v6.py`.
   - `llm1_user`: versão v6 da mesma migration, combinada com a renderização final do service legado (`_render_user_prompt`) quando o prompt for efetivamente enviado ao LLM.
4. O fallback LLM1 não deve ser simplificado nem retornar apenas `{case_id}` para nomes canônicos conhecidos.
5. Validar:
   - `schema_version == "1.1"`;
   - `language == "pt-BR"`;
   - enums;
   - campos obrigatórios;
   - rejeição de campos extras;
   - alinhamento pediátrico;
   - alinhamento de subtipo EDA.
6. `Llm1Service.run()` deve:
   - renderizar o prompt final com instruções legadas para LLM1;
   - decodificar JSON;
   - validar `Llm1Response`;
   - verificar `agency_record_number`;
   - retornar `structured_data` via `model_dump(mode="json")`;
   - retornar `summary_text = validated.summary.one_liner`.
7. Se a validação falhar, lançar exceção clara. Pode ser uma nova exceção local, por exemplo `Llm1ValidationError`, ou reutilizar um erro existente, desde que o orchestrator consiga tratar como falha de pipeline.
8. Não implementar language retry neste slice se isso expandir demais. Se não implementar, registre como pendência explícita no relatório.

## TDD — Testes RED Esperados

Antes de implementar, atualize testes para falharem com o serviço atual:

1. payload LLM1 válido legado schema 1.1 passa;
2. `schema_version: 1.0` falha;
3. campo extra falha;
4. `agency_record_number` divergente falha;
5. pediatria inconsistente falha;
6. subtipo EDA duplicado inconsistente falha;
7. prompt final contém instruções legadas de escopo: EDA, GTT/gastrostomia/PEG, dilatação esofágica, corpo estranho, CPRE como non-EDA.
8. fallback/default LLM1 contém instruções críticas do legado v6:
   - `schema_version 1.1`;
   - `origin_context`;
   - `tracked_exams`;
   - `had_transfusion`;
   - `gastrostomia/GTT/PEG`;
   - `dilatacao esofagica` ou equivalente sem acento;
   - `corpo estranho`;
   - `CPRE` como `non_eda` na renderização final.
9. seed e fallback LLM1 não divergem nos blocos essenciais do legado v6.

## Critérios de Sucesso

- LLM1 passa a produzir apenas payload validado e normalizado.
- Testes antigos simplificados são atualizados para o contrato correto.
- Fallback/default LLM1 usa o prompt legado mais recente e mais completo, não fallback mínimo.
- Nenhuma alteração de roteamento `non_eda`/`unknown` neste slice.

## Comandos de Validação Focados

```bash
uv run pytest apps/pipeline/tests/test_llm1_service.py -q
uv run ruff check pyproject.toml apps/pipeline
uv run mypy apps/pipeline
```

## Relatório Obrigatório

Crie:

```text
/tmp/ats-web-slice-002-llm1-pydantic-report.md
```

Inclua:

- schemas portados;
- diferenças deliberadas em relação ao legado, se houver;
- testes executados;
- pendências, especialmente language retry se não for implementado.

Responda com:

```text
REPORT_PATH=/tmp/ats-web-slice-002-llm1-pydantic-report.md
```

## Stop Rule

Não implemente LLM2, scope gate, presenter médico ou role guard neste slice.
