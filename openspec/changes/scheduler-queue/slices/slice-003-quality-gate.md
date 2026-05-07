# Slice 3: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Login como scheduler (via intranet IP ou desabilitar guard para teste)
  - Fila do agendador com cards de casos pendentes
  - Clicar "Agendar" → tela de confirmação
  - Confirmar com data + hora → modal → redirect para fila
  - Negar com motivo → modal → redirect para fila
  - Visual equivalente ao mock em `demo-reference/scheduler/`

## Arquivos: 0 (apenas validação)
