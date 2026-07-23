<!-- markdownlint-disable MD013 -->

# Tasks: Intercorrência pós-aceitação

## Status

Change concluído e arquivado. Slices 001, 002 e 003 foram implementados, revisados, sincronizados com `origin/main`, validados, commitados e enviados para `origin/change/post-acceptance-intercurrence`.

## Slices verticais

- [x] Slice 001 — Tornar notices operacionais iniciais duráveis até ACK (`slices/slice-001-durable-operational-notices.md`)
- [x] Slice 002 — Generalizar com compatibilidade o fluxo agendado para intercorrência pós-aceitação (`slices/slice-002-scheduled-post-acceptance-intercurrence.md`)
- [x] Slice 003 — Entregar intercorrência pós-aceitação apenas para ciência nos quatro fluxos sem agenda (`slices/slice-003-operational-post-acceptance-intercurrence.md`)

## Justificativa do dimensionamento

- Slice 001 entrega isoladamente a correção da perda de notices na virada do dia, sem depender da feature nova.
- Slice 002 protege e renomeia primeiro o comportamento agendado existente, cria o contrato compatível de contexto/ciclo e fortalece auditoria antes de ampliar elegibilidade.
- Slice 003 usa esse contrato para entregar o novo fluxo sem agenda end-to-end, sem misturar ações de agendamento com ACK de ciência.
- Unir Slices 002 e 003 produziria um slice excessivo envolvendo migration, dois workflows, NIR, CHD, templates, métricas e muitos testes; separá-los por fluxo observável reduz risco sem criar fatias horizontais.

## Definition of Done do change

- [x] Notice operacional inicial sem ACK não expira na virada do dia.
- [x] Badge e fila CHD usam o mesmo critério durável.
- [x] Histórico de ciências confirmadas hoje continua filtrado pelo timestamp do ACK.
- [x] Conceito/UI passa a usar "intercorrência pós-aceitação" (Slice 002).
- [x] Campos legados e eventos históricos permanecem compatíveis (Slice 002).
- [x] Contexto `scheduled`/`operational_notice` e `cycle_id` são persistidos para ciclo ativo (Slice 002).
- [x] Backfill trata eventual intercorrência legada ativa sem perda (Slice 002).
- [x] Fluxo agendado preserva ações, locks e FSM existentes (Slice 002).
- [x] Resposta agendada audita snapshots anterior/novo da agenda (Slice 002).
- [x] Os quatro fluxos sem agenda ficam elegíveis somente quando aceitos e `CLEANED`.
- [x] Fluxo sem agenda permanece `CLEANED` e não altera nenhum campo `appointment_*`.
- [x] CHD recebe pendência de ciência operacional por ciclo e confirma atomicamente.
- [x] ACK histórico do notice inicial ou de ciclo anterior não oculta novo ciclo.
- [x] Notice inicial não duplica card quando há intercorrência operacional ativa.
- [x] Motivos de evasão e aceite por unidade mais próxima existem e são exibidos em português.
- [x] `CaseEvent` preserva eventos legados e registra os novos ciclos genericamente.
- [x] Mensagens sistêmicas da thread reconhecem eventos novos e antigos sem gerar `UserNotification`.
- [x] Encerramento administrativo e métricas não mudam de semântica.
- [x] Specs, `PROJECT_CONTEXT.md` e manual/documentação afetada são atualizados ao final.
- [x] Cada slice executa baseline, RED, GREEN, inspeções e quality gate completo.
- [x] Cada slice gera relatório temporário verificável, commit e push próprios.

## Regra de execução

Implementar somente o próximo slice incompleto. Após relatório, commit e push, parar para revisão do planner antes de iniciar o seguinte.
