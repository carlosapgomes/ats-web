# Tasks: Banner de erro no topo da decisão médica

## Slice vertical

- [x] Slice 001 — Banner SSR com âncora nativa substituindo o scroll automático (`slices/slice-001-error-banner.md`)

## Definition of Done do change

- [x] Banner `alert-danger` aparece no topo somente quando há erros de validação, com contagem e botão de âncora.
- [x] Botão aponta para `#doctor-decision-form` e rola por âncora nativa.
- [x] Marcador `data-scroll-to-errors` e bloco de scroll JS removidos.
- [x] Testes SSR cobrem presença/ausência do banner e remoção do marcador.
- [x] Nenhuma mudança de validação ou outra tela.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice em markdown temporário.
- [x] Commit e push na branch do change.
