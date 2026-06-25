# Tasks: Acesso contextual CHD e detalhe histórico antes da intercorrência

## Slices verticais

- [x] Slice 001 — NIR histórico: cards → detalhe → intercorrência (`slices/slice-001-nir-historical-detail-before-intercurrence.md`)
- [x] Slice 002 — CHD mencionado: detalhe read-only e resposta sem workflow (`slices/slice-002-mentioned-scheduler-readonly-context.md`)
- [x] Slice 003 — CHD histórico: busca e mensagem operacional ao NIR (`slices/slice-003-scheduler-historical-search-message-nir.md`)

## Definition of Done do change

- [ ] NIR vê resultados da busca de encerrados como cards com botão `Detalhes`.
- [ ] NIR consegue abrir detalhe histórico de caso `CLEANED` pela busca.
- [ ] NIR consegue abrir detalhe histórico de caso `CLEANED` ao abrir notificação vinculada ao caso.
- [ ] Detalhe histórico NIR mostra contexto do caso, timeline e comunicação operacional.
- [ ] Dentro do detalhe histórico, NIR consegue registrar intercorrência quando o caso é elegível.
- [ ] Detalhe histórico mostra motivo claro quando o caso não é elegível para intercorrência.
- [ ] Abertura de intercorrência continua usando `open_post_schedule_issue` existente.
- [ ] Abertura de intercorrência move caso elegível para `WAIT_APPT` e registra eventos existentes.
- [x] Scheduler mencionado em caso fora de `WAIT_APPT` abre detalhe read-only contextual por notificação.
- [x] Scheduler mencionado consegue responder na comunicação quando o caso não está `CLEANED`.
- [x] Scheduler mencionado não vê ações de agendamento, resposta de intercorrência, lock ou mudança de FSM.
- [x] Scheduler sem notificação não abre detalhe contextual por UUID.
- [x] Scheduler consegue buscar casos históricos agendados/processados por ocorrência ou nome.
- [x] Scheduler consegue abrir detalhe histórico read-only de caso elegível pela busca.
- [x] Scheduler consegue enviar mensagem operacional ao NIR em caso histórico.
- [x] Mensagem histórica do scheduler garante notificação in-app para usuários NIR ativos.
- [x] Mensagem histórica do scheduler permite menções adicionais a usuários/grupos e preserva/notifica esses destinatários pelo parser existente.
- [x] Mensagem histórica do scheduler em caso `CLEANED` não altera `Case.status`.
- [x] `post_case_communication_message` mantém bloqueio de `CLEANED` por padrão, liberando apenas quando caller explícito validar acesso histórico.
- [x] `resolve_notification_redirect_url` redireciona NIR `CLEANED` para detalhe histórico.
- [x] `resolve_notification_redirect_url` redireciona scheduler fora de `WAIT_APPT` para detalhe contextual.
- [x] Nenhum novo estado FSM é criado.
- [x] Nenhum modelo/tabela de solicitação CHD é criado neste MVP.
- [x] Testes relevantes foram escritos antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: nomes claros, funções pequenas, coesão, baixo acoplamento, sem dead code.
- [x] DRY aplicado: serviço de comunicação e serviços de intercorrência reutilizados; sem duplicar regra de elegibilidade em views.
- [x] YAGNI aplicado: sem ticket model, sem WebSocket/SSE, sem push/SMS/email operacional, sem busca avançada.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [ ] Relatório markdown temporário criado por cada slice com snippets antes/depois e evidências.
- [x] Cada slice atualiza este `tasks.md` ao concluir.
- [ ] Commit e push realizados após cada slice.

## Notas para implementadores

- Use slices verticais e enxutos. Não implementar Slice 002/003 junto com Slice 001.
- O NIR deve abrir intercorrência **dentro dos detalhes**, não diretamente no card.
- O CHD/scheduler nunca reabre o caso diretamente; ele apenas envia comunicação operacional ao NIR.
- Para caso `CLEANED`, não liberar comunicação globalmente. Se necessário, use parâmetro explícito (`allow_cleaned=True`) somente após validação contextual.
- Não criar novo estado FSM.
- Não criar modelo/tabela de solicitação CHD neste change.
- Se um slice precisar tocar mais arquivos que o previsto, justificar no relatório antes de ampliar escopo.

## Status final do change

Slice 003 implementado. Todos os 3 slices verticais concluídos.
