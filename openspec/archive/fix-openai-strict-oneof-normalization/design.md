# Design: Normalização de oneOf/discriminator para strict mode

## Contexto

O modo strict (structured outputs) da OpenAI aceita um subconjunto de JSON
Schema. Uniões são suportadas apenas via `anyOf`; `oneOf` é rejeitado com
`invalid_json_schema`. A chave `discriminator` não faz parte do subconjunto
suportado. Pydantic serializa uniões discriminadas como `oneOf` +
`discriminator` + `$ref` — exatamente o caso de
`requested_procedures.items` em `Llm1ResponseV2`.

## Decisão

**D1 — Reescrever no normalizador, não nos modelos.**
Em `_normalize_schema_node` (`apps/pipeline/llm.py`):

- se um nó contém `oneOf`, mover a lista para `anyOf` (preservando ordem e
  `$ref`);
- remover `discriminator` do nó.

Justificativa:

- os modelos Pydantic permanecem autoritativos para validação local
  (discriminador continua ativo em `Llm1ResponseV2.model_validate`);
- o schema enviado à API é uma cópia normalizada — rewrite cirúrgico não
  altera semântica de decodificação restrita: cada variante da união declara
  `procedure_type` com valor `const` distinto, então a geração continua
  deterministicamente válida;
- footprint mínimo (1 função + testes).

Alternativas rejeitadas:

- **Eliminar a união discriminada nos modelos V2**: mudaria contrato interno,
  validação e testes de todo o pipeline por causa de uma limitação de
  serialização do provedor.
- **Caír para `json_object` mode**: perderia decodificação restrita
  (propriedade central do desenho de robustez do Slice 008 anterior).

**D2 — Remoção do `discriminator` é segura.**
O discriminador orienta validadores, não o gerador. Em strict mode a API
gera dentro das variantes `anyOf`; a escolha da variante é induzida pelos
`const` de `procedure_type`. A validação local posterior
(`Llm1ResponseV2.model_validate`) aplica o discriminador normalmente sobre a
resposta recebida.

## Riscos

| Risco | Mitigação |
|---|---|
| API recusar outra construção não mapeada | Teste inventaria `oneOf`/`allOf`/`discriminator` no schema normalizado; smoke real imediato após deploy |
| Reescrita alterar semântica da união | `anyOf` mantém as mesmas variantes `$ref`; validação local inalterada; teste cobre equivalência de conteúdo |

## Rollout e rollback

Rebuild + `up -d` (sem migration). Rollback: revert + rebuild.
