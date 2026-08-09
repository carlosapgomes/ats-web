# Design: Vínculo do strict json_schema aos contratos V2

## Contexto

O pipeline é exclusivamente v2 (ADR-0004). A produção cria os clientes via
`apps/pipeline/orchestrator.py::run_pipeline` quando nenhum cliente é
injetado:

```python
from apps.pipeline.llm import create_openai_llm1_client, create_openai_llm2_client
client_llm1 = create_openai_llm1_client()
client_llm2 = create_openai_llm2_client()
```

Em `apps/pipeline/llm.py`, essas factories chamam `create_openai_client` com o
JSON Schema dos modelos **1.1** (`Llm1Response` / `Llm2Response`). O modo
`json_schema` com `strict: True` usa decodificação restrita: o modelo só pode
emitir tokens válidos para o schema fornecido. Prompts pedindo 2.0 são
inefetivos nesse modo — a forma da saída é decidida pelo schema, não pelo
texto do prompt.

## Decisão

**D1 — Corrigir as factories existentes em vez de criar factories novas.**
`create_openai_llm1_client()` passa a importar `Llm1ResponseV2`
(`apps/pipeline/schemas/llm1_v2.py`) e `create_openai_llm2_client()` passa a
importar `Llm2ResponseV2` (`apps/pipeline/schemas/llm2_v2.py`).

Justificativa:

- não existe mais consumidor de produção do schema 1.1 (pipeline 1.1 foi
  removido no Slice 007 do change anterior);
- manter os mesmos nomes de função preserva o call site do orchestrator e os
  nomes de schema (`llm1_response`, `llm2_response`) já assertados em testes;
- footprint mínimo: 1 arquivo de produto + 1 de teste.

Alternativas rejeitadas:

- **Criar `create_openai_llm1_v2_client()`**: deixaria factories mortas com o
  schema errado disponíveis para uso futuro (mesma armadilha que causou o
  incidente).
- **Cair para `json_object` mode**: perderia a garantia estrutural de schema
  que motivou o strict mode (Slice 008 do change anterior) e transferiria toda
  a responsabilidade de forma para o prompt.

**D2 — Teste de contrato asserta chaves distintivas, não apenas modo strict.**
O teste novo deve falhar se o schema vinculado for 1.1:

- `schema_version` com valor fixo `"2.0"` (const ou enum unitário);
- presença de `common_preop` e `requested_procedures` (LLM1) e
  `procedure_recommendations` (LLM2);
- ausência de chaves exclusivas 1.1 (`preop_screening`, `eda` no topo para
  LLM1; `suggestion` no topo para LLM2).

**D3 — Normalização strict permanece a mesma.**
`_normalize_openai_strict_schema` já cobre os requisitos do modo strict
(`additionalProperties: false` + `required` completo em nós objeto). Os
schemas V2 usam construções suportadas (Literal, pattern, min/max length,
`X | None`). O slice inclui validação explícita de que o schema normalizado
resultante mantém essas propriedades.

## Riscos

| Risco | Mitigação |
|---|---|
| Schema V2 conter construção incompatível com strict mode | Teste unitário de normalização sobre `model_json_schema()` dos dois modelos V2; smoke real em homologação antes de liberar ao NIR |
| Casos já `FAILED` sem retomada | Recuperação operacional documentada (encerramento administrativo + reapresentação); fora de escopo do hotfix |
| Regressão em testes com cliente fake | Nenhuma alteração em orquestração/serviços; apenas vínculo de schema |

## Rollout

1. Slice único com TDD (RED verificável contra o código atual).
2. Quality gate completo.
3. Tag `v0.3.0-rc.2` + GitHub Release prerelease + imagem OCI.
4. Servidor temporário: `git pull --ff-only`, `build`, `up -d` (sem migrate).
5. Smoke: enviar 1 relatório de colonoscopia e 1 de EDA conhecidos como bons;
   confirmar `WAIT_DOCTOR` e `schema_version: "2.0"` persistido.

## Rollback

Revert do commit + rebuild + `up -d`. Nenhuma migration envolvida; banco
permanece idêntico. Casos novos voltarão a falhar (estado atual), por isso o
rollback só se justifica se o hotfix introduzir falha nova.
