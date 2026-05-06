# Slice 3: Quality gate

## Objetivo

Validação final: ruff, mypy, pytest, teste manual no browser.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Login: `admin` / `admin`
  - Selecionar papel NIR
  - Tela de upload aparece com drag & drop funcional
  - Upload de PDF → caso criado → extração de texto
  - Meus Casos → cards com badges de status
  - Detalhe do caso → stepper + timeline + PDF inline
  - Visual equivalente ao mock em `demo-reference/nir/`

## Arquivos: 0 (apenas validação)
