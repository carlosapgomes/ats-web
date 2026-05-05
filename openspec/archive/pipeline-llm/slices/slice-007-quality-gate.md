# Slice 7: Quality Gate — Testes Completos + ruff + mypy

> **Status**: TODO
> **Depende de**: Slices 1-6 todos implementados
> **Change**: `openspec/changes/pipeline-llm/`

---

## Leitura Obrigatória Antes de Implementar

1. `AGENTS.md` — seção 2 (comandos de validação)

---

## Handoff para Implementador (LLM com contexto zero)

### Contexto

Todos os slices da pipeline LLM implementados. Garantir quality gate completo.

### Sua Tarefa

1. Garantir que todos os testes passam (existentes + novos da pipeline)
2. Garantir ruff check + format limpo
3. Garantir mypy limpo
4. Garantir zero regressão nos testes da Fase 0 e Fase 1

### Gates

```bash
uv run ruff check .                  # All checks passed!
uv run ruff format --check .         # X files already formatted
uv run mypy .                        # Success: no issues found
uv run pytest -v                     # All passing
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
# EXIT_CODE=0
```

### Ajustes comuns que podem ser necessários

- Adicionar `apps.pipeline.*` ao mypy overrides no pyproject.toml
- Adicionar `openai` ao mypy ignore ou instalar stubs
- Formatar com `uv run ruff format .` se necessário
- Remover imports não usados

### Relatório

Gere `/tmp/slice-pipeline-007-report.md` com:

```markdown
# Slice 7 Report: Quality Gate

## Resultado dos Gates
(output de cada gate)

## Contagem Final
- Testes: X passando (X novos da pipeline)
- mypy: X files, 0 errors
- ruff: 0 errors

## Resumo da Fase 2
- Apps criados: apps/pipeline/
- Policy engine: X funções, X testes
- Services: Llm1Service, Llm2Service
- Pipeline: run_pipeline + django-q2 task
```

Informe `REPORT_PATH=/tmp/slice-pipeline-007-report.md`.
