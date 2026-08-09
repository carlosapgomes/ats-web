# Proposal: Normalizar oneOf/discriminator para strict mode da OpenAI

**Change ID**: `fix-openai-strict-oneof-normalization`
**Fase**: hotfix de produção (sequência de `fix-pipeline-v2-openai-strict-schema`)
**Risco**: PROFISSIONAL (função pura de normalização; contrato externo LLM; produção bloqueada)
**Incidente**: caso `9f1e9d3a-0d5e-4dd6-ac00-cd4b178a4ec4`, produção 2026-08-09, pós-deploy `v0.3.0-rc.2`.

## Why

Após o hotfix `fix-pipeline-v2-openai-strict-schema`, o vínculo strict passou
a enviar o schema V2 real à API. A chamada LLM1 agora falha com `400
invalid_json_schema`:

```text
Invalid schema for response_format 'llm1_response':
In context=('properties', 'requested_procedures', 'items'),
'oneOf' is not permitted.
```

Causa: `Llm1ResponseV2.requested_procedures` é uma união discriminada
(`Llm1EdaProcedureV2 | Llm1ColonoscopyProcedureV2` com `procedure_type` como
discriminador). `model_json_schema()` serializa isso como `oneOf` +
`discriminator` + `$ref`. O modo strict da OpenAI **não aceita `oneOf`**;
uniões são suportadas via `anyOf`. O normalizador
`_normalize_openai_strict_schema` (apps/pipeline/llm.py) não trata `oneOf` —
ele foi escrito para a geometria 1.1, que não tinha uniões desse tipo.

Impacto: 100% dos casos novos continuam falhando (agora no envio do schema,
antes mesmo da geração). LLM2 não é afetado diretamente (sem `oneOf`), mas o
pipeline nunca chega lá.

O smoke do rollout de `v0.3.0-rc.2` existia exatamente para capturar isto; o
incidente foi detectado no primeiro caso real.

## What Changes

- `_normalize_openai_strict_schema` passa a reescrever todo nó `oneOf` para
  `anyOf` e remover a chave `discriminator` (não suportada) do schema
  **enviado à API**. Nada muda nos modelos Pydantic nem na validação local
  (`Llm1ResponseV2.model_validate` segue usando o discriminador normalmente).
- Testes: normalização de schema sintético com `oneOf`+`discriminator`;
  garantia de que o schema V2 do LLM1 normalizado não contém `oneOf` nem
  `discriminator` em nenhum nível e mantém a união via `anyOf` com `$ref`.

Fora de escopo: alteração de modelos V2, prompts, orquestração, FSM ou
migrations.

## Impact

- **Código**: `apps/pipeline/llm.py` (normalizador) e
  `apps/pipeline/tests/test_llm_client.py` (testes).
- **Spec**: delta ADDED em `procedure-neutral-analysis` (compatibilidade de
  uniões no schema enviado).
- **Banco**: nenhuma migration.
- **Rollout**: tag candidata `v0.3.0-rc.3`, imagem OCI, rebuild no servidor
  temporário; aliases `latest`/`0.2` intocados.
- **Rollback**: revert + rebuild; sem efeito sobre dados.
