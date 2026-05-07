# Slice 3: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [x] `uv run ruff check .` — 0 errors
- [x] `uv run ruff format --check .` — 0 errors
- [x] `uv run mypy .` — 0 type errors
- [x] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Login como admin → dashboard → clicar "Usuários"
  - Criar novo usuário com papéis
  - Editar papéis de usuário existente
  - Bloquear/desbloquear usuário (verificar proteção auto-bloqueio)
  - Clicar "Prompts" → lista de prompts
  - Criar nova versão de prompt
  - Ativar/desativar versão
  - Login como manager → pode ver mas não editar

## Arquivos: 0 (apenas validação)
