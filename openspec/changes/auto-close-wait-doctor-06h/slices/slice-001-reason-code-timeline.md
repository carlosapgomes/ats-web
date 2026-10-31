# Slice 001: Motivo "não avaliado" + razão na Linha do Tempo

## 1. Objetivo

Casos encerrados pela futura rotina (e, de forma geral, qualquer encerramento
administrativo) passam a exibir a **razão na Linha do Tempo**, e o catálogo
ganha o motivo dedicado da rotina. Comportamento de fechamento inalterado.

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `apps/cases/services.py:1085-1130` (`ADMINISTRATIVE_CLOSURE_REASONS`) e
  `apps/cases/services.py:1617-1680` (`_format_administratively_closed`).
- `apps/cases/procedure_review.py:275-300` (`timeline_detail_lines`,
  despacho por tipo) — **verificar imports antes de referenciar o catálogo
  de motivos (risco de import circular `services ↔ procedure_review`; se
  houver, definir o label localmente a partir do payload ou importar de
  forma tardia).**
- `apps/intake/views.py:505-530` (`EVENT_LABELS`) — leitura, não alterar
  (label estático permanece).
- `templates/intake/case_detail.html:137-160` (bloco `administratively_closed`
  do Resultado Final) — leitura, para manter vocabulário consistente.
- Restrições: `AGENTS.md` (TDD RED→GREEN→REFACTOR; `uv`; ruff; mypy; sem
  vocabulário CSS novo).

## 3. Requisitos verificáveis

- **R1.** `ADMINISTRATIVE_CLOSURE_REASONS` contém `not_evaluated_by_doctor`
  com label pt-BR contendo "Não avaliado pelo médico" e menção à rotina 06:00.
- **R2.** `timeline_detail_lines(evento CASE_ADMINISTRATIVELY_CLOSED)` retorna
  linhas não vazias contendo o motivo (label ou texto) e o status anterior,
  projetadas **somente do `payload`** (sem query ao Case).
- **R3.** Eventos `CASE_ADMINISTRATIVELY_CLOSED` históricos (payload sem
  `reason_code`, ex. `{}`) não quebram: retornam linhas degradadas ou `[]`,
  nunca levantam.
- **R4.** Nenhuma mudança de FSM, transição, querysets de fila ou métricas
  (diff restrito ao catálogo + projeção de timeline + testes).

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - apps/cases/services.py  # só ADMINISTRATIVE_CLOSURE_REASONS (+ escolhas derivadas, se houver)
  - apps/cases/procedure_review.py  # só format_* novo + despacho em timeline_detail_lines

allowed_incidental_files:
  - apps/cases/tests/test_administrative_closure.py  # asserts novos (ou arquivo novo equivalente)

out_of_scope:
  - models.py (FSM), views.py, templates/, scheduler, workers, migrations, prompts, CSS
```

Escalar em vez de ampliar se: precisar mexer na FSM/evento para exibir o
detalhe; qualquer teste de timeline/dashboard quebrar (investigar antes de
tocar o teste); import circular exigir mover o catálogo de lugar (documentar
e pedir revisão do desenho).

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) | Teste/check |
|---|---|---|
| R1 | `services.py` | assert `not_evaluated_by_doctor` no dict + label pt-BR |
| R2 | `procedure_review.py` | `timeline_detail_lines` com payload `{reason_code, reason_text, previous_status: WAIT_DOCTOR}` contém motivo e status |
| R3 | `procedure_review.py` | payload `{}` / sem chaves → sem exceção |
| R4 | repo | `git diff --name-only` só arquivos previstos; suítes vizinhas verdes |

### RED

- Teste novo que afirma R1+R2 contra o código atual — falha (código ausente;
  `timeline_detail_lines` hoje retorna `[]`).

### GREEN / verificação local

- `uv run pytest apps/cases/tests/test_administrative_closure.py -q` → exit 0
  (criar o arquivo se não existir; checar o nome real da suíte antes).
- Regressão vizinha: suítes que cobrem `timeline_detail_lines` /
  `enrich_timeline_events` (descobrir com grep) → exit 0.
- `uv run ruff check . && uv run ruff format --check .` nos tocados; `uv run mypy` nos tocados.

## 6. Critérios de aceitação

- [ ] R1: código novo presente com label pt-BR.
- [ ] R2: detalhe da timeline contém motivo + status anterior (só payload).
- [ ] R3: payloads históricos/legados não quebram.
- [ ] R4: diff restrito; gates do §5 verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`. Não
criar o batch, o command nem o agendamento (slices 002/003); não atualizar
`tasks.md`, não commitar. Reviewer verifica BEHAVIOR/TESTS/SCOPE/DESIGN com
veredito `OK`/`BLOCK`.

## 8. Prompt pronto (implementador com contexto zero)

```text
Read AGENTS.md and PROJECT_CONTEXT.md first.
Implement ONLY openspec/changes/auto-close-wait-doctor-06h/slices/slice-001-reason-code-timeline.md.
Follow TDD (RED failing test -> GREEN minimal pass -> REFACTOR).
Keep the diff to the files listed in section 4; do not start slices 002/003.
Run the section 5 checks and report results.
STOP after this slice and wait for explicit confirmation.
```

## 9. Gates de autoavaliação (antes de declarar pronto)

1. `timeline_detail_lines` faz alguma query ao banco? (esperado: não)
2. O label novo aparece em `ADMINISTRATIVE_CLOSURE_REASON_CHOICES` do form
   manual sem quebrar o template? (derivado do dict — conferir)
3. Evento antigo com payload `{}` renderiza sem exceção?
