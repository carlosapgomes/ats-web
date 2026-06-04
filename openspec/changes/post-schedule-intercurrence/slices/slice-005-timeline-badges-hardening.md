# Slice 005: Timeline, badges e hardening

## Handoff para implementador LLM com contexto zero

Este slice fecha o change com refinamento visual/auditável e validações de integração. Os fluxos principais já devem existir nos Slices 001–004.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. Slices 001–004
7. Este arquivo
8. Templates de timeline/detalhe NIR, fila scheduler, testes de dashboard se afetados

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Garantir que a feature seja rastreável e operacionalmente clara em múltiplos ciclos, mantendo filas, locks, timeline e métricas básicas coerentes.

## Escopo funcional

- Melhorar renderização da timeline para eventos:
  - `POST_SCHEDULE_ISSUE_OPENED`;
  - `POST_SCHEDULE_ISSUE_RESPONDED`;
  - `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`.
- Adicionar/garantir badges consistentes:
  - `Intercorrência em avaliação` quando issue `opened`;
  - `Intercorrência respondida` quando issue `responded`;
  - distinção na fila do agendador.
- Garantir que busca NIR mostra bloqueio claro para issue ativa.
- Adicionar testes de múltiplos ciclos sequenciais com timeline preservada.
- Rodar validações de integração focadas em:
  - fila NIR operacional;
  - fila agendador normal;
  - confirmação NIR normal;
  - locks scheduler/NIR.
- Atualizar documentação curta, se necessário, dentro do próprio OpenSpec ou docs operacionais existentes.

## Fora de escopo

- Dashboard/BI novo.
- Exportação de relatórios.
- Entidade separada de histórico.
- Notificações externas.
- Refactor amplo de templates.

## Arquivos prováveis

1. `templates/intake/case_detail.html` ou includes de timeline
2. `templates/intake/closed_cases.html`
3. templates de scheduler já tocados
4. testes em `apps/intake/tests/`, `apps/scheduler/tests/`, `apps/cases/tests/`
5. talvez presenter/helper pequeno para eventos, se já houver padrão
6. `openspec/changes/post-schedule-intercurrence/tasks.md` ao final

## Plano TDD obrigatório

### RED

Criar testes:

1. Timeline exibe abertura da intercorrência com motivo e mensagem quando houver.
2. Timeline exibe resposta do agendador com ação e mensagem.
3. Timeline exibe ciência NIR.
4. Dois ciclos sequenciais geram dois conjuntos de eventos em ordem cronológica.
5. Após primeiro ciclo encerrado, nova intercorrência pode ser aberta se o agendamento atual estiver confirmado.
6. Após cancelamento, nova abertura não aparece como elegível por não haver agendamento confirmado.
7. Badge `Intercorrência em avaliação` aparece para issue `opened`.
8. Badge `Intercorrência respondida` aparece para issue `responded`.
9. Fluxo normal de agendamento inicial continua sem badges de intercorrência.

### GREEN

Implementar apenas o necessário para os testes. Se já existir renderização genérica de eventos, adaptar com labels amigáveis sem criar framework de timeline.

### REFACTOR

- Extrair mapeamentos de labels se houver repetição.
- Garantir templates legíveis e pequenos.
- Remover código morto criado nos slices anteriores.

## Critérios de aceitação

- [ ] Timeline mostra os três eventos da intercorrência de forma compreensível.
- [ ] Múltiplos ciclos ficam visíveis em ordem.
- [ ] Badges aparecem nos estados ativos corretos.
- [ ] Busca NIR bloqueia duplicidade com mensagem clara.
- [ ] Caso cancelado não permite nova intercorrência por não estar confirmado.
- [ ] Fluxos sem intercorrência permanecem coerentes.
- [ ] Quality gate completo executado.

## Gates de autoavaliação

Responder no relatório:

1. Como a timeline mostra múltiplos ciclos?
2. Quais templates receberam badges e por quê?
3. Quais validações de integração foram executadas?
4. Há alguma métrica/dashboard impactada? Se sim, como foi mitigado?
5. Algum arquivo ficou grande demais ou com duplicação? Se sim, o que foi feito?

## Comandos de validação mínimos

```bash
uv run pytest apps/cases/tests apps/intake/tests apps/scheduler/tests -q
uv run ruff check apps/cases apps/intake apps/scheduler
uv run ruff format --check apps/cases apps/intake apps/scheduler
uv run mypy apps/cases apps/intake apps/scheduler
```

Quality gate completo obrigatório neste slice de fechamento:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-005-post-schedule-hardening-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-005-post-schedule-hardening-report.md
```

Pare e peça confirmação antes de arquivar/implementar novo change.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through Slice 005. Implement ONLY Slice 005 using TDD. Harden post-schedule intercurrence: friendly timeline rendering for opened/responded/acknowledged events, badges for opened/responded, duplicate-active messaging, multi-cycle tests, cancellation ineligibility, and integration checks for NIR/scheduler flows. Keep changes lean, DRY and YAGNI. Run full quality gate, update tasks.md, create /tmp/ats-web-slice-005-post-schedule-hardening-report.md, commit and push, reply REPORT_PATH and stop.
```
