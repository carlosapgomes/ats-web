# Slice 002: Fila do agendador priorizada

## Handoff para implementador LLM com contexto zero

Você está no projeto `/projects/dev/ats-web`, um monolito Django 5.2 SSR com templates Bootstrap, sem API REST e sem SPA.

Antes de codar, leia obrigatoriamente:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `openspec/changes/prioritize-queues-by-regulation-days/proposal.md`
4. `openspec/changes/prioritize-queues-by-regulation-days/design.md`
5. `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`
6. `openspec/changes/prioritize-queues-by-regulation-days/slices/slice-001-extracao-persistencia-fila-medica.md`
7. Este arquivo de slice

Pré-condição: Slice 001 concluído, com `Case.regulation_days_on_screen` persistido e fila médica já priorizada.

Implemente **somente este slice**. Não altere parser, migration, extração de PDF ou fila médica, exceto ajuste mínimo se testes existentes quebrarem. Use TDD: RED → GREEN → REFACTOR. No refactor, aplique clean code, DRY e YAGNI.

## Objetivo do slice

Entregar a fatia vertical para o agendador:

```text
Case WAIT_APPT com Dias em tela persistido -> fila WAIT_APPT ordena por maior número -> agendador vê Dias em tela no card -> vinda imediata continua no topo absoluto
```

## Escopo funcional

- Ordenar apenas os casos `WAIT_APPT` da fila do agendador por maior `regulation_days_on_screen`.
- Casos `WAIT_APPT` sem dado (`NULL`) devem ficar no final.
- Empate deve usar `created_at` mais antigo primeiro.
- Exibir `Dias em tela: N` nos cards `WAIT_APPT` quando disponível.
- Garantir que a seção de vinda imediata continua aparecendo antes dos cards `WAIT_APPT`.

## Fora de escopo neste slice

- Parser de PDF.
- Campo/migration/backfill.
- Fila médica.
- Ordenar cards de vinda imediata por `Dias em tela`.
- Somar dias desde upload.
- Criar score composto.
- Alterar FSM, locks, decisão médica ou fluxo de agendamento.
- Alterar cards processados hoje.

## Arquivos prováveis

Mantenha o slice enxuto. Arquivos previstos:

1. `apps/scheduler/views.py`
2. `templates/scheduler/_queue_content.html`
3. testes em `apps/scheduler/tests/`
4. `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`

Se tocar outros arquivos, justifique no relatório final.

## Estado técnico relevante

- `apps/scheduler/views.py::_scheduler_queue_context` monta:
  - `pending_cards` para casos `WAIT_APPT`;
  - `immediate_notice_cards` para vinda imediata.
- `pending_cases` hoje usa `.order_by("created_at")`.
- `_build_case_card` centraliza dados dos cards do agendador.
- `templates/scheduler/_queue_content.html` renderiza primeiro `immediate_notice_cases` e depois `pending_cases` quando `active_tab == "pending"`.
- A regra de negócio confirmada: vinda imediata tem prioridade absoluta e deve continuar no topo. A ordenação por `Dias em tela` vale só para `WAIT_APPT`.

## Plano TDD obrigatório

### RED — testes primeiro

Crie/atualize testes antes da implementação em `apps/scheduler/tests/`.

#### 1. Ordenação `WAIT_APPT` por maior `Dias em tela`

- criar usuário com role `scheduler` logado;
- criar três casos `WAIT_APPT`:
  - A com `regulation_days_on_screen=2`;
  - B com `regulation_days_on_screen=10`;
  - C com `regulation_days_on_screen=None`;
- acessar `scheduler:queue`;
- assert que B aparece antes de A, e A antes de C.

#### 2. Exibição no card `WAIT_APPT`

No mesmo teste ou em teste separado:

- assert que aparece `Dias em tela: 10` e `Dias em tela: 2`;
- assert que não aparece `Dias em tela: None`;
- assert que caso sem dado não renderiza badge vazia.

#### 3. Desempate por `created_at`

- criar dois casos `WAIT_APPT` com mesmo `regulation_days_on_screen`, mas `created_at` diferente;
- assert que o mais antigo aparece antes.

Se o projeto tiver dificuldade com `auto_now_add`, use `Case.objects.filter(...).update(created_at=...)` após criação.

#### 4. Vinda imediata permanece no topo

- criar um caso de vinda imediata que apareça em `immediate_notice_cases` conforme padrão existente dos testes;
- criar um caso `WAIT_APPT` com `regulation_days_on_screen` muito alto, por exemplo `999`;
- acessar `scheduler:queue`;
- assert que o bloco/texto `Vinda imediata autorizada` aparece antes do card `WAIT_APPT`.

Não é necessário ordenar as vindas imediatas por `Dias em tela`.

### GREEN — implementação mínima

#### 1. `apps/scheduler/views.py`

Importar `F`:

```python
from django.db.models import F, QuerySet
```

ou ajustar import existente de `QuerySet`.

Alterar somente a query de `pending_cases`:

```python
pending_cases: QuerySet[Case] = (
    Case.objects.filter(status=CaseStatus.WAIT_APPT)
    .select_related("doctor", "locked_by")
    .order_by(F("regulation_days_on_screen").desc(nulls_last=True), "created_at")
)
```

Em `_build_case_card`, adicionar:

```python
"regulation_days_on_screen": case.regulation_days_on_screen,
```

Não altere `immediate_notice_qs`.

#### 2. `templates/scheduler/_queue_content.html`

Nos cards de `pending_cases`/`WAIT_APPT`, adicionar badge curta quando o dado existir:

```django
{% if c.regulation_days_on_screen is not None %}
<span class="badge bg-warning text-dark mb-2">Dias em tela: {{ c.regulation_days_on_screen }}</span>
{% endif %}
```

Local sugerido: perto do nome/metadados do paciente e das badges existentes (`Obs. médica`, intercorrência). Não exibir nos cards de vinda imediata neste slice.

## Critérios de aceitação do slice

- [ ] Fila `WAIT_APPT` do agendador ordena por maior `regulation_days_on_screen`.
- [ ] Casos `WAIT_APPT` com `NULL` ficam após casos com número.
- [ ] Empate usa `created_at` mais antigo primeiro.
- [ ] Card `WAIT_APPT` exibe `Dias em tela: N` quando disponível.
- [ ] Card `WAIT_APPT` sem dado não mostra badge vazia nem `None`.
- [ ] Vinda imediata continua aparecendo antes da lista `WAIT_APPT`.
- [ ] Query/lista de vinda imediata não foi reordenada por `Dias em tela`.
- [ ] Nenhuma FSM/transição/lock foi alterado.
- [ ] Testes do slice passam.
- [ ] `tasks.md` marca o change como concluído se todos os itens estiverem satisfeitos.

## Gates de autoavaliação

Antes de finalizar, responda no relatório:

1. A ordenação alterada afeta somente `WAIT_APPT`?
2. `immediate_notice_cases` permaneceu no topo e sem ordenação por `Dias em tela`?
3. A ordenação usa `NULLS LAST`?
4. O card diferencia `Dias em tela` de `Aguardando há X min`?
5. Casos sem dado não exibem UI vazia?
6. Quantos arquivos foram tocados e por quê?
7. Alguma alteração fora do scheduler foi necessária? Se sim, justifique.

## Comandos de validação

Rode no mínimo:

```bash
uv run pytest apps/scheduler/tests -q
uv run ruff check apps/scheduler
uv run ruff format --check apps/scheduler
uv run mypy apps/scheduler
```

Como este é o último slice do change, rode preferencialmente o quality gate completo do `AGENTS.md`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Se algum comando não puder ser executado, registre motivo e saída relevante no relatório.

## Atualização de artefatos

Ao concluir:

- marcar este slice como concluído em `openspec/changes/prioritize-queues-by-regulation-days/tasks.md`;
- marcar todos os itens de DoD satisfeitos;
- se o quality gate completo passar, registrar no relatório.

## Relatório final obrigatório

Crie relatório temporário em:

```text
/tmp/ats-web-slice-002-regulation-days-scheduler-report.md
```

O relatório deve conter:

- resumo do que foi implementado;
- lista de arquivos alterados;
- snippets antes/depois dos pontos principais;
- testes adicionados/alterados;
- comandos executados e resultados;
- riscos/observações;
- confirmação de atualização de `tasks.md`;
- status final do DoD do change;
- commit hash e push, quando realizados.

Na resposta final, informe exatamente:

```text
REPORT_PATH=/tmp/ats-web-slice-002-regulation-days-scheduler-report.md
```

Depois pare e peça confirmação explícita antes de qualquer novo trabalho.

## Prompt pronto para o implementador

```text
Read AGENTS.md and PROJECT_CONTEXT.md first. Then read openspec/changes/prioritize-queues-by-regulation-days/proposal.md, design.md, tasks.md, slice-001, and slices/slice-002-fila-agendador-priorizada.md.

Implement ONLY Slice 002. Use TDD: write failing scheduler tests first for WAIT_APPT ordering by regulation_days_on_screen DESC NULLS LAST, card display, created_at tie-break, and immediate notices remaining above WAIT_APPT. Then implement the minimal code to pass.

Do not touch parser, migration, PDF extraction, doctor queue, FSM, locks, or immediate notice ordering unless strictly necessary and justified. Add regulation_days_on_screen to scheduler cards, order only pending WAIT_APPT by F('regulation_days_on_screen').desc(nulls_last=True), 'created_at', and display a short Dias em tela badge only for WAIT_APPT cards with a value.

Run the validation commands from the slice and preferably the full AGENTS.md quality gate. Update tasks.md. Generate /tmp/ats-web-slice-002-regulation-days-scheduler-report.md with summary, files, before/after snippets, tests, commands/results, risks, tasks update, final DoD status, commit hash and push status. Reply with REPORT_PATH only plus a short stop/confirmation request.
```
