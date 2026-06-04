# Slice 001: Release backend pós-submit médico/agendador

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR com Bootstrap, HTMX e Vanilla JS. O mecanismo de locks temporários já existe e foi implementado na change arquivada `openspec/archive/shared-work-queue-leases/`.

Leia antes de codar:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/release-lock-on-successful-handoff/proposal.md`
4. `openspec/changes/release-lock-on-successful-handoff/design.md`
5. `openspec/archive/shared-work-queue-leases/design.md` somente para contexto do mecanismo original
6. Este arquivo

Implemente **somente este slice** com TDD: RED → GREEN → REFACTOR.

## Objetivo do slice

Liberar locks de forma determinística no backend quando uma etapa operacional é concluída com sucesso:

```text
Médico envia decisão válida
→ transições FSM são persistidas
→ lock doctor_decision é limpo no backend
→ próximo papel não espera expiração do lease
```

```text
Agendador envia confirmação/negação válida
→ transições FSM são persistidas
→ lock scheduler_confirm é limpo no backend
→ NIR não espera expiração do lease
```

## Escopo funcional

- Em `doctor_submit`, liberar lock após submit válido e transições FSM concluídas.
- Em `scheduler_submit`, liberar lock após submit válido e transições FSM concluídas.
- Reutilizar o serviço existente `release_case_lock(...)`.
- Adicionar testes de regressão para sucesso e preservação do lock em erros.
- Validar handoff imediato médico → scheduler e scheduler → NIR.

## Fora de escopo

- Alterar `static/js/work_lock.js`.
- Alterar o botão Cancelar.
- Remover release best-effort de navegação.
- Alterar heartbeat, idle detection, lease duration ou polling HTMX.
- Criar endpoints novos.
- Alterar FSM.
- Alterar templates, salvo se um teste revelar necessidade real.

## Arquivos prováveis

1. `apps/doctor/views.py`
2. `apps/doctor/tests/test_views.py`
3. `apps/scheduler/views.py`
4. `apps/scheduler/tests/test_views.py`
5. Talvez `apps/intake/tests/test_nir_receipt_lease.py` para teste de handoff scheduler → NIR, se ficar mais legível lá
6. `openspec/changes/release-lock-on-successful-handoff/tasks.md` ao final

Evite tocar mais arquivos sem justificativa no relatório.

## Plano TDD obrigatório

### RED — médico

Adicionar testes antes da implementação:

1. `test_submit_accept_scheduled_releases_lock_after_success`
   - cria caso em `WAIT_DOCTOR`;
   - médico adquire lock;
   - POST válido com `decision=accept`, `admission_flow=scheduled` e `lock_token` correto;
   - espera redirect;
   - caso vai para `WAIT_APPT`;
   - `locked_by`, `lock_token`, `locked_until`, `lock_context`, `lock_role` ficam limpos;
   - existe `WORK_LOCK_RELEASED`.

2. `test_submit_deny_releases_lock_after_success`
   - fluxo similar, decisão `deny`;
   - caso vai para `WAIT_R1_CLEANUP_THUMBS`;
   - lock limpo.

3. `test_submit_invalid_form_preserves_lock`
   - lock válido;
   - POST inválido, por exemplo `decision=accept` sem campos obrigatórios;
   - response 200 re-renderiza formulário;
   - caso continua `WAIT_DOCTOR`;
   - lock continua com o mesmo médico/token.

4. Se ainda não houver cobertura suficiente, garantir/ajustar testes existentes para token ausente/inválido:
   - status não muda;
   - lock não é limpo.

5. Handoff imediato médico → scheduler:
   - após aceite `scheduled`, login como scheduler;
   - GET `scheduler_confirm` do mesmo caso;
   - espera 200 e novo lock `scheduler_confirm` do scheduler, sem aguardar 5 minutos.

### RED — scheduler

Adicionar testes antes da implementação:

1. `test_submit_confirm_releases_lock_after_success`
   - cria caso em `WAIT_APPT`;
   - scheduler adquire lock;
   - POST válido `decision=confirm` com data/hora;
   - espera redirect;
   - caso vai para `WAIT_R1_CLEANUP_THUMBS`;
   - lock limpo;
   - existe `WORK_LOCK_RELEASED`.

2. `test_submit_deny_releases_lock_after_success`
   - fluxo similar, decisão `deny`;
   - caso vai para `WAIT_R1_CLEANUP_THUMBS`;
   - lock limpo.

3. `test_submit_invalid_form_preserves_lock`
   - lock válido;
   - POST inválido, por exemplo `decision=confirm` sem data/hora;
   - response 200;
   - caso continua `WAIT_APPT`;
   - lock continua com o mesmo scheduler/token.

4. Garantir/ajustar cobertura para token ausente/inválido:
   - status não muda;
   - lock não é limpo.

5. Handoff imediato scheduler → NIR:
   - após scheduler concluir, login como NIR;
   - GET `intake:case_detail` do caso em `WAIT_R1_CLEANUP_THUMBS`;
   - espera que NIR adquira lock `nir_receipt` imediatamente.

## GREEN — implementação mínima

### Médico

Em `apps/doctor/views.py::doctor_submit`, depois que todas as transições/saves de negócio forem concluídas e antes do redirect final:

```python
release_lock_service(
    case_id=case.case_id,
    user=request.user,
    token=token,
    context="doctor_decision",
)
```

Notas:

- `token` já foi validado por `assert_case_lock`.
- Não chamar release se o formulário for inválido.
- Não chamar release se token estiver ausente/inválido.
- Não transformar falha de release pós-submit em erro de usuário neste slice.

### Scheduler

Em `apps/scheduler/views.py::scheduler_submit`, depois de `case.final_reply_posted(...)` e `case.save()`, antes do redirect final:

```python
release_lock_service(
    case_id=case.case_id,
    user=request.user,
    token=token,
    context="scheduler_confirm",
)
```

Notas iguais ao fluxo médico.

## REFACTOR — limpeza segura

- Se houver duplicação excessiva nos testes, criar helpers pequenos no próprio arquivo de teste.
- Não criar abstração genérica de lock/handoff.
- Não mexer em templates/JS sem necessidade.
- Manter nomes claros e específicos.

## Critérios de sucesso

- [ ] Médico libera lock no backend após submit válido.
- [ ] Agendador libera lock no backend após submit válido.
- [ ] Lock é preservado em formulários inválidos.
- [ ] Lock é preservado em token ausente/inválido.
- [ ] Scheduler assume imediatamente caso aceito pelo médico.
- [ ] NIR assume imediatamente resultado finalizado pelo scheduler.
- [ ] `WORK_LOCK_RELEASED` é registrado nos releases explícitos pós-submit.
- [ ] Nenhuma mudança em Cancelar/pagehide/heartbeat.
- [ ] Testes relevantes passam.

## Gates de autoavaliação

Responder no relatório:

1. O release acontece somente depois de persistir transições FSM?
2. O lock é preservado quando o formulário é inválido?
3. O lock é preservado quando o token é ausente/inválido?
4. O próximo papel consegue assumir sem esperar expiração?
5. Algum comportamento de Cancelar ou `work_lock.js` foi alterado? Se sim, por quê?

## Comandos de validação mínimos

```bash
uv run pytest apps/doctor/tests apps/scheduler/tests apps/intake/tests/test_nir_receipt_lease.py apps/cases/tests/test_lock_service.py -q
uv run ruff check apps/doctor apps/scheduler apps/intake apps/cases
uv run ruff format --check apps/doctor apps/scheduler apps/intake apps/cases
uv run mypy apps/doctor apps/scheduler apps/intake apps/cases
```

Quality gate completo, se possível:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar:

```text
/tmp/ats-web-slice-001-release-backend-pos-submit-report.md
```

Incluir:

- resumo;
- arquivos alterados;
- snippets antes/depois;
- testes adicionados;
- evidência de que locks são limpos após sucesso;
- evidência de que locks são preservados em erro;
- comandos executados;
- atualização de `tasks.md`;
- commit hash e push.

Resposta final do implementador:

```text
REPORT_PATH=/tmp/ats-web-slice-001-release-backend-pos-submit-report.md
```

Pare e peça confirmação explícita antes de qualquer próximo slice.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md, openspec/changes/release-lock-on-successful-handoff/proposal.md, design.md, tasks.md and slices/slice-001-release-backend-pos-submit.md.
Implement ONLY Slice 001 using TDD.
Goal: after successful doctor_submit and scheduler_submit, release the held Case lock in the backend using the existing release_case_lock service. Preserve locks on invalid forms and invalid/missing tokens. Do not change Cancelar, work_lock.js, heartbeat, lease duration, templates or FSM.
Add regression tests proving doctor -> scheduler and scheduler -> NIR handoffs do not wait for lease expiry.
Run validations, update tasks.md, create /tmp/ats-web-slice-001-release-backend-pos-submit-report.md with before/after snippets, commit and push, then reply REPORT_PATH and stop.
```
