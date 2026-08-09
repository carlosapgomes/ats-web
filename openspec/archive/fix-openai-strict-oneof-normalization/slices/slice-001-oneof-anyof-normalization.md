# Slice 001: Reescrever oneOf→anyOf e remover discriminator no normalizador strict

## Handoff com contexto zero

Leia `AGENTS.md`, `PROJECT_CONTEXT.md`, a ADR-0004 e todos os artefatos deste
change (`proposal.md`, `design.md`,
`specs/procedure-neutral-analysis/spec.md`). Inspecione obrigatoriamente:

- `apps/pipeline/llm.py` — `create_openai_client`,
  `_normalize_openai_strict_schema`, `_normalize_schema_node`;
- `apps/pipeline/schemas/llm1_v2.py` — `requested_procedures` é união
  discriminada (`Llm1EdaProcedureV2 | Llm1ColonoscopyProcedureV2`);
- `apps/pipeline/tests/test_llm_client.py` — classe
  `TestNormalizeOpenAiStrictSchema`.

### Incidente que este slice corrige

Produção `v0.3.0-rc.2`, caso `9f1e9d3a-0d5e-4dd6-ac00-cd4b178a4ec4`:

```text
openai.BadRequestError: 400 invalid_json_schema
Invalid schema for response_format 'llm1_response':
In context=('properties', 'requested_procedures', 'items'),
'oneOf' is not permitted.
```

`model_json_schema()` serializa a união discriminada como `oneOf` +
`discriminator` + `$ref`; o modo strict da OpenAI só aceita uniões via
`anyOf` e não reconhece `discriminator`. O normalizador atual não trata
nenhum dos dois.

## Escopo (cap: 2 arquivos de código)

Permitidos:

1. `apps/pipeline/llm.py` — somente `_normalize_schema_node` (e docstring da
   função de normalização, se necessário).
2. `apps/pipeline/tests/test_llm_client.py` — testes novos na classe
   `TestNormalizeOpenAiStrictSchema`.

Além destes, apenas
`openspec/changes/fix-openai-strict-oneof-normalization/tasks.md`.

Proibidos: modelos de schema, serviços, orchestrator, prompts, templates,
migrations. Se precisar tocar outro arquivo, PARE e reporte INCOMPLETO.

## Protocolo obrigatório (TDD)

**Se qualquer item falhar, marque INCOMPLETO: não atualize `tasks.md`, não
faça commit/push e reporte bloqueio com evidência.**

### 1. RED

Adicione em `TestNormalizeOpenAiStrictSchema`:

- `test_rewrites_oneof_to_anyof_and_drops_discriminator`: schema sintético
  com nó `{"oneOf": [...], "discriminator": {...}}`; após normalização o nó
  tem `anyOf` com a MESMA lista de variantes, sem `oneOf` e sem
  `discriminator`; o schema original não foi mutado.
- `test_normalized_llm1_v2_schema_has_no_oneof_or_discriminator`: aplica a
  normalização em `Llm1ResponseV2.model_json_schema()` e asserta
  recursivamente ausência total das chaves `oneOf` e `discriminator`, e que
  `properties.requested_procedures.items` mantém `anyOf` com 2 variantes.

Rode e registre a falha esperada:

```bash
uv run pytest apps/pipeline/tests/test_llm_client.py -q
```

Os dois testes DEVEM falhar contra o código atual. Registre a saída.

### 2. GREEN

Em `_normalize_schema_node`, para cada nó dict:

1. se houver `oneOf`: `node["anyOf"] = node.pop("oneOf")`;
2. remover `discriminator` com `node.pop("discriminator", None)`;
3. manter a lógica existente de `required`/`additionalProperties` para nós
   objeto;
4. recursão sobre os valores AFTER das mutações (cuidado com views de
   dicionário mutado).

Nada mais muda: modelos Pydantic, validação local, nomes de schema e
factories permanecem.

### 3. REFACTOR

Sem código morto; docstring do normalizador descrevendo também a reescrita de
uniões.

## Gates de autoavaliação (responda no relatório)

1. Os testes novos falharam no RED? Cole a saída.
2. O schema normalizado do LLM1 ainda contém `oneOf` ou `discriminator` em
   qualquer nível? Mostre o assert recursivo.
3. A validação local segue usando o discriminador? (Mostre que
   `Llm1ResponseV2.model_validate` não foi alterado — nenhum diff em
   `schemas/`.)
4. Quality gate completo passou? Cole resumo.

## Quality gates obrigatórios

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Relatório

Salvar em `/tmp/fix-openai-strict-oneof-normalization-slice-001-report.md`
com: status, BASE_REF, commit, arquivos alterados, evidência RED/GREEN, diff
resumido, gates e respostas aos gates de autoavaliação.

## Commit

Mensagem: `fix(pipeline): converter oneOf em anyOf no strict schema enviado à API`.
Push na branch `feature/fix-openai-strict-oneof-normalization`.
