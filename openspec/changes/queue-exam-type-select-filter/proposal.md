# Proposal: Filtro por tipo de exame com `<select>` nas filas (opção A)

**Change ID:** `queue-exam-type-select-filter`

**Tipo:** melhoria de UI/UX client-side, 2 slices, sem backend

**BASE_REF:** `a8d4c75347699639757ea00ddd4cfd5128712ec6` (`main`, pós `v0.10.0-rc.7`)

## Why

As filas do scheduler e do médico filtram por tipo de exame com uma fileira de
radio-botões Bootstrap (`.btn-group`, `flex-wrap: nowrap`, sem override em
`static/css/`). O catálogo cresceu de ~4 para **11 conjuntos selecionáveis**
(10 tipos atômicos + par EDA+Colonoscopia), mais `Todos` (+ `Nenhum autorizado`
nos Decididos do médico):

- scheduler: **12 botões** por aba (`templates/scheduler/queue.html:11-76`);
- médico: **12** (Pendentes) / **13** (Decididos Hoje) (`templates/doctor/queue.html:14-77`).

Labels longos ("Retossigmoidoscopia + Dilatação", "EDA + Gastrostomia (GTT)"…)
estouram a fileira em telas estreitas/intranet. A filtragem é 100% client-side
(`scheduler_queue_filter.js`, `doctor_queue_filter.js`: alternam `card.hidden`,
sem GET param, sem persistência — headers declaram *"no URL, storage, cookie or
session"*), então nada impede trocar o controle por um `<select>` que dispara
no `change`, sem botão extra — padrão já usado na busca histórica do scheduler
(`request.GET["exam_type"]`, `<select>` server-side).

## What Changes

**Slice 001 — scheduler: `<select>` com filtro imediato (pending + processed):**
- `templates/scheduler/queue.html`: os dois blocos `.btn-group` de radios
  (pending `exam_type_options`, processed `processed_exam_type_options`) viram
  um `<select class="form-select">` cada, com as **mesmas options do backend**
  (mesmo universo do catálogo, mesmos `key`/`label`/`count`).
- `static/js/scheduler_queue_filter.js`: lê a seleção do `<select>` e aplica o
  filtro no evento `change`, sem botão "Filtrar". Status `aria-live`,
  `no-results`, contadores e reaplicação pós-`htmx:afterSwap` preservados.
- Sem mudança em views/URLs/queryset: continua client-side, sem `GET param`.

**Slice 002 — médico: `<select>` com filtro imediato (pending + decided):**
- `templates/doctor/queue.html`: os dois blocos de radios
  (`procedure_filter_options`, incluindo `none` em Decididos) viram `<select>`.
- `static/js/doctor_queue_filter.js`: filtro `change` imediato, **composição
  tipo + busca preservada** (termo não limpa o tipo; limpar/Escape não reseta o
  tipo; limiar de 3 letras; status "casos"; `htmx:afterSwap` reaplica ambos).
- Sem mudança em views/queryset/busca.

## Decisões de design (sem `design.md` separado)

- **Client-side primeiro (opção A):** resolve o overflow com o menor diff
  (template + JS por fila). Server-side `?exam_type=` (opção B) fica como
  evolução futura, fora deste change.
- **Sem botão de ação:** o `change` do select filtra imediatamente (requisito
  explícito do solicitante).
- **Vocabulário CSS restrito ao Bootstrap:** só `form-select` (+ classes já
  usadas); nenhum seletor novo em `static/css/` (respeita o anti-pattern de
  vocabulário CSS do `AGENTS.md`).
- **Controles fora do alvo htmx:** selects continuam fora de
  `#scheduler-queue-content` / `#doctor-queue-content`, sobrevivendo ao poll de
  20s como hoje.
- **Contadores dentro do label da option:** `<option>` não comporta `<span
  class="badge">`; os contadores passam a compor o texto da option
  (`"EDA (3)"`), com o label-base preservado para recomputação pelo JS.

## Non-goals

- Filtro server-side / `GET param` / deep-link / paginação (opção B — futuro).
- Persistência (URL/storage/cookie/session).
- Fila do NIR (`apps/intake/*`) e busca histórica (já é `<select>`).
- Mudança em views, URLs, querysets, catálogo (`apps/cases/procedures.py`),
  FSM, migrations, prompts,CSS customizado.
- Unificação dos JS/builders duplicados além do necessário em cada slice.

## Sucesso

- Filas do scheduler e do médico com 1 controle compacto por aba em vez de
  12–13 botões; seleção filtra imediatamente, sem clique extra.
- Status, sem-resultado, contadores, busca do médico e poll htmx intactos.
- Zero regressão: testes focados + suíte completa verdes; `ruff`/`mypy` limpos.
