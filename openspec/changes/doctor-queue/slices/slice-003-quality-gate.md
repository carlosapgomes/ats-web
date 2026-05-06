# Slice 3: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Login como doctor
  - Fila médica com cards de casos pendentes
  - Clicar "Avaliar Caso" → tela de decisão
  - Aceitar com suporte + fluxo → confirmação → redirect para fila
  - Negar com motivo → confirmação → redirect para fila
  - Visual equivalente ao mock em `demo-reference/doctor/`

## Arquivos: 0 (apenas validação)
