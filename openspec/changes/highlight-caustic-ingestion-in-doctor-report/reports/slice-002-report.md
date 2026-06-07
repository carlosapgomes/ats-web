# Relatório Slice 002 — Reforço do prompt canônico LLM1 para resumo narrativo

## Resumo

Reforço do `LLM1_DEFAULT_USER_PROMPT` e do prompt renderizado por `_render_user_prompt()` para instruir o LLM1 a mencionar ingestão cáustica/corrosiva e tempo desde a ingestão no resumo narrativo, sem transformar o tempo em motivo automático de negativa.

## Arquivos alterados

1. **`apps/pipeline/llm1_service.py`** — Adicionada instrução em `LLM1_DEFAULT_USER_PROMPT` e no corpo de `_render_user_prompt()`.
2. **`apps/pipeline/tests/test_llm1_service.py`** — Adicionada classe `TestLlm1CausticIngestionPrompt` com 5 testes.
3. **`apps/llm/tests/test_seed_prompts.py`** — Adicionado teste `test_llm1_user_seed_mentions_caustic_ingestion`.

## Snippets: Antes → Depois

### `LLM1_DEFAULT_USER_PROMPT` (antes)

```python
    "Registrar had_transfusion como binario (yes/no); ausencia de "
    "evidencia de transfusao deve ser tratada como 'no'. "
    "Em tracked_exams, inclua apenas exames efetivamente realizados; "
```

### `LLM1_DEFAULT_USER_PROMPT` (depois)

```python
    "Registrar had_transfusion como binario (yes/no); ausencia de "
    "evidencia de transfusao deve ser tratada como 'no'. "
    "Se houver ingestao de substancia caustica/corrosiva, soda caustica, "
    "produto corrosivo ou acido em contexto de ingestao, mencione o evento "
    "no resumo e inclua o tempo desde a ingestao quando disponivel. "
    "Em tracked_exams, inclua apenas exames efetivamente realizados; "
```

### `_render_user_prompt()` (antes)

```python
        "e hemocomponent quando disponivel.\n"
        f"Texto clinico do relatorio:\n{clean_text}"
```

### `_render_user_prompt()` (depois)

```python
        "e hemocomponent quando disponivel.\n"
        "Se o relatorio mencionar ingestao de substancia caustica/corrosiva, "
        "soda caustica, produto corrosivo ou acido em contexto de ingestao, "
        "mencione esse evento no summary.one_liner ou summary.bullet_points e "
        "inclua o tempo desde a ingestao quando o texto informar "
        "(por exemplo, \"ha 3 semanas\" ou \"em 12/05/2026\"). "
        "Nao transforme esse tempo em motivo automatico de negativa.\n"
        f"Texto clinico do relatorio:\n{clean_text}"
```

## Testes adicionados

### `apps/pipeline/tests/test_llm1_service.py` — `TestLlm1CausticIngestionPrompt`

| Teste | O que verifica |
|-------|----------------|
| `test_default_user_prompt_mentions_caustic_ingestion` | `LLM1_DEFAULT_USER_PROMPT` contém `cáustica`/`caustica` ou `corrosiva`/`corrosivo` |
| `test_default_user_prompt_mentions_time_since_ingestion` | `LLM1_DEFAULT_USER_PROMPT` menciona `tempo desde` ou `tempo` |
| `test_render_user_prompt_mentions_caustic_ingestion` | Prompt renderizado menciona ingestão cáustica/corrosiva |
| `test_render_user_prompt_mentions_time_when_available` | Prompt renderizado instrui incluir tempo quando disponível |
| `test_render_user_prompt_forbids_auto_denial_from_time` | Prompt renderizado proíbe transformar tempo em motivo automático de negativa |

### `apps/llm/tests/test_seed_prompts.py` — `test_llm1_user_seed_mentions_caustic_ingestion`

Verifica que o seed do `llm1_user` contém instrução de ingestão cáustica/corrosiva.

## Quality Gate

| Comando | Resultado |
|---------|-----------|
| `uv run ruff check .` | ✅ All checks passed |
| `uv run ruff format --check .` | ✅ 3 files reformatted |
| `uv run mypy .` | ✅ Success: no issues found |
| `uv run pytest` | ✅ 1191 passed |

## Gates de autoavaliação

### 1. A instrução aparece no default e no prompt renderizado?

✅ **Sim.** `LLM1_DEFAULT_USER_PROMPT` contém: *"Se houver ingestao de substancia caustica/corrosiva, soda caustica, produto corrosivo ou acido em contexto de ingestao, mencione o evento no resumo e inclua o tempo desde a ingestao quando disponivel."*

`_render_user_prompt()` também contém a instrução completa, incluindo a proibição de negativa automática.

### 2. O texto deixa claro que o tempo não vira motivo automático de negativa?

✅ **Sim.** A linha final do prompt renderizado diz explicitamente: *"Nao transforme esse tempo em motivo automatico de negativa."*

Teste `test_render_user_prompt_forbids_auto_denial_from_time` verifica esse requisito.

### 3. `seed_prompts` continua sem sobrescrever prompts existentes?

✅ **Sim.** Nenhuma alteração foi feita em `seed_prompts.py`. O comando continua usando `get_or_create` implícito via `if exists: skip`. O teste `test_idempotent` em `test_seed_prompts.py` comprova.

### 4. Algum schema ou campo JSON novo foi criado?

❌ **Não.** Nenhum schema, migration ou campo JSON foi criado. A informação flui pelo resumo narrativo existente (`summary.one_liner`, `summary.bullet_points`).

### 5. Algum arquivo fora dos esperados foi alterado? Se sim, por quê?

Apenas os 3 arquivos esperados foram alterados:
- `apps/pipeline/llm1_service.py` (esperado)
- `apps/pipeline/tests/test_llm1_service.py` (esperado)
- `apps/llm/tests/test_seed_prompts.py` (opcional, conforme slice)

Nenhum arquivo inesperado foi tocado. `seed_prompts.py` não foi alterado (já importa `LLM1_DEFAULT_USER_PROMPT`).

## Conclusão

Slice 002 completo com TDD (RED → GREEN → REFACTOR). Todos os critérios de sucesso e gates de autoavaliação são atendidos.
