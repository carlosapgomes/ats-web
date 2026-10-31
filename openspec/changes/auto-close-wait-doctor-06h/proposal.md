# Proposal: Encerramento administrativo automático diário (06:00 America/Bahia) de casos não avaliados pelo médico

**Change ID:** `auto-close-wait-doctor-06h`

**Tipo:** feature operacional (rotina batch + motivo novo + agendamento), 3 slices verticais

**BASE_REF:** `08f94789e9c53a50369ee6fa9a26a05516ffdf08` (`main`, pós `v0.10.0-rc.12`)

## Why

Casos que permanecem em `WAIT_DOCTOR` (aguardando avaliação médica) sem decisão
do médico ficam parados na fila indefinidamente, poluindo a fila médica e as
métricas de "em progresso". A operação quer uma rotina diária às **06:00
America/Bahia** que encerre administrativamente esses casos com um rótulo
explícito de **"não avaliados pelo médico"**, mantendo rastreabilidade total
na auditoria (`CaseEvent`) e na Linha do Tempo.

## What Changes

**Slice 001 — motivo novo + razão visível na Linha do Tempo:**
- Novo `reason_code` em `ADMINISTRATIVE_CLOSURE_REASONS`
  (`apps/cases/services.py`): `not_evaluated_by_doctor` →
  "Não avaliado pelo médico — rotina 06:00".
- `timeline_detail_lines` (`apps/cases/procedure_review.py`) passa a devolver
  linhas de detalhe para `CASE_ADMINISTRATIVELY_CLOSED` (motivo + status
  anterior), em vez de `[]`. Hoje a timeline mostra só o label estático
  "Encerrado administrativamente" (`apps/intake/views.py:520`).

**Slice 002 — batch de encerramento + management command (ator sistema):**
- Novo serviço `close_unevaluated_wait_doctor_cases()` em
  `apps/cases/services.py`: filtra `status=WAIT_DOCTOR`, por caso com
  `select_for_update()` + rechecagem de status; **pula casos com lock válido**
  (reporta `skipped_locked`); encerra os demais via
  `administratively_close_case` com ator sistema (`user=None`,
  `actor_type="system"`, `active_role="system"`).
- Novo management command (ex.: `auto_close_unevaluated_cases`) com
  `--dry-run`, que imprime o relatório `{closed, skipped_locked, skipped_changed}`.
- Adaptação mínima em `administratively_close_case` para aceitar `user=None`
  (o `_record_event` do model já mapeia `None → "system"`, e
  `CaseEvent.actor` é nullable).

**Slice 003 — agendamento diário 06:00 America/Bahia:**
- `Schedule` django-q2 `CRON` (`0 6 * * *`, diário) ou `DAILY` apontando para a
  tarefa batch, com **`cluster` explícito** (dev/prod rodam só `llm` e `pdf`;
  `cluster=NULL` cai no default `ats`, não implantado — precedente documentado
  em `apps/intake/services.py::_schedule_pipeline_recovery`).
- Seed do `Schedule` via migration de dados ou comando `ensure_*` idempotente;
  verificação de fuso (cron avaliado no `TIME_ZONE` do Django).

## Decisões do solicitante (fechadas antes do change)

1. **Escopo do filtro: só `status=WAIT_DOCTOR`.** Casos em `NEW…R2_POST_WIDGET`
   (pipeline automático) não entram.
2. **Lock médico ativo válido → pular + reportar** (não limpar). Só casos sem
   lock (ou com lock expirado) são encerrados.
3. **Ator: sistema** (`user=None`, `actor_type="system"`, `active_role="system"`).
4. **Concorrência: `select_for_update()` + rechecagem** por caso (nunca
   `update()` em massa); caso que saiu de `WAIT_DOCTOR` durante a varredura é
   reportado como `skipped_changed`.
5. **A razão do encerramento aparece na Linha do Tempo** do caso (hoje só
   aparece "Encerrado administrativamente" sem detalhe).

## Non-goals

- Fechar casos em qualquer outro estado; alterar a FSM (as 17 fontes de
  `administratively_close` já incluem `WAIT_DOCTOR` — nenhuma transição nova).
- Mudar o fluxo normal (médico → scheduler → NIR) ou o encerramento manual
  (`dashboard_administrative_close`, continua exigindo humano + motivo livre).
- Notificações ao NIR/médico sobre o fechamento automático (sistêmicas não
  geram `UserNotification` por contrato; reavaliar depois se a operação pedir).
- Cutoff por idade do caso (ex.: só casos criados antes de 06:00) — v1 fecha
  tudo que estiver em `WAIT_DOCTOR` sem lock no instante da execução.
