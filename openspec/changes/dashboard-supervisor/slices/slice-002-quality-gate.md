# Slice 2: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Login como admin → redireciona para `/dashboard/`
  - Summary cards com contagens
  - Filtros por status e data funcionam
  - Paginação funciona
  - Clicar "Ver" → detalhe do caso
  - Login como manager → mesmo dashboard
  - Visual equivalente ao mock `demo-reference/admin/dashboard.html`

## Arquivos: 0 (apenas validação)
