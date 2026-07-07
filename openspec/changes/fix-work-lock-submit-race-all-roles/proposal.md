# Proposal: Corrigir race condition de reserva ao submeter ações com lock

**Change ID**: `fix-work-lock-submit-race-all-roles`  
**Fase**: bugfix operacional / hardening de fila de trabalho  
**Risco**: PROFISSIONAL (corrige fluxo transversal de lock em NIR, médico e agendador; sem mudança de FSM/modelos)  
**Dependências**: `shared-work-queue-leases`, `release-lock-on-successful-handoff`, `doctor-queue`, `scheduler-queue`, `nir-result-closure`

## Problema

As telas operacionais com reserva de caso usam `static/js/work_lock.js` para renovar e liberar locks de trabalho. O script libera a reserva em eventos de navegação/ocultação da página (`pagehide` e `visibilitychange`).

Em produção ocorreu um caso na tela do agendador: o usuário abriu o card, preencheu a confirmação e, ao clicar em **Enviar Confirmação**, recebeu a mensagem:

```text
Caso não possui reserva ativa.
```

A investigação do fluxo mostrou uma race condition plausível:

```text
Usuário abre tela protegida por lock
→ backend cria Case.locked_by/lock_token
→ usuário confirma ação final
→ navegador inicia navegação do POST
→ work_lock.js recebe pagehide/visibilitychange e chama /lock/release/
→ release limpa o lock antes do POST principal chegar
→ backend executa assert_case_lock()
→ locked_by está vazio
→ ação é bloqueada com mensagem ambígua
```

O mesmo padrão existe em outros papéis:

| Papel | Tela/ação protegida | Template | Backend |
|-------|----------------------|----------|---------|
| `scheduler` | confirmar/negar agendamento e responder intercorrência | `templates/scheduler/confirm*.html` | `apps/scheduler/views.py::scheduler_submit` |
| `doctor` | confirmar decisão médica | `templates/doctor/decision.html` | `apps/doctor/views.py::doctor_submit` |
| `nir` | confirmar recebimento/conclusão | `templates/intake/case_detail.html` | `apps/intake/views.py::confirm_receipt` |

A mensagem atual também é tecnicamente correta, mas ruim para o usuário final: “reserva ativa” não deixa claro que a reserva da tela expirou/liberou antes do envio.

## Objetivo

Proteger todos os fluxos com lock contra liberação prematura durante submissão de ação final e melhorar a mensagem quando a reserva já não está disponível.

Resultado esperado:

```text
Usuário abre tela com reserva
→ usuário submete ação final
→ work_lock.js não libera o lock durante o submit
→ backend processa a ação usando o lock válido
→ backend libera o lock deterministicamente após sucesso
```

Se, por expiração real ou liberação prévia, o lock não existir no momento do POST, a UI deve mostrar mensagem clara:

```text
A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente.
```

## Escopo

### Funcionalidades

1. Impedir que `work_lock.js` chame `lock/release/` enquanto um formulário de ação protegida por `lock_token` está sendo submetido.
2. Aplicar a proteção de forma centralizada para NIR, médico e agendador.
3. Cobrir o caso especial do agendador em `scheduler_confirm.js`, que hoje usa `form.submit()` programático e pode bypassar o evento `submit` nativo.
4. Remover ou neutralizar a liberação automática em `visibilitychange`, porque trocar de aba/minimizar não deve significar abandono do card.
5. Manter liberação explícita ao sair por link/cancelar/voltar sem decidir.
6. Preservar liberação determinística no backend após sucesso (`release_case_lock` ou limpeza equivalente já existente).
7. Substituir a mensagem genérica de ausência/expiração de lock por mensagem acionável para o usuário final.

### Fora de escopo

- Alterar models, migrations ou campos de lock.
- Alterar FSM ou estados de caso.
- Criar WebSocket/SSE, beacon API ou endpoint novo.
- Implementar autosave de formulário.
- Alterar regras de expiração/TTL (`CASE_LOCK_LEASE_SECONDS`).
- Bloquear múltiplas abas do mesmo usuário neste change.
- Refatorar todos os fluxos de release backend para um único helper.
- Criar browser test runner/framework JS.

## Dimensionamento dos slices

Este change deve ser implementado em **1 slice vertical enxuto**.

Justificativa:

- A causa raiz é central (`work_lock.js`) e a mensagem é central (`assert_case_lock`).
- Separar “corrigir race” e “melhorar mensagem” em slices distintos criaria entrega parcial: o usuário poderia continuar recebendo mensagem ruim ou continuar sujeito à race.
- Um único slice toca poucos arquivos previstos (idealmente 5):
  1. `static/js/work_lock.js`
  2. `static/js/scheduler_confirm.js`
  3. `apps/cases/services.py`
  4. `apps/cases/tests/test_lock_service.py`
  5. `apps/scheduler/tests/test_views.py`
- Doctor e NIR são protegidos pelo mesmo `work_lock.js` porque usam submit nativo/requestSubmit em formulários com `lock_token`.

## Critérios de sucesso

- Submit de formulário protegido por `lock_token` não dispara release client-side antes do POST principal.
- `visibilitychange` não libera lock de caso aberto.
- Scheduler continua liberando lock ao clicar em links de saída/cancelar e após sucesso no backend.
- Doctor e NIR passam a herdar a proteção central sem alteração de templates.
- A mensagem de lock ausente/expirado orienta o usuário a voltar à fila e abrir novamente.
- Testes unitários/integrados relevantes cobrem a mensagem e a regressão principal no scheduler.
- Quality gate do AGENTS.md passa na implementação.
