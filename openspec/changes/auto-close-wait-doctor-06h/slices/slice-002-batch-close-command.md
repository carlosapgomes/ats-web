# Slice 002: Batch de encerramento + management command (ator sistema)

## 1. Objetivo

Rotina executável (via management command, com `--dry-run`) que encerra todos
os casos em `WAIT_DOCTOR` sem lock válido, com ator sistema, motivo
`not_evaluated_by_doctor`, pulando + reportando locks válidos e mudanças de
status. Sem agendamento (slice 003).

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `apps/cases/services.py:1118-1230` (`administratively_close_case` na
  íntegra) — adaptar para `user=None` + `active_role="system"`.
- `apps/cases/models.py:610-640` (transição `administratively_close`, fontes).
- `apps/cases/services.py:1745-1770` (`local_day_bounds` — NÃO usar filtro de
  data na v1, só referência de fuso se precisar logar).
- `apps/cases/management/commands/check_specialized_procedure_downgrade.py`
  — padrão de command existente a replicar (estrutura/estilo).
- Slice 001 deste change (motivo `not_evaluated_by_doctor` + `reason_text`
  padrão) — depende dele; se ainda não mergeado, definir o `reason_text`
  padrão aqui e reconciliar.
- Restrições: `AGENTS.md` (TDD; transação por caso; `uv`; ruff; mypy).

## 3. Requisitos verificáveis

- **R1.** Serviço novo (ex.: `close_unevaluated_wait_doctor_cases(*, dry_run=False)`)
  em `apps/cases/services.py`: filtra `status=WAIT_DOCTOR`; por caso, sob **uma
  única `transaction.atomic()` externa** com `select_for_update()`, recheca o
  status e checa o lock **antes** de chamar `administratively_close_case`
  (o `atomic` interno do serviço vira savepoint) com
  `reason_code="not_evaluated_by_doctor"`, `reason_text` padrão não vazio,
  `user=None`, `active_role="system"`. O recheck e o fechamento NA MESMA
  transação eliminam o TOCTOU `WAIT_DOCTOR → DOCTOR_ACCEPTED` (ver D7).
- **R2.** Caso com lock válido (`locked_by` + `locked_until > now`) é **pulado**,
  sem limpar o lock, e contado em `skipped_locked` (com identificação para o
  relatório). Lock expirado segue o comportamento atual (limpeza + fechamento).
- **R3.** Caso que saiu de `WAIT_DOCTOR` entre a listagem e o lock de linha é
  contado em `skipped_changed`, sem erro e sem evento. `CLEANED` nunca é tocado.
- **R4.** `CaseEvent` gerado com `actor=None`, `actor_type="system"`,
  `event_type="CASE_ADMINISTRATIVELY_CLOSED"`, payload com
  `previous_status="WAIT_DOCTOR"`, `reason_code` novo e `active_role="system"`.
- **R5.** Management command (ex.: `auto_close_unevaluated_cases`) com
  `--dry-run` (não escreve; imprime o que faria) e saída de relatório
  `{closed, skipped_locked, skipped_changed}`.
- **R6.** Re-execução idempotente: segunda rodada fecha só o restante, sem
  duplicar eventos nos já encerrados.

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/services.py  # serviço batch + adaptação user=None em administratively_close_case
  - apps/cases/management/commands/auto_close_unevaluated_cases.py  # nome sujeito a convenção do repo
  - apps/cases/tests/test_auto_close_unevaluated.py  # ou suíte equivalente

allowed_incidental_files:
  - apps/dashboard/tests/test_dashboard.py  # só se a adaptação user=None exigir ajuste de assert existente

out_of_scope:
  - models.py (FSM — sem transição nova), Schedule/agendamento, templates/, CSS, prompts, migrations de schema
```

Escalar em vez de ampliar se: `user=None` exigir mudar assinatura usada pelo
caminho manual (preferir parâmetro opcional/compatível); qualquer fila ou
métrica mudar de contagem (investigar antes de tocar testes); surgir
necessidade de cutoff por idade (explicitamente v2 — não incluir).

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Teste |
|---|---|
| R1 (fecha WAIT_DOCTOR sem lock) | caso em `WAIT_DOCTOR` → após run, `CLEANED` + evento system com payload esperado |
| R1 (dry-run) | `--dry-run` não altera status nem cria evento |
| R2 (lock válido pula) | caso com lock de outro usuário e `locked_until` futuro → status mantido, lock intacto, `skipped_locked=1` |
| R2 (lock expirado fecha) | `locked_until` passado → fechado, lock limpo |
| R3 (mudou de status) | caso decidido (ex.: `doctor_decide`) entre setup e run → `skipped_changed`, sem exceção |
| R4 (ator sistema) | `actor is None`, `actor_type == "system"` |
| R6 (idempotência) | rodar 2× → 2ª rodada `closed=0`, nenhum evento novo |

### RED

- Testes novos contra o serviço/command inexistentes — falham (import error /
  `AttributeError`) antes do GREEN.

### GREEN / verificação local

- `uv run pytest <arquivo-novo> -q` → exit 0.
- Regressão: `apps/cases/tests/test_administrative_closure.py` (se existir) +
  suítes de `administratively_close_case` no dashboard → exit 0.
- `uv run ruff check . && uv run ruff format --check .`; `uv run mypy` nos tocados.

## 6. Critérios de aceitação

- [ ] R1–R6 verificados por testes (matriz acima).
- [ ] `--dry-run` comprovadamente sem escrita (status + contagem de eventos antes/depois).
- [ ] Diff restrito ao §4; gates verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`. Depende
do slice 001 (motivo + timeline); não criar agendamento (slice 003); não
atualizar `tasks.md`, não commitar. Reviewer verifica
BEHAVIOR/TESTS/SCOPE/DESIGN com veredito `OK`/`BLOCK`.

## 8. Prompt pronto (implementador com contexto zero)

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/auto-close-wait-doctor-06h/slices/slice-002-batch-close-command.md
(depends on slice 001 for the reason_code; reconcile if slice 001 is not merged yet).
Follow TDD (RED failing test -> GREEN minimal pass -> REFACTOR).
Keep the diff to the files listed in section 4; do not create any scheduling.
Run the section 5 checks and report results.
STOP after this slice and wait for explicit confirmation.
```

## 9. Gates de autoavaliação (antes de declarar pronto)

1. Algum caminho do batch usa `update()` em massa ou atribui `status`
   diretamente? (esperado: não — só transição FSM via serviço existente)
1b. O recheck de status e a chamada ao serviço estão na MESMA transação
   externa por caso? (esperado: sim — ver D7 do `design.md`)
2. O caminho manual (`dashboard_administrative_close`) continua exigindo
   humano + motivo livre? (testes manuais existentes verdes)
3. `reason_text` padrão contém dado clínico ou identificador? (esperado: não —
   texto fixo operacional)
4. Segunda execução gera zero eventos novos?
