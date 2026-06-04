# Proposal: Intercorrência pós-agendamento

**Change ID**: `post-schedule-intercurrence`  
**Risco**: PROFISSIONAL (FSM cíclica a partir de `CLEANED`, migration em `Case`, alteração de filas NIR/agendador)  
**Solicitante**: operação NIR/agendamento — Centro de Hemorragia Digestiva

## Contexto greenfield

Este projeto ainda não está em produção nem em uso assistencial. Não há
necessidade de compatibilidade retrógrada com dados reais ou fluxos já
implantados. A feature deve priorizar clareza do modelo, qualidade e preparo
para demonstração em aproximadamente 15 dias e início de uso em cerca de 3
semanas.

## Objetivo

Permitir que o NIR registre uma intercorrência em caso previamente agendado e encerrado, para que o agendador possa cancelar, reagendar, manter ou negar uma solicitação de alteração, com retorno obrigatório ao NIR para ciência e encerramento.

O fluxo deve ser auditável, suportar múltiplos ciclos ao longo do tempo e impedir mais de uma intercorrência ativa simultânea por caso.

## Problema

O fluxo atual encerra casos após agendamento e confirmação do NIR (`CLEANED`). Na operação real, 1–2 vezes por semana surgem eventos após o encerramento:

- paciente faleceu;
- paciente perdeu condição clínica de transporte;
- unidade de origem não consegue providenciar transporte na data marcada;
- regulação estadual marcou/realizou o exame em outra unidade;
- unidade solicita reagendamento;
- outros motivos operacionais.

Hoje não há forma rastreável de recuperar um caso encerrado e solicitar ação do agendamento sem abrir um novo fluxo clínico. Abrir novo fluxo só é a rotina correta quando há novo relatório ou necessidade de reavaliação médica.

## Decisão proposta

Implementar uma **intercorrência pós-agendamento** no próprio `Case`, sem criar novos estados FSM.

Fluxo conceitual:

```text
CLEANED
→ NIR abre intercorrência pós-agendamento
→ WAIT_APPT, marcado como intercorrência ativa
→ Agendador resolve: cancelar / reagendar / manter / negar
→ WAIT_R1_CLEANUP_THUMBS
→ NIR confirma ciência
→ CLEANED
```

A timeline (`CaseEvent`) preserva todos os ciclos. Campos principais de agendamento no `Case` representam sempre o agendamento atual/mais recente; valores anteriores ficam auditados nos eventos.

## Escopo funcional

1. Adicionar metadados mínimos no `Case` para representar a intercorrência ativa/latest:
   - status da intercorrência (`none/opened/responded` ou equivalente);
   - motivo NIR;
   - mensagem NIR opcional/condicional;
   - abertura por/horário;
   - ação/resposta do agendador;
   - resposta/motivo do agendador;
   - resposta por/horário.
2. Adicionar transição FSM explícita de `CLEANED` para `WAIT_APPT` para abrir intercorrência elegível.
3. Reaproveitar a fila do agendador (`WAIT_APPT`) com destaque visual para intercorrência.
4. Permitir ao NIR buscar casos encerrados por número da ocorrência ou nome do paciente.
5. Mostrar botão de abertura somente para casos elegíveis:
   - `status=CLEANED`;
   - decisão médica aceita;
   - fluxo médico `scheduled`;
   - agendamento atualmente confirmado;
   - sem intercorrência ativa.
6. Permitir motivos oficiais:
   - paciente faleceu;
   - paciente sem condição clínica de transporte;
   - transporte indisponível pela unidade de origem;
   - exame agendado/realizado pela regulação estadual em outro serviço;
   - solicitação de reagendamento pela unidade de origem;
   - outro.
7. Exigir mensagem NIR de forma condicional:
   - opcional para motivo óbito e regulação estadual;
   - obrigatória para sem condição clínica, transporte indisponível, solicitação de reagendamento e outro.
8. Permitir ações do agendador:
   - cancelar agendamento;
   - reagendar;
   - manter agendamento;
   - negar solicitação, por exemplo por falta de vaga.
9. Após resposta do agendador, retornar ao NIR para confirmar ciência.
10. Registrar todos os passos em `CaseEvent` append-only.

## Fora de escopo

- Reavaliação médica neste fluxo. Quando houver necessidade clínica, a rotina é abrir novo fluxo com relatório atualizado.
- Intercorrência para casos previamente negados.
- Intercorrência para casos sem agendamento confirmado.
- Notificações externas por e-mail/SMS/push.
- Entidade genérica de workflow ou ticketing.
- Histórico relacional completo de agendamentos; a timeline por `CaseEvent` é suficiente nesta entrega.
- Alteração dos 17 estados preservados da FSM.
- Dashboard/BI avançado; manter apenas métricas planejadas coerentes.

## UX esperada

### Busca NIR de casos encerrados

O NIR acessa uma aba/página de busca de casos encerrados e pesquisa por:

```text
Número da ocorrência ou nome do paciente
```

Resultados mostram elegibilidade. Quando elegível:

```text
[Registrar intercorrência]
```

Quando não elegível:

```text
Intercorrência indisponível: caso não possui agendamento confirmado encerrado.
```

Quando já existe intercorrência ativa:

```text
Intercorrência em avaliação. Aguarde resposta/ciência antes de abrir nova solicitação.
```

### Fila do agendador

Cards de intercorrência devem ficar distinguíveis dos agendamentos iniciais:

```text
Intercorrência pós-agendamento
Motivo: Transporte indisponível
Mensagem do NIR: Unidade solicita nova data para a próxima semana.
```

Ações:

```text
Cancelar | Reagendar | Manter | Negar solicitação
```

### Retorno ao NIR

Após resposta do agendador, o caso aparece como pendente de ciência NIR, com badge:

```text
Intercorrência respondida pelo agendamento
```

O NIR confirma recebimento e o caso volta a `CLEANED`.

## Critérios globais de sucesso

- NIR consegue localizar caso encerrado elegível por ocorrência ou nome.
- NIR consegue abrir intercorrência pós-agendamento com motivo oficial e mensagem validada condicionalmente.
- Outra pessoa do NIR não consegue abrir segunda intercorrência ativa no mesmo caso.
- Agendador vê a intercorrência na fila e resolve com uma das quatro ações.
- Reagendamento atualiza os campos principais de agendamento.
- Cancelamento marca o agendamento atual como cancelado e encerra sem criar novo fluxo.
- Negação da solicitação preserva o agendamento atual confirmado.
- NIR confirma ciência e o caso retorna a `CLEANED`.
- Timeline registra abertura, resposta do agendamento e confirmação de ciência.
- Múltiplos ciclos em momentos diferentes ficam preservados por eventos.
