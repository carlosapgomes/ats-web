# Follow-up Slice 001: Ajustar transição de ciência da intercorrência

## Commit esperado

```text
fix(cases): streamline post-schedule issue acknowledgement transition
```

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR greenfield.
O Slice 001 do change `post-schedule-intercurrence` já foi implementado e
commitado em `ea1a307`. Um verificador apontou uma melhoria não-bloqueante,
mas importante antes de seguir para o Slice 002.

Leia, nesta ordem:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. `openspec/changes/post-schedule-intercurrence/slices/slice-001-domain-fsm-services.md`
7. Este arquivo
8. `apps/cases/models.py`
9. `apps/cases/services.py`
10. `apps/cases/tests/test_post_schedule_issue_services.py`
11. `/tmp/ats-web-slice-001-post-schedule-domain-report.md`, se existir

Implemente **somente este follow-up** com TDD/ajuste focado. Não avance para o
Slice 002.

## Problema

`acknowledge_post_schedule_issue` atualmente encerra a intercorrência passando
por dois estados/saves transitórios:

```text
WAIT_R1_CLEANUP_THUMBS
→ CLEANUP_RUNNING
→ CLEANED
```

Isso reaproveita o cleanup normal, mas nesta feature não há cleanup real. O
resultado é semanticamente ruim: gera um estado transitório artificial e pode
criar eventos de cleanup que não representam uma ação operacional real.

Como o projeto é greenfield e ainda não está em produção, não precisamos manter
compatibilidade retrógrada com essa implementação inicial.

## Objetivo

Criar uma transição FSM direta e explícita para encerrar a intercorrência após
ciência do NIR:

```text
WAIT_R1_CLEANUP_THUMBS → CLEANED
```

A função `acknowledge_post_schedule_issue` deve limpar os campos da
intercorrência ativa, executar essa transição direta e salvar o caso sem passar
por `CLEANUP_RUNNING`.

## Escopo funcional

- Adicionar ao `Case` uma transição FSM dedicada para ciência de intercorrência,
  por exemplo:

```python
@transition(
    field=status,
    source=CaseStatus.WAIT_R1_CLEANUP_THUMBS,
    target=CaseStatus.CLEANED,
)
def post_schedule_issue_acknowledged(self, user=None):
    self._record_event("POST_SCHEDULE_ISSUE_ACKNOWLEDGED", user=user)
```

- Ajustar `acknowledge_post_schedule_issue` para:
  - exigir `post_schedule_issue_status == responded`;
  - limpar campos da intercorrência ativa;
  - chamar a nova transição direta;
  - fazer apenas o save necessário;
  - não chamar `cleanup_triggered` nem `cleanup_completed`.
- Ajustar/remover evento manual duplicado se a nova transição já registrar
  `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` via `_record_event`.
- Atualizar testes para garantir que:
  - o caso sai de `WAIT_R1_CLEANUP_THUMBS` direto para `CLEANED`;
  - eventos `CLEANUP_TRIGGERED` e `CLEANUP_COMPLETED` não são criados nesse
    fluxo;
  - `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` continua sendo criado uma única vez;
  - campos da intercorrência continuam limpos;
  - múltiplos ciclos sequenciais continuam possíveis.
- Corrigir o relatório temporário do Slice 001, se existir, removendo a menção
  a “pendente — aguardando confirmação” caso o push já tenha ocorrido e
  registrando esta correção como follow-up.

## Fora de escopo

- Implementar qualquer parte do Slice 002.
- Criar UI NIR ou agendador.
- Alterar regras de abertura/resposta da intercorrência.
- Criar novos estados FSM.
- Alterar o fluxo normal de cleanup para casos sem intercorrência.
- Marcar o checkbox global “Cada slice teve commit e push” em `tasks.md`, pois
  ele pertence ao DoD do change inteiro e só deve ser marcado ao fim de todos
  os slices.

## Plano TDD obrigatório

### RED

Antes da mudança, adicione ou ajuste testes em
`apps/cases/tests/test_post_schedule_issue_services.py`:

1. `acknowledge_post_schedule_issue` não cria `CLEANUP_TRIGGERED`.
2. `acknowledge_post_schedule_issue` não cria `CLEANUP_COMPLETED`.
3. `acknowledge_post_schedule_issue` cria exatamente um
   `POST_SCHEDULE_ISSUE_ACKNOWLEDGED`.
4. O caso fica `CLEANED` após a ciência.
5. Os campos `post_schedule_issue_*` são limpos.
6. Um novo ciclo pode ser aberto depois da ciência se o agendamento atual ainda
   estiver confirmado.

### GREEN

Implemente a nova transição direta no model e ajuste o serviço com o mínimo de
mudança necessário para os testes passarem.

### REFACTOR

- Remova código morto ou comentário antigo mencionando
  `cleanup_triggered → cleanup_completed` neste fluxo.
- Mantenha nomes explícitos e domínio claro.
- Não crie abstração genérica de FSM.

## Critérios de aceitação

- [ ] `acknowledge_post_schedule_issue` não passa por `CLEANUP_RUNNING`.
- [ ] O encerramento da intercorrência usa transição direta
      `WAIT_R1_CLEANUP_THUMBS → CLEANED`.
- [ ] `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` é criado uma única vez.
- [ ] Eventos de cleanup não são criados nesse fluxo.
- [ ] Fluxo normal de cleanup continua inalterado.
- [ ] Testes de `apps/cases` passam.
- [ ] `tasks.md` não marca o DoD global de todos os slices como completo.
- [ ] Relatório temporário do Slice 001 é corrigido se existir.
- [ ] Commit e push realizados com a mensagem esperada.

## Gates de autoavaliação

Responder no relatório:

1. Qual transição FSM direta foi adicionada?
2. Quantos saves `acknowledge_post_schedule_issue` faz agora?
3. Como os testes provam que eventos de cleanup não são gerados?
4. O evento `POST_SCHEDULE_ISSUE_ACKNOWLEDGED` é criado onde?
5. Algum comportamento do cleanup normal foi alterado? Deve ser “não”.
6. O checkbox global de commit/push permaneceu desmarcado? Deve ser “sim”.

## Comandos de validação mínimos

```bash
uv run pytest apps/cases/tests/test_post_schedule_issue_services.py -q
uv run pytest apps/cases/tests -q
uv run ruff check apps/cases
uv run ruff format --check apps/cases
uv run mypy apps/cases
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
/tmp/ats-web-follow-up-slice-001-ack-transition-fix-report.md
```

Incluir resumo, arquivos tocados, snippets antes/depois, testes, validações,
riscos, atualização documental, commit hash e push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-follow-up-slice-001-ack-transition-fix-report.md
```

Pare e peça confirmação antes de iniciar o Slice 002.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through follow-up-slice-001-acknowledgement-transition-fix.md. Implement ONLY this follow-up using TDD. Add a direct FSM transition for post-schedule issue acknowledgement from WAIT_R1_CLEANUP_THUMBS to CLEANED, update acknowledge_post_schedule_issue to use it without cleanup_triggered/cleanup_completed, ensure POST_SCHEDULE_ISSUE_ACKNOWLEDGED is created once and cleanup events are not created, keep normal cleanup unchanged, fix the Slice 001 temp report if present, do not mark the change-level commit/push DoD checkbox, run validations, commit with "fix(cases): streamline post-schedule issue acknowledgement transition", push, reply REPORT_PATH and stop.
```
