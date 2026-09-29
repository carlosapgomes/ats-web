# Slice 002: Médico — `<select>` com filtro imediato (tipo + busca)

## 1. Objetivo

Na fila do médico (abas Pendentes e Decididos Hoje), trocar a fileira de
radio-botões por um `<select>` que filtra por tipo **imediatamente no `change`**,
sem botão extra, **preservando a composição com a busca** (nome/ocorrência) nos
Pendentes. Contadores, status, aviso sem-resultado e reaplicação após o poll
htmx (20s) continuam funcionando. Nenhuma mudança de backend. Requer o padrão
do slice 001 (scheduler) já aplicado — seguir a mesma abordagem, sem
unificar/refatorar os JS além do necessário.

## 2. Contexto necessário

Ler antes de editar (mínimo suficiente):

- `templates/doctor/queue.html` — inteiro (blocos pending `:14-41` com busca e
  decided `:63-86`; container htmx `#doctor-queue-content`; controles **fora**
  do alvo do swap — manter assim).
- `static/js/doctor_queue_filter.js` — inteiro (foco: `getSelectedType`,
  `scopeLabel`, `emptyCounts`/`updateCounts`, `applyFilter` composto tipo+termo,
  `clearFilter` preservando o tipo, limiar 3 letras, `onTypeChange`,
  `onHtmxAfterSwap`, `init`).
- `slices/slice-001-scheduler-select-filter.md` — o padrão aplicado no
  scheduler (estrutura do `<select>`, contadores no texto da option, listener
  `change`); **replicar a abordagem, não importar código entre apps**.
- `apps/doctor/tests/test_queue_exam_type_filters.py` — cabeçalho + asserts que
  inspecionam o markup do filtro (o contrato atual espera radios; será
  atualizado).
- Restrições: `AGENTS.md` (TDD RED→GREEN→REFACTOR via `uv`; Vanilla JS;
  Bootstrap 5.3; sem vocabulário CSS novo).

## 3. Requisitos verificáveis

- **R1.** Cada aba renderiza **um** `<select class="form-select">` com as mesmas
  options do backend (`procedure_filter_options`): `all` ("Todos") default + uma
  option por chave de seleção; Decididos mantém `none` ("Nenhum autorizado");
  sem radio-botões de filtro restantes.
- **R2.** Trocar a seleção filtra **imediatamente** (`change`, sem botão
  extra): cards com `data-proc-selection` (fallback `data-exam-type`) diferente
  ficam `hidden`; `all` mostra todos.
- **R3.** Busca composta preservada nos Pendentes: digitar/buscar não reseta o
  tipo; trocar o tipo não limpa o termo; Limpar/Escape limpam só o termo;
  limiar "3 letras", normalização e busca numérica intactos.
- **R4.** Contadores, status (`data-doctor-queue-filter-status`, "casos") e
  aviso sem-resultado (`data-doctor-queue-no-results`) comportam-se como hoje;
  contadores compõem o texto das options e são recalculados pelo JS.
- **R5.** Poll htmx preservado: controles fora de `#doctor-queue-content`;
  `htmx:afterSwap` reaplica tipo+termo sem resetar nenhum dos dois.
- **R6.** Sem backend: views/querysets/busca inalterados; nenhum `GET param`
  novo, nenhuma persistência.

## 4. Escopo e expected blast radius

```yaml
expected_files:
  - templates/doctor/queue.html
  - static/js/doctor_queue_filter.js
  - apps/doctor/tests/test_queue_exam_type_filters.py

allowed_incidental_files: []

out_of_scope:
  - fila do scheduler (slice 001), fila do NIR, busca histórica
  - views/querysets/busca server-side, GET param, persistência, paginação
  - unificação dos JS das filas, CSS customizado novo, FSM, migrations, prompts
```

Escalar (parar e pedir decisão) em vez de ampliar se:

- precisar mudar views/queryset/busca para o teste passar;
- precisar tocar scheduler/NIR/histórico ou `static/css/`;
- o universo de options precisar divergir do backend (incluindo `none`);
- qualquer teste fora de `test_queue_exam_type_filters.py` quebrar pelo markup novo.

## 5. Plano de testes do slice

### Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) esperado(s) | Teste/check |
|---|---|---|
| R1 | `templates/doctor/queue.html`, `apps/doctor/tests/test_queue_exam_type_filters.py` | asserts de `<select>` + options (incl. `none` em Decididos) |
| R2 | `static/js/doctor_queue_filter.js` | inspeção: listener `change` no select, sem botão de ação |
| R3 | JS + teste | asserts/inspeção da composição tipo+termo, Limpar/Escape, limiar 3 letras |
| R4 | template + JS | asserts/inspeção de contadores, status, no-results |
| R5 | template + JS | inspeção: controles fora do alvo htmx + `htmx:afterSwap` sem reset |
| R6 | — | `git diff --name-only` restrito aos 3 arquivos |

### RED

- Comando: `uv run pytest apps/doctor/tests/test_queue_exam_type_filters.py -x -q`
- Falha esperada: após atualizar/criar os asserts para `<select>` (options por
  chave incl. `none`, ausência de `btn-check`/`btn-group` de filtro), o teste
  falha contra o markup atual de radios.

### GREEN / verificação local

- `uv run pytest apps/doctor/tests/test_queue_exam_type_filters.py -x -q` → exit 0.
- Regressão próxima: `uv run pytest apps/doctor/tests/test_expanded_catalog_queues.py -q` → exit 0.
- `uv run ruff check` nos arquivos Python tocados → exit 0.
- `git diff --name-only` → só os 3 arquivos previstos.

## 6. Critérios de aceitação

- [ ] R1: um `<select>` por aba com o universo do backend (incl. `none`), sem radios.
- [ ] R2: `change` filtra na hora, sem botão extra.
- [ ] R3: composição tipo+busca intacta (Limpar/Escape/limiar).
- [ ] R4: contadores, status e sem-resultado como hoje.
- [ ] R5: poll htmx reaplica sem resetar tipo nem termo.
- [ ] R6: diff restrito; verificações do slice verdes.

## 7. Contrato de handoff

Worker com contexto fresco implementa só este slice via `/slice-loop`, após o
slice 001 aceito. Não refatorar o scheduler, não atualizar `tasks.md`, não
commitar. Reviewer verifica BEHAVIOR/TESTS/SCOPE/DESIGN com veredito
`OK`/`BLOCK`.
