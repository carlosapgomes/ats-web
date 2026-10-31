# Slice 003: Agendamento diário 06:00 America/Bahia

## 1. Objetivo

A rotina do slice 002 passa a executar **todo dia às 06:00 America/Bahia**,
sem intervenção humana, com seed idempotente do agendamento e evidência de
fuso correto.

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- Slice 002 (command + serviço) — é o que será agendado.
- `apps/intake/services.py:648-680` (`_schedule_pipeline_recovery`: precedente
  de `q_schedule` com `Schedule.ONCE`, `name=` determinístico e
  **`cluster="pdf"` explícito + comentário do porquê**).
- `config/settings/base.py` (`Q_CLUSTER` + `ALT_CLUSTERS`, `TIME_ZONE`,
  `SUMMARY_TIMEZONE`) e `docker-compose.dev.yml` / `docker-compose.prod.yml`
  (workers `llm`/`pdf`; default `ats` **não implantado**).
- `config/settings/test.py` — checar se `Schedule`/qcluster precisam de stub
  nos testes (seguir o padrão do teste do recovery, se houver).
- Restrições: `AGENTS.md` (tocar poucos arquivos; sem commit pelo worker).

## 3. Requisitos verificáveis

- **R1.** Existe um `Schedule` django-q2 persistido (seed idempotente via
  migration de dados `get_or_create` por `name`, ou comando `ensure_*` chamado
  no deploy — escolher UM e documentar; **nunca via `tasks.schedule()`/`q_schedule`**,
  que levanta `IntegrityError` se o nome existir) que dispara a tarefa batch
  **diariamente às 06:00 no fuso America/Bahia**. Primário: `DAILY` (documentar
  a escolha). CRON (`0 6 * * *`) é alternativa **não primária**: exige `croniter`,
  que não está instalado (ver D6 do `design.md`) — adotar CRON implicaria nova
  dependência, fora do blast radius.
- **R2.** O `Schedule` declara **`cluster` explícito** implantado (`llm`
  sugerido — tarefa leve, só ORM; `pdf` aceitável). `cluster=NULL` é proibido
  (cairia no `ats` não implantado e nunca executaria).
- **R3.** O seed é idempotente: aplicar 2× não duplica `Schedule`.
- **R4.** Há evidência de fuso: `next_run` do `Schedule` corresponde a 06:00
  America/Bahia (teste ou comando de verificação documentado). Nota: Bahia é
  UTC-3 fixo, sem DST — 06:00 local = 09:00 UTC o ano todo. Atenção: o seed
  DAILY deve computar o próximo 06:00 local explicitamente, pois `schedule()`
  defaulta `next_run=now` (auto-cálculo no save só existe para CRON).
- **R5.** Documentado como a operação verifica a execução diária
  (onde olhar: admin do django-q2 / log do worker / relatório do command) **e
  a semântica de falta**: com `catch_up: False`, worker fora do ar às 06:00 =
  execução pulada sem back-fill (tolerado pelo desenho idempotente).

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/migrations/00XX_seed_auto_close_schedule.py  # OU comando ensure_* (um dos dois)
  - apps/pipeline/tasks.py  # wrapper da tarefa batch, se o Schedule precisar de entrypoint importável
  - apps/cases/tests/test_auto_close_schedule.py  # teste do seed/fuso (ou equivalente)

allowed_incidental_files:
  - docs/…  # nota operacional curta, se o repo tiver local para runbooks (verificar; não criar estrutura nova)

out_of_scope:
  - Lógica do batch (slice 002), FSM, filas, templates/, CSS, prompts, workers/compose (não implantar cluster novo)
```

Escalar em vez de ampliar se: o DAILY não preservar o horário local ou o
`Schedule` exigir `croniter` ausente para a expressão escolhida (oscilar para
**cron do SO chamando o management command** — alternativa já prevista em D6
do `design.md`, documentar a troca sem replanejar); seed exigir
nova infra de deploy; qualquer teste precisar de qcluster real.

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Teste/check |
|---|---|
| R1–R2 | teste: seed cria `Schedule` com func do batch, expressão diária e `cluster` explícito implantado |
| R3 | aplicar seed 2× → 1 `Schedule` |
| R4 | `next_run` em dia conhecido → 06:00 America/Bahia (usar data fixa, ex. fora de qualquer transição DST — Bahia não tem, mas fixar mesmo assim) |
| R5 | leitura: documentar verificação |

### RED

- Teste do seed/fuso contra código ausente — falha antes do GREEN.

### GREEN / verificação local

- `uv run pytest <arquivo-novo> -q` → exit 0.
- `uv run ruff check . && uv run ruff format --check .`; `uv run mypy` nos tocados.
- Checagem manual (fora do pytest, registrada no relatório): criar o `Schedule`
  em ambiente de teste e inspecionar `next_run`.

## 6. Critérios de aceitação

- [ ] R1–R5 verificados.
- [ ] Nenhum worker/compose alterado; diff restrito ao §4; gates verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`. Depende
dos slices 001+002; não reabrir decisões de escopo (D6 prevê fallback para
cron do SO); não atualizar `tasks.md`, não commitar. Reviewer verifica
BEHAVIOR/TESTS/SCOPE/DESIGN com veredito `OK`/`BLOCK`.

## 8. Prompt pronto (implementador com contexto zero)

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/auto-close-wait-doctor-06h/slices/slice-003-daily-schedule.md
(depends on slices 001 and 002).
Follow TDD (RED failing test -> GREEN minimal pass -> REFACTOR).
Keep the diff to the files listed in section 4.
If django-q2 CRON does not honor TIME_ZONE, fall back to documenting OS-cron
invoking the management command (per design.md D6) instead of expanding scope.
Run the section 5 checks and report results.
STOP after this slice and wait for explicit confirmation.
```

## 9. Gates de autoavaliação (antes de declarar pronto)

1. `Schedule.cluster` é `NULL` em algum caminho? (esperado: nunca)
2. O seed roda 2× sem duplicar?
3. `next_run` confere 06:00 America/Bahia numa data fixa conhecida?
4. Foi preciso criar cluster/worker novo? (esperado: não)
