# Slice 5: LLM1 Service + LLM2 Service

> **Status**: TODO
> **Depende de**: Slice 1 (LLM client), Slice 2 (policy types)
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — regras do projeto
2. `docs/DOMAIN_ANALYSIS.md` — seção 3.2 (FSM), seção 5.1 (eventos)
3. `apps/llm/models.py` — PromptTemplate (get_active)
4. `apps/pipeline/llm.py` — LlmClient protocol
5. Legado `application/services/llm1_service.py` — referência
6. Legado `application/services/llm2_service.py` — referência
7. Legado `application/services/llm_json_parser.py` — referência

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Policy engine e scope detection portados. Agora criamos os serviços que chamam o LLM.

### Sua Tarefa

1. Criar JSON parser helper (decode_llm_json_object)
2. Criar `Llm1Service` — extração estruturada
3. Criar `Llm2Service` — sugestão de decisão

### Arquivos a Criar

```
apps/pipeline/json_parser.py          # decode_llm_json_object
apps/pipeline/llm1_service.py         # Llm1Service
apps/pipeline/llm2_service.py         # Llm2Service
apps/pipeline/tests/test_json_parser.py
apps/pipeline/tests/test_llm1_service.py
apps/pipeline/tests/test_llm2_service.py
```

### Detalhes Técnicos

#### json_parser.py

Portar `llm_json_parser.py` do legado:

```python
class LlmJsonParseError(RuntimeError): ...

def decode_llm_json_object(raw_response: str) -> dict[str, object]:
    """Extract JSON object from LLM response.
    Handles markdown code blocks, trailing commas, etc."""
    # Strip markdown code blocks if present
    text = raw_response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)
```

#### Llm1Service

```python
@dataclass
class Llm1Result:
    structured_data: dict[str, object]
    summary_text: str

class Llm1Service:
    def __init__(self, client: LlmClient): ...

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        extracted_text: str,
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm1Result:
        """Call LLM with prompts, parse JSON response, return structured data + summary."""
```

**Simplificação vs legado**: O legado tem validação Pydantic (Llm1Response), language guard (pt-BR retry), e interaction repository. Na Fase 2:
- Sem Pydantic validation — validar apenas que é JSON válido e tem `schema_version`
- Sem language guard — será adicionado em fase futura
- Sem interaction repository — eventos de auditoria pelo CaseEvent

O service deve:
1. Renderizar user_prompt_template com os dados do caso
2. Chamar `client.complete()`
3. Fazer decode do JSON
4. Extrair `summary.one_liner` como `summary_text`
5. Retornar o dict completo como `structured_data`

#### Llm2Service

```python
@dataclass
class Llm2Result:
    suggested_action: dict[str, object]
    contradictions: list[dict[str, object]]

class Llm2Service:
    def __init__(self, client: LlmClient): ...

    def run(
        self,
        *,
        case_id: str,
        agency_record_number: str,
        llm1_structured_data: dict[str, object],
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm2Result:
        """Call LLM with LLM1 data, parse JSON response, return suggestion."""
```

O service deve:
1. Renderizar user_prompt com llm1_structured_data
2. Chamar `client.complete()`
3. Fazer decode do JSON
4. Retornar o dict como `suggested_action`
5. `contradictions` começa vazio — será preenchido pelo reconciliation

### Testes

#### JSON Parser:
1. `test_decode_valid_json`: JSON puro → dict
2. `test_decode_json_in_markdown_block`: ` ```json ... ``` ` → dict
3. `test_decode_raises_on_invalid_json`: texto não-JSON → LlmJsonParseError

#### LLM1 Service:
4. `test_llm1_returns_structured_data`: mock client → dict com structured_data
5. `test_llm1_extracts_summary_text`: summary.one_liner extraído
6. `test_llm1_raises_on_invalid_json`: client retorna lixo → erro
7. `test_llm1_uses_prompts`: verifica system + user prompts passados ao client

#### LLM2 Service:
8. `test_llm2_returns_suggestion`: mock client → dict com suggestion
9. `test_llm2_receives_llm1_data`: structured_data passado no user prompt
10. `test_llm2_raises_on_invalid_json`: client retorna lixo → erro

### Critérios de Sucesso

```bash
uv run pytest apps/pipeline/tests/ -v
uv run pytest -v  # zero regressão
```

### Relatório

Gere `/tmp/slice-pipeline-005-report.md`.
Informe `REPORT_PATH=/tmp/slice-pipeline-005-report.md`.
