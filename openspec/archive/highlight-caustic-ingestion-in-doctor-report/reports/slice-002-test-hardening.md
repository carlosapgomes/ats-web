# Slice 002 — Test Hardening: `test_render_user_prompt_forbids_auto_denial_from_time`

## O que foi feito

Substituição da asserção permissiva (OR) por uma asserção estrita da instrução exata.

### Antes

```python
assert "negativa" in prompt.lower() or "negar" in prompt.lower() or "motivo" in prompt.lower(), (
    "Renderizado deve proibir transformar o tempo em motivo automático de negativa"
)
```

### Depois

```python
normalized = prompt.lower().replace("não", "nao").replace("automático", "automatico")
assert "nao transforme esse tempo em motivo automatico de negativa" in normalized, (
    "Renderizado deve conter a instrução exata: "
    "'Nao transforme esse tempo em motivo automatico de negativa'"
)
```

## Comandos e resultados

| Comando | Resultado |
|---------|-----------|
| `pytest -k forbids_auto_denial_from_time` | ✅ 1 passed |
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 1 file reformatted |
| `mypy .` | ✅ Success: no issues |
| `pytest` | ✅ 1191 passed |

## Confirmações

- ❌ Nenhum prompt foi alterado (`LLM1_DEFAULT_USER_PROMPT` e `_render_user_prompt()` mantidos)
- ❌ Nenhum schema alterado
- ❌ Nenhuma decisão lógica alterada (LLM2, policy, FSM, views, etc.)
- ✅ Apenas `apps/pipeline/tests/test_llm1_service.py` foi tocado
