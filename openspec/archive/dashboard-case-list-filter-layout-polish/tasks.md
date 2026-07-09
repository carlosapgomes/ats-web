<!-- markdownlint-disable MD013 -->

# Tasks: Polimento visual dos filtros de "Todos os Casos"

## Slice vertical

- [x] Slice 001 — Layout em duas linhas para filtros de "Todos os Casos"
  (`slices/slice-001-case-list-filter-layout-polish.md`)

## Definition of Done

- [x] Header do card separa título e `Atenção necessária` dos filtros.
- [x] `Atenção necessária` não fica espremido entre inputs.
- [x] Formulário de filtros usa grid Bootstrap responsivo.
- [x] Campo de busca tem mais largura que status/datas no desktop.
- [x] Mobile empilha controles de forma legível.
- [x] Labels visíveis e acessíveis foram preservadas.
- [x] Formulário da lista não envia `search` duplicado.
- [x] Hidden `metrics_date` continua preservado quando aplicável.
- [x] Busca dinâmica continua com os hooks esperados.
- [x] Fallback sem JavaScript continua funcional.
- [x] Sem alterações de queries, migrations, models, FSM ou permissões.
- [x] Testes relevantes passam.
- [x] Quality gate executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório markdown temporário criado e `REPORT_PATH` informado.
- [x] Commit e push realizados somente com arquivos de implementação do slice.

## Observação para implementadores

Não commitar os arquivos OpenSpec antes do arquivamento final do change. Se criar
relatório Markdown temporário, aplicar `markdownlint-cli2` somente nesse arquivo
criado.
