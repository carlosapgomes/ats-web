# Proposal: Filas compartilhadas com reserva temporária de casos

**Change ID**: `shared-work-queue-leases`  
**Risco**: PROFISSIONAL (migration em `Case`, concorrência transacional, alterações em filas médico/agendador/NIR)  
**Solicitante**: operação ATS — múltiplos usuários por papel

## Objetivo

Permitir que múltiplos usuários no mesmo papel operacional trabalhem sobre filas compartilhadas sem que duas pessoas processem simultaneamente o mesmo caso.

A solução deve usar o stack já adotado pelo projeto:

- Django SSR;
- PostgreSQL;
- Django ORM/transações;
- HTMX já existente para polling de fila;
- Vanilla JS para heartbeat/idle detection;
- `CaseEvent` append-only para auditoria.

Não introduzir Redis, RabbitMQ, SQS, Django REST Framework, SPA ou framework JS.

## Problema

Hoje as filas de trabalho são compartilhadas, mas os itens não possuem reserva operacional:

- Médicos veem todos os casos `WAIT_DOCTOR` e podem abrir o mesmo caso ao mesmo tempo.
- Agendadores veem todos os casos `WAIT_APPT` e podem abrir o mesmo caso ao mesmo tempo.
- A fila NIR precisa passar a permitir continuidade de plantão: todos os usuários NIR devem ver todos os casos operacionais, não apenas quem criou o caso.

Sem reserva temporária, dois usuários podem:

1. abrir o mesmo caso;
2. preencher formulários diferentes;
3. tentar salvar decisões concorrentes;
4. gerar erro de fluxo, perda de trabalho ou auditoria ambígua.

## Decisão proposta

Implementar **lease-based locking** no próprio PostgreSQL, por campos persistidos no `Case`.

Um caso em fila pode ser reservado por um usuário durante uma janela curta. Enquanto o usuário estiver ativo na tela, o frontend renova a reserva via heartbeat. Se o navegador fechar, a rede cair ou o usuário abandonar a tela, o lease expira e o caso volta a ficar disponível.

## Escopo funcional

1. Adicionar metadados de lock temporário ao `Case`.
2. Criar serviço transacional centralizado para:
   - adquirir reserva;
   - renovar reserva;
   - liberar reserva;
   - validar propriedade da reserva antes de ações finais;
   - detectar e auditar expiração.
3. Aplicar reserva à fila médica:
   - abrir decisão médica reserva o caso;
   - fila mostra quem está com o caso;
   - submit médico exige reserva válida.
4. Aplicar heartbeat com idle detection na tela médica.
5. Revisar permissões do agendador adicionando `@role_required("scheduler")` às views do app scheduler.
6. Aplicar reserva à fila do agendador:
   - abrir confirmação reserva o caso;
   - fila mostra quem está com o caso;
   - submit exige reserva válida;
   - ciência operacional de vinda imediata permanece idempotente e protegida por papel.
7. Ajustar NIR:
   - todos os usuários NIR veem todos os casos operacionais (`status != CLEANED`), independentemente de `created_by`;
   - NIR consegue abrir detalhe de caso operacional de outro usuário NIR;
   - confirmação de recebimento exige reserva válida quando o caso está em `WAIT_R1_CLEANUP_THUMBS`;
   - após confirmação/cleanup, o caso sai da fila operacional NIR.
8. Registrar auditoria de expiração contendo quem estava com o caso quando o lease expirou.
9. Cobrir tudo com TDD e relatórios por slice.

## Fora de escopo

- Servidor de fila dedicado.
- WebSocket ou atualização realtime além do polling HTMX existente.
- Redis/cache distribuído.
- Advisory locks do PostgreSQL como mecanismo principal.
- Novos estados FSM como `EM_PARECER` ou `EM_AGENDAMENTO`.
- Mudança dos 17 estados preservados.
- Override manual por supervisor/admin nesta primeira entrega.
- Edição colaborativa simultânea.
- Notificações por e-mail/SMS/push.
- Sistema genérico de tarefas para entidades além de `Case`.

## UX esperada

### Fila médica/agendador

Cards devem continuar visíveis para todos, mas exibir estado operacional:

```text
Disponível
[Avaliar Caso]
```

```text
Em avaliação por Dra. Ana até 14:35
[Botão desabilitado]
```

```text
Reservado por você até 14:35
[Continuar]
```

### Tela de trabalho

Mostrar feedback discreto:

```text
Caso reservado para você. Reserva renovada automaticamente enquanto houver atividade.
```

Se o lease expirar ou for perdido:

```text
Sua reserva expirou ou foi assumida por outro usuário. Volte para a fila antes de continuar.
```

### NIR

A lista operacional NIR deve permitir continuidade de plantão:

- todos os NIR veem todos os casos operacionais (`status != CLEANED`), independentemente de quem criou;
- todos os NIR podem abrir o detalhe operacional desses casos para acompanhamento;
- qualquer NIR autorizado pode confirmar recebimento de um resultado pendente (`WAIT_R1_CLEANUP_THUMBS`), desde que possua a reserva válida.

## Assunções de produto para implementação

1. **Casos operacionais NIR** significam todos os casos com `status != CLEANED`.
2. Todos os usuários com papel ativo `nir` podem ver e abrir detalhes de todos os casos operacionais para continuidade de plantão.
3. Qualquer usuário com papel ativo `nir` pode assumir e concluir um resultado pendente (`WAIT_R1_CLEANUP_THUMBS`), mesmo que não seja `created_by`.
4. A auditoria deve registrar o usuário anterior quando um lock expira. Como não haverá job dedicado, a expiração será registrada de forma lazy quando a fila for consultada ou quando outro usuário tentar adquirir o caso.

Se alguma dessas assunções precisar mudar, ajustar o `design.md` antes da implementação do slice afetado.

## Critérios de aceitação do change

- [ ] Dois médicos não conseguem submeter decisão para o mesmo caso simultaneamente.
- [ ] Dois agendadores não conseguem submeter agendamento para o mesmo caso simultaneamente.
- [ ] Dois NIR não conseguem confirmar recebimento do mesmo resultado simultaneamente.
- [ ] Fila médica mostra casos reservados por outro usuário com identificação humana e ação bloqueada.
- [ ] Fila do agendador mostra casos reservados por outro usuário com identificação humana e ação bloqueada.
- [ ] Fila NIR mostra todos os casos operacionais compartilhados entre todos os NIR.
- [ ] Abrir tela operacional adquire lock de forma transacional.
- [ ] Ações finais exigem `locked_by`, `lock_token` e `locked_until` válidos.
- [ ] Heartbeat renova o lock apenas quando há atividade recente do usuário.
- [ ] Se a aba/navegador for abandonado, o lock expira e outro usuário pode assumir.
- [ ] `CaseEvent` registra quem estava com o caso quando o lock expirou.
- [ ] Heartbeats não poluem a timeline com evento a cada minuto.
- [ ] Views do scheduler exigem papel ativo `scheduler`.
- [ ] A solução usa apenas Django/PostgreSQL/Vanilla JS/HTMX já existente.
- [ ] Testes relevantes implementados via TDD.
- [ ] Quality gate do `AGENTS.md` executado.
- [ ] Cada slice gera relatório temporário com snippets antes/depois e informa `REPORT_PATH`.
