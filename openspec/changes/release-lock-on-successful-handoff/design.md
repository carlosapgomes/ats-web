# Design: Liberar lock após handoff operacional bem-sucedido

## Contexto

A change `shared-work-queue-leases` implementou locks temporários persistidos em `Case` com lease de 5 minutos, heartbeat e release best-effort no navegador.

A garantia real de liberação em abandono de tela continua sendo a expiração automática. Porém, quando uma ação final é concluída no backend, o servidor já possui contexto suficiente para limpar o lock de forma determinística.

## Estado atual relevante

### Médico

`apps/doctor/views.py::doctor_submit`:

1. valida método POST;
2. carrega `Case` em `WAIT_DOCTOR`;
3. parseia `lock_token`;
4. chama `assert_case_lock(... context="doctor_decision")`;
5. valida `DoctorDecisionForm`;
6. executa transições FSM;
7. redireciona para a fila.

Hoje o lock pode continuar gravado após o caso sair de `WAIT_DOCTOR`.

### Agendador

`apps/scheduler/views.py::scheduler_submit`:

1. valida método POST;
2. carrega `Case` em `WAIT_APPT`;
3. parseia `lock_token`;
4. chama `assert_case_lock(... context="scheduler_confirm")`;
5. valida `SchedulerDecisionForm`;
6. executa transições FSM;
7. redireciona para a fila.

Hoje o lock pode continuar gravado após o caso sair de `WAIT_APPT`.

### Serviço existente

`apps/cases/services.py::release_case_lock(...)` já:

- valida `user + token + context` via `assert_case_lock`;
- registra `WORK_LOCK_RELEASED`;
- limpa todos os campos de lock;
- retorna `True`/`False`.

## Decisão de implementação

Reutilizar `release_case_lock(...)` nos submits bem-sucedidos.

### D1: Release somente após sucesso de negócio

O lock só deve ser limpo depois que:

- o formulário é válido;
- as transições FSM foram executadas;
- os campos e eventos de negócio foram persistidos.

Isso preserva o lock quando o usuário precisa corrigir erro de formulário.

### D2: Release não deve mascarar a ação de negócio

Depois de `assert_case_lock` já ter passado, espera-se que `release_case_lock` retorne `True`. Ainda assim, se retornar `False` por corrida incomum, a ação de negócio já terá sido concluída.

Neste slice, não transformar falha de release pós-submit em erro para o usuário. O fallback de lease continua existindo.

### D3: Não alterar Cancelar/navegação

Este slice não muda `work_lock.js` nem o link Cancelar. O objetivo é somente corrigir handoff após submissão bem-sucedida.

### D4: Ordem recomendada

#### Fluxo médico

Em `doctor_submit`, após todas as transições/saves da decisão médica e antes do `return redirect("doctor:queue")`:

```python
release_lock_service(
    case_id=case.case_id,
    user=request.user,
    token=token,
    context="doctor_decision",
)
```

#### Fluxo scheduler

Em `scheduler_submit`, após `case.final_reply_posted(...)` e `case.save()`, antes do `return redirect("scheduler:queue")`:

```python
release_lock_service(
    case_id=case.case_id,
    user=request.user,
    token=token,
    context="scheduler_confirm",
)
```

## Testes esperados

### Testes médico

- Submit `accept + scheduled` com token válido:
  - status final esperado: `WAIT_APPT`;
  - `locked_by`, `lock_token`, `locked_until` limpos;
  - evento `WORK_LOCK_RELEASED` criado.
- Submit `deny` com token válido:
  - status final esperado: `WAIT_R1_CLEANUP_THUMBS`;
  - lock limpo.
- Submit inválido com token válido:
  - response 200 re-renderizando formulário;
  - status continua `WAIT_DOCTOR`;
  - lock continua do médico.
- Submit com token inválido/ausente:
  - status continua `WAIT_DOCTOR`;
  - lock não é limpo.
- Integração handoff:
  - após aceite `scheduled`, scheduler abre `scheduler_confirm` imediatamente e adquire lock `scheduler_confirm`.

### Testes scheduler

- Submit `confirm` com token válido:
  - status final esperado: `WAIT_R1_CLEANUP_THUMBS`;
  - lock limpo;
  - evento `WORK_LOCK_RELEASED` criado.
- Submit `deny` com token válido:
  - status final esperado: `WAIT_R1_CLEANUP_THUMBS`;
  - lock limpo.
- Submit inválido com token válido:
  - response 200 re-renderizando formulário;
  - status continua `WAIT_APPT`;
  - lock continua do scheduler.
- Submit com token inválido/ausente:
  - status continua `WAIT_APPT`;
  - lock não é limpo.
- Integração handoff:
  - após scheduler concluir, NIR abre detalhe de `WAIT_R1_CLEANUP_THUMBS` imediatamente e adquire lock `nir_receipt`.

## Riscos

| Risco | Mitigação |
| --- | --- |
| Limpar lock antes de persistir decisão | Chamar release apenas ao final do fluxo bem-sucedido |
| Perder lock em formulário inválido | Testar preservação do lock em erro de validação |
| Duplicar regra de limpeza manual | Reutilizar `release_case_lock(...)` |
| Alterar comportamento de Cancelar sem querer | Não tocar templates/JS neste slice |

## Rollback

Rollback simples: remover as chamadas de `release_lock_service(...)` adicionadas a `doctor_submit` e `scheduler_submit`, mantendo os testes como referência ou revertendo-os junto.
