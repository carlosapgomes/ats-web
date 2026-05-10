# Slice 3: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Criar caso com agency_record_number que tem negação recente
  - Abrir decisão médica → card "Caso Anterior" visível
  - Verificar motivo, data e contagem
  - Abrir case detail → card visível
  - Caso sem anterior → sem card

## Arquivos: 0 (apenas validação)
