<!-- markdownlint-disable MD013 -->

# QUICK bugfix: eliminar duplicação do evento CASE_READY_FOR_DOCTOR no fluxo v2

## Status

- [x] Concluído

> Executado via loop parent-controlled (worker + reviewer pi-subagents, contexto
> fresh) em 2026-09-05. Veredito do reviewer: `Merge verdict: OK with notes`
> (0 P0, 0 P1, 1 P2 report-only). Relatório com evidências inline na sessão do
> parent; protocolo de commit/push executado pelo parent conforme o loop.

## Classificação e justificativa

- **Tipo:** QUICK bugfix simples e reversível.
- **Risco:** baixo; remove um registro duplicado idêntico de auditoria. Nenhuma segunda chamada ao LLM, nenhuma mudança de FSM, estado, payload ou ordem dos eventos restantes.
- **Design separado:** dispensado pela exceção QUICK do `AGENTS.md`.
- **Dívida técnica conhecida e aceita desde a v0.5.1**; este slice a liquida.

## Handoff para implementador LLM com contexto zero

Este projeto é um monolito Django SSR. Leia integralmente, antes de editar:

1. `AGENTS.md` e `PROJECT_CONTEXT.md`
2. este arquivo: `tasks/quick-bugfix-duplicate-case-ready-for-doctor-event.md`
3. `apps/cases/models.py` — `Case._record_event` (~linha 605): grava em `self._pending_event`, persistido pelo `save()` seguinte; e a transição `ready_for_doctor` (~linha 477): **já registra** `CASE_READY_FOR_DOCTOR` internamente
4. `apps/pipeline/orchestrator.py` — fim do fluxo v2 de sucesso (~linhas 476-481)
5. `apps/pipeline/tests/test_orchestrator.py` — testes do fluxo v2 (especialmente `TestPipelineGeneratesEvents::test_pipeline_generates_events`, ~linha 311). O teste novo deve copiar exatamente este setup: helpers `_make_case`, `RecordingLlmClient(responses=[_eda_llm1_response(), _llm2_v2(str(case.case_id))])` e chamada `run_pipeline(case.case_id, llm_client=client, llm1_system_prompt="sp1", llm1_user_template="ut1")`
6. Somente leitura, para confirmar que nada mais depende da duplicação: `apps/intake/views.py` (`EVENT_LABELS`, ~linhas 290/356) e `apps/dashboard/views.py` (~linha 1118) — ambos tratam o evento por ocorrência/membership, não por contagem

### Estado técnico atual (bug)

No final do pipeline v2 bem-sucedido, `apps/pipeline/orchestrator.py` executa:

```python
    case.ready_for_doctor()
    case.save()
    case._record_event("CASE_READY_FOR_DOCTOR")
    case.save()
```

- `case.ready_for_doctor()` é a transição FSM que **já** chama `self._record_event("CASE_READY_FOR_DOCTOR", user=user)` internamente (com `user=None` → ator `system`, payload `{}`).
- O primeiro `case.save()` persiste o novo status `WAIT_DOCTOR` **e** esse evento (slot `_pending_event`).
- As duas linhas seguintes registram o **mesmo evento idêntico** uma segunda vez.

Resultado: todo sucesso v2 grava **2** `CaseEvent` idênticos `CASE_READY_FOR_DOCTOR` (duplicados aparecem na timeline do caso). Na falha do pipeline, nenhum é gravado (correto e inalterado).

### Correção esperada

Remover **somente** as duas linhas duplicadas, deixando:

```python
    case.ready_for_doctor()
    case.save()
```

Exatamente **um** evento `CASE_READY_FOR_DOCTOR` (ator `system`, payload `{}`) por sucesso v2, com o mesmo significado de antes.

## Protocolo obrigatório para o implementador

**Se qualquer item obrigatório falhar ou não tiver evidência, o bugfix está INCOMPLETO. Não marque o status acima, não faça commit/push e reporte o bloqueio.**

1. Antes de editar: `git status --short` (árvore deve estar limpa, exceto as deleções pré-existentes não relacionadas em `.pi/skills/`), crie a branch `quick/fix-duplicate-ready-for-doctor-event` a partir do `main` atualizado e registre `BASE_REF=$(git rev-parse HEAD)`.
2. Rode o baseline `uv run pytest` e registre exit code, `passed`, `failed`, `errors`. Baseline vermelho → pare antes de codar.
3. Escreva a matriz `Requisito → arquivo(s) → teste(s)` no relatório.
4. TDD real: RED primeiro (teste novo falhando por constar 2 eventos onde deve haver 1), GREEN mínimo depois. RED por import/fixture não conta.
5. Execute as inspeções e o quality gate completo, interpretando cada resultado no relatório.
6. Compare o pytest final com o baseline: exit code 0, zero failures/errors e `passed_final >= passed_baseline`.
7. Somente após todos os gates: marque este arquivo como concluído, gere o relatório, commit claro, push da branch, responda com `REPORT_PATH` e pare.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
| --- | --- | --- |
| R1 exatamente 1 evento por sucesso v2 | `apps/pipeline/orchestrator.py`, `apps/pipeline/tests/test_orchestrator.py` | novo teste `count() == 1` após pipeline v2 de sucesso |
| R2 sem mudança de contrato | `apps/pipeline/orchestrator.py` | diff remove somente as 2 linhas duplicadas; membership test existente (~linha 311) continua verde |
| R3 sem regressão de falha/auditoria | `apps/pipeline/tests/test_orchestrator.py`, `apps/cases/tests/test_audit.py` | testes existentes de falha (nenhum evento) e auditoria verdes |

## RED

- Comando: `uv run pytest apps/pipeline/tests/test_orchestrator.py -k "ready_for_doctor_single_event" -x`
- Falha esperada: o teste novo afirma `CaseEvent.objects.filter(case=case, event_type="CASE_READY_FOR_DOCTOR").count() == 1` e falha com `2 == 1` violado — prova da duplicação atual. (Nome do teste sugerido; mantenha o sufixo `-k` coerente.)

## GREEN / verificação local

- `uv run pytest apps/pipeline/tests/test_orchestrator.py -k "ready_for_doctor_single_event"` — exit code 0.
- `uv run pytest apps/pipeline/tests/test_orchestrator.py apps/cases/tests/test_audit.py` — exit code 0.
- `uv run ruff check apps/pipeline` e `uv run ruff format --check apps/pipeline` — exit code 0.
- `uv run mypy apps/pipeline` — exit code 0.
- Inspeção: `git diff apps/pipeline/orchestrator.py` deve mostrar **somente** a remoção das duas linhas (`case._record_event("CASE_READY_FOR_DOCTOR")` e o `case.save()` subsequente) e nada mais.

## Quality gate completo

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

## Objetivo vertical

```text
Pipeline v2 conclui com sucesso
→ transição FSM ready_for_doctor persiste status WAIT_DOCTOR + 1 evento CASE_READY_FOR_DOCTOR
→ auditoria/timeline exibem o evento uma única vez
→ fluxos de falha seguem sem o evento
```

## Requisitos funcionais

### R1. Evento único por sucesso v2

Após uma execução v2 bem-sucedida do pipeline, existe **exatamente um** `CaseEvent` com `event_type="CASE_READY_FOR_DOCTOR"` para o caso (ator `system`, payload `{}`).

### R2. Nenhuma outra alteração de comportamento

Status final, ordem dos eventos restantes, payloads, timestamps de FSM, fluxo de falha (nenhum evento) e labels/timeline permanecem inalterados. O diff de produção se limita à remoção das duas linhas duplicadas.

## Out of scope

- Refactor do orquestrador, renomeação de eventos, alteração de payload/ator, consolidar outros eventos, tocar FSM ou migrations, "deduplicar" eventos já gravados historicamente no banco (auditoria é append-only; duplicatas históricas permanecem).
