# Design — Rotina diária de encerramento de casos não avaliados pelo médico

## Context

Ver `proposal.md` e o relatório de viabilidade que originou o change. Baseline
de leitura: `main` em `08f9478`, produção com workers `llm` + `pdf`.

- FSM (`apps/cases/models.py`): `administratively_close` aceita 17 fontes,
  incluindo `WAIT_DOCTOR` → `CLEANED`, sem passar por
  `FINAL_REPLY_POSTED`/`CLEANUP_*`. Nenhuma transição nova é necessária.
- Serviço (`apps/cases/services.py:1118`): `administratively_close_case`
  exige `user` + `active_role` + `reason_code` + `reason_text`; limpa lock e
  intercorrência; registra `CASE_ADMINISTRATIVELY_CLOSED` com payload
  `{previous_status, reason_code, reason_text, active_role, had_lock, …}`.
- Auditoria/apresentação: dashboard separa `administratively_closed` de
  `accepted/denied` (`admin_closed_case_ids`); `dashboard_case_detail` prioriza
  `result_info.type == "administratively_closed"` (badge + `reason_text` +
  `previous_status`); a thread recebe aviso sistêmico
  (`_format_administratively_closed`); a **timeline não mostra detalhe**
  (`timeline_detail_lines` retorna `[]` para o tipo).
- Fila médica (`apps/doctor/views.py`): lease de 60 min (`CASE_LOCK_LEASE_SECONDS_DOCTOR`)
  + heartbeat; `expire_stale_locks_for_statuses` limpa expirados na leitura.
- Scheduler django-q2: `Schedule` com `ONCE/DAILY/CRON` + `cluster`;
  `TIME_ZONE = "America/Bahia"` (UTC-3 fixo, sem DST).

## Goals / Non-Goals

**Goals:** fechar todo `WAIT_DOCTOR` sem lock válido às 06:00 com motivo
distinguível; pular + reportar locks válidos e mudanças de status; ator sistema
auditável; razão visível na timeline; agendamento diário no fuso correto;
idempotência (re-execução fecha só o restante).

**Non-Goals:** ver `proposal.md`. Em particular: sem cutoff de idade na v1,
sem notificação nova, sem tocar no encerramento manual.

## Decisions

### D1 — Reutilizar `administratively_close_case`, não criar transição/evento

O caminho `WAIT_DOCTOR → CLEANED` já existe e já sai das filas operacionais,
já separa métricas e já projeta aviso na thread. Criar transição/evento novos
duplicaria auditoria e quebraria os filtros `admin_closed_case_ids`.
Só o motivo novo distingue a rotina nos relatórios.

Alternativa rejeitada: evento dedicado `CASE_AUTO_CLOSED_UNEVALUATED` —
exigiria atualizar `admin_closed_case_ids`, `EVENT_LABELS`, formatters e
analytics para não perder a contagem; ganho zero frente a `reason_code` novo.

### D2 — `reason_code` novo, `reason_text` padronizado

`not_evaluated_by_doctor` com `reason_text` padrão gerado pelo serviço
(ex.: "Encerrado pela rotina diária 06:00 — sem decisão médica registrada.").
Mantém o contrato "motivo obrigatório, não vazio" sem inventar texto por caso
(risco LGPD de texto livre em batch: nenhum dado clínico no payload).

### D3 — Pular lock válido, nunca limpar no batch

`case.locked_by + locked_until > now` → skip + `skipped_locked` (com
`locked_by_display` para o relatório). Lock expirado segue o comportamento
atual do serviço (limpeza + fechamento), consistente com
`expire_stale_locks_for_statuses`. Justificativa: às 06:00 um médico pode estar
com o caso aberto; limpar seria perda de trabalho silenciosa.

### D4 — Ator sistema via `user=None`

`Case._record_event` já produz `actor_type="system"` quando `user` é None e
`CaseEvent.actor` é nullable. `administratively_close_case` passa a aceitar
`user=None` exigindo, nesse caso, `active_role="system"`. O caminho manual
(`dashboard_administrative_close`, humano + sessão) não muda.

### D5 — Detalhe na timeline via `timeline_detail_lines`

Adicionar `format_admin_closed_lines(event)`: motivo (label do catálogo +
texto) e status anterior, projetados **só do payload** (sem consultar o Case
mutável — mesmo princípio das projeções existentes). Mantém append-only e
funciona para eventos históricos (payloads antigos sem `reason_code` novo
renderizam o que houver).

### D6 — Agendamento: `Schedule` DAILY com cluster explícito + seed idempotente

Primário: `DAILY` com `cluster` = um dos implantados (`llm` sugerido; tarefa é
leve, só ORM). DAILY preserva o horário local (06:00 permanece 06:00 em UTC-3
fixo da Bahia) sem depender de `croniter` — que **não está instalado** (ausente
do `uv.lock`; django-q2 1.10.0 não o depende) e sem o qual `validate_cron` e
`calculate_next_run` levantam `ImportError`. Adicionar a dependência estouraria
o blast radius do slice 003. Alternativa documentada (não primária): CRON
`"0 6 * * *"` — só se `croniter` for adotado deliberadamente depois.
Fallback operacional: cron do SO chamando o management command (decisão
documentada no slice 003, sem replanejar).

Seed via migration de dados com `get_or_create` por `name` (idempotente;
re-runs não duplicam) — **nunca via `tasks.schedule()`/`q_schedule`**, que
levanta `IntegrityError` quando o nome já existe. Atenção: `schedule()`
defaulta `next_run=now`, e o auto-cálculo no save existe só para CRON — o seed
DAILY **deve computar o próximo 06:00 local explicitamente** (`timezone.localtime`
+ `local_day_bounds` ou equivalente). Semântica de falta (`catch_up: False` em
todos os clusters): se o worker do cluster estiver fora do ar às 06:00, a
execução é pulada e `next_run` avança para o dia seguinte, sem back-fill — o
desenho idempotente tolera, mas o doc operacional (R5 do slice 003) deve
declarar isso. Gate de verificação: `Schedule` existe, `cluster` explícito e
não-nulo, `next_run` cai às 06:00 no fuso `America/Bahia` (django-q2 avalia no
`TIME_ZONE` do Django — confirmar no teste/ambiente), worker do cluster consome.

### D7 — Concorrência e idempotência

Loop: `filter(status=WAIT_DOCTOR)` → por caso, **uma única `transaction.atomic()`
externa** envolvendo `select_for_update()` → recheck de status → check de lock →
chamada a `administratively_close_case` (o `atomic` interno do serviço vira
savepoint; o re-lock da mesma linha na mesma transação é seguro). Sem isso, um
caso que mude `WAIT_DOCTOR → DOCTOR_ACCEPTED` entre o recheck e o fechamento
seria encerrado (válido na FSM, que aceita qualquer fonte, mas violando o escopo
"só WAIT_DOCTOR" e o contrato `skipped_changed`) — TOCTOU não capturável por
teste determinístico, por isso fixado na prosa, não só na matriz de testes.
`CLEANED` nunca é fonte (`administratively_close_case` levanta `ValueError`, tratado como
`skipped_changed`). Re-execução no mesmo dia: fecha o que restar (ex.: locks
liberados depois), sem duplicar eventos nos já fechados.
