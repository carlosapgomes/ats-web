# Follow-up: Correção pós Slice 5

> **Prioridade**: antes do Slice 6
> **Motivo**: mensagem de erro do login ainda diz "Email" mas o campo é "Usuário"

---

## Correção: Mensagem de erro do login

**Arquivo**: `apps/accounts/views.py`

```python
# Antes:
messages.error(request, "Email ou senha inválidos.")

# Depois:
messages.error(request, "Usuário ou senha inválidos.")
```

Uma linha, um arquivo. Sem necessidade de novo teste — o teste `test_login_invalid_credentials` já valida que a mensagem contém "inválid", o que continua verdadeiro.

## Gates

```bash
uv run ruff check . && uv run pytest -v
```

Esperado: 81 testes passando, zero mudança de comportamento.

## Relatório

Gere `/tmp/slice-005-followup-report.md`.
Informe `REPORT_PATH=/tmp/slice-005-followup-report.md`.
