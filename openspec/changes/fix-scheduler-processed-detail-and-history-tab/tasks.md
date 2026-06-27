# Tasks: Corrigir detalhe do agendador e aba de busca histórica

## Dimensionamento dos slices

Este change foi planejado com **2 slices verticais e enxutos**, mais **1 follow-up hardening** do Slice 001 antes do Slice 002.

Justificativa:

- O problema funcional/segurança de papel está no detalhe de `Processados Hoje`; ele deve ser entregue sozinho para reduzir risco e garantir que o agendador possa comunicar o NIR sem ver ações do NIR.
- O problema de UI da busca antiga como aba é independente e pode ser entregue depois, tocando poucos templates/testes.
- Combinar tudo em um slice aumentaria escopo de arquivos e dificultaria revisão por terceiro LLM.
- Quebrar o plano original em mais de 2 slices geraria fatias horizontais pequenas demais sem valor operacional isolado.
- O follow-up foi criado após avaliação do Slice 001 para corrigir duas regressões/correções pequenas antes de avançar: microcopy imprecisa de `Comunicar NIR` e perda do link de PDF no detalhe de `Processados Hoje`.

## Slices verticais

- [x] Slice 001 — Detalhe único do scheduler + mensagem ao NIR em `Processados Hoje` (`slices/slice-001-unified-scheduler-detail-message-nir.md`)
- [x] Follow-up Slice 001 — Microcopy e link de PDF no detalhe scheduler (`slices/follow-up-slice-001-copy-and-pdf-hardening.md`)
- [ ] Slice 002 — `Buscar caso antigo` como terceira aba do agendador (`slices/slice-002-historical-search-as-tab.md`)

## Definition of Done do change

- [ ] `scheduler_processed_detail` não renderiza mais `templates/intake/case_detail.html`.
- [ ] `Processados Hoje` e busca histórica/contextual usam um único template de detalhe do scheduler.
- [ ] Detalhe do scheduler aberto por `Processados Hoje` não mostra `Reenviar caso corrigido`.
- [ ] Detalhe do scheduler aberto por `Processados Hoje` não mostra `Confirmar Recebimento`.
- [ ] Detalhe do scheduler aberto por `Processados Hoje` mostra `Comunicar NIR` para casos em escopo scheduler.
- [x] Microcopy de `Comunicar NIR` é neutra e não afirma que caso recém-processado já está encerrado.
- [x] Detalhe do scheduler aberto por `Processados Hoje` mostra link/atalho para PDF original via `scheduler:processed_pdf`.
- [ ] Agendador consegue enviar mensagem ao NIR a partir de caso processado hoje.
- [ ] Mensagem ao NIR preserva menções adicionais e não altera `Case.status`.
- [ ] Detalhe contextual por notificação continua funcionando e sem ações de workflow.
- [ ] Navegação principal do agendador mostra `Pendentes`, `Processados Hoje` e `Buscar caso antigo`.
- [ ] Botão pequeno separado `🔍 Buscar histórico` removido de `scheduler/queue.html`.
- [ ] Página de busca histórica mostra a aba `Buscar caso antigo` ativa.
- [x] Nenhuma migration criada.
- [x] Nenhum estado FSM criado/alterado.
- [x] Testes relevantes escritos/ajustados antes da implementação passar (TDD RED → GREEN → REFACTOR).
- [x] Clean code aplicado: nomes claros, funções coesas, baixo acoplamento, sem dead code.
- [x] DRY aplicado localmente, sem refactor amplo horizontal.
- [x] YAGNI aplicado: sem novo model/tabela, sem busca avançada, sem WebSocket/SSE, sem email/SMS/push operacional.
- [x] Quality gate do AGENTS.md executado:
  - [x] `uv run ruff check .`
  - [x] `uv run ruff format --check .`
  - [x] `uv run mypy .`
  - [x] `uv run pytest`
- [x] Cada slice gera relatório markdown temporário com snippets antes/depois e evidências.
- [x] Cada implementação responde com `REPORT_PATH=<arquivo-temporario>`.
- [ ] Commit e push realizados após cada slice implementado.

## Nota para implementadores

Implementar apenas o próximo slice incompleto. Não iniciar o slice seguinte sem confirmação explícita do usuário/planner.
