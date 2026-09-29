# Slice 001: Scheduler — `<select>` com filtro imediato

## 1. Objetivo

Na fila do scheduler (abas pendente e processada), trocar a fileira de
radio-botões por um `<select>` que filtra os cards **imediatamente no `change`**,
sem botão extra. Contadores, status `aria-live`, aviso sem-resultado e
reaplicação após o poll htmx (20s) continuam funcionando. Nenhuma mudança de
backend.

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `templates/scheduler/queue.html` — inteiro (blocos pending `:11-43` e
  processed `:47-76`; container htmx `#scheduler-queue-content`; os controles
  estão **fora** do alvo do swap — manter assim).
- `static/js/scheduler_queue_filter.js` — inteiro (foco: `resolveElements`,
  `getSelectedType`, `scopeLabel`, `emptyCounts`/`updateCounts`, `applyFilter`,
  `onTypeChange`, `onHtmxAfterSwap`, `init`).
- `templates/scheduler/_queue_content.html` — só os atributos dos cards
  (`data-scheduler-queue-card` / `data-scheduler-processed-card`,
  `data-approved-selection`, fallback `data-exam-type`).
- `apps/scheduler/tests/test_exam_type_filters.py` — cabeçalho + asserts que
  inspecionam o markup do filtro (o contrato atual espera radios; será
  atualizado).
- Restrições: `AGENTS.md` (TDD RED→GREEN→REFACTOR via `uv`; Vanilla JS;
  Bootstrap 5.3 + CSS existente; sem vocabulario CSS novo; lógica de negócio
  fora de templates).

## 3. Requisitos verificáveis

- **R1.** Cada aba (pending/processed) renderiza **um** `<select
  class="form-select">` com as mesmas options do backend (`exam_type_options`
  / `processed_exam_type_options`): `all` ("Todos") default + uma option por
  conjunto do catálogo, valores `option.key` preservados, sem radio-botões de
  filtro restantes.
- **R2.** Trocar a seleção dispara a filtragem **imediatamente** (listener
  `change`, sem botão "Filtrar"/"Aplicar"): cards com
  `data-approved-selection` (fallback `data-exam-type`) diferente do
  selecionado ficam `hidden`; `all` mostra todos.
- **R3.** Contadores por tipo continuam corretos: o texto de cada option reflete
  a contagem (`"Todos (N)"`, `"EDA (M)"`…), recomputada pelo JS após cada swap;
  o label-base de cada tipo é preservado para recomposição (ex.: via atributo
  de dados na option).
- **R4.** Status `aria-live` (`data-scheduler-queue-filter-status`) e aviso
  sem-resultado (`data-scheduler-queue-no-results`) comportam-se como hoje
  (mensagens "Mostrando …", vazio → aviso visível + status limpo).
- **R5.** Poll htmx preservado: selects fora de `#scheduler-queue-content`;
  `htmx:afterSwap` reaplica o filtro com a seleção atual (não reseta para
  `all`).
- **R6.** Sem backend: `apps/scheduler/views.py`, `urls.py`, querysets e
  `?tab=` inalterados; nenhum `GET param` novo, nenhuma persistência.

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - templates/scheduler/queue.html
  - static/js/scheduler_queue_filter.js
  - apps/scheduler/tests/test_exam_type_filters.py

allowed_incidental_files: []

out_of_scope:
  - fila do médico (slice 002)
  - views/urls/querysets do scheduler, busca histórica, fila do NIR
  - filtro server-side, GET param, persistência, paginação
  - CSS customizado novo, FSM, migrations, prompts
```

Escalar (parar e pedir decisão) em vez de ampliar se:

- precisar mudar `views.py`/`urls.py`/queryset para o teste passar;
- precisar tocar `static/css/`, fila do médico/NIR ou busca histórica;
- o universo de options precisar divergir do que o backend entrega;
- qualquer teste fora de `test_exam_type_filters.py` quebrar por causa do markup novo.

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
|---|---|---|
| R1 | `templates/scheduler/queue.html`, `apps/scheduler/tests/test_exam_type_filters.py` | asserts de `<select>` + options (atualizados) |
| R2 | `static/js/scheduler_queue_filter.js` | inspeção estática: listener `change` no select, sem botão de ação |
| R3 | template + JS | asserts de contadores + inspeção do texto das options |
| R4 | template + JS | asserts/inspeção de status + no-results |
| R5 | template + JS | inspeção: controles fora do alvo htmx + handler `htmx:afterSwap` |
| R6 | — | `git diff --name-only` restrito aos 3 arquivos |

### RED

- Comando: `uv run pytest apps/scheduler/tests/test_exam_type_filters.py -x -q`
- Falha esperada: após atualizar/criar os asserts para `<select>` (ex.:
  `assert '<select' in html`, options por `option.key`, ausência de
  `btn-check`/`btn-group` de filtro), o teste falha contra o markup atual de
  radios — provando que o comportamento novo ainda não existe.

### GREEN / verificação local

- `uv run pytest apps/scheduler/tests/test_exam_type_filters.py -x -q` → exit 0.
- Regressão próxima: `uv run pytest apps/scheduler/tests/test_expanded_catalog_scheduler.py -q` → exit 0.
- `uv run ruff check` nos arquivos Python tocados → exit 0 (JS/template: só
  inspeção; sem runner JS no projeto).
- `git diff --name-only` → só os 3 arquivos previstos.

## 6. Critérios de aceitação

- [ ] R1: um `<select>` por aba com o universo do backend, `all` default, sem radios.
- [ ] R2: `change` filtra na hora, sem botão extra.
- [ ] R3: contadores corretos no texto das options, recalculados no cliente.
- [ ] R4: status + sem-resultado como hoje.
- [ ] R5: poll htmx reaplica sem resetar a seleção.
- [ ] R6: diff restrito; verificações do slice verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`. Não tocar
a fila do médico (slice 002), não atualizar `tasks.md`, não commitar. Reviewer
verifica BEHAVIOR/TESTS/SCOPE/DESIGN com veredito `OK`/`BLOCK`.
