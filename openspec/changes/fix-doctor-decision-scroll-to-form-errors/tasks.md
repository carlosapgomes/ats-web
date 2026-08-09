# Tasks: Rolar até o formulário de decisão médica após erro de validação

## Slice vertical

- [x] Slice 001 — Marcador SSR `data-scroll-to-errors` + scroll JS até o primeiro campo inválido (`slices/slice-001-scroll-to-form-errors.md`)

## Definition of Done do change

^- [x] `<form id="decision-form">` recebe `data-scroll-to-errors` somente quando há erros de validação.
- [x] `decision.js` rola até o primeiro `.is-invalid` quando o marcador está presente.
- [x] Teste SSR: POST inválido contém o marcador; resposta sem erros não contém.
- [x] Nenhuma mudança de validação, layout ou outra tela.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário.
- [x] Commit e push realizados na branch do change.
