# Tasks: Banner de erro no topo da decisão médica

## Slice vertical

- [ ] Slice 001 — Banner SSR com âncora nativa substituindo o scroll automático (`slices/slice-001-error-banner.md`)

## Definition of Done do change

- [ ] Banner `alert-danger` aparece no topo somente quando há erros de validação, com contagem e botão de âncora.
- [ ] Botão aponta para `#doctor-decision-form` e rola por âncora nativa.
- [ ] Marcador `data-scroll-to-errors` e bloco de scroll JS removidos.
- [ ] Testes SSR cobrem presença/ausência do banner e remoção do marcador.
- [ ] Nenhuma mudança de validação ou outra tela.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice em markdown temporário.
- [ ] Commit e push na branch do change.
