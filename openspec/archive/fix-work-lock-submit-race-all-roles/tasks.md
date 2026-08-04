# Tasks: Corrigir race condition de reserva ao submeter ações com lock

## Slice vertical

- [x] Slice 001 — Proteção central contra release durante submit + mensagem acionável (`slices/slice-001-protect-lock-submit-and-message.md`)

## Definition of Done do change

- [x] `work_lock.js` identifica submissão protegida apenas em forms com `lock_token` correspondente ao lock atual.
- [x] `work_lock.js::sendRelease()` não libera lock enquanto submissão protegida está em andamento.
- [x] `visibilitychange` não libera reserva de card aberto.
- [x] Cliques em links de saída continuam liberando reserva quando não há submit protegido em andamento.
- [x] `scheduler_confirm.js` protege o caminho programático `form.submit()`.
- [x] Doctor e NIR herdam a proteção central sem alteração de fluxo, templates ou views.
- [x] `assert_case_lock` usa mensagem acionável para lock ausente ou expirado:
  - `A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.`
- [x] Mensagens de token inválido, usuário diferente e contexto diferente não foram relaxadas.
- [x] Nenhum model, migration, URL, endpoint novo ou FSM foi alterado.
- [x] Testes relevantes foram adicionados/ajustados antes da implementação passar.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Relatório do slice gerado em markdown temporário com snippets antes/depois, evidência TDD, resultados dos gates e respostas aos gates de autoavaliação.
- [x] Commit e push realizados após implementação.
