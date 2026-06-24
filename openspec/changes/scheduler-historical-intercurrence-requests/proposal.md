# Proposal: Acesso contextual CHD, busca histórica e detalhe antes da intercorrência

**Change ID**: `scheduler-historical-intercurrence-requests`  
**Fase**: melhoria operacional pós-comunicação por caso  
**Risco**: PROFISSIONAL (novas rotas read-only para casos históricos/mencionados e permissão controlada de mensagem operacional em caso encerrado; sem novos estados FSM)  
**Dependências**: `post-schedule-intercurrence`, `case-operational-communication-mvp`, `case-communication-mentions-notifications`, `case-communication-mention-aliases`, `workflow-system-notices-in-case-communication`, `scheduler-processed-today-tab`

## Problemas

### P1. NIR decide abrir intercorrência antes de ver o detalhe histórico

Hoje a busca NIR de casos encerrados é centrada na ação de abrir intercorrência pós-agendamento. O NIR não possui um passo natural de **abrir detalhes** do caso encerrado, ler timeline/comunicação/contexto e só então registrar intercorrência.

O fluxo desejado é:

```text
NIR busca caso histórico
→ vê lista de cards
→ clica em Detalhes
→ lê o caso, histórico e comunicação
→ dentro dos detalhes, se elegível, abre intercorrência
```

### P2. Menção ao CHD antes da etapa de agendamento não abre contexto útil

Se alguém menciona `@scheduler`/`@chd` ou um agendador específico em um caso que ainda não chegou a `WAIT_APPT`, o agendador recebe notificação, mas o redirect atual tende a levá-lo para a fila em vez de para o contexto do caso.

Isso é legítimo em casos como:

```text
@chd se este caso for aceito, há alguma restrição de agenda para esta semana?
```

O CHD precisa conseguir ler contexto e responder na comunicação, sem poder confirmar/negar agendamento fora da etapa correta.

### P3. CHD não consegue avisar o NIR a partir de caso histórico

Caso já teve parecer médico, foi agendado, recebeu recomendação final e depois o CHD descobre um problema operacional interno — por exemplo, médico do dia indisponível. Hoje o CHD teria que avisar o NIR fora do sistema, porque não há busca histórica multi-dia do agendador nem detalhe operacional para enviar mensagem ao NIR.

## Objetivos

1. Trocar a experiência NIR de casos encerrados para **cards com botão Detalhes**; a intercorrência passa a ser criada dentro do detalhe.
2. Permitir que o NIR abra detalhes de caso `CLEANED` vindo da busca histórica ou de notificação, sem reabrir o caso automaticamente.
3. Permitir que o CHD/agendador mencionado abra detalhe read-only operacional do caso, responda na comunicação quando o caso não estiver `CLEANED` e não veja ações de workflow.
4. Permitir que o CHD/agendador pesquise casos históricos agendados/processados, abra detalhe read-only e envie mensagem operacional ao NIR pelo sistema.
5. Manter o workflow estruturado intacto: somente o NIR abre intercorrência pós-agendamento usando o serviço existente; mensagem do CHD não muda estado por si só.

## Decisões de produto

### D1. Detalhe antes da intercorrência para o NIR

Sim: no item 3 discutido, o NIR deve ver **uma lista de cards com botão Detalhes**. Dentro do detalhe do caso encerrado, se o caso for elegível, haverá a ação de criar intercorrência pós-agendamento.

Motivos:

- evita abrir intercorrência sem ler contexto;
- permite ler mensagem operacional do CHD;
- reutiliza o detalhe/timeline como fonte de contexto;
- mantém a intercorrência como ação consciente e estruturada do NIR.

### D2. Menção concede contexto, não permissão de workflow

Quando um agendador é mencionado em caso fora de `WAIT_APPT`, ele pode abrir detalhe read-only operacional e responder na comunicação, mas não pode:

- assumir lock;
- confirmar agendamento;
- negar agendamento;
- responder intercorrência;
- alterar FSM;
- executar ações estruturadas fora da fila/status correto.

### D3. Mensagem CHD → NIR não reabre caso

A mensagem histórica do CHD ao NIR cria comunicação operacional e notificação in-app para NIR (`@nir`), mas não muda o status do caso.

Menções adicionais são permitidas e devem seguir o parser existente de comunicação operacional. Exemplo legítimo: o agendador menciona `@medico`/usuário médico para explicar o motivo da recusa operacional e também aciona `@nir` para reapresentação/reagendamento.

O caso só volta para `WAIT_APPT` quando o NIR, dentro do detalhe histórico, registra a intercorrência usando `open_post_schedule_issue` existente.

### D4. Sem ticket/request model neste MVP

Não criar uma nova entidade de “solicitação CHD pendente” neste change. A chamada para ação do NIR será uma `UserNotification` gerada por menção explícita/automática a `@nir` na `CaseCommunicationMessage`.

Menções adicionais digitadas pelo agendador devem ser preservadas e processadas normalmente (`@doctor`/`@medico`, `@username`, `@manager` etc.). O endpoint histórico apenas garante que `@nir` também esteja presente; ele não deve sanitizar/remover outros destinatários legítimos.

Motivo: o sistema já tem comunicação operacional, menções, inbox e mensagens sistêmicas. Para este slice vertical, usar esse mecanismo entrega rastreabilidade suficiente com menor escopo e menor risco. Uma fila estruturada de solicitações CHD pode ser avaliada depois se as notificações forem insuficientes.

## Escopo

### Funcionalidades

1. **Busca NIR de encerrados com cards e detalhe**
   - Busca por ocorrência ou nome do paciente continua existindo.
   - Resultado passa a ser card com botão `Detalhes`.
   - Detail read-only de caso encerrado mostra contexto do caso, timeline e thread de comunicação.
   - Dentro do detalhe, se elegível, NIR abre intercorrência pós-agendamento usando o serviço existente.
   - Se inelegível, detalhe mostra motivo de inelegibilidade.

2. **Redirect seguro de notificação NIR para caso encerrado**
   - Se NIR abre notificação vinculada a caso `CLEANED`, o redirect vai para o detalhe histórico NIR, não para home.

3. **Detalhe operacional CHD por menção**
   - Se scheduler recebeu `UserNotification` vinculada ao caso, pode abrir detalhe read-only operacional.
   - Tela inclui comunicação operacional e permite resposta quando `case.status != CLEANED`.
   - Tela não inclui ações de agendamento nem locks.

4. **Busca histórica CHD**
   - Nova entrada/aba para o agendador buscar casos históricos por ocorrência ou nome do paciente.
   - Lista casos aceitos para agendamento e já processados/agendados, incluindo `CLEANED`.
   - Não limita a “processados hoje”.

5. **Mensagem operacional CHD → NIR em caso histórico**
   - A partir do detalhe histórico, CHD envia mensagem operacional ao NIR.
   - O sistema garante menção a `@nir` para gerar notificação in-app.
   - Menções adicionais a usuários/grupos são permitidas e geram notificações pelo mecanismo existente.
   - A mensagem fica na thread do caso e não altera FSM.
   - NIR abre a notificação, lê o detalhe e, se couber, cria intercorrência.

## Fora de escopo

- CHD reabrir diretamente o caso para `WAIT_APPT` sem NIR.
- Novo estado FSM.
- Novo modelo/tabela de solicitações CHD.
- Fila estruturada de solicitações CHD pendentes.
- Busca histórica para todos os papéis.
- Edição/deleção de mensagens.
- SLA, filtros avançados, paginação avançada ou exportação.
- Comunicação externa por email/SMS/push.
- WebSocket/SSE.
- Transformar comunicação operacional em chat em tempo real.
- Resolver o problema geral de qualquer papel mencionado em qualquer status. Este change trata NIR histórico e CHD/agendador.

## Critérios globais de sucesso

- NIR vê resultados de busca histórica como cards com botão `Detalhes`.
- NIR consegue abrir detalhe de caso `CLEANED` pela busca histórica.
- NIR consegue abrir detalhe de caso `CLEANED` por notificação.
- NIR consegue criar intercorrência dentro do detalhe histórico quando o caso é elegível.
- NIR vê motivo claro quando o caso histórico não é elegível para intercorrência.
- CHD mencionado em caso fora de `WAIT_APPT` consegue abrir detalhe read-only e responder na comunicação quando o caso não é `CLEANED`.
- CHD mencionado não vê botões de confirmação/recusa/agendamento/intercorrência.
- CHD consegue buscar caso histórico agendado/processado por ocorrência ou nome.
- CHD consegue abrir detalhe histórico read-only sem lock e sem ações de workflow.
- CHD consegue enviar mensagem operacional ao NIR em caso histórico, gerando `UserNotification` para NIR.
- CHD pode mencionar outros usuários/grupos na mesma mensagem; essas menções adicionais são preservadas e notificadas pelo parser existente.
- Mensagem CHD → NIR em caso histórico não altera `Case.status`.
- NIR, após ler mensagem do CHD, usa o fluxo existente de intercorrência para mover caso elegível para `WAIT_APPT`.
- Timeline/thread registram comunicação e intercorrência com `CaseEvent` append-only.
- Nenhum novo estado FSM é criado.
- Quality gate do `AGENTS.md` passa.
- Cada slice gera relatório temporário com `REPORT_PATH`.
