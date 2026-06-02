# Slice 009: Otimização N+1 em lock display das filas

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, monolito Django SSR. A change `shared-work-queue-leases` já foi implementada e fechada no Slice 008, mas o avaliador identificou uma recomendação menor de performance: após a extração de `compute_lock_display()` para `apps/cases/services.py`, algumas filas podem fazer query extra por card bloqueado ao acessar `case.locked_by.display_name`.

Leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/shared-work-queue-leases/proposal.md`
4. `openspec/changes/shared-work-queue-leases/design.md`
5. `openspec/changes/shared-work-queue-leases/slices/slice-008-hardening-quality-closeout.md`
6. Este arquivo

Implemente **somente este slice**. É um mini slice pós-closeout de otimização, não uma mudança funcional. Use TDD sempre que viável: RED → GREEN → REFACTOR.

## Contexto da recomendação

O avaliador reportou:

```text
doctor faz Case.objects.filter(status=WAIT_DOCTOR).order_by(...) sem select_related.
Isso causa N+1 em compute_lock_display quando acessa case.locked_by.display_name.
Não é bloqueante, mas vale registrar como recomendação futura.

Para change futuro de otimização: adicionar .select_related("locked_by") às queries de fila em apps/doctor/views.py
(scheduler já tem; intake não tem mas NIR usa created_by no card).
```

Estado observado após Slice 008:

- `apps/doctor/views.py::_doctor_queue_context` usa `Case.objects.filter(status=WAIT_DOCTOR).order_by(...)` e passa cada case para `compute_lock_display()`.
- `apps/scheduler/views.py` já usa `.select_related("doctor", "locked_by")` no queryset principal de `WAIT_APPT`.
- `apps/intake/views.py::_my_cases_context` usa `.select_related("doctor", "created_by")`; para casos `WAIT_R1_CLEANUP_THUMBS`, também chama `compute_lock_display()`.

## Objetivo do slice

Eliminar N+1 previsível em filas que renderizam `compute_lock_display()` para casos com lock ativo.

Fluxo esperado:

```text
Fila renderiza N casos com locked_by ativo
→ locked_by já vem no queryset via select_related
→ compute_lock_display acessa locked_by.display_name sem query extra por card
```

## Escopo funcional

- Adicionar `.select_related("locked_by")` às queries de fila que passam casos para `compute_lock_display()`.
- No médico, ajustar o queryset de casos pendentes `WAIT_DOCTOR`.
- No NIR, ajustar o queryset operacional para incluir `locked_by`, mantendo `doctor` e `created_by`.
- Revisar scheduler apenas para confirmar se o queryset principal já cobre `locked_by`; se houver outro queryset que também chama `_build_case_card()` e pode renderizar locks, adicionar `locked_by` por consistência sem ampliar escopo.
- Adicionar teste de performance/regressão simples, se viável no padrão do projeto.

## Fora de escopo

- Alterar regra de negócio de locks.
- Alterar templates.
- Alterar FSM.
- Alterar `compute_lock_display()` semanticamente.
- Otimizar todo o dashboard ou todas as queries do projeto.
- Introduzir cache, Redis ou nova dependência.

## Arquivos prováveis

Mantenha o slice muito enxuto:

1. `apps/doctor/views.py`
2. `apps/intake/views.py`
3. talvez `apps/scheduler/views.py` se a revisão encontrar queryset que renderiza lock sem `locked_by`
4. testes em `apps/doctor/tests/` e/ou `apps/intake/tests/`, se houver padrão adequado
5. `openspec/changes/shared-work-queue-leases/tasks.md` ao final

Se tocar outros arquivos, justificar no relatório.

## Plano TDD recomendado

### RED — teste de regressão/performance

Se o projeto tiver padrão de `assertNumQueries` ou `CaptureQueriesContext`, adicionar teste que demonstre ausência de query extra por `locked_by`.

Sugestões:

#### Doctor

1. Criar dois casos `WAIT_DOCTOR` com lock ativo e `locked_by` preenchido.
2. Renderizar a fila médica ou chamar `_doctor_queue_context()` com request autenticado como doctor.
3. Verificar que o número de queries não cresce linearmente por `locked_by`.

Como contagem absoluta pode ser frágil, preferir uma das estratégias:

- usar `assertNumQueries` apenas se já houver padrão estável;
- ou usar `CaptureQueriesContext` e afirmar que não há SELECT adicional para o usuário `locked_by` durante a construção dos cards;
- ou testar diretamente que os objetos do queryset chegam com `locked_by` em cache, se isso ficar simples e legível.

#### Intake/NIR

1. Criar caso `WAIT_R1_CLEANUP_THUMBS` com lock ativo e `locked_by` preenchido.
2. Renderizar/chamar `_my_cases_context()`.
3. Verificar que `locked_by` não dispara query extra por card.

Se os testes de query ficarem frágeis demais para o padrão atual, registre no relatório e faça teste funcional mínimo garantindo que a fila continua renderizando lock display corretamente. Não crie teste complexo ou instável só para cumprir métrica.

### GREEN — implementação mínima

#### Doctor

Alterar o queryset principal de pendentes de:

```python
pending_cases = Case.objects.filter(status=CaseStatus.WAIT_DOCTOR).order_by("created_at")
```

para algo equivalente a:

```python
pending_cases = (
    Case.objects.filter(status=CaseStatus.WAIT_DOCTOR)
    .select_related("locked_by")
    .order_by("created_at")
)
```

#### Intake/NIR

Alterar o queryset operacional de:

```python
qs = Case.objects.exclude(status="CLEANED").select_related("doctor", "created_by").order_by("-created_at")
```

para algo equivalente a:

```python
qs = (
    Case.objects.exclude(status=CaseStatus.CLEANED)
    .select_related("doctor", "created_by", "locked_by")
    .order_by("-created_at")
)
```

Preferir `CaseStatus.CLEANED` em vez de string literal se já estiver no arquivo e não causar mudança ampla.

#### Scheduler

Confirmar se `WAIT_APPT` já possui:

```python
.select_related("doctor", "locked_by")
```

Se `_build_case_card()` for chamado para outros querysets que podem ter lock ativo e isso for relevante, adicionar `locked_by` também. Se não for relevante, não mexer.

### REFACTOR

- Não criar helper genérico para querysets só por causa de dois `select_related`.
- Manter views simples.
- Não alterar `compute_lock_display()` sem necessidade.

## Critérios de aceitação

- [ ] Fila médica carrega `locked_by` com `select_related` nos casos pendentes.
- [ ] Fila NIR operacional carrega `locked_by` com `select_related` quando pode renderizar lock display.
- [ ] Scheduler revisado; se já estiver correto, isso é registrado no relatório.
- [ ] Lock display continua funcionando visual/funcionalmente.
- [ ] Nenhuma regra de negócio foi alterada.
- [ ] Teste de regressão/performance adicionado quando viável, ou justificativa registrada se teste de query for frágil.
- [ ] Quality gate relevante passa.
- [ ] `tasks.md` atualizado ao final.

## Gates de autoavaliação

Responder no relatório:

1. Quais querysets chamam `compute_lock_display()`?
2. Todos os querysets relevantes usam `select_related("locked_by")`?
3. Algum teste prova ou caracteriza a otimização?
4. Alguma regra de negócio, FSM ou template mudou? Não deveria.
5. O scheduler já estava correto? Se houve alteração, por quê?
6. Quantos arquivos foram tocados e por quê?

## Comandos de validação mínimos

```bash
uv run pytest apps/doctor/tests apps/intake/tests apps/scheduler/tests -q
uv run ruff check apps/doctor apps/intake apps/scheduler
uv run ruff format --check apps/doctor apps/intake apps/scheduler
uv run mypy apps/doctor apps/intake apps/scheduler
```

Se possível, rode o quality gate completo:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Relatório final obrigatório

Criar relatório temporário em:

```text
/tmp/ats-web-slice-009-lock-display-query-optimization-report.md
```

O relatório deve conter:

- resumo da otimização;
- arquivos alterados;
- snippets antes/depois dos querysets;
- teste adicionado ou justificativa para não criar teste de query frágil;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- commit hash e push, quando realizados.

Resposta final obrigatória:

```text
REPORT_PATH=/tmp/ats-web-slice-009-lock-display-query-optimization-report.md
```

Depois pare.

## Prompt pronto para implementador

```text
Read AGENTS.md, PROJECT_CONTEXT.md and openspec/changes/shared-work-queue-leases/slices/slice-009-lock-display-query-optimization.md.
Implement ONLY Slice 009.
This is a post-closeout mini optimization: eliminate N+1 queries from compute_lock_display() by adding select_related("locked_by") to queue querysets that render lock display, especially doctor WAIT_DOCTOR and NIR operational cases. Review scheduler and only change it if needed. Do not change business rules, FSM, templates or lock semantics. Add a query/performance regression test if viable without fragility; otherwise add/keep functional tests and justify.
Run validations, update tasks.md, create /tmp/ats-web-slice-009-lock-display-query-optimization-report.md with before/after snippets, commit and push, then reply REPORT_PATH and stop.
```
