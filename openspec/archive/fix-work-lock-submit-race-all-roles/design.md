# Design: Corrigir race condition de reserva ao submeter ações com lock

## Estado atual

O serviço central de lock está em `apps/cases/services.py`:

- `claim_case_lock(...)` cria/renova lock de trabalho.
- `assert_case_lock(...)` valida `locked_by`, usuário, token, contexto e expiração.
- `release_case_lock(...)` limpa lock quando o usuário abandona ou quando o fluxo conclui.
- `compute_lock_display(...)` alimenta UI de fila com `Reservado`/`Continuar`.

As páginas com lock carregam `static/js/work_lock.js` via `data-work-lock-config`:

| Papel | Template | Form final | Contexto de lock |
|-------|----------|------------|------------------|
| `scheduler` | `templates/scheduler/confirm.html` | `#schedule-form` com `lock_token` | `scheduler_confirm` |
| `scheduler` | `templates/scheduler/confirm_post_schedule_issue.html` | `#psi-form` com `lock_token` | `scheduler_confirm` |
| `doctor` | `templates/doctor/decision.html` | `#decision-form` com `lock_token` | `doctor_decision` |
| `nir` | `templates/intake/case_detail.html` | form de confirmar recebimento com `lock_token` | `nir_receipt` |

O JS atual libera a reserva em:

- clique em link de saída;
- `pagehide`;
- `visibilitychange` quando a aba fica oculta.

O backend também libera após sucesso:

- scheduler: `apps/scheduler/views.py::scheduler_submit` chama `release_lock_service(...)`;
- doctor: `apps/doctor/views.py::doctor_submit` chama `release_lock_service(...)`;
- NIR: `apps/intake/views.py::confirm_receipt` limpa campos de lock após concluir.

## Causa raiz

`pagehide`/`visibilitychange` são disparados durante navegações normais, inclusive ao submeter formulários. Como o release é uma requisição independente, ele pode chegar ao servidor antes do POST principal.

Isso cria ordem indesejada:

```text
POST /lock/release/      → limpa Case.locked_by
POST /submit ou receipt  → assert_case_lock vê locked_by=None
```

A mensagem vem de `assert_case_lock` quando `case.locked_by is None`:

```text
Caso não possui reserva ativa.
```

## Decisões

### D1. Guardar submissão protegida no `work_lock.js`

Adicionar ao `work_lock.js` um estado de submissão protegida, por exemplo:

```javascript
var protectedSubmitInProgress = false;

function isProtectedSubmitInProgress() {
  return protectedSubmitInProgress || window.ATS_WORK_LOCK_SUBMITTING === true;
}
```

O script deve registrar um listener global de submit **somente enquanto está em página com lock**, porque ele já retorna cedo quando não há `data-work-lock-config`.

O listener deve ativar o guard apenas para formulários que realmente serão enviados e carregam o token do lock atual:

```javascript
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

Importante: não usar fase de captura para esse guard. As telas de scheduler/doctor podem interceptar o primeiro submit para abrir modal de confirmação com `preventDefault()`. O guard deve rodar na fase bubble e ignorar `event.defaultPrevented`, para não suprimir release quando o usuário apenas abriu o modal e depois desistiu.

Motivo para exigir `lock_token` no form:

- evita prender locks quando o usuário posta comunicação operacional na mesma tela;
- evita interferir em forms administrativos ou de anexos que não concluem o fluxo com lock;
- cobre os forms finais de scheduler, doctor e NIR.

### D2. `sendRelease()` deve respeitar o guard

No início de `sendRelease()`, antes de marcar `released = true`, verificar:

```javascript
if (isProtectedSubmitInProgress()) return;
```

Isto é crucial: se `released = true` for marcado antes do retorno, uma liberação legítima futura pode ser bloqueada incorretamente.

### D3. Não liberar lock em `visibilitychange`

Remover o `sendRelease()` em `visibilitychange` ou transformá-lo em no-op/log.

Motivo:

- usuário pode alternar aba, minimizar, abrir PDF, usar gerenciador de senhas ou dialog nativo;
- isso não significa abandono da tela;
- o heartbeat já para por inatividade e o lock expira naturalmente após o TTL se o usuário realmente abandonar.

`pagehide` pode continuar tentando release best-effort, mas protegido por D2 para não concorrer com submit.

### D4. Manter release em clique de links de saída

O listener de clique em `<a href>` deve continuar chamando `sendRelease()` para casos como:

- Voltar sem decidir;
- Cancelar;
- voltar à fila;
- navegação manual para outra página.

Isso preserva a liberação rápida quando o usuário realmente abandona o card.

### D5. Cobrir submit programático do scheduler

`static/js/scheduler_confirm.js` usa `form.submit()` após modal de confirmação. `HTMLFormElement.submit()` não dispara o evento `submit`, então D1 não captura esse caminho.

Antes de chamar `form.submit()`, definir explicitamente:

```javascript
window.ATS_WORK_LOCK_SUBMITTING = true;
```

Não é necessário refatorar todo o fluxo para `requestSubmit()` neste change. O objetivo é bugfix enxuto e reversível.

Observação: `static/js/decision.js` do médico usa `requestSubmit()` quando disponível; isso dispara o evento `submit` e é coberto por D1. O fallback `form.submit()` é raro, mas o implementador pode, se mantiver escopo enxuto, também setar `window.ATS_WORK_LOCK_SUBMITTING = true` antes do fallback. Não é obrigatório se aumentar arquivos sem necessidade.

### D6. Mensagem centralizada para lock ausente/expirado

Criar uma constante central em `apps/cases/services.py`, por exemplo:

```python
LOCK_LOST_USER_MESSAGE = (
    "A reserva desta tela expirou ou foi liberada antes do envio. "
    "Volte à fila e abra o caso novamente."
)
```

Usar em `assert_case_lock(...)` quando:

- `case.locked_by is None`;
- `case.locked_until is None or case.locked_until <= now`.

Motivo:

- a mesma mensagem passa a valer para scheduler, doctor e NIR;
- reduz ambiguidade sem alterar regras de autorização;
- mantém mensagens específicas para token inválido, usuário diferente e contexto diferente, que representam problemas distintos.

### D7. Não mudar contrato backend de sucesso

Não alterar FSM nem a liberação backend após sucesso.

A ordem correta permanece:

```text
assert_case_lock passa
→ regra de negócio/FSM salva decisão
→ backend libera lock deterministicamente
→ redirect para fila/lista
```

## Arquivos previstos

Idealmente tocar apenas:

| Arquivo | Mudança |
|---------|---------|
| `static/js/work_lock.js` | guard central de submit protegido; `sendRelease` respeita guard; remover/no-op de release em `visibilitychange` |
| `static/js/scheduler_confirm.js` | setar `window.ATS_WORK_LOCK_SUBMITTING = true` antes de `form.submit()` programático |
| `apps/cases/services.py` | constante de mensagem e uso em `assert_case_lock` para lock ausente/expirado |
| `apps/cases/tests/test_lock_service.py` | testes unitários da mensagem central |
| `apps/scheduler/tests/test_views.py` | regressão integrada do submit após lock liberado antes do POST |

Não tocar modelos, migrations, URLs, templates ou views de doctor/NIR, salvo justificativa forte no relatório.

## Estratégia de testes

### Testes unitários de serviço

Em `apps/cases/tests/test_lock_service.py`:

1. `test_assert_fails_for_missing_lock_with_actionable_message`
   - criar caso sem lock;
   - chamar `assert_case_lock` com token qualquer;
   - assert `PermissionError` contém exatamente:
     `A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.`

2. Ajustar/adicionar teste de lock expirado:
   - caso com lock expirado;
   - `assert_case_lock` levanta a mesma mensagem acionável.

### Teste integrado scheduler

Em `apps/scheduler/tests/test_views.py`:

- abrir/adquirir lock ou criar lock via serviço;
- capturar `lock_token`;
- simular release antes do submit, chamando `release_case_lock(...)` ou limpando lock como o endpoint faria;
- POST em `/scheduler/<case_id>/submit/` com o token antigo;
- assert status `200` (re-render de erro);
- assert conteúdo contém a nova mensagem;
- assert o caso não saiu de `WAIT_APPT`.

Esse teste reproduz a ordem ruim da race sem precisar de browser.

### Verificação estática/manual JS obrigatória

Como o projeto não tem browser test runner, o relatório deve incluir verificação estática/manual:

- `work_lock.js` só ativa submit guard para submit não cancelado (`!event.defaultPrevented`) de form com `input[name="lock_token"]` igual ao token atual;
- `sendRelease()` retorna sem liberar quando `window.ATS_WORK_LOCK_SUBMITTING === true`;
- `visibilitychange` não chama mais `sendRelease()`;
- `scheduler_confirm.js` seta `window.ATS_WORK_LOCK_SUBMITTING = true` antes de `form.submit()`;
- Doctor e NIR não exigem alteração porque usam formulários com `lock_token` e submit nativo/requestSubmit.

Não introduzir framework JS neste change.

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Lock ficar preso após modal/validação client-side | Guard roda na fase bubble e ignora `event.defaultPrevented`; submits interceptados para modal/validação não são tratados como envio real. |
| Comunicação operacional em página com lock prender reserva | Guard exige `input[name="lock_token"]` igual ao token atual; comunicação não tem esse campo. |
| Scheduler `form.submit()` bypassar listener | Setar flag global explicitamente em `scheduler_confirm.js`. |
| Trocar de aba deixar lock ativo mais tempo | Aceito: card aberto deve continuar reservado; TTL/heartbeat expira se abandonado. |
| Mensagem ocultar casos de token inválido | Não alterar mensagens de token/usuário/contexto inválidos. |

## Rollback

Reverter os arquivos do slice:

1. `static/js/work_lock.js`;
2. `static/js/scheduler_confirm.js`;
3. `apps/cases/services.py`;
4. testes associados.

Não há migração nem alteração persistente de dados.
