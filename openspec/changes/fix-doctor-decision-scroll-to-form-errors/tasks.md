# Tasks: Rolar até o formulário de decisão médica após erro de validação

## Slice vertical

- [ ] Slice 001 — Marcador SSR `data-scroll-to-errors` + scroll JS até o primeiro campo inválido (`slices/slice-001-scroll-to-form-errors.md`)

## Definition of Done do change

- [ ] `<form id="decision-form">` recebe `data-scroll-to-errors` somente quando há erros de validação.
- [ ] `decision.js` rola até o primeiro `.is-invalid` quando o marcador está presente.
- [ ] Teste SSR: POST inválido contém o marcador; resposta sem erros não contém.
- [ ] Nenhuma mudança de validação, layout ou outra tela.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário.
- [ ] Commit e push realizados na branch do change.
