# Slice 001: Proteção central contra release durante submit + mensagem acionável

## Handoff para implementador com contexto zero

O sistema é um monolito Django SSR, sem API REST e sem SPA. O frontend usa templates Django, Bootstrap 5.3 e Vanilla JS. Não introduza React/Vue, bundler, DRF, endpoint novo, model novo ou migration.

Existe um mecanismo de reserva/lock de trabalho para impedir que dois usuários processem o mesmo caso ao mesmo tempo. O lock vive no model `Case` (`locked_by`, `locked_until`, `lock_token`, `lock_context`, `lock_role`) e é manipulado por `apps/cases/services.py`.

Fluxos protegidos por lock:

| Papel | Tela | Arquivo de template | View final | Contexto de lock |
|-------|------|---------------------|------------|------------------|
| `scheduler` | confirmar/negar agendamento | `templates/scheduler/confirm.html` | `apps/scheduler/views.py::scheduler_submit` | `scheduler_confirm` |
| `scheduler` | responder intercorrência pós-agendamento | `templates/scheduler/confirm_post_schedule_issue.html` | `apps/scheduler/views.py::scheduler_submit` | `scheduler_confirm` |
| `doctor` | decisão médica | `templates/doctor/decision.html` | `apps/doctor/views.py::doctor_submit` | `doctor_decision` |
| `nir` | confirmar recebimento final | `templates/intake/case_detail.html` | `apps/intake/views.py::confirm_receipt` | `nir_receipt` |

Todas essas páginas carregam `static/js/work_lock.js`, que hoje renova lock por heartbeat e tenta liberar lock ao sair da página. O bug: durante o submit final, eventos como `pagehide`/`visibilitychange` podem chamar `/lock/release/` antes do POST principal. Aí o backend recebe o submit com token antigo, mas `Case.locked_by` já foi limpo, resultando na mensagem ambígua `Caso não possui reserva ativa.`.

## Objetivo do slice

Entregar uma correção vertical única:

```text
Usuário de NIR/médico/agendador abre tela protegida por lock
→ usuário submete uma ação final com lock_token
→ work_lock.js não libera a reserva durante esse submit
→ backend processa usando o lock válido
→ backend libera o lock após sucesso como já faz hoje
```

E, se o lock realmente tiver sido perdido/expirado antes do submit, mostrar:

```text
A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.
```

## Arquivos esperados

Idealmente tocar apenas estes 5 arquivos:

1. `static/js/work_lock.js`
2. `static/js/scheduler_confirm.js`
3. `apps/cases/services.py`
4. `apps/cases/tests/test_lock_service.py`
5. `apps/scheduler/tests/test_views.py`

Evite tocar views/templates de doctor e NIR, models, migrations, URLs ou settings. Doctor e NIR devem ser cobertos pelo `work_lock.js` central. Se precisar tocar algo além dos arquivos acima, justifique claramente no relatório.

## Metodologia obrigatória

Siga TDD:

1. **RED** — primeiro escreva/ajuste testes que falham para a mensagem e para a regressão integrada principal.
2. **GREEN** — implemente o mínimo para passar.
3. **REFACTOR** — limpe nomes/duplicações sem ampliar escopo.

Princípios obrigatórios:

- **Clean code**: nomes claros; funções JS pequenas e defensivas.
- **DRY**: uma mensagem central, um guard central de submit no `work_lock.js`.
- **YAGNI**: não criar beacon API, autosave, endpoint novo, storage, framework JS ou refactor amplo.
- **Escopo mínimo**: preservar queries, locks backend, FSM, templates e views fora do necessário.

## Requisitos funcionais

### R1. Guard central para submit protegido em `work_lock.js`

Em `static/js/work_lock.js`, adicionar estado de submissão protegida.

O guard deve ativar apenas quando um formulário realmente enviado contém o `lock_token` atual da página:

```javascript
var protectedSubmitInProgress = false;

function isProtectedSubmitInProgress() {
    return protectedSubmitInProgress || window.ATS_WORK_LOCK_SUBMITTING === true;
}

document.addEventListener('submit', function (event) {
    if (event.defaultPrevented) return;

    var form = event.target;
    if (!form || !form.querySelector) return;

    var tokenInput = form.querySelector('input[name="lock_token"]');
    if (tokenInput && tokenInput.value === lockToken) {
        protectedSubmitInProgress = true;
        window.ATS_WORK_LOCK_SUBMITTING = true;
    }
});
```

A lógica exata pode variar, mas deve preservar esses comportamentos:

- só roda em páginas com `data-work-lock-config` válido;
- usar fase bubble/default, não captura, para permitir que validação/modal chame `preventDefault()` antes;
- ignorar `event.defaultPrevented`, porque scheduler/doctor usam o primeiro submit para abrir modal de confirmação;
- só considerar protegido um form com `lock_token` igual ao token atual;
- não marcar submit de comunicação operacional, anexos, encerramento administrativo ou outros forms sem `lock_token`;
- não lançar erro se o form ou input não existir.

### R2. `sendRelease()` não libera durante submit protegido

No início de `sendRelease()`:

```javascript
if (isProtectedSubmitInProgress()) return;
```

Atenção: essa verificação deve ocorrer **antes** de `released = true`. Caso contrário, um release real futuro poderia ser bloqueado indevidamente.

### R3. `visibilitychange` não libera lock

Remover o `sendRelease()` do handler de `visibilitychange` ou transformá-lo em log/no-op.

Critério:

- trocar de aba/minimizar/navegar para diálogo do navegador não deve chamar `/lock/release/`.

Manter `pagehide` com o guard de R2 é aceitável.

### R4. Links de saída continuam liberando lock

Não remover o listener de clique em `<a href>` que chama `sendRelease()`.

Ele deve continuar liberando lock para abandono explícito, por exemplo:

- `Cancelar`;
- `Voltar sem decidir`;
- voltar à fila/lista por link.

### R5. Proteger `form.submit()` programático do scheduler

Em `static/js/scheduler_confirm.js`, antes do `form.submit()` final, setar:

```javascript
window.ATS_WORK_LOCK_SUBMITTING = true;
```

Motivo: `HTMLFormElement.submit()` não dispara o evento `submit`, então o guard central de R1 não vê esse caminho.

Não refatore todo o fluxo do modal se não for necessário.

### R6. Mensagem acionável centralizada

Em `apps/cases/services.py`, criar constante central, por exemplo:

```python
LOCK_LOST_USER_MESSAGE = (
    "A reserva desta tela expirou ou foi liberada antes do envio. "
    "Volte à fila e abra o caso novamente."
)
```

Usar em `assert_case_lock(...)` quando:

- `case.locked_by is None`;
- `case.locked_until is None or case.locked_until <= now`.

Não alterar mensagens de:

- usuário diferente (`Lock pertence a outro usuário...`);
- token inválido;
- contexto inválido.

### R7. Não alterar FSM nem liberação backend de sucesso

Não alterar transições de `Case`, status, eventos de workflow ou endpoints.

A ordem backend correta deve continuar:

```text
assert_case_lock(...)
→ salvar decisão/recebimento
→ transições FSM existentes
→ release/limpeza de lock após sucesso
→ redirect
```

## TDD obrigatório

### Testes unitários em `apps/cases/tests/test_lock_service.py`

Adicionar/ajustar antes da implementação:

1. `test_assert_fails_for_missing_lock_with_actionable_message`
   - criar caso em status compatível, sem lock;
   - chamar `assert_case_lock(case=case, user=user, token=uuid.uuid4(), context="scheduler_confirm")`;
   - assert `PermissionError` contém exatamente:

```text
A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.
```

2. `test_assert_fails_for_expired_lock_with_actionable_message`
   - criar lock válido via `claim_case_lock`;
   - forçar `locked_until` para passado;
   - chamar `assert_case_lock` com token original;
   - assert mesma mensagem.

Se já existir teste de lock expirado esperando `Lock expirou.`, atualize a expectativa para a nova mensagem.

### Teste integrado em `apps/scheduler/tests/test_views.py`

Adicionar teste antes da implementação, por exemplo:

`test_submit_after_lock_released_before_post_shows_actionable_message`

Fluxo:

1. login como scheduler;
2. criar caso `WAIT_APPT`;
3. adquirir lock via GET `/scheduler/<case_id>/` ou `claim_case_lock`;
4. guardar `lock_token`;
5. simular release antes do submit usando `release_case_lock(...)` com o token guardado ou limpando lock como o endpoint faria;
6. POST `/scheduler/<case_id>/submit/` com decisão válida e token antigo;
7. assert `response.status_code == 200`;
8. assert conteúdo contém:

```text
A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.
```

9. assert caso continua em `WAIT_APPT` e sem decisão de agendamento aplicada.

Esse teste reproduz a ordem ruim da race sem browser.

### Verificação JS obrigatória no relatório

Como não há browser test runner configurado, não crie um framework JS. No relatório, inclua verificação estática/manual dos pontos:

- `work_lock.js` ativa guard apenas para submit não cancelado (`!event.defaultPrevented`) de form com `input[name="lock_token"]` igual ao token atual;
- `sendRelease()` retorna antes de liberar quando submit protegido está em andamento;
- `visibilitychange` não chama `sendRelease()`;
- `scheduler_confirm.js` seta `window.ATS_WORK_LOCK_SUBMITTING = true` antes de `form.submit()`;
- Doctor e NIR são cobertos pelo submit nativo/requestSubmit de forms com `lock_token`.

## Critérios de aceitação

- [ ] Submit protegido por `lock_token` não libera lock client-side antes do POST principal.
- [ ] Guard não é ativado por submits cancelados com `preventDefault()` para modal/validação.
- [ ] Guard não é ativado por forms sem `lock_token`.
- [ ] `sendRelease()` verifica o guard antes de `released = true`.
- [ ] `visibilitychange` não libera lock.
- [ ] Clique em link de saída/cancelar continua liberando lock.
- [ ] Scheduler programático (`form.submit()`) seta a flag global antes do envio.
- [ ] Doctor continua funcionando com `requestSubmit()`/submit nativo.
- [ ] NIR continua funcionando com submit nativo.
- [ ] `assert_case_lock` mostra a nova mensagem para lock ausente e expirado.
- [ ] Token inválido/usuário diferente/contexto inválido continuam bloqueando sem relaxamento de segurança.
- [ ] Nenhum model, migration, URL, endpoint novo ou FSM foi alterado.

## Gates de autoavaliação

Responder no relatório antes de finalizar:

1. Qual era a race condition e qual ordem de requisições causava o bug?
2. Onde o guard de submit protegido foi implementado?
3. Como o guard evita prender lock quando o primeiro submit é cancelado para abrir modal/validação (`event.defaultPrevented`)?
4. Como o guard evita prender lock quando o usuário envia comunicação operacional na mesma tela?
5. `sendRelease()` checa o guard antes de marcar `released = true`?
6. `visibilitychange` ainda chama `/lock/release/`? A resposta esperada é não.
7. Por que `scheduler_confirm.js` precisou de tratamento especial?
8. Por que doctor e NIR ficaram cobertos sem alterar suas views/templates?
9. Qual constante/mensagem central foi criada em `apps/cases/services.py`?
10. Que testes provam a mensagem para lock ausente e expirado?
11. Que teste reproduz a race no scheduler sem browser?
12. Alguma regra de FSM, model, migration, URL ou autorização foi alterada? A resposta esperada é não.

## Comandos de validação

Durante o ciclo, rodar pelo menos:

```bash
uv run pytest apps/cases/tests/test_lock_service.py apps/scheduler/tests/test_views.py -q
```

Ao final, rodar o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Também verificar:

```bash
git status --short
```

## Relatório obrigatório

Criar relatório markdown temporário para revisão por terceiro LLM:

```text
/tmp/fix-work-lock-submit-race-all-roles-slice-001-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- evidência RED/GREEN/REFACTOR;
- snippets antes/depois de `work_lock.js`, `scheduler_confirm.js` e `assert_case_lock`;
- explicação de por que scheduler, doctor e NIR estão cobertos;
- resultados dos comandos de validação;
- respostas aos gates de autoavaliação;
- limitações aceitas (sem browser runner; sem bloquear múltiplas abas do mesmo usuário neste change);
- confirmação de commit e push.

Ao responder, retornar:

```text
REPORT_PATH=/tmp/fix-work-lock-submit-race-all-roles-slice-001-report.md
```

## Prompt pronto para o implementador LLM

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/fix-work-lock-submit-race-all-roles/{proposal.md,design.md,tasks.md,slices/slice-001-protect-lock-submit-and-message.md,specs/work-lock-leases/spec.md}.

Implement ONLY Slice 001 for change fix-work-lock-submit-race-all-roles.
Use vertical slicing and keep it lean: prefer touching only static/js/work_lock.js, static/js/scheduler_confirm.js, apps/cases/services.py, apps/cases/tests/test_lock_service.py and apps/scheduler/tests/test_views.py.

Use TDD: first add failing tests for the actionable lock-lost message and scheduler submit-after-release regression. Then implement the minimal code. Refactor only for clarity/DRY/YAGNI.

Do not alter models, migrations, URLs, endpoints, FSM states, permissions or unrelated templates/views. Do not add JS frameworks or browser test infrastructure.

Acceptance: protected form submit with current lock_token must suppress client-side release during real submit, but not when the submit event was canceled for modal/validation; visibilitychange must not release locks; scheduler programmatic form.submit path must set the work-lock submitting flag; assert_case_lock must show the new actionable message for missing/expired locks.

Run uv run ruff check ., uv run ruff format --check ., uv run mypy ., uv run pytest. Update tasks.md, create /tmp/fix-work-lock-submit-race-all-roles-slice-001-report.md with before/after snippets, TDD evidence, validation output and answers to self-eval gates. Commit and push. Reply only with REPORT_PATH and stop.
```
