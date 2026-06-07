# Proposal: Encerramento administrativo e filtro de atenção

**Change ID**: `administrative-case-closure-and-attention-filter`  
**Fase**: ajuste operacional pós-Fase 3  
**Risco**: PROFISSIONAL (altera FSM com transição excepcional para `CLEANED` e adiciona ação administrativa no dashboard)  
**Dependências**: `dashboard-supervisor`, `nir-result-closure`, `shared-work-queue-leases`

## Problema

Alguns casos podem ficar presos no meio da máquina de estados por erro de processamento, bug sistêmico, falha de LLM, worker interrompido ou handoff incompleto. Quando isso acontece, o caso pode permanecer indefinidamente em filas operacionais como:

- NIR: casos pendentes/aguardando confirmação;
- médico: aguardando decisão;
- agendador: aguardando agendamento;
- dashboard: casos em andamento sem avanço.

Isso prejudica a usabilidade dos usuários operacionais, pois mantém pendências que não serão resolvidas automaticamente. O supervisor (`manager`) ou administrador (`admin`) precisa conseguir retirar esse caso da operação de forma controlada, auditável e reversível apenas por novo envio/reapresentação do relatório.

## Objetivo

Adicionar um fluxo excepcional para que supervisor/admin possam:

1. identificar casos com sinais de travamento na listagem principal do dashboard;
2. abrir o detalhe do caso;
3. encerrá-lo administrativamente no estado atual;
4. remover o caso das filas operacionais sem apagar histórico nem mascarar a causa.

## Escopo

### Funcionalidades

1. **Encerramento administrativo**
   - Disponível apenas para papel ativo `manager` ou `admin`.
   - Acessível no detalhe de caso do dashboard.
   - Permite encerrar qualquer caso operacional (`status != CLEANED`).
   - Move o caso para `CLEANED`, pois este já é o estado terminal usado para sair das filas.
   - Exige motivo/justificativa obrigatória.
   - Registra evento append-only `CaseEvent` com status anterior, ator, papel ativo, motivo e estado de lock/intercorrência.
   - Limpa lock operacional, se houver.

2. **Filtro “Atenção necessária” no dashboard**
   - Adiciona um preset/filtro na listagem inicial do dashboard de supervisor/admin.
   - Exibe casos operacionais suspeitos de travamento ou falha.
   - Não fecha casos automaticamente; apenas facilita a triagem humana.
   - Mostra um badge/motivo compacto no card do caso.

## Fora de escopo

- Reprocessamento automático do mesmo caso.
- Nova página dedicada para “casos travados”.
- Deleção física ou soft delete de casos.
- Novo estado FSM como `CANCELLED` ou `ADMIN_CLOSED`.
- Alterar filas operacionais de médico/agendador/NIR além do efeito natural de `CLEANED` sair delas.
- Notificações push/email/SMS.
- Mudanças no pipeline LLM ou nos workers.

## Decisão de produto

O encerramento administrativo **não significa sucesso clínico nem processamento normal**. Ele significa:

> “Este caso foi retirado da operação por intervenção de supervisor/admin e deve ser tratado fora do fluxo atual, geralmente por reapresentação do relatório.”

Por isso, o estado final será `CLEANED`, mas a origem excepcional ficará registrada no evento `CASE_ADMINISTRATIVELY_CLOSED`.

## Critérios de sucesso

- Supervisor/admin veem ação de encerramento administrativo no detalhe do dashboard para casos não `CLEANED`.
- NIR, médico e agendador não veem essa ação.
- POST sem motivo é rejeitado e não altera o caso.
- POST válido move o caso para `CLEANED`.
- Caso encerrado administrativamente sai das filas operacionais existentes.
- Lock ativo ou expirado é limpo no encerramento.
- Evento `CASE_ADMINISTRATIVELY_CLOSED` é criado com payload auditável.
- Dashboard possui filtro/preset `Atenção necessária`.
- O filtro inclui `FAILED`, estados intermediários antigos, waits antigos e locks expirados.
- O filtro não inclui casos `CLEANED`.
- Quality gate do AGENTS.md passa.
