# Follow-up Slice 003: Extrair JS inline da intercorrência

## Commit esperado

```text
refactor(scheduler): extract post-schedule issue form javascript
```

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR greenfield.
O Slice 003 do change `post-schedule-intercurrence` implementou a resolução da
intercorrência pelo agendador. Um verificador apontou que o template novo
`templates/scheduler/confirm_post_schedule_issue.html` contém JavaScript inline
para alternar seções do formulário conforme a ação escolhida.

O template original de agendamento usa arquivo externo
`static/js/scheduler_confirm.js`. Este follow-up deve alinhar o template novo ao
mesmo padrão, sem mudar regra de negócio.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. `openspec/changes/post-schedule-intercurrence/slices/slice-003-scheduler-resolve-issue.md`
7. Este arquivo
8. `templates/scheduler/confirm_post_schedule_issue.html`
9. `templates/scheduler/confirm.html`
10. `static/js/scheduler_confirm.js`
11. `apps/scheduler/tests/`

Implemente **somente este follow-up**. Não avance para o Slice 004.

## Problema

`confirm_post_schedule_issue.html` tem aproximadamente 40 linhas de JS inline
para UI toggle. Isso não contém lógica de negócio, mas deixa o template menos
limpo e fora do padrão já adotado pelo agendador.

## Objetivo

Extrair o JS inline para arquivo estático dedicado, por exemplo:

```text
static/js/post_schedule_issue_form.js
```

O template deve carregar esse arquivo externo e continuar carregando
`work_lock.js` como antes.

## Escopo funcional

- Remover o bloco `<script>...</script>` inline de
  `templates/scheduler/confirm_post_schedule_issue.html`.
- Criar `static/js/post_schedule_issue_form.js` com o comportamento equivalente.
- Manter a lógica exclusivamente de apresentação:
  - alternar campos/seções conforme ação selecionada;
  - ajustar required/disabled se o JS inline já fazia isso;
  - não adicionar regra de negócio nova.
- Garantir que o script inicializa com segurança quando os elementos existem.
- Garantir que a página não quebra caso algum elemento esperado esteja ausente.
- Atualizar ou adicionar teste simples que confirme que o template carrega o
  arquivo JS externo e não contém o bloco inline removido.

## Fora de escopo

- Alterar serviço de domínio da intercorrência.
- Alterar validações server-side do formulário.
- Alterar ações do agendador.
- Refatorar `scheduler_confirm.js`.
- Resolver duplicação de `conftest.py`.
- Corrigir type hints `case_id: str`.
- Implementar Slice 004.

## Plano TDD obrigatório

### RED

Adicionar ou ajustar teste em `apps/scheduler/tests/`:

1. GET da tela de intercorrência do agendador inclui:

```html
<script src="/static/js/post_schedule_issue_form.js"></script>
```

ou caminho equivalente gerado por `{% static %}`.

1. O HTML renderizado não contém o JS inline antigo. Use uma asserção simples,
   por exemplo ausência de trecho específico do código inline removido.

### GREEN

- Criar o arquivo JS estático.
- Mover a lógica inline para o arquivo.
- Substituir o bloco inline por `<script src="{% static 'js/post_schedule_issue_form.js' %}"></script>`.
- Manter `work_lock.js` carregado.

### REFACTOR

- Nomear funções de forma clara.
- Evitar dependências externas.
- Usar Vanilla JS.
- Evitar duplicação desnecessária com `scheduler_confirm.js`, mas não fazer
  refactor amplo.

## Critérios de aceitação

- [ ] `confirm_post_schedule_issue.html` não possui JS inline de toggle.
- [ ] `static/js/post_schedule_issue_form.js` existe e contém o comportamento
  equivalente.
- [ ] A tela continua carregando `work_lock.js`.
- [ ] Teste confirma que o arquivo JS externo é carregado.
- [ ] Nenhuma regra server-side foi alterada.
- [ ] Débito técnico correspondente em `tasks.md` foi marcado como resolvido.
- [ ] Commit e push realizados com a mensagem esperada.

## Gates de autoavaliação

Responder no relatório:

1. Qual bloco inline foi removido?
2. Qual arquivo JS foi criado?
3. O comportamento é apenas apresentação/UI toggle?
4. Alguma validação server-side mudou? Deve ser “não”.
5. `work_lock.js` continua carregado?
6. O item de débito técnico em `tasks.md` foi marcado como resolvido?

## Comandos de validação mínimos

```bash
uv run pytest apps/scheduler/tests -q
uv run ruff check apps/scheduler
uv run ruff format --check apps/scheduler
uv run mypy apps/scheduler
markdownlint-cli2 --config /home/dev/.markdownlint.json \
  "openspec/changes/post-schedule-intercurrence/**/*.md" \
  "openspec/changes/post-schedule-intercurrence/*.md"
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-follow-up-slice-003-extract-inline-js-report.md
```

Incluir resumo, arquivos tocados, snippets antes/depois, testes, validações,
riscos, atualização de `tasks.md`, commit hash e push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-follow-up-slice-003-extract-inline-js-report.md
```

Pare e peça confirmação antes de iniciar o Slice 004.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through follow-up-slice-003-extract-inline-js.md. Implement ONLY this follow-up. Extract the inline UI-toggle JavaScript from templates/scheduler/confirm_post_schedule_issue.html into static/js/post_schedule_issue_form.js, load it via {% static %}, keep work_lock.js loaded, preserve server-side behavior and validations, add/update scheduler tests to assert the external JS is loaded and inline JS was removed, mark the corresponding technical-debt item in tasks.md as resolved, run validations, commit with "refactor(scheduler): extract post-schedule issue form javascript", push, reply REPORT_PATH and stop.
```
