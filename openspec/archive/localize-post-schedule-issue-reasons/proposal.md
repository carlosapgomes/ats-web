# Proposal: Localizar motivos de intercorrência pós-agendamento

**Change ID**: `localize-post-schedule-issue-reasons`  
**Risco**: ESSENCIAL  
**Origem**: teste manual da feature `post-schedule-intercurrence`

## Contexto

Durante teste manual, o NIR abriu uma intercorrência pós-agendamento com motivo
`death`. Na fila/tela do agendador, o motivo apareceu como código técnico em
inglês:

```text
Motivo: death
```

A feature original foi implementada em:

```text
openspec/archive/post-schedule-intercurrence/
```

O problema está na apresentação para o agendador, não na regra de domínio. Os
códigos persistidos continuam sendo valores canônicos internos.

## Problema

Algumas views/templates exibem `post_schedule_issue_reason` diretamente ao
usuário. Isso vaza códigos internos como `death`, `clinical_condition`,
`transport_unavailable`, `external_regulation`, `reschedule_request` e `other`.

Pontos identificados:

- `templates/scheduler/confirm_post_schedule_issue.html`
- `templates/scheduler/_queue_content.html`
- `apps/scheduler/views.py`, que passa o código cru no contexto
- testes scheduler que aceitam o código cru como alternativa, enfraquecendo a
  regressão

Também existe mapeamento duplicado em `apps/intake/views.py` para o detalhe NIR.

## Objetivo

Garantir que motivos de intercorrência pós-agendamento sejam exibidos em
português em todas as superfícies operacionais, especialmente para o agendador.

## Escopo

- Criar fonte única de labels para motivos de intercorrência pós-agendamento.
- Usar labels em contexto/templates do scheduler.
- Reutilizar a mesma fonte no detalhe NIR, removendo mapeamento duplicado se
  couber no slice.
- Ajustar testes para exigir labels em português e rejeitar códigos crus na UI.

## Fora de escopo

- Alterar valores persistidos no banco.
- Criar migration de dados.
- Renomear códigos internos.
- Alterar regras de elegibilidade ou FSM.
- Revisar todo o vocabulário clínico do sistema fora de intercorrência
  pós-agendamento.

## Critérios de sucesso

- O agendador vê `Paciente faleceu`, não `death`.
- O agendador vê labels em português para todos os motivos oficiais.
- Fila e tela de resolução do scheduler não exibem códigos crus de motivo.
- Detalhe NIR continua exibindo label em português.
- Testes relevantes passam.
