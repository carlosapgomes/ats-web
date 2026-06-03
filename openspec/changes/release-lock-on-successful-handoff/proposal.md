# Proposal: Liberar lock após handoff operacional bem-sucedido

**Change ID**: `release-lock-on-successful-handoff`  
**Risco**: ESSENCIAL  
**Solicitante**: operação ATS / revisão do mecanismo de locking

## Objetivo

Garantir que locks de trabalho sejam liberados de forma determinística no backend quando uma etapa operacional é concluída com sucesso e o caso passa para o próximo papel.

O foco é evitar que o próximo papel precise aguardar a expiração automática do lease quando o release best-effort do navegador falhar.

## Problema

O mecanismo atual de locking funciona corretamente para impedir edição concorrente, mas a liberação imediata depende principalmente de `work_lock.js` em navegação/`pagehide`, que é best-effort.

Isso é aceitável para abandono de tela ou clique em Cancelar, mas é indesejado após submissões bem-sucedidas:

```text
Médico envia decisão aceita para agendamento
→ caso muda para WAIT_APPT
→ lock doctor_decision pode permanecer ativo se release JS falhar
→ agendador pode enxergar o caso como reservado até o lease expirar
```

```text
Agendador confirma/nega agendamento
→ caso muda para WAIT_R1_CLEANUP_THUMBS
→ lock scheduler_confirm pode permanecer ativo se release JS falhar
→ NIR pode esperar até expiração para confirmar recebimento
```

## Decisão proposta

Após uma ação final bem-sucedida, liberar explicitamente o lock no backend, usando o serviço centralizado existente `release_case_lock(...)`.

Aplicar apenas aos handoffs concluídos:

1. `doctor_submit` após decisão médica válida e transições FSM concluídas.
2. `scheduler_submit` após confirmação/negação válida e transições FSM concluídas.

## Fora de escopo

- Remover ou alterar o release best-effort do `work_lock.js`.
- Alterar o comportamento do botão Cancelar.
- Reduzir tempo de lease.
- Alterar heartbeat, idle detection ou `visibilitychange`.
- Criar endpoint novo.
- Alterar FSM.
- Alterar regras NIR, exceto validar que NIR não fica bloqueado após handoff do scheduler.

## Critérios de aceitação

- [ ] Submit médico válido limpa campos de lock imediatamente.
- [ ] Submit médico inválido preserva lock para permitir correção do formulário.
- [ ] Submit médico com token ausente/inválido não altera status e preserva lock.
- [ ] Após aceite médico para agendamento, scheduler consegue abrir o caso imediatamente.
- [ ] Submit scheduler válido limpa campos de lock imediatamente.
- [ ] Submit scheduler inválido preserva lock para permitir correção do formulário.
- [ ] Submit scheduler com token ausente/inválido não altera status e preserva lock.
- [ ] Após conclusão scheduler, NIR consegue abrir/assumir confirmação de recebimento imediatamente.
- [ ] `WORK_LOCK_RELEASED` é registrado no release explícito pós-submit sem poluir heartbeat.
- [ ] Nenhum comportamento de Cancelar/navegação é alterado.
