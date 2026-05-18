# Slice 008 — OpenAI Strict Schema e Language Retry

## Handoff para Implementador LLM

Leia antes de implementar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `docs/investigations/2026-05-18-self-handoff-align-llm-contract.md`
4. `openspec/changes/align-llm-contract-and-doctor-routing/design.md`
5. `openspec/changes/align-llm-contract-and-doctor-routing/tasks.md`
6. Este arquivo.

Este slice reabre o closeout do change por bug encontrado em teste manual com LLM real.

## Contexto do Bug

Durante testes manuais, o pipeline falhou no LLM1 por respostas JSON válidas mas fora do schema Pydantic. Exemplos observados:

- `eda.indication_category` veio como texto livre em vez de enum (`bleeding`, `dyspepsia`, etc.).
- `eda.requested_procedure.urgency` veio como `unknown`, mas o schema aceita `indefinido`.
- `eda.cardiovascular_risk` veio como string (`"yes"`) em vez de objeto `{level, source_text_hint}` ou `null`.
- `clinical_flags` recebeu campos inventados/traduzidos (`hepatopatia_ou_cirrose`, `suspeita_varizes_esofagicas`, etc.).

A investigação confirmou que:

- `apps/pipeline/schemas/llm1.py` é estruturalmente equivalente ao DTO legado.
- Os prompts base LLM1 v6 também são equivalentes ao legado.
- A diferença crítica é o runtime OpenAI:
  - legado usava `response_format={"type": "json_schema", "json_schema": {"strict": True, ...}}` com `Llm1Response.model_json_schema()` e `Llm2Response.model_json_schema()`;
  - Django atual usa apenas `response_format={"type": "json_object"}`.

Além disso, o legado implementa retry de linguagem pt-BR para LLM1/LLM2 após validação Pydantic.

## Objetivo

Portar o comportamento efetivo do legado para o runtime OpenAI do Django:

1. Usar OpenAI `response_format=json_schema` com `strict: true` para LLM1 e LLM2.
2. Instanciar clientes específicos por estágio/schema, evitando um client genérico sem schema.
3. Portar/adaptar `_normalize_openai_strict_schema()` do legado para compatibilidade com schemas Pydantic v2 em strict mode.
4. Implementar retry de linguagem pt-BR para LLM1 e LLM2, equivalente ao legado.

## Fontes Legadas

Use como referência principal:

- `/home/carlos/projects/augmented-triage-system/src/triage_automation/infrastructure/llm/openai_client.py`
  - `OpenAiChatCompletionsClient`
  - `_normalize_openai_strict_schema()`
  - uso de `response_format=json_schema` com `strict=True`
- `/home/carlos/projects/augmented-triage-system/apps/worker/main.py`
  - `build_runtime_llm_clients()`
  - instancia LLM1 com `Llm1Response.model_json_schema()`
  - instancia LLM2 com `Llm2Response.model_json_schema()`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm1_service.py`
  - retry de linguagem LLM1
  - `_collect_llm1_forbidden_terms()`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/llm2_service.py`
  - retry de linguagem LLM2
  - `_collect_llm2_forbidden_terms()`
- `/home/carlos/projects/augmented-triage-system/src/triage_automation/application/services/ptbr_language_guard.py`
  - detecção de termos narrativos em inglês

## Escopo Preferencial

Arquivos prováveis:

- `apps/pipeline/llm.py`
- `apps/pipeline/llm1_service.py`
- `apps/pipeline/llm2_service.py`
- `apps/pipeline/tests/test_llm_client.py`
- `apps/pipeline/tests/test_llm1_service.py`
- `apps/pipeline/tests/test_llm2_service.py`
- possivelmente novo `apps/pipeline/ptbr_language_guard.py`

Evite tocar em roteamento, FSM, views, templates ou OpenSpec de outros changes.

## Decisão de Design Obrigatória

Não manter LLM1/LLM2 em runtime real usando o mesmo client OpenAI genérico sem schema.

Preferir uma destas abordagens:

### Opção A — Factories por estágio

Criar factories explícitas, por exemplo:

```python
def create_openai_llm1_client() -> LlmClient:
    return OpenAiLlmClient(
        model=settings.OPENAI_MODEL_LLM1 ou settings.OPENAI_MODEL,
        response_schema_name="llm1_response",
        response_schema=Llm1Response.model_json_schema(),
    )

def create_openai_llm2_client() -> LlmClient:
    return OpenAiLlmClient(
        model=settings.OPENAI_MODEL_LLM2 ou settings.OPENAI_MODEL,
        response_schema_name="llm2_response",
        response_schema=Llm2Response.model_json_schema(),
    )
```

E ajustar o orchestrator/factory para usar cliente LLM1 no passo LLM1 e cliente LLM2 no passo LLM2.

### Opção B — Client aceita schema por chamada

Permitir `complete(..., response_schema_name=..., response_schema=...)`, mas só se isso ficar limpo e testável.

A Opção A é mais próxima do legado.

## Requisitos Funcionais

1. OpenAI runtime deve enviar `response_format` em strict schema para LLM1:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "llm1_response",
    "schema": <Llm1Response.model_json_schema() normalizado>,
    "strict": true
  }
}
```

2. OpenAI runtime deve enviar `response_format` em strict schema para LLM2 com `llm2_response` e `Llm2Response.model_json_schema()`.
3. Portar/adaptar `_normalize_openai_strict_schema()` para que schemas Pydantic sejam aceitos pelo OpenAI strict mode.
4. Manter fallback `json_object` apenas para client sem schema, se necessário para testes/compatibilidade.
5. LLM1 deve fazer retry de linguagem:
   - validar Pydantic primeiro;
   - coletar termos narrativos proibidos em campos narrativos;
   - se houver termos, chamar LLM novamente com instrução adicional;
   - validar de novo;
   - se persistirem termos, levantar erro claro.
6. LLM2 deve fazer retry de linguagem no mesmo padrão.
7. Não implementar normalização permissiva pré-Pydantic neste slice, exceto se indispensável e justificada. O objetivo é schema strict no provider, não aceitar payload fora do contrato.
8. Preservar clientes de teste (`StaticLlmClient`, `RecordingLlmClient`) sem exigir OpenAI.

## TDD — Testes RED Esperados

Antes da implementação, criar/ajustar testes que falhem com o código atual:

### LLM Client

1. `create_openai_llm1_client`/factory equivalente envia `response_format.type == "json_schema"`.
2. Payload enviado contém `json_schema.name == "llm1_response"` e `strict is True`.
3. Schema enviado contém propriedades de `Llm1Response` e não é `json_object` genérico.
4. Equivalente para LLM2 com `llm2_response`.
5. `_normalize_openai_strict_schema()` remove/ajusta constructs incompatíveis com strict mode conforme legado e garante `additionalProperties: false` nos objetos.

### Orchestrator / wiring

6. LLM1 e LLM2 usam schemas específicos no runtime real. Não basta um único `get_llm_client()` sem schema para ambos.

### Language retry LLM1

7. Primeira resposta LLM1 validada contém termo narrativo proibido; service chama o client duas vezes e retorna a segunda resposta válida.
8. Se a segunda resposta ainda contém termo proibido, `Llm1ValidationError` ou erro equivalente é levantado com mensagem clara.
9. Se a primeira resposta não contém termos proibidos, só uma chamada é feita.

### Language retry LLM2

10. Mesmo comportamento para campos narrativos de `rationale` e `policy_alignment.notes`.

## Critérios de Sucesso

- Runtime OpenAI LLM1/LLM2 usa schema strict como no legado.
- Testes provam que `response_format=json_schema` substituiu `json_object` nos clients com schema.
- Retry de linguagem portado para LLM1 e LLM2.
- Sem regressão nos testes existentes.
- Testes manuais com LLM real têm chance realista de passar sem payloads com schema inventado.

## Comandos de Validação Focados

```bash
uv run pytest apps/pipeline/tests/test_llm_client.py apps/pipeline/tests/test_llm1_service.py apps/pipeline/tests/test_llm2_service.py -q
uv run ruff check apps/pipeline
uv run mypy apps/pipeline
```

## Quality Gate Completo

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q
```

## Relatório Obrigatório

Criar:

```text
/tmp/ats-web-slice-008-openai-strict-schema-language-retry-report.md
```

Incluir:

- comparação com runtime legado;
- decisão de design escolhida para client por estágio/schema;
- detalhes de `_normalize_openai_strict_schema()` portado/adaptado;
- testes executados;
- pendências remanescentes, se houver;
- instrução para reset/atualização do ambiente dev, se necessário.

Responder com:

```text
REPORT_PATH=/tmp/ats-web-slice-008-openai-strict-schema-language-retry-report.md
```

## Stop Rule

Não implementar mudanças de UI, FSM, scope gate, presenter ou role guard neste slice.
Após concluir, commitar, dar push, informar `REPORT_PATH` e aguardar avaliação.
