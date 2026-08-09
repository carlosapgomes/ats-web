# Slice 001: Vincular factories OpenAI aos schemas V2 com teste de contrato

## Handoff com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, a ADR-0004 e todos os artefatos deste
change (`proposal.md`, `design.md`, `specs/procedure-neutral-analysis/spec.md`).
Inspecione obrigatoriamente antes de codar:

- `apps/pipeline/llm.py` — `create_openai_client`, `create_openai_llm1_client`,
  `create_openai_llm2_client`, `_normalize_openai_strict_schema`;
- `apps/pipeline/schemas/llm1.py` e `apps/pipeline/schemas/llm2.py` (contrato
  1.1 — apenas leitura, para entender o erro);
- `apps/pipeline/schemas/llm1_v2.py` e `apps/pipeline/schemas/llm2_v2.py`
  (contrato 2.0 — alvo do vínculo);
- `apps/pipeline/orchestrator.py::run_pipeline` (call site de produção);
- `apps/pipeline/tests/test_llm_client.py` — classe
  `TestCreateOpenAiStrictSchemaClients`.

### Incidente que este slice corrige

Produção `v0.3.0-rc.1`: as factories vinculam strict json_schema aos modelos
1.1 (`Llm1Response`/`Llm2Response`). Em modo strict a API força a saída ao
schema informado; a resposta chega em formato 1.1 e falha em
`Llm1ResponseV2.model_validate` para 100% dos casos novos. Evidência: evento
`PIPELINE_FAILED` do caso `1a700cc4-bb3f-416a-b2b0-f3a027d0027b`.

### Fluxo esperado após o slice

```text
run_pipeline sem cliente injetado
→ create_openai_llm1_client() → strict schema de Llm1ResponseV2
→ create_openai_llm2_client() → strict schema de Llm2ResponseV2
→ resposta estruturalmente 2.0 → validação V2 passa
```

## Escopo (cap: 2 arquivos de código)

Permitidos:

1. `apps/pipeline/llm.py` — trocar o modelo vinculado nas duas factories e
   atualizar docstrings.
2. `apps/pipeline/tests/test_llm_client.py` — converter/adicionar testes de
   contrato do vínculo (asserts de chaves distintivas 2.0 + ausência de 1.1).

Além destes, apenas `openspec/changes/fix-pipeline-v2-openai-strict-schema/tasks.md`
(checkbox do slice).

Proibidos: orchestrator, serviços, schemas, prompts, templates, migrations,
qualquer outro arquivo. Se precisar tocar outro arquivo, PARE e reporte
INCOMPLETO com justificativa.

## Protocolo obrigatório (TDD)

**Se qualquer item falhar, marque INCOMPLETO: não atualize `tasks.md`, não
faça commit/push e reporte bloqueio com evidência.**

### 1. RED

Escreva primeiro os testes em `test_llm_client.py` (mock de `openai.OpenAI`
como nos testes existentes):

- `test_llm1_client_binds_v2_strict_schema`: captura `response_format` e
  asserta: `type == "json_schema"`, `strict is True`,
  `schema.properties.schema_version` fixado em `"2.0"` (`const` ou `enum`
  unitário), presença de `common_preop` e `requested_procedures` em
  `properties`, ausência de `preop_screening` e `eda` no topo.
- `test_llm2_client_binds_v2_strict_schema`: idem para LLM2 com
  `procedure_recommendations` presente e sem `suggestion` no topo;
  `schema_version` fixado em `"2.0"`.
- `test_v2_schemas_normalize_for_strict_mode`: aplica
  `_normalize_openai_strict_schema` ao `model_json_schema()` de
  `Llm1ResponseV2` e `Llm2ResponseV2` e asserta que todo nó objeto tem
  `additionalProperties is False` e `required` completo.

Rode e registre a falha esperada:

```bash
uv run pytest apps/pipeline/tests/test_llm_client.py -q
```

Os dois primeiros testes DEVEM falhar contra o código atual (vínculo 1.1).
Registre a saída no relatório.

### 2. GREEN

Em `apps/pipeline/llm.py`, troque as importações internas das factories:

- `create_openai_llm1_client`: `from apps.pipeline.schemas.llm1_v2 import Llm1ResponseV2`,
  vincule `Llm1ResponseV2.model_json_schema()`;
- `create_openai_llm2_client`: `from apps.pipeline.schemas.llm2_v2 import Llm2ResponseV2`,
  vincule `Llm2ResponseV2.model_json_schema()`.

Nada mais muda: nomes de função, nomes de schema (`llm1_response`,
`llm2_response`) e normalização permanecem. Atualize as docstrings.

Ajuste apenas o necessário nos testes antigos da mesma classe que assertavam
características incidentais do schema 1.1, sem enfraquecer cobertura.

### 3. REFACTOR

Nomes claros, sem código morto, docstrings coerentes. Nenhuma mudança de
comportamento além do vínculo.

## Gates de autoavaliação (responda no relatório)

1. Os testes novos falharam no RED contra o código antigo? Cole a saída.
2. O `response_format` de produção agora carrega `schema_version` `"2.0"`?
   Mostre o assert correspondente.
3. Algum call site ou teste ainda referencia `Llm1Response`/`Llm2Response`
   para criar cliente OpenAI? (`rg -n "Llm1Response\b|Llm2Response\b" apps/pipeline` —
   excluindo os próprios módulos de schema e leitura histórica 1.1.)
4. Quality gate completo passou? Cole resumo.

## Quality gates obrigatórios

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Relatório

Salvar em `/tmp/fix-pipeline-v2-openai-strict-schema-slice-001-report.md` com:
status (COMPLETO/INCOMPLETO), BASE_REF, commit, arquivos alterados, evidência
RED/GREEN, diff resumido, gates e respostas aos gates de autoavaliação.

## Commit

Mensagem: `fix(pipeline): vincular clientes OpenAI aos strict schemas V2`.
Push na branch `feature/fix-pipeline-v2-openai-strict-schema`.
