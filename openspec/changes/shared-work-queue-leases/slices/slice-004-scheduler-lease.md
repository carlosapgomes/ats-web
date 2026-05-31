# Slice 004: Agendador — lease end-to-end e ciência operacional segura

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`. O lock médico e o JS de heartbeat já devem existir dos slices anteriores. O app scheduler já deve exigir `@role_required("scheduler")` desde o Slice 001.

Leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. slices 001–003 desta change
6. Este arquivo

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Aplicar a reserva temporária ao fluxo do agendador.

Fluxo entregue:

```text
Agendador A abre caso em WAIT_APPT
→ backend reserva o caso para Agendador A com token/context scheduler_confirm
→ fila mostra caso reservado
→ Agendador B não consegue abrir/submeter o mesmo caso
→ Agendador A submete confirmação/negação com token válido
→ caso segue FSM existente
```

Também proteger a ação de ciência operacional de vinda imediata para evitar duplicidade sob concorrência.

## Escopo funcional

- Reutilizar serviço de lock existente, sem duplicar regra.
- Aplicar lock em `scheduler_confirm` e `scheduler_submit`.
- Adicionar hidden `lock_token` ao formulário do scheduler.
- Reutilizar `static/js/work_lock.js` na tela `scheduler/confirm.html`.
- Adicionar endpoints scheduler de renew/release.
- Fila scheduler mostra caso `WAIT_APPT` reservado por outro usuário e bloqueia botão.
- `immediate_ack` deve ser protegido por papel e idempotente de forma segura sob concorrência.

## Fora de escopo

- NIR shared queue.
- Novos campos de modelo.
- Alterações no fluxo médico.
- Override por manager/admin.
- WebSocket.

## Arquivos prováveis

1. `apps/scheduler/views.py`
2. `apps/scheduler/urls.py`
3. `templates/scheduler/_queue_content.html`
4. `templates/scheduler/confirm.html`
5. testes em `apps/scheduler/tests/`
6. talvez `apps/cases/services.py` se precisar pequeno ajuste reutilizável
7. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

## Plano TDD obrigatório

### RED — fluxo de confirmação

Criar testes:

1. GET `scheduler_confirm` em caso `WAIT_APPT` disponível adquire lock com context `scheduler_confirm`.
2. Template contém hidden `lock_token` e configuração JS de heartbeat.
3. Segundo agendador não abre formulário editável para caso com lock vigente de outro usuário.
4. Submit com token válido confirma agendamento e segue FSM existente.
5. Submit com token inválido/ausente não altera status nem dados de agendamento.
6. Lock expirado pode ser assumido por outro agendador e gera `WORK_LOCK_EXPIRED` com usuário anterior.
7. Endpoints renew/release exigem papel scheduler e token correto.

### RED — fila scheduler

1. Card `WAIT_APPT` reservado por outro usuário mostra nome de quem reservou.
2. Botão `Agendar` fica indisponível para outro usuário.
3. Se lock pertence ao usuário atual, botão mostra/permite continuar.

### RED — immediate ack

1. Usuário sem papel scheduler não consegue confirmar ciência.
2. Duas chamadas concorrentes ou repetidas não geram múltiplos `SCHEDULER_IMMEDIATE_ACK` para o mesmo caso.

Se teste concorrente real for complexo, crie ao menos teste de idempotência sequencial e use transação/constraint ou `select_for_update()` para reduzir corrida.

## GREEN — implementação mínima

### Confirm/submit

- Em `scheduler_confirm`, chamar `claim_case_lock` com:

```python
expected_status=CaseStatus.WAIT_APPT
context="scheduler_confirm"
role="scheduler"
```

- Em `scheduler_submit`, chamar `assert_case_lock` antes de alterar campos do agendamento.
- Após transição final, liberar/limpar lock explicitamente.

### Queue

- Chamar expiração lazy de locks em `WAIT_APPT` antes de montar contexto.
- Enviar flags prontas aos templates.

### Heartbeat

- Reutilizar JS criado no slice 003.
- Não duplicar script.
- Endpoints devem usar context `scheduler_confirm`.

### Immediate ack

- Manter sem lease, porque é uma ação rápida e idempotente, não uma tela longa de trabalho.
- Garantir autorização e idempotência segura.
- Se necessário, usar `transaction.atomic()` + `select_for_update()` no `Case` antes de checar/criar evento.

## Critérios de aceitação

- [ ] Agendador adquire lock ao abrir confirmação.
- [ ] Segundo agendador não edita caso reservado por outro.
- [ ] Submit scheduler exige lock válido.
- [ ] Heartbeat/release funcionam na tela scheduler.
- [ ] Fila scheduler mostra reserva ativa.
- [ ] Lock expirado gera auditoria com usuário anterior.
- [ ] Immediate ack exige papel scheduler e não duplica evento sob repetição.
- [ ] Regras existentes de agendamento e FSM não foram quebradas.
- [ ] Testes passam.

## Gates de autoavaliação

Responder no relatório:

1. A lógica de lock foi reutilizada ou duplicada?
2. Por que immediate ack usa idempotência e não lease?
3. O submit altera dados antes ou depois de validar lock?
4. A fila mostra claramente reserva por outro usuário?
5. Foram criadas dependências novas? Não deveriam.

## Comandos de validação mínimos

```bash
uv run pytest apps/scheduler/tests apps/cases/tests -q
uv run ruff check apps/scheduler apps/cases static/js/work_lock.js
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
/tmp/ats-web-slice-004-scheduler-lease-report.md
```

Incluir resumo, arquivos, snippets, testes, validações, riscos, atualização de `tasks.md`, commit hash e push.

Resposta final:

```text
REPORT_PATH=/tmp/ats-web-slice-004-scheduler-lease-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and shared-work-queue-leases OpenSpec through Slice 004.
Implement ONLY Slice 004 using TDD.
Reuse the Case lock service and work_lock.js for scheduler_confirm/scheduler_submit with context scheduler_confirm. Queue must show active locks. Submit must require valid lock_token. Make immediate_ack scheduler-only and idempotent under repeated/concurrent calls. Do not implement NIR changes.
Run validations, update tasks.md, create /tmp/ats-web-slice-004-scheduler-lease-report.md, commit and push, reply REPORT_PATH and stop.
```
