<!-- markdownlint-disable MD013 -->

# Tasks: Intercorrência pós-aceitação

## Status

Change aberto na branch `change/post-acceptance-intercurrence`. Implementação ainda não iniciada.

## Slices verticais

- [x] Slice 001 — Tornar notices operacionais iniciais duráveis até ACK (`slices/slice-001-durable-operational-notices.md`)
- [ ] Slice 002 — Generalizar com compatibilidade o fluxo agendado para intercorrência pós-aceitação (`slices/slice-002-scheduled-post-acceptance-intercurrence.md`)
- [ ] Slice 003 — Entregar intercorrência pós-aceitação apenas para ciência nos quatro fluxos sem agenda (`slices/slice-003-operational-post-acceptance-intercurrence.md`)

## Justificativa do dimensionamento

- Slice 001 entrega isoladamente a correção da perda de notices na virada do dia, sem depender da feature nova.
- Slice 002 protege e renomeia primeiro o comportamento agendado existente, cria o contrato compatível de contexto/ciclo e fortalece auditoria antes de ampliar elegibilidade.
- Slice 003 usa esse contrato para entregar o novo fluxo sem agenda end-to-end, sem misturar ações de agendamento com ACK de ciência.
- Unir Slices 002 e 003 produziria um slice excessivo envolvendo migration, dois workflows, NIR, CHD, templates, métricas e muitos testes; separá-los por fluxo observável reduz risco sem criar fatias horizontais.

## Definition of Done do change

- [ ] Notice operacional inicial sem ACK não expira na virada do dia.
- [ ] Badge e fila CHD usam o mesmo critério durável.
- [ ] Histórico de ciências confirmadas hoje continua filtrado pelo timestamp do ACK.
- [ ] Conceito/UI passa a usar “intercorrência pós-aceitação”.
- [ ] Campos legados e eventos históricos permanecem compatíveis.
- [ ] Contexto `scheduled`/`operational_notice` e `cycle_id` são persistidos para ciclo ativo.
- [ ] Backfill trata eventual intercorrência legada ativa sem perda.
- [ ] Fluxo agendado preserva ações, locks e FSM existentes.
- [ ] Resposta agendada audita snapshots anterior/novo da agenda.
- [ ] Os quatro fluxos sem agenda ficam elegíveis somente quando aceitos e `CLEANED`.
- [ ] Fluxo sem agenda permanece `CLEANED` e não altera nenhum campo `appointment_*`.
- [ ] CHD recebe pendência de ciência operacional por ciclo e confirma atomicamente.
- [ ] ACK histórico do notice inicial ou de ciclo anterior não oculta novo ciclo.
- [ ] Notice inicial não duplica card quando há intercorrência operacional ativa.
- [ ] Motivos de evasão e aceite por unidade mais próxima existem e são exibidos em português.
- [ ] `CaseEvent` preserva eventos legados e registra os novos ciclos genericamente.
- [ ] Mensagens sistêmicas da thread reconhecem eventos novos e antigos sem gerar `UserNotification`.
- [ ] Encerramento administrativo e métricas não mudam de semântica.
- [ ] Specs, `PROJECT_CONTEXT.md` e manual/documentação afetada são atualizados ao final.
- [ ] Cada slice executa baseline, RED, GREEN, inspeções e quality gate completo.
- [ ] Cada slice gera relatório temporário verificável, commit e push próprios.

## Regra de execução

Implementar somente o próximo slice incompleto. Após relatório, commit e push, parar para revisão do planner antes de iniciar o seguinte.
