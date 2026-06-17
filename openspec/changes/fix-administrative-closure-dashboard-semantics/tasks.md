# Tasks: Corrigir semântica de encerramento administrativo no dashboard

## Slice vertical

- [x] Slice 001 — Separar encerramento administrativo em resultado final, badges e cards de totalização (`slices/slice-001-dashboard-admin-closure-semantics.md`)

## Definition of Done do change

- [x] Card “Resultado Final” no detalhe do dashboard mostra **Encerrado administrativamente** para caso com evento `CASE_ADMINISTRATIVELY_CLOSED`.
- [x] Card “Resultado Final” não mostra **Agendamento Confirmado** para caso administrativamente encerrado.
- [x] Badge de resultado na listagem do dashboard mostra **Encerrado administrativamente**.
- [x] Dashboard exibe card de totalização **Encerrados admin.**.
- [x] `Em Andamento` exclui encerrados administrativos.
- [x] `Aceitos`, `Negados`, `Encerrados admin.` e `Em Andamento` são mutuamente exclusivos na totalização diária.
- [x] Caso aceito/confirmado mas encerrado administrativamente conta como administrativo, não como aceito.
- [x] Testes relevantes adicionados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário com snippets antes/depois.
- [x] Commit e push realizados após implementação.
