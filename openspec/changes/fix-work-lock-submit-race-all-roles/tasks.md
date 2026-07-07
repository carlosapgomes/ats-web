# Tasks: Corrigir race condition de reserva ao submeter ações com lock

## Slice vertical

- [ ] Slice 001 — Proteção central contra release durante submit + mensagem acionável (`slices/slice-001-protect-lock-submit-and-message.md`)

## Definition of Done do change

- [ ] `work_lock.js` identifica submissão protegida apenas em forms com `lock_token` correspondente ao lock atual.
- [ ] `work_lock.js::sendRelease()` não libera lock enquanto submissão protegida está em andamento.
- [ ] `visibilitychange` não libera reserva de card aberto.
- [ ] Cliques em links de saída continuam liberando reserva quando não há submit protegido em andamento.
- [ ] `scheduler_confirm.js` protege o caminho programático `form.submit()`.
- [ ] Doctor e NIR herdam a proteção central sem alteração de fluxo, templates ou views.
- [ ] `assert_case_lock` usa mensagem acionável para lock ausente ou expirado:
  - `A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.`
- [ ] Mensagens de token inválido, usuário diferente e contexto diferente não foram relaxadas.
- [ ] Nenhum model, migration, URL, endpoint novo ou FSM foi alterado.
- [ ] Testes relevantes foram adicionados/ajustados antes da implementação passar.
- [ ] Quality gate do AGENTS.md executado:
  - [ ] `uv run ruff check .`
  - [ ] `uv run ruff format --check .`
  - [ ] `uv run mypy .`
  - [ ] `uv run pytest`
- [ ] Relatório do slice gerado em markdown temporário com snippets antes/depois, evidência TDD, resultados dos gates e respostas aos gates de autoavaliação.
- [ ] Commit e push realizados após implementação.
