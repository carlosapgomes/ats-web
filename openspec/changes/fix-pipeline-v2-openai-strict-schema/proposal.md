# Proposal: Corrigir vinculo do strict json_schema aos contratos V2 no pipeline LLM

**Change ID**: `fix-pipeline-v2-openai-strict-schema`
**Fase**: hotfix de produção (pós-release `v0.3.0-rc.1`)
**Risco**: CRÍTICO (pipeline LLM de produção quebrado para 100% dos casos novos; contrato externo LLM)
**Relação com ADR**: implementa corretamente a ADR-0004 (contrato neutro 2.0 autoritativo). Nenhuma decisão nova; sem ADR adicional.
**Incidente**: caso `1a700cc4-bb3f-416a-b2b0-f3a027d0027b` (ocorrência 4999496), produção 2026-08-09.

## Why

O pipeline v2 (exclusivo desde a ADR-0004) cria seus clientes OpenAI via
`create_openai_llm1_client()` / `create_openai_llm2_client()` em
`apps/pipeline/llm.py`. Essas factories vinculam o modo **strict json_schema**
aos schemas legados do contrato 1.1:

- `Llm1Response` (`apps/pipeline/schemas/llm1.py`, `schema_version: Literal["1.1"]`, `preop_screening`, bloco `eda`);
- `Llm2Response` (`apps/pipeline/schemas/llm2.py`, `schema_version: Literal["1.1"]`).

Em modo strict, a API força estruturalmente a saída ao schema fornecido.
Resultado: mesmo com prompts neutros 2.0 corretos no banco, a resposta chega
sempre no formato 1.1 e falha em `Llm1ResponseV2.model_validate`:

```text
LLM1 v2 schema validation failed: 5 validation errors for Llm1ResponseV2
schema_version: Input should be '2.0' [input_value='1.1']
common_preop: Field required
requested_procedures: Field required
eda: Extra inputs are not permitted
preop_screening: Extra inputs are not permitted
```

Impacto: **todo caso novo (EDA ou colonoscopia) entra em `FAILED`** desde o
deploy de `v0.3.0-rc.1`. Não há transição FSM de retomada a partir de
`FAILED`; casos afetados precisam de encerramento administrativo e
reapresentação.

Por que os testes não detectaram: todos os testes de pipeline injetam cliente
LLM fake. Os testes da factory (`test_llm_client.py`) assertam modo strict,
nome do schema e presença de `agency_record_number` — campo presente nos dois
contratos — mas nunca assertam o valor de `schema_version` nem as chaves
distintivas de cada contrato.

## What Changes

- Vincular `create_openai_llm1_client()` ao strict schema de `Llm1ResponseV2`.
- Vincular `create_openai_llm2_client()` ao strict schema de `Llm2ResponseV2`.
- Adicionar testes de contrato que falhem contra vínculo 1.1 (assertam
  `schema_version` fixo `"2.0"`, chaves distintivas 2.0 e ausência de chaves
  exclusivas 1.1), além de validação da normalização strict dos schemas V2.
- Atualizar a spec `procedure-neutral-analysis` com requisito de vínculo.

Fora de escopo: prompts, FSM, migrations, modelos, orquestração,
reprocessamento automático de casos já `FAILED` (recuperação operacional via
encerramento administrativo + reapresentação).

## Impact

- **Código**: `apps/pipeline/llm.py` (2 factories + docstrings) e
  `apps/pipeline/tests/test_llm_client.py` (testes de contrato).
- **Spec**: delta ADDED em `procedure-neutral-analysis`.
- **Banco**: nenhuma migration; estado idêntico antes/depois.
- **Rollout**: tag candidata `v0.3.0-rc.2`, imagem OCI, rebuild local no
  servidor temporário (`git pull --ff-only`, `build`, `up -d`);
  `latest`/`0.2` permanecem intocados.
- **Rollback**: revert + rebuild; sem efeito sobre dados.
- **Operação**: smoke com 1 relatório EDA e 1 colonoscopia conhecidos como
  bons; casos falhos do incidente tratados por encerramento + reapresentação.
