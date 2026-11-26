# Slice: ordem inversa das opções de fluxo de admissão no mobile — Relatório de implementação

Task: `tasks/quick-ui-admission-flow-mobile-order.md` · Branch
`carlosapgomes/fix-admission-flow-order` · `BASE_REF=61918827f9dcbb7ca29ec0bceebd766afce66efb`

## Summary

No formulário de decisão médica, o `<select>` "Fluxo de Admissão" passa a listar
as opções reais em ordem inversa **somente em tela mobile** (< 768 px, mesmo
corte de `md`/`d-md-none`), mantendo o placeholder "Selecione..." em primeiro e
o valor submetido inalterado. O SSR continua renderizando a ordem desktop (mais
comum primeiro); a inversão é progressive enhancement em JS vanilla sobre o
marcador declarativo `data-mobile-reverse-options`. Sem JS (ou sem
`matchMedia`): ordem atual.

Contexto de campo (aparelho real, iPhone 13 Safari/Chrome + Android): o picker
nativo é lista vertical em ordem do DOM; com a página rolada até o fim, o menu
do iOS abre **acima** do select — logo a primeira opção fica no ponto mais
distante do dedo. Invertendo, `Agendamento` (mais comum) fica adjacente ao
select/dedo e as opções raras vão para o topo, longe do polegar.

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `templates/doctor/decision.html` | Modified | `data-mobile-reverse-options` nos 2 selects `#admission-flow` (linhas 456 e 519); `<script>` novo carregado nos 2 ramos do `extra_js` |
| `static/js/mobile_select_order.js` | **New** | IIFE vanilla: `window.MobileSelectOrder = { MOBILE_QUERY, MARKER_SELECTOR, enhance, enhanceAll }` + auto-init por `DOMContentLoaded` |
| `static/js/tests/mobile_select_order.test.js` | **New** | 7 testes Node (`node --test`, mini-DOM sem jsdom, padrão de `procedure_combobox.test.js`) |
| `apps/doctor/tests/test_admission_flow_order.py` | **New** | Guarda do contrato HTML: ordem SSR == `ADMISSION_FLOW_CHOICES` + placeholder em 1º + atributo + script, nos ramos legado 1.1 e por procedimento (2 testes parametrizados) |
| `tasks/quick-ui-admission-flow-mobile-order.md` | **New** | Slice QUICK (handoff, matriz, RED/GREEN, gates) |
| `.reports/slice-admission-flow-mobile-order.md` | **New** | Este relatório |

`git diff --stat` (código): 1 template modificado (+3/−2), 3 arquivos novos.

## Matriz requisito → arquivo → teste

| Requisito | Arquivo | Teste/check | Resultado |
| --- | --- | --- | --- |
| R1 ordem SSR inalterada (placeholder + `ADMISSION_FLOW_CHOICES`) nos 2 ramos | `decision.html` | `test_ssr_keeps_desktop_order_and_marks_select_for_mobile[legacy|per_procedure]` | ✅ 2 passed |
| R2 select marcado `data-mobile-reverse-options` (2 ramos) | `decision.html` | idem | ✅ |
| R3 script carregado nos 2 ramos | `decision.html` | idem (`js/mobile_select_order.js` no HTML) | ✅ |
| R4 inversão/restauração idempotente, placeholder em 1º, seleção preservada, seletor restrito, corte 767.98px, auto-init, no-op sem `matchMedia` | `mobile_select_order.js` | `mobile_select_order.test.js` (7 testes) | ✅ 23/23 no diretório (7 novos + 16 existentes) |
| R5 sem expansão | — | `git status --short` → só os arquivos previstos | ✅ |

## Before/After

### `templates/doctor/decision.html` — select (2 ocorrências idênticas)

**Before:**
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

**After** (opções intocadas — só a tag de abertura muda):
```django
<select class="form-select{% if form.admission_flow.errors %} is-invalid{% endif %}" id="admission-flow" name="admission_flow" data-mobile-reverse-options>
  ... mesmos 6 <option> ...
```

### `templates/doctor/decision.html` — `{% block extra_js %}`

**Before:**
```django
{% if per_procedure %}
<script src="{% static 'js/procedure_combobox.js' %}"></script>
{% else %}
<script src="{% static 'js/decision.js' %}"></script>
{% endif %}
<script src="{% static 'js/work_lock.js' %}"></script>
```

**After:**
```django
{% if per_procedure %}
<script src="{% static 'js/procedure_combobox.js' %}"></script>
{% else %}
<script src="{% static 'js/decision.js' %}"></script>
{% endif %}
<script src="{% static 'js/mobile_select_order.js' %}"></script>
<script src="{% static 'js/work_lock.js' %}"></script>
```

### `static/js/mobile_select_order.js` — núcleo (novo)

```js
function enhance(select, mediaQueryList) {
  var original = snapshotOptions(select); // original[0] = placeholder, fica em primeiro
  var rest = original.slice(1);

  function apply() {
    var ordered = mediaQueryList.matches ? rest.slice().reverse() : rest;
    for (var i = 0; i < ordered.length; i++) {
      select.appendChild(ordered[i]);   // move o nó → preserva `selected`
    }
  }

  apply();
  if (typeof mediaQueryList.addEventListener === 'function') {
    mediaQueryList.addEventListener('change', apply);
  } else if (typeof mediaQueryList.addListener === 'function') {
    mediaQueryList.addListener(apply); // Safari < 14
  }
  return apply;
}
```

Ordem derivada sempre da original capturada uma vez → idempotente e reversível
(rotação/redimensionamento). `enhanceAll` é no-op sem `document.querySelectorAll`
ou sem `window.matchMedia`.

### Comportamento resultante

| Contexto | Ordem exibida |
| --- | --- |
| Desktop ≥ 768 px | `Selecione...`, Agendamento, Vinda Imediata, Vinda prévia para UTI, Enfermaria (retaguarda UTI), EM pediátrica — com agendamento |
| Mobile < 768 px com JS | `Selecione...`, EM pediátrica — com agendamento, Enfermaria (retaguarda UTI), Vinda prévia para UTI, Vinda Imediata, **Agendamento** |
| Sem JS / sem `matchMedia` | ordem do SSR (desktop) |

## TDD — evidências

**RED**
- `uv run pytest apps/doctor/tests/test_admission_flow_order.py -q` → `2 failed, 1
  passed`: asserção `data-mobile-reverse-options` ausente na tag do select
  (falha por comportamento, não por import/fixture). A ordem SSR (R1) já
  passava — teste de caracterização.
- `node --test static/js/tests/mobile_select_order.test.js` → `fail 1`, `ENOENT`
  (script inexistente).

**GREEN**
- `uv run pytest apps/doctor/tests/test_admission_flow_order.py -q` → `3 passed`
  (antes do REFACTOR; 2 parametrizados após consolidar a pré-condição do
  placeholder no teste parametrizado).
- `node --test static/js/tests/*.test.js` → `tests 23, pass 23, fail 0`.
- `uv run pytest apps/doctor -q` → `565 passed`.

**REFACTOR**
- Teste Django: pré-condição "placeholder em primeiro" movida para o teste
  parametrizado (removeu teste duplicado com login próprio); `html: str` para
  satisfazer mypy strict (`no-any-return`).
- Teste Node: `assert.equal(length, 0)` no lugar de `deepEqual([], [])` — array
  retornado vem de outro realm (`vm`) e `deepStrictEqual` compara protótipos.
- Script: sem código morto; 2 espaços/estilo do `procedure_combobox.js`.

## Quality gate (AGENTS.md §2)

| Gate | Resultado |
| --- | --- |
| `node --test static/js/tests/*.test.js` | 23 passed, 0 failed |
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 312 files already formatted |
| `uv run mypy .` | Success: no issues found in 344 source files |
| `uv run pytest` (baseline) | **4804 passed**, exit 0 |
| `uv run pytest` (final) | **4806 passed**, exit 0 (zero failures/errors; +2 = testes novos) |
| `git status --short` | somente os arquivos previstos |

## Decisões e desvios justificados

- **Sem alteração em `static/js/sw.js`** (o plano inicial previa bump de
  `CACHE_NAME`): o fetch handler é **network-first para `/static/`** (linhas
  46–70), então o JS novo/alterado chega no próximo load online; o precache
  (`STATIC_ASSETS`) é só semente para offline, e a decisão médica é HTML SSR que
  nunca abre offline. Reduz o blast radius e evita invalidar o cache de todos.
- **Sem `pointer: coarse`** e sem cartões/chips: fora de escopo (ver task).
- `decision.js` (ramo legado) continua lendo `admissionFlow.value` e
  `options[selectedIndex].text` corretamente — os nós são movidos, não recriados.

## Verificação manual pendente (pós-deploy)

- iPhone 13 (Safari/Chrome), página rolada até o fim: menu abre acima com
  `Agendamento` adjacente ao select.
- Desktop ≥ 768 px: ordem atual.
- Aparelho de tela pequena: confirmar que o menu ainda abre acima; se abrir
  abaixo, reverter = remover o atributo `data-mobile-reverse-options`.

## Próximo passo

Aguardando confirmação explícita do usuário (Stop Rule). Nenhum outro slice
iniciado.
