# Slice 6: Quality Gate — Testes Completos + ruff + mypy

> **Status**: DONE
> **Depende de**: Slices 1-5 todos implementados
> **Change**: `openspec/changes/intake-nir/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — seção 2 (comandos de validação)

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Todos os slices do intake NIR implementados. Garantir quality gate completo.

### Sua Tarefa

1. Garantir que todos os testes passam
2. Garantir ruff check + format limpo
3. Garantir mypy limpo
4. Garantir que testes da Fase 0 (accounts, cases, llm) continuam passando

### Gates

```bash
# Gate 1: ruff lint
uv run ruff check .
# Esperado: "All checks passed!"

# Gate 2: ruff format
uv run ruff format --check .
# Esperado: "X files already formatted"

# Gate 3: mypy
uv run mypy .
# Esperado: "Success: no issues found"

# Gate 4: pytest
uv run pytest -v
# Esperado: todos passando, zero falhas

# Gate 5: gate completo
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
# Esperado: exit code 0
```

### Limpeza de código morto

- **Remover** `templates/intake/upload_success.html` — template órfão do Slice 3, substituído por `case_detail.html` no Slice 5. Nenhuma view o referencia mais.

### Ajustes comuns que podem ser necessários

- Adicionar `apps.intake.tests.*` ao mypy overrides no pyproject.toml
- Adicionar `apps.intake.migrations.*` ao mypy overrides
- Adicionar `pymupdf` / `fitz` ao mypy ignore_missing_imports
- Formatar com `uv run ruff format .` se necessário

### Relatório

Gere `/tmp/slice-intake-006-report.md` com:

```markdown
# Slice 6 Report: Quality Gate

## Configurações Aplicadas
(snippets de pyproject.toml se alterado)

## Resultado dos Gates
(output de cada gate)

## Contagem Final
- Arquivos .py: X
- Testes: X passando
- mypy: X files, 0 errors
```

Informe `REPORT_PATH=/tmp/slice-intake-006-report.md`.
