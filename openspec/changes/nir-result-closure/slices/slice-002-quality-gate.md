# Slice 2: Quality gate

## Objetivo

Validação final completa.

## Checklist

- [ ] `uv run ruff check .` — 0 errors
- [ ] `uv run ruff format --check .` — 0 errors
- [ ] `uv run mypy .` — 0 type errors
- [ ] `uv run pytest` — todos passando
- [ ] Teste manual no browser:
  - Login como NIR
  - Abrir caso aceito (APPT_CONFIRMED): ver resultado com data + suporte + fluxo
  - Abrir caso negado pelo médico: ver motivo da recusa
  - Abrir caso negado pelo scheduler: ver motivo da negativa
  - Clicar "Confirmar Recebimento" → caso marcado como CLEANED
  - Top Info mostra nome do paciente
  - Visual equivalente ao mock `demo-reference/nir/case-detail.html`

## Arquivos: 0 (apenas validação)
