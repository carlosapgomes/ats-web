<!-- markdownlint-disable MD013 -->

# QUICK fix de UI: ordem inversa das opções de fluxo de admissão no mobile

## Status

- [x] Concluído

> Executado em 2026-11-24 na branch `carlosapgomes/fix-admission-flow-order`
> (`BASE_REF=61918827f9dcbb7ca29ec0bceebd766afce66efb`). Baseline `pytest` 4804
> passed → final 4806 passed (+2 parametrizados), ruff/format/mypy ok, Node 23/23.
> Relatório com evidências e snippets antes/depois em
> `.reports/slice-admission-flow-mobile-order.md`.

## Classificação e justificativa

- **Tipo:** QUICK fix de UX, simples e reversível (apresentação: 1 atributo no
  template + script progressivo). Reverter = remover o atributo e a tag `<script>`.
- **Risco:** baixo; um único controle (`#admission-flow`) da decisão médica, sem
  backend, migration, FSM, validação ou auditoria. O valor submetido é o mesmo
  código (`scheduled`, `immediate`, …) — só a posição no picker muda.
- **Design separado:** dispensado pela exceção QUICK do `AGENTS.md`.

### Problema

No formulário de decisão médica (`templates/doctor/decision.html`) as opções de
"Fluxo de Admissão" estão em ordem "mais comum primeiro" (`Agendamento`,
`Vinda Imediata`, …) porque no **desktop** o dropdown nativo abre logo abaixo do
cursor e a primeira opção fica a um pixel do mouse.

No **celular** isso inverte: o picker nativo é uma lista vertical centralizada
(Android Chrome) ou um menu ancorado no select (iOS 16+, Safari e Chrome, que
usam WebKit). Verificado em aparelho real (iPhone 13, Safari e Chrome, e
Android): a lista segue a ordem do DOM com `Agendamento` no topo; com a página
rolada até o fim — a posição em que o médico toca o select — o menu do iOS abre
**acima** do select, deixando a primeira opção no ponto mais distante do dedo.
(Rolagem máxima é o ponto mais alto que o select alcança nesta página: o menu
abre acima em 100% das posições de rolagem nesse aparelho.)

### Decisão aprovada pelo usuário

Inverter a ordem das opções reais **somente em tela mobile** (< 768 px, mesmo
corte de `md`/`d-md-none`), mantendo o placeholder "Selecione..." em primeiro.
Desktop e/ou sem JavaScript: ordem atual (SSR intocado).

Ordem esperada no mobile: `Selecione...` → `Compartilhar com EM pediátrica — com
agendamento` → `Vinda para enfermaria (para retaguarda em UTI)` → `Vinda prévia
para UTI` → `Vinda Imediata` → **`Agendamento`** (adjacente ao select/dedo). As
opções raras ficam no topo, longe do polegar — onde um toque errado é menos
provável (no ramo por procedimento não há modal de confirmação antes do submit).

## Handoff para implementador LLM com contexto zero

Monolito Django SSR, templates Django, Bootstrap 5.3, JS vanilla em `static/js/`
(sem framework, sem bundler, sem `package.json`). Leia integralmente antes de
editar:

1. `AGENTS.md` e `PROJECT_CONTEXT.md`
2. este arquivo
3. `templates/doctor/decision.html` — os dois `<select id="admission-flow">`
   (ramo `per_procedure`, ~linha 456; ramo legado, ~linha 519) e o
   `{% block extra_js %}` no fim do arquivo (hoje carrega `procedure_combobox.js`
   OU `decision.js` conforme o ramo, depois `work_lock.js`)
4. `static/js/procedure_combobox.js` e `static/js/tests/procedure_combobox.test.js`
   — padrão do projeto para script progressivo (IIFE, API em `window`, auto-init
   por `DOMContentLoaded`) e para teste Node (`node --test`, mini-DOM sem jsdom)
5. `apps/doctor/tests/test_expanded_procedure_decision.py` (`_make_case`,
   `_login`) e `apps/doctor/tests/test_pediatric_em_scheduling.py`
   (`_make_case` legado) — fixtures de caso 2.0/4.0 e legado 1.1 e login médico
6. `apps/cases/admission.py` — `ADMISSION_FLOW_CHOICES` (ordem canônica; só
   valida, não renderiza)
7. `static/js/sw.js` — somente leitura: o fetch handler é **network-first para
   `/static/`** (linhas 46–70); por isso este slice NÃO altera o service worker

### Estado técnico atual

```django
<select class="form-select{% if form.admission_flow.errors %} is-invalid{% endif %}" id="admission-flow" name="admission_flow">
  <option value="" selected disabled>Selecione...</option>
  <option value="scheduled"{% if form.admission_flow.value == "scheduled" %} selected{% endif %}>Agendamento</option>
  <option value="immediate"{% if form.admission_flow.value == "immediate" %} selected{% endif %}>Vinda Imediata</option>
  <option value="pre_icu"{% if form.admission_flow.value == "pre_icu" %} selected{% endif %}>Vinda prévia para UTI</option>
  <option value="ward_icu_backup"{% if form.admission_flow.value == "ward_icu_backup" %} selected{% endif %}>Vinda para enfermaria (para retaguarda em UTI)</option>
  <option value="pediatric_appt"{% if form.admission_flow.value == "pediatric_appt" %} selected{% endif %}>Compartilhar com EM pediátrica — com agendamento</option>
</select>
```

Bloco duplicado nos dois ramos do template. Nenhum JS toca esse select no ramo
`per_procedure`; no legado, `decision.js` lê `admissionFlow.value` e
`options[selectedIndex].text` (modal de confirmação) — ambos continuam corretos
com os nós reordenados. Não há detecção de mobile no servidor; o padrão do
projeto para mobile × desktop é o breakpoint `md` (768px).

### Correção esperada

1. **Template** — adicionar `data-mobile-reverse-options` aos dois selects e
   carregar `static/js/mobile_select_order.js` nos dois ramos (tag fora do
   `{% if per_procedure %}`).
2. **Script novo** `static/js/mobile_select_order.js` — IIFE vanilla, sem
   dependências, expondo `window.MobileSelectOrder = { MOBILE_QUERY, enhance,
   enhanceAll }` e auto-init igual ao `procedure_combobox.js`:
   - `MOBILE_QUERY = '(max-width: 767.98px)'`;
   - `enhance(select, mql)`: captura uma vez a ordem original dos `<option>`;
     a primeira opção (placeholder) fica em primeiro; quando `mql.matches` é
     `true` move as demais em ordem inversa, quando é `false` restaura a
     original; escuta `change` do `mql` (rotação/redimensionamento). Move os
     nós com `appendChild` (não recria) para preservar a opção `selected`;
     idempotente (sempre deriva a ordem da original capturada);
   - `enhanceAll(document)`: aplica somente em `select[data-mobile-reverse-options]`;
     no-op sem `document.querySelectorAll` ou sem `window.matchMedia`.
3. **Testes** — guarda Django da ordem SSR (os dois ramos) + teste Node do
   script. Ver RED/GREEN abaixo.

## Protocolo obrigatório para o implementador

**Se qualquer item obrigatório falhar ou não tiver evidência, o fix está
INCOMPLETO. Não marque o status acima, não faça commit/push e reporte o bloqueio.**

1. Antes de editar: `git status --short` limpo; branch
   `carlosapgomes/fix-admission-flow-order`; registre `BASE_REF`.
2. Baseline `uv run pytest` (banco de teste:
   `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d`).
   Baseline vermelho → pare.
3. TDD real: RED primeiro (Django: asserção falha porque o template não tem o
   atributo/tag; Node: falha porque o script não existe), GREEN mínimo depois,
   REFACTOR limpo.
4. Quality gate completo e `node --test static/js/tests/`.
5. `passed_final >= passed_baseline`, exit 0, zero failures.
6. Somente após os gates: marcar concluído, gerar o relatório em
   `.reports/slice-admission-flow-mobile-order.md`, commit rastreável, push,
   responder com `REPORT_PATH` e parar.

## Matriz requisito → arquivo → teste/check

| Requisito | Arquivo(s) | Teste/check |
| --- | --- | --- |
| R1 ordem SSR (desktop) inalterada nos dois ramos | `templates/doctor/decision.html` | `apps/doctor/tests/test_admission_flow_order.py`: valores do select == `[c for c, _ in ADMISSION_FLOW_CHOICES]` (legado 1.1 e 2.0/4.0) |
| R2 select marcado para inversão no mobile | idem | idem: `data-mobile-reverse-options` no select (os dois ramos) |
| R3 script carregado nos dois ramos | idem | idem: `js/mobile_select_order.js` no HTML (os dois ramos) |
| R4 inversão/restauração idempotente, placeholder em 1º, seleção preservada, seletor restrito, no-op sem `matchMedia`, auto-init | `static/js/mobile_select_order.js` | `static/js/tests/mobile_select_order.test.js` (`node --test`) |
| R5 sem expansão | — | `git diff --stat` limitado aos 4 arquivos previstos |

## RED

- Django: `uv run pytest apps/doctor/tests/test_admission_flow_order.py -x`
  — falha: `data-mobile-reverse-options` ausente no select (R2) e tag do script
  ausente (R3). A ordem SSR (R1) já passa hoje — é teste de caracterização.
- Node: `node --test static/js/tests/mobile_select_order.test.js` — falha com
  `ENOENT` (script ainda não existe).

## GREEN

- `uv run pytest apps/doctor/tests/test_admission_flow_order.py` — exit 0.
- `node --test static/js/tests/mobile_select_order.test.js` — exit 0.
- `uv run pytest apps/doctor` — exit 0.

## Quality gate completo

```bash
node --test static/js/tests/
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest
git status --short
```

## Verificação manual (pós-deploy, aparelho real)

- iPhone 13 (Safari e Chrome), página rolada até o fim: menu abre acima do
  select com `Agendamento` na posição adjacente ao select.
- Desktop ≥ 768 px: dropdown na ordem atual.
- Aparelho de tela pequena (ex.: iPhone SE / Android compacto): confirmar que o
  menu ainda abre acima; se abrir abaixo, reverter é remover o atributo.

## Objetivo vertical

```text
Médico abre a decisão no celular
→ toca "Fluxo de Admissão"
→ picker lista: Selecione..., EM pediátrica, Enfermaria+UTI, Pré-UTI, Vinda Imediata, Agendamento
→ "Agendamento" (mais comum) fica junto do select/dedo
→ valor submetido, validação, FSM e auditoria inalterados
→ desktop e sem-JS: ordem atual
```

## Requisitos funcionais

### R1. SSR intocado

Os `<option>` do select `admission_flow` permanecem na ordem de
`ADMISSION_FLOW_CHOICES` nos dois ramos do template.

### R2. Marcador declarativo

Os dois selects levam `data-mobile-reverse-options`. Nenhum outro atributo,
id, name ou classe muda.

### R3. Script nos dois ramos

`<script src="{% static 'js/mobile_select_order.js' %}"></script>` carregado no
`extra_js` tanto no ramo `per_procedure` quanto no legado.

### R4. Inversão progressiva e reversível

Conforme "Correção esperada" item 2. Sem `matchMedia` ou sem JS: ordem do SSR.

### R5. Sem expansão

Diff limitado a `templates/doctor/decision.html`,
`static/js/mobile_select_order.js`, `static/js/tests/mobile_select_order.test.js`,
`apps/doctor/tests/test_admission_flow_order.py` (mais este arquivo e o
relatório). Sem CSS novo, sem service worker, sem view/form.

## Out of scope

- Cartões de rádio ou chips de atalho no mobile; gatilho `(pointer: coarse)`;
  extrair o select duplicado para um include; bump de `CACHE_NAME` no
  `sw.js` (desnecessário: network-first para `/static/`); pré-selecionar um fluxo
  padrão (risco clínico de viés de default).
