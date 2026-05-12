# Slice 3: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Chrome DevTools → Application → Manifest → app instalável
  - Service Worker registrado e ativo
  - Ícone aparece na aba e como touch icon
  - Badge de contagem visível para doctor/scheduler
  - Layout mobile sem quebras (< 576px)
  - Instalar como PWA → abre standalone
  - Badges atualizam ao criar/resolver casos

## Arquivos: 0 (apenas validação)
