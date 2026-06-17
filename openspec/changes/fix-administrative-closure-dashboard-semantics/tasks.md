# Tasks: Corrigir semântica de encerramento administrativo no dashboard

## Slice vertical

- [ ] Slice 001 — Separar encerramento administrativo em resultado final, badges e cards de totalização (`slices/slice-001-dashboard-admin-closure-semantics.md`)

## Definition of Done do change

- [ ] Card “Resultado Final” no detalhe do dashboard mostra **Encerrado administrativamente** para caso com evento `CASE_ADMINISTRATIVELY_CLOSED`.
- [ ] Card “Resultado Final” não mostra **Agendamento Confirmado** para caso administrativamente encerrado.
- [ ] Badge de resultado na listagem do dashboard mostra **Encerrado administrativamente**.
- [ ] Dashboard exibe card de totalização **Encerrados admin.**.
- [ ] `Em Andamento` exclui encerrados administrativos.
- [ ] `Aceitos`, `Negados`, `Encerrados admin.` e `Em Andamento` são mutuamente exclusivos na totalização diária.
- [ ] Caso aceito/confirmado mas encerrado administrativamente conta como administrativo, não como aceito.
- [ ] Testes relevantes adicionados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário com snippets antes/depois.
- [ ] Commit e push realizados após implementação.
