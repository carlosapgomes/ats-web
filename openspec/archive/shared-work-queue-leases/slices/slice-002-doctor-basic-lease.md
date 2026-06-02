# Slice 002: Médico — lease básico end-to-end

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. Não há API REST/SPA. O projeto usa PostgreSQL, Django ORM, django-fsm, HTMX e Vanilla JS.

Antes de codar, leia:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. Este arquivo

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Entregar o primeiro fluxo vertical de lock temporário para a fila médica, ainda sem heartbeat JS.

Fluxo entregue:

```text
Médico A abre caso em WAIT_DOCTOR
→ backend reserva o caso para Médico A com token
→ fila mostra caso reservado por Médico A
→ Médico B não consegue abrir/submeter o mesmo caso
→ Médico A consegue submeter decisão com token válido
→ lock é liberado/irrelevante ao sair de WAIT_DOCTOR
```

Este slice deve criar a base de modelo/serviço que será reutilizada pelos próximos slices, mas sem criar framework genérico além do necessário.

## Escopo funcional

- Adicionar campos de lease ao `Case`.
- Criar migration enxuta.
- Criar serviço centralizado de lock em `apps/cases/services.py`.
- Implementar aquisição de lock ao abrir `doctor_decision`.
- Implementar validação de lock ao submeter `doctor_submit`.
- Incluir `lock_token` em campo hidden no formulário médico.
- Fila médica deve mostrar quando caso está reservado por outro usuário.
- Botão de avaliação deve ser bloqueado/desabilitado para usuário que não possui o lock.
- Registrar auditoria básica:
  - `WORK_LOCK_CLAIMED` ao adquirir;
  - `WORK_LOCK_EXPIRED` quando uma aquisição detecta lock anterior expirado, contendo quem estava com o caso.
- Não registrar heartbeat neste slice.

## Fora de escopo

- Heartbeat/idle detection/release via JS.
- Scheduler lock.
- NIR shared queue.
- Override por supervisor/admin.
- WebSocket.
- Novos estados FSM.

## Arquivos prováveis

Este slice é maior porque cria a fundação e entrega o primeiro fluxo vertical. Mantenha enxuto e justifique se exceder o previsto.

1. `apps/cases/models.py`
2. nova migration em `apps/cases/migrations/`
3. `apps/cases/services.py`
4. testes de cases/services
5. `apps/doctor/views.py`
6. `templates/doctor/_queue_content.html`
7. `templates/doctor/decision.html`
8. testes de doctor views
9. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

## Plano TDD obrigatório

### RED — serviço de lock

Criar testes para o serviço antes da implementação:

1. `claim_case_lock` adquire caso em `WAIT_DOCTOR` sem lock ativo.
2. Segundo usuário não adquire caso com lock vigente.
3. Mesmo usuário pode receber/continuar lock conforme decisão implementada, mas deve preservar token corretamente.
4. Lock expirado pode ser assumido por outro usuário.
5. Ao assumir lock expirado, cria `CaseEvent` `WORK_LOCK_EXPIRED` com:
   - `expired_locked_by_id`;
   - `expired_locked_by_display`;
   - `expired_locked_at`;
   - `expired_locked_until`;
   - `context`.
6. `assert_case_lock` passa para user+token+context válidos.
7. `assert_case_lock` falha para token errado, usuário errado, context errado ou lock expirado.

### RED — views médicas

Adicionar testes de view:

1. GET `doctor_decision` em caso disponível retorna 200 e grava lock no caso.
2. Template contém hidden input `lock_token`.
3. Segundo médico tentando GET no mesmo caso recebe redirect/mensagem ou status bloqueado conforme padrão escolhido, sem abrir formulário editável.
4. Fila médica renderiza texto indicando que o caso está reservado por outro médico.
5. Submit com lock válido executa fluxo existente e salva decisão.
6. Submit sem token/token inválido não altera status e mostra erro amigável.

Use fixtures existentes para avançar caso até `WAIT_DOCTOR` sem violar FSM.

## GREEN — implementação mínima

### Modelo

Adicionar campos no `Case` conforme `design.md`.

Adicionar índices úteis, sem exagero:

```python
models.Index(fields=["status", "locked_until"])
```

### Serviço

Implementar API pequena. Exemplo mínimo aceitável para este slice:

```python
claim_case_lock(...)
assert_case_lock(...)
release_case_lock(...)
expire_stale_locks_for_statuses(...)
```

Pode deixar `renew_case_lock` para o slice 003 se não for necessário aqui, mas desenhe o serviço para evolução limpa.

Use `transaction.atomic()` e `select_for_update()` ou update condicional. Priorize legibilidade e testes.

### Doctor views

- Em `_doctor_queue_context`, chamar expiração lazy para `WAIT_DOCTOR` antes da query.
- Incluir dados de lock nos cards via `_build_case_card`.
- Em `doctor_decision`, tentar `claim_case_lock` antes de renderizar formulário.
- Se não conseguir adquirir, não renderizar formulário editável. Preferir redirect para fila com `messages.warning`.
- Em `doctor_submit`, obter `lock_token` do POST e chamar `assert_case_lock` antes de alterar campos/transicionar FSM.
- Ao salvar decisão e o caso sair de `WAIT_DOCTOR`, limpar lock ou deixar serviço liberar explicitamente antes/depois do save. Preferir limpeza explícita para evitar metadado obsoleto.

### Templates

- Cards bloqueados devem mostrar quem reservou e até quando.
- Se lock pertence ao usuário atual, botão pode ser “Continuar”.
- Se lock pertence a outro usuário, botão deve ficar desabilitado ou não navegável.
- `decision.html` deve incluir hidden `lock_token`.

## Critérios de aceitação

- [ ] Migration adiciona apenas campos de lock/índices necessários.
- [ ] Serviço centralizado cobre claim/assert/release/expired audit.
- [ ] Médico adquire lock ao abrir decisão.
- [ ] Médico sem lock válido não submete decisão.
- [ ] Segundo médico não abre formulário editável de caso reservado por outro.
- [ ] Fila médica comunica reserva ativa por outro usuário.
- [ ] Lock expirado pode ser assumido e gera auditoria com usuário anterior.
- [ ] Heartbeat não foi implementado neste slice.
- [ ] Nenhum estado FSM novo foi criado.
- [ ] Testes do slice passam.

## Gates de autoavaliação

Responder no relatório:

1. A aquisição é atômica sob concorrência?
2. Onde a auditoria de expiração registra quem estava com o caso?
3. `lock_token` impede conflito entre abas?
4. As views continuam finas, delegando regra ao serviço?
5. Heartbeat foi evitado neste slice?
6. Quantos arquivos foram tocados e por quê?

## Comandos de validação mínimos

```bash
uv run pytest apps/cases/tests apps/doctor/tests -q
uv run ruff check apps/cases apps/doctor
uv run ruff format --check apps/cases apps/doctor
uv run mypy apps/cases apps/doctor
```

Se possível, rode o quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-002-doctor-basic-lease-report.md
```

O relatório deve conter:

- resumo;
- arquivos alterados;
- snippets antes/depois;
- estratégia transacional usada;
- eventos de auditoria adicionados;
- testes adicionados/alterados;
- comandos e resultados;
- riscos/observações;
- atualização de `tasks.md`;
- commit hash e push.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-slice-002-doctor-basic-lease-report.md
```

Pare e peça confirmação antes do próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and the shared-work-queue-leases OpenSpec files.
Implement ONLY Slice 002 using TDD.
Create Case lease fields, migration and a small transactional lock service. Apply it end-to-end only to doctor: claim on GET decision, hidden lock_token, assert on submit, queue shows active locks, expired lock takeover creates WORK_LOCK_EXPIRED with previous owner.
Do not implement heartbeat, scheduler lock or NIR changes.
Use Django/PostgreSQL only, clean code, DRY without overengineering, YAGNI.
Run validations, update tasks.md, create /tmp/ats-web-slice-002-doctor-basic-lease-report.md with snippets, commit and push, then reply REPORT_PATH and stop.
```
