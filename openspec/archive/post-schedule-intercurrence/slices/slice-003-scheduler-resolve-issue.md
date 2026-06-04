# Slice 003: Agendador resolve intercorrência

## Handoff para implementador LLM com contexto zero

Este slice adapta a fila/formulário do agendador para casos `WAIT_APPT` que são intercorrência pós-agendamento, mantendo o fluxo de agendamento inicial coerente.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/post-schedule-intercurrence/proposal.md`
4. `openspec/changes/post-schedule-intercurrence/design.md`
5. `openspec/changes/post-schedule-intercurrence/tasks.md`
6. Slices 001 e 002
7. Este arquivo
8. `apps/scheduler/views.py`, `apps/scheduler/forms.py`, templates e testes existentes
9. Serviços de lock em `apps/cases/services.py`

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Quando uma intercorrência aberta pelo NIR estiver em `WAIT_APPT`, o agendador deve vê-la na fila, abrir com lock existente, ler motivo/mensagem do NIR e responder com uma das ações:

```text
cancel | reschedule | maintain | deny
```

Após resposta, o caso deve ir para `WAIT_R1_CLEANUP_THUMBS` aguardando ciência NIR.

## Escopo funcional

- Destacar cards de intercorrência na fila do agendador.
- Na tela de confirmação/agendamento, renderizar variante de formulário para intercorrência ativa.
- Reusar lock existente `scheduler_confirm` para GET/POST.
- Form de resposta:
  - ação obrigatória;
  - mensagem/motivo do agendador obrigatório para `cancel` e `deny`; recomendado/permitido para outros;
  - campos de data/local/instruções obrigatórios para `reschedule`;
  - para `maintain`, não exigir nova data.
- Chamar serviço do Slice 001 para responder e auditar.
- Redirecionar para fila do agendador com feedback.

## Fora de escopo

- NIR confirmar ciência final.
- Criar tela separada de agendamento histórico.
- Alterar fluxo normal de agendamento inicial exceto para ramificar quando `post_schedule_issue_status == opened`.
- Criar novas ações além das quatro aprovadas.
- Reavaliação médica.

## Arquivos prováveis

1. `apps/scheduler/views.py`
2. `apps/scheduler/forms.py`
3. templates em `templates/scheduler/`
4. `apps/scheduler/tests/test_post_schedule_issue.py` ou seção nova em testes existentes
5. talvez `apps/cases/services.py` se pequenos ajustes forem necessários
6. `openspec/changes/post-schedule-intercurrence/tasks.md` ao final

## Plano TDD obrigatório

### RED — fila e acesso

1. Caso `WAIT_APPT` com `post_schedule_issue_status="opened"` aparece na fila do agendador.
2. Card mostra badge `Intercorrência pós-agendamento` e motivo.
3. GET da tela do agendador mostra mensagem do NIR.
4. Lock scheduler existente é adquirido da mesma forma que no agendamento normal.

### RED — ações

1. POST `reschedule` com data/local/instruções válidas atualiza agendamento e vai para `WAIT_R1_CLEANUP_THUMBS`.
2. POST `cancel` com motivo marca `appointment_status="cancelled"` e vai para `WAIT_R1_CLEANUP_THUMBS`.
3. POST `maintain` preserva agendamento confirmado e vai para `WAIT_R1_CLEANUP_THUMBS`.
4. POST `deny` com motivo preserva agendamento confirmado e vai para `WAIT_R1_CLEANUP_THUMBS`.
5. POST `deny` sem motivo exibe erro.
6. POST `reschedule` sem nova data exibe erro.
7. Submit sem lock válido continua bloqueado como no fluxo normal.
8. Fluxo normal de `WAIT_APPT` sem intercorrência continua confirmando/negando como antes.

## GREEN

- Detectar intercorrência ativa com helper/propriedade simples, se já não existir.
- Preferir um formulário específico para intercorrência se evitar condicionais confusas no formulário normal.
- Chamar serviço de domínio para atualização; não manipular FSM e campos diretamente na view.

## REFACTOR

- Manter separação clara entre fluxo normal e fluxo de intercorrência.
- Evitar duplicar HTML grande; usar includes pequenos apenas se necessário.
- Não introduzir JavaScript novo.

## Critérios de aceitação

- [ ] Intercorrência aparece na fila do agendador com destaque.
- [ ] Agendador vê motivo/mensagem do NIR.
- [ ] As quatro ações funcionam conforme regras.
- [ ] Campos principais de agendamento são atualizados/preservados corretamente.
- [ ] Caso vai para `WAIT_R1_CLEANUP_THUMBS` após resposta.
- [ ] Evento `POST_SCHEDULE_ISSUE_RESPONDED` registra payload suficiente.
- [ ] Locks existentes continuam obrigatórios.
- [ ] Agendamento inicial sem intercorrência permanece coerente.

## Gates de autoavaliação

Responder no relatório:

1. Como a UI distingue intercorrência de agendamento inicial?
2. Qual caminho de código preserva o fluxo normal?
3. Como `deny` preserva o agendamento atual?
4. Como `reschedule` valida data/local?
5. Lock scheduler foi reaproveitado sem mudança arriscada?

## Comandos de validação mínimos

```bash
uv run pytest apps/scheduler/tests -q
uv run pytest apps/cases/tests -q
uv run ruff check apps/scheduler apps/cases
uv run ruff format --check apps/scheduler apps/cases
uv run mypy apps/scheduler apps/cases
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-003-scheduler-resolve-issue-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-003-scheduler-resolve-issue-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/post-schedule-intercurrence through Slice 003. Implement ONLY Slice 003 using TDD. Adapt scheduler queue/detail/submit to resolve WAIT_APPT cases with opened post-schedule issue. Show badge and NIR reason/message. Reuse scheduler_confirm lock. Add form/actions cancel, reschedule, maintain, deny with validations. Call domain service so case moves to WAIT_R1_CLEANUP_THUMBS and audit event is recorded. Preserve normal scheduling flow. Keep code simple, DRY and YAGNI. Run validations, update tasks.md, create /tmp/ats-web-slice-003-scheduler-resolve-issue-report.md, commit and push, reply REPORT_PATH and stop.
```
